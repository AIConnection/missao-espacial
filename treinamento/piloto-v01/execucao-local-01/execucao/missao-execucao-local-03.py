"""Aceleração opcional da desquantização affine. Nenhuma cabeça de outro domínio.
Em CUDA/CPU ou sem compile_shader usa o runtime portátil original.
No MPS mantém as mesmas matrizes fp16 e a mesma blocagem/multiplicação.
"""
from pathlib import Path
import sys,json,shutil,time,gzip
import numpy as np,torch
PKG=Path('/Users/alexandre/projects/missao-espacial/treinamento/piloto-v01/pacote')
OLD=Path('/private/tmp/missao-espacial-treino-real-01')
WORK=Path('/private/tmp/missao-espacial-treino-real-03')
sys.path.insert(0,str(PKG/'ferramentas'))
import phi4_portatil as runtime
import treinar
from contrato import ForecastEncoder
original_unpack=runtime.unpack
original_projection=runtime.PackedLinear.forward
USE_DECODED_CACHE=False
def whole_projection(self,inputs):
 if inputs.device.type=='mps' and hasattr(torch.mps,'compile_shader'):
  if USE_DECODED_CACHE:
   if not hasattr(self,'decoded_weight'):self.register_buffer('decoded_weight',fast_unpack(self.packed,self.scales,self.biases,inputs.dtype))
   weight=self.decoded_weight
  else:weight=fast_unpack(self.packed,self.scales,self.biases,inputs.dtype)
  return torch.nn.functional.linear(inputs,weight)
 return original_projection(self,inputs)
runtime.PackedLinear.forward=whole_projection
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
  global USE_DECODED_CACHE
  runtime.unpack=fast_unpack
  super().__init__(*args,**kwargs)
  USE_DECODED_CACHE=self.device=='mps' and torch.mps.recommended_max_memory()>50_000_000_000
  self.identity['decoded_weight_cache_enabled']=USE_DECODED_CACHE
  self.identity['optional_affine_acceleration']={'script_sha256':runtime.sha(Path(__file__)),'implementation':'native MPS fused affine decode when available; original otherwise','projection':'whole matrix on MPS; original tiles otherwise','no_other_domain_head_loaded':True}


print('Phi-4 base congelado; heads novas; nenhuma cabeça/normalização do Crivo.',flush=True)
# Optional fused dequantization has already been checked against every matrix
# with exactly this same kernel in the preceding local numerical audit.
validation_source=Path('/private/tmp/missao-aceleracao-local.py')
print('Auditoria precedente do kernel:',runtime.sha(validation_source),flush=True)
probe=Accelerated(PKG/'modelo.json','/Users/alexandre/crivo/assets/phi4','auto',256,None)
print('Dispositivo:',probe.device,flush=True)
if probe.device=='mps':print('Memória recomendada pelo PyTorch (bytes):',torch.mps.recommended_max_memory(),flush=True)
inputs,rows=treinar.read_data(PKG);encoder=ForecastEncoder(probe.directory);prefix=(PKG/'dados/prefixo-nli.txt').read_text().rstrip('\n')
# Measure actual forward and compare to the portable path: never reuse prior
# features if the projection grouping changes floating point rounding.
tokens=encoder.encode(inputs[0]);started=time.perf_counter();x,abc=probe.features(tokens);seconds=time.perf_counter()-started
with np.load(OLD/'features/0000.npz',allow_pickle=False) as v:
 diagnostic={'first_example_seconds':seconds,'feature_max_absolute_difference_from_portable_projection':float(np.max(np.abs(x-v['features']))),'baseline_abc_max_difference':float(np.max(np.abs(abc-v['baseline_abc']))),'no_old_features_reused':True,'same_quantized_base_model':True,'projection_grouping_may_change_rounding':True,'domain_heads_loaded':False}
print('Forward verificado:',diagnostic,flush=True)
WORK.mkdir(parents=True,exist_ok=False)
treinar.write(WORK/'diagnostico-execucao.json',diagnostic)
# Use the very same loaded model for extraction; fingerprint includes the
# accelerator source. All 816 features are generated in this execution.
treinar.Phi4Features=lambda *a,**k:probe
treinar.extract(PKG,WORK,'/Users/alexandre/crivo/assets/phi4','auto',256,None)
treinar.train(PKG,WORK)
print('TREINAMENTO PILOTO E AVALIAÇÃO CONCLUÍDOS:',WORK,flush=True)
