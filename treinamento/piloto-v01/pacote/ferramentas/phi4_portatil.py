"""Mesmo Phi-4 quantizado, executado por PyTorch em CUDA, MPS ou CPU.
Não usa geração, bitsandbytes, FlashAttention obrigatório, MLX ou kernel Metal próprio.
"""
from pathlib import Path
import hashlib,json,platform
import numpy as np
import transformers
import torch
from torch import nn
from torch.nn import functional as F
from safetensors import safe_open
from transformers import AutoTokenizer,Phi3Config
from transformers.models.phi3.modeling_phi3 import Phi3Model,Phi3RotaryEmbedding

NLI_SYSTEM=('Classify the relation of a hypothesis to a premise using only the premise. '
 'A = entailment: the hypothesis follows from the premise. '
 'B = neutral: the hypothesis neither follows from nor contradicts the premise. '
 'C = contradiction: the hypothesis contradicts the premise. '
 'Answer with exactly one letter: A, B, or C.')

def sha(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def automatic_device():
 if torch.cuda.is_available():return 'cuda'
 if hasattr(torch.backends,'mps') and torch.backends.mps.is_available():return 'mps'
 return 'cpu'
def choose_device(requested='auto'):
 value=automatic_device() if requested=='auto' else requested
 if value not in ('cpu','cuda','mps'):raise ValueError('Dispositivo desconhecido')
 if value=='cuda' and not torch.cuda.is_available():raise ValueError('CUDA indisponível; use auto ou cpu')
 if value=='mps' and not torch.backends.mps.is_available():raise ValueError('MPS indisponível; use auto ou cpu')
 return value

def prepare_assets(manifest_path,model_directory=None):
 manifest=json.loads(Path(manifest_path).read_text())
 if model_directory is None:
  from huggingface_hub import snapshot_download
  model_directory=snapshot_download(repo_id=manifest['repo'],revision=manifest['revision'],allow_patterns=[r['path'] for r in manifest['model_files']])
 directory=Path(model_directory)
 for r in manifest['model_files']:
  p=directory/r['path']
  if not p.is_file() or p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:raise ValueError(f'Peso/tokenizer ausente ou incompatível: {p}')
 return directory,manifest

def unpack(weight,scales,biases,dtype):
 """Grupos de 64; 8 nibbles por inteiro; arredondamento original fp16."""
 weight=weight.to(torch.int32)
 shifts=torch.arange(0,32,4,dtype=torch.int32,device=weight.device)
 values=((weight.unsqueeze(-1)>>shifts)&15).reshape(weight.shape[0],-1,64)
 decoded=values.float()*scales.float().unsqueeze(-1)+biases.float().unsqueeze(-1)
 return decoded.reshape(weight.shape[0],-1).to(torch.float16).to(dtype)

class PackedLinear(nn.Module):
 def __init__(self,weight,scales,biases,tile_rows=256):
  super().__init__()
  if type(tile_rows) is not int or tile_rows<1:raise ValueError('tile_rows deve ser positivo')
  self.tile_rows=tile_rows
  self.register_buffer('packed',weight.to(torch.int32));self.register_buffer('scales',scales);self.register_buffer('biases',biases)
 def forward(self,inputs):
  blocks=[]
  for start in range(0,self.packed.shape[0],self.tile_rows):
   sl=slice(start,start+self.tile_rows)
   w=unpack(self.packed[sl],self.scales[sl],self.biases[sl],inputs.dtype)
   blocks.append(F.linear(inputs,w))
  return torch.cat(blocks,dim=-1)

class PackedEmbedding(PackedLinear):
 def forward(self,ids):
  dtype=torch.float32 if ids.device.type=='cpu' else torch.float16
  shape=ids.shape;flat=ids.reshape(-1)
  # Blocagem também limita buffers de desquantização de embeddings longos.
  result=[unpack(self.packed[flat[s:s+self.tile_rows]],self.scales[flat[s:s+self.tile_rows]],self.biases[flat[s:s+self.tile_rows]],dtype) for s in range(0,len(flat),self.tile_rows)]
  return torch.cat(result,dim=0).reshape(*shape,-1)

def last_token(hidden,mask):
 lengths=mask.sum(-1)
 if bool((lengths<=0).any()):raise ValueError('Entrada vazia')
 return hidden[torch.arange(len(lengths),device=hidden.device),lengths-1]

def final_hidden(model,inputs,prefill_chunk=0):
 if not prefill_chunk:
  mask=torch.ones_like(inputs)
  return model(input_ids=inputs,attention_mask=mask,use_cache=False).last_hidden_state[:,-1]
 cache=None
 for start in range(0,inputs.shape[1],prefill_chunk):
  end=min(start+prefill_chunk,inputs.shape[1])
  mask=torch.ones((inputs.shape[0],end),dtype=inputs.dtype,device=inputs.device)
  output=model(input_ids=inputs[:,start:end],attention_mask=mask,past_key_values=cache,use_cache=True)
  cache=output.past_key_values
 return output.last_hidden_state[:,-1]

class Phi4Features:
 def __init__(self,manifest_path,model_directory=None,device='auto',tile_rows=256,prefill_chunk=None):
  self.directory,self.manifest=prepare_assets(manifest_path,model_directory)
  self.device=choose_device(device)
  self.prefill_chunk=(256 if self.device=='cpu' else 0) if prefill_chunk is None else prefill_chunk
  if type(self.prefill_chunk) is not int or self.prefill_chunk<0:raise ValueError('prefill_chunk deve ser inteiro não negativo')
  dtype=torch.float32 if self.device=='cpu' else torch.float16
  self.tokenizer=AutoTokenizer.from_pretrained(self.directory,local_files_only=True,trust_remote_code=False)
  cfg=json.loads((self.directory/'config.json').read_text())
  if cfg.get('quantization')!={'group_size':64,'bits':4}:raise ValueError('Quantização incompatível')
  cfg.pop('quantization_config',None);cfg.pop('quantization',None)
  config=Phi3Config.from_dict(cfg)
  if config.hidden_size!=5120 or config.max_position_embeddings!=16384:raise ValueError('Arquitetura incompatível')
  config._attn_implementation='sdpa';config.use_cache=False
  self.window=min(config.max_position_embeddings,self.tokenizer.model_max_length)
  with torch.device('meta'):self.model=Phi3Model(config)
  index=json.loads((self.directory/'model.safetensors.index.json').read_text())['weight_map']
  def read(name,selected=None):
   with safe_open(self.directory/index[name],framework='pt',device='cpu') as shard:
    t=shard.get_tensor(name);return t.clone() if selected is None else t[selected].clone()
  for name,module in list(self.model.named_modules()):
   if isinstance(module,(nn.Linear,nn.Embedding)):
    parent,_,child=name.rpartition('.');owner=self.model.get_submodule(parent) if parent else self.model
    values=[read(f'model.{name}.{suffix}') for suffix in ('weight','scales','biases')]
    cls=PackedEmbedding if isinstance(module,nn.Embedding) else PackedLinear
    setattr(owner,child,cls(*values,tile_rows=tile_rows).to(self.device))
  for name,_ in list(self.model.named_parameters()):
   parent,_,child=name.rpartition('.')
   setattr(self.model.get_submodule(parent),child,nn.Parameter(read('model.'+name).to(device=self.device,dtype=dtype),requires_grad=False))
  self.model.rotary_emb=Phi3RotaryEmbedding(config,device=self.device);self.model.eval();self.model.requires_grad_(False)
  letters=[self.tokenizer.encode(x,add_special_tokens=False) for x in 'ABC']
  if any(len(x)!=1 for x in letters):raise ValueError('Classes A/B/C precisam ser tokens únicos')
  ids=[x[0] for x in letters]
  self.abc_weight=unpack(*[read('lm_head.'+s,ids).to(self.device) for s in ('weight','scales','biases')],dtype)
  if any(p.device.type=='meta' for p in self.model.parameters()):raise ValueError('Peso não carregado')
  self.identity={'repo':self.manifest['repo'],'revision':self.manifest['revision'],'device':self.device,'dtype':str(dtype),'torch':torch.__version__,'transformers':transformers.__version__,'numpy':np.__version__,'platform':platform.platform(),'tile_rows':tile_rows,'prefill_chunk':self.prefill_chunk,'feature':'last nonpadding token, final hidden state','dimension':5120,'model_files':self.manifest['model_files']}
 def encode_nli(self,pair,prefix):
  if set(pair)!={'premise','hypothesis'} or any(not isinstance(v,str) for v in pair.values()):raise ValueError('Schema NLI inválido')
  value={'premise':prefix+'\n\n'+pair['premise'],'hypothesis':pair['hypothesis']}
  prompt=self.tokenizer.apply_chat_template([{'role':'system','content':NLI_SYSTEM},{'role':'user','content':json.dumps(value,ensure_ascii=False)}],tokenize=False,add_generation_prompt=True)
  return self.tokenizer.encode(prompt,add_special_tokens=False)
 @torch.inference_mode()
 def features(self,tokens):
  if not tokens or len(tokens)>self.window:raise ValueError('Contexto vazio ou acima da janela; truncamento proibido')
  inputs=torch.tensor([tokens],dtype=torch.long,device=self.device);mask=torch.ones_like(inputs)
  final=final_hidden(self.model,inputs,self.prefill_chunk)
  x=final.float().cpu().numpy()[0];abc=F.linear(final,self.abc_weight).float().cpu().numpy()[0]
  if not np.isfinite(x).all() or not np.isfinite(abc).all():raise ValueError('Features não finitas')
  return x,abc
