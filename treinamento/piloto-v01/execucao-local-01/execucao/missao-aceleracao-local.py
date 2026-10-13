"""Aceleração opcional da desquantização affine. Nenhuma cabeça de outro domínio.
Em CUDA/CPU ou sem compile_shader usa o runtime portátil original.
No MPS mantém as mesmas matrizes fp16 e a mesma blocagem/multiplicação.
"""
from pathlib import Path
import sys,json,shutil,time,gzip
import numpy as np,torch
PKG=Path('/Users/alexandre/projects/missao-espacial/treinamento/piloto-v01/pacote')
OLD=Path('/private/tmp/missao-espacial-treino-real-01')
WORK=Path('/private/tmp/missao-espacial-treino-real-02')
sys.path.insert(0,str(PKG/'ferramentas'))
import phi4_portatil as runtime
import treinar
from contrato import ForecastEncoder
original_unpack=runtime.unpack
verified=set();statistics={'verified_weight_values':0,'verified_chunks':0,'all_comparisons_exact':True}
shader=None

def fast_unpack(weight,scales,biases,dtype):
 global shader
 if weight.device.type!='mps' or not hasattr(torch.mps,'compile_shader'):return original_unpack(weight,scales,biases,dtype)
 if shader is None:
  shader=torch.mps.compile_shader('''
  #include <metal_stdlib>
  using namespace metal;
  kernel void affine_decode(device const uint* packed,
                            device const half* scales,
                            device const half* biases,
                            device half* output,
                            uint i [[thread_position_in_grid]]) {
     uint q=(packed[i/8]>>((i%8)*4))&15;
     output[i]=half(float(q)*float(scales[i/64])+float(biases[i/64]));
  }
  ''')
 weight=weight.to(torch.int32)
 output=torch.empty((weight.shape[0],weight.shape[1]*8),device=weight.device,dtype=torch.float16)
 shader.affine_decode(weight,scales,biases,output,threads=output.numel())
 return output.to(dtype)

class Accelerated(runtime.Phi4Features):
 def __init__(self,*args,**kwargs):
  runtime.unpack=fast_unpack
  super().__init__(*args,**kwargs)
  self.identity['optional_affine_acceleration']={'script_sha256':runtime.sha(Path(__file__)),'implementation':'native MPS fused affine decode when available; original otherwise','same_projection_tile_rows':True,'no_other_domain_head_loaded':True}

# First compare every quantized matrix in the actual model before extraction.
print('Carregando o corpo Phi-4; sem cabeça/normalização do Crivo.',flush=True)
probe=Accelerated(PKG/'modelo.json','/Users/alexandre/crivo/assets/phi4','auto',256,None)
for name,module in probe.model.named_modules():
 if isinstance(module,runtime.PackedLinear):
  for start in range(0,module.packed.shape[0],1024):
   sl=slice(start,start+1024);args=(module.packed[sl],module.scales[sl],module.biases[sl],torch.float16)
   actual=fast_unpack(*args);expected=original_unpack(*args)
   if not torch.equal(actual,expected):raise RuntimeError('Desquantização divergente: '+name)
   statistics['verified_chunks']+=1;statistics['verified_weight_values']+=actual.numel()
  print('Matriz conferida:',name,flush=True)
print('Todas as matrizes reconstruídas são exatamente iguais.',statistics,flush=True)
# Cached rows only move to new work after re-extraction is bit-identical.
inputs,rows=treinar.read_data(PKG);encoder=ForecastEncoder(probe.directory);prefix=(PKG/'dados/prefixo-nli.txt').read_text().rstrip('\n')
old=json.loads((OLD/'features/manifesto.json').read_text())
if WORK.exists():raise RuntimeError('Não sobrescrever execução anterior')
(WORK/'features').mkdir(parents=True)
identity={'package_sha256':runtime.sha(PKG/'integridade.json'),'backend':probe.identity,'extractor_sha256':runtime.sha(PKG/'ferramentas/treinar.py'),'portable_runtime_sha256':runtime.sha(PKG/'ferramentas/phi4_portatil.py')}
new={'identity':identity,'rows':[],'completed':False,'truncation':False,'tokens_max':old['tokens_max']}
for record in old['rows']:
 i=record['index'];p=OLD/'features'/record['file']
 if runtime.sha(p)!=record['sha256']:raise RuntimeError('Cache original corrompido')
 tokens=encoder.encode(inputs[i]) if rows[i]['task']=='forecast' else probe.encode_nli(inputs[i],prefix)
 started=time.perf_counter();x,abc=probe.features(tokens)
 with np.load(p,allow_pickle=False) as v:
  if not np.array_equal(x,v['features']) or not np.array_equal(abc,v['baseline_abc']):raise RuntimeError('Feature alterada pela aceleração')
 shutil.copy2(p,WORK/'features'/record['file']);new['rows'].append(record)
 print('Feature preservada bit a bit:',i,'seconds',round(time.perf_counter()-started,2),flush=True)
treinar.write(WORK/'features/manifesto.json',new)
treinar.write(WORK/'equivalencia-aceleracao.json',{**statistics,'cached_rows_features_bit_identical':len(new['rows']),'runtime_uses_same_weight_revision':True,'domain_head_loaded':False,'acceleration_source_sha256':runtime.sha(Path(__file__))})
del probe
import gc;gc.collect()
if torch.backends.mps.is_available():torch.mps.empty_cache()
treinar.Phi4Features=Accelerated
# Exact same portable extraction/training; optional kernel added to provenance.
treinar.extract(PKG,WORK,'/Users/alexandre/crivo/assets/phi4','auto',256,None)
treinar.train(PKG,WORK)
print('Treinamento piloto e avaliação concluídos:',WORK,flush=True)
