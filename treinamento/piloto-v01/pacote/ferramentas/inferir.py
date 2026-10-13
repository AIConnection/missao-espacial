"""Inferência com as cabeças exportadas; a implementação externa escolhe a ação."""
from pathlib import Path
import json,numpy as np
from phi4_portatil import Phi4Features,sha
from contrato import ForecastEncoder,validate_output
from treinar import probabilities,LABELS

def head_probabilities(path,x,task):
 if task not in ('nli','forecast'):raise ValueError('Tarefa desconhecida')
 if np.asarray(x).shape!=(5120,) or not np.isfinite(x).all():raise ValueError('Feature inválida')
 with np.load(path,allow_pickle=False) as h:
  shape=(3 if task=='nli' else 1,5120)
  if h['weight'].shape!=shape or h['mean'].shape!=(5120,) or h['scale'].shape!=(5120,) or h['bias'].shape!=(shape[0],) or not all(np.isfinite(h[k]).all() for k in h.files) or not (h['scale']>0).all() or float(h['temperature'])<=0:raise ValueError('Cabeça inválida')
  logits=((x-h['mean'])/h['scale'])@h['weight'].T+h['bias']
  return probabilities(logits.reshape(1,-1),task,float(h['temperature']))[0]

class PilotPredictor:
 def __init__(self,package,heads,model_directory=None,device='auto',tile_rows=256,prefill_chunk=None):
  self.package=Path(package);self.heads=Path(heads)
  self.artifact=json.loads((self.heads/'artefato.json').read_text())
  if self.artifact['version']!='mission-pilot-heads-v1' or self.artifact['package_sha256']!=sha(self.package/'integridade.json'):raise ValueError('Artefato pertence a outro pacote')
  for name,h in json.loads((self.package/'integridade.json').read_text()).items():
   if sha(self.package/name)!=h:raise ValueError('Pacote alterado: '+name)
  for name,h in self.artifact['code_sha256'].items():
   if sha(self.package/'ferramentas'/name)!=h:raise ValueError('Código da inferência mudou')
  for task,h in self.artifact['heads'].items():
   if sha(self.heads/f'{task}.npz')!=h:raise ValueError('Cabeça corrompida')
  self.backend=Phi4Features(self.package/'modelo.json',model_directory,device,tile_rows,prefill_chunk)
  for key in ('repo','revision','model_files','dimension','feature'):
   if self.artifact['body_identity'][key]!=self.backend.identity[key]:raise ValueError('Modelo/feature incompatível')
  self.encoder=ForecastEncoder(self.backend.directory)
  self.prefix=(self.package/'dados/prefixo-nli.txt').read_text().rstrip('\n')
 def predict(self,task,value):
  if task not in ('nli','forecast'):raise ValueError('Tarefa desconhecida')
  tokens=self.encoder.encode(value) if task=='forecast' else self.backend.encode_nli(value,self.prefix)
  x,_=self.backend.features(tokens)
  p=head_probabilities(self.heads/f'{task}.npz',x,task)
  if task=='nli':return {'classification':LABELS[int(p.argmax())]}
  return validate_output({'entrega_no_planeta':float(p[0]),'retorno_com_sobrevivencia':float(p[1])})

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--package',type=Path,default=Path(__file__).parents[1]);p.add_argument('--heads',type=Path,required=True);p.add_argument('--task',choices=('nli','forecast'),required=True);p.add_argument('--input',type=Path,required=True);p.add_argument('--model-directory',type=Path);p.add_argument('--device',default='auto');a=p.parse_args()
 model=PilotPredictor(a.package,a.heads,a.model_directory,a.device)
 print(json.dumps(model.predict(a.task,json.loads(a.input.read_text())),ensure_ascii=False,allow_nan=False))
