"""Extração retomável, treino de heads, calibração e avaliação com cortes separados."""
from pathlib import Path
import json,gzip,hashlib,time,sys,platform
import numpy as np,torch
from torch import nn
from torch.nn import functional as F
from phi4_portatil import Phi4Features,sha
from contrato import ForecastEncoder,validate_output
from avaliar_probabilidades import evaluate

TEMPERATURES=(.5,.75,1.,1.5,2.,3.,5.,10.)
LABELS=('suporte','insuficiente','contradição')
def write(path,value):
 tmp=path.with_name(path.name+'.tmp');tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n');tmp.replace(path)
def read_data(package):
 package=Path(package);lock=json.loads((package/'integridade.json').read_text())
 for name,h in lock.items():
  if sha(package/name)!=h:raise ValueError('Pacote alterado: '+name)
 with gzip.open(package/'dados/inputs.jsonl.gz','rt',encoding='utf-8') as f:inputs=[json.loads(l) for l in f]
 rows=[json.loads(l) for l in (package/'dados/supervisao.jsonl').read_text().splitlines()]
 if len(inputs)!=816 or len(rows)!=len(inputs):raise ValueError('Massa incompleta')
 if [r['index'] for r in rows]!=list(range(len(rows))):raise ValueError('Índices fora de ordem')
 for task,expected in [('nli',{'train':420,'calibration':90,'test':90}),('forecast',{'train':144,'calibration':36,'test':36})]:
  members=[r for r in rows if r['task']==task]
  for split,n in expected.items():
   part=[r for r in members if r['split']==split]
   if len(part)!=n:raise ValueError('Partição incompleta')
   if {r['group'] for r in part}&{r['group'] for r in members if r['split']!=split}:raise ValueError('Grupo vazou entre partições')
 for r,x in zip(rows,inputs):
  if r['task']=='nli' and set(x)!={'premise','hypothesis'}:raise ValueError('Metadado na entrada NLI')
  if r['task']=='forecast' and set(x)!={'context','objective','candidate_plan','forecast_target','sampling_assumptions'}:raise ValueError('Metadado na entrada probabilística')
 return inputs,rows

def extract(package,work,model_directory=None,device='auto',tile_rows=256,prefill_chunk=None):
 package,work=Path(package),Path(work);inputs,rows=read_data(package)
 work.mkdir(parents=True,exist_ok=True);cache=work/'features';cache.mkdir(exist_ok=True)
 print('Carregando e verificando os pesos Phi-4...',flush=True)
 backend=Phi4Features(package/'modelo.json',model_directory,device,tile_rows,prefill_chunk)
 print('Dispositivo:',backend.device,flush=True)
 encoder=ForecastEncoder(backend.directory)
 prefix=(package/'dados/prefixo-nli.txt').read_text().rstrip('\n')
 tokens=[encoder.encode(x) if r['task']=='forecast' else backend.encode_nli(x,prefix) for x,r in zip(inputs,rows)]
 if any(not t or len(t)>backend.window for t in tokens):raise ValueError('Janela excedida; nenhum contexto será truncado')
 identity={'package_sha256':sha(package/'integridade.json'),'backend':backend.identity,'extractor_sha256':sha(Path(__file__)),'portable_runtime_sha256':sha(Path(__file__).with_name('phi4_portatil.py'))}
 path=cache/'manifesto.json'
 report=json.loads(path.read_text()) if path.exists() else {'identity':identity,'rows':[],'completed':False,'truncation':False,'tokens_max':max(map(len,tokens))}
 if report['identity']!=identity:raise ValueError('Cache de outro pacote/hardware/runtime; escolha outro WORK_DIR')
 for i,record in enumerate(report['rows']):
  if record['index']!=i or record['sha256']!=sha(cache/record['file']):raise ValueError('Cache corrompido')
 for i in range(len(report['rows']),len(rows)):
  started=time.perf_counter();x,abc=backend.features(tokens[i]);name=f'{i:04d}.npz';tmp=cache/(name+'.tmp')
  with tmp.open('wb') as f:np.savez_compressed(f,features=x,baseline_abc=abc)
  tmp.replace(cache/name)
  report['rows'].append({'index':i,'file':name,'sha256':sha(cache/name),'tokens':len(tokens[i]),'seconds':time.perf_counter()-started});write(path,report)
  print(f"{i+1}/{len(rows)} — {rows[i]['task']} — {len(tokens[i])} tokens — {report['rows'][-1]['seconds']:.1f}s",flush=True)
 report['completed']=True;write(path,report)
 return report

def load_features(work,expected_count=816):
 cache=Path(work)/'features';m=json.loads((cache/'manifesto.json').read_text())
 if not m['completed'] or len(m['rows'])!=expected_count:raise ValueError('Extração incompleta; não treinar uma massa parcial')
 x=[];abc=[]
 for i,r in enumerate(m['rows']):
  if r['index']!=i or sha(cache/r['file'])!=r['sha256']:raise ValueError('Features corrompidas ou fora de ordem')
  with np.load(cache/r['file'],allow_pickle=False) as a:x.append(a['features']);abc.append(a['baseline_abc'])
 x=np.asarray(x,dtype=np.float32);abc=np.asarray(abc,dtype=np.float32)
 if x.shape!=(expected_count,5120) or abc.shape!=(expected_count,3) or not np.isfinite(x).all() or not np.isfinite(abc).all():raise ValueError('Features inválidas')
 return x,abc,m

def normalize(train):
 mean=train.mean(0).astype(np.float32);scale=np.maximum(train.std(0),1e-3).astype(np.float32)
 return mean,scale

def fit(x,y,task,seed=171,epochs=400,lr=.01,l2=.1):
 torch.manual_seed(seed);torch.set_num_threads(min(4,torch.get_num_threads()));torch.use_deterministic_algorithms(True)
 model=nn.Linear(x.shape[1],3 if task=='nli' else 1);nn.init.zeros_(model.weight);nn.init.zeros_(model.bias)
 optimizer=torch.optim.Adam(model.parameters(),lr=lr)
 xt=torch.tensor(x,dtype=torch.float32);yt=torch.tensor(y,dtype=torch.long if task=='nli' else torch.float32)
 history=[]
 for epoch in range(epochs):
  optimizer.zero_grad(set_to_none=True);z=model(xt)
  loss=F.cross_entropy(z,yt) if task=='nli' else F.binary_cross_entropy_with_logits(z[:,0],yt)
  objective=loss+l2*model.weight.square().sum()/2
  if not torch.isfinite(objective):raise ValueError('Treinamento não finito')
  objective.backward();optimizer.step()
  if (epoch+1)%20==0 or epoch==0:history.append({'epoch':epoch+1,'train_loss':float(loss.detach()),'regularized_objective':float(objective.detach())})
 return model.weight.detach().numpy(),model.bias.detach().numpy(),history

def probabilities(logits,task,temperature=1):
 z=np.asarray(logits,dtype=np.float64)/temperature
 if task=='nli':
  e=np.exp(z-z.max(-1,keepdims=True));return e/e.sum(-1,keepdims=True)
 p=np.exp(-np.logaddexp(0,-z.reshape(-1)))
 return np.column_stack([p,1-p])

def nll(p,y,task):
 p=np.clip(p,1e-12,1-1e-12)
 if task=='nli':return float(-np.log(p[np.arange(len(y)),np.asarray(y,dtype=int)]).mean())
 y=np.asarray(y);return float(-(y*np.log(p[:,0])+(1-y)*np.log(p[:,1])).mean())

def calibrate(logits,y,task):
 scores=[(nll(probabilities(logits,task,t),y,task),t) for t in TEMPERATURES]
 loss,t=min(scores,key=lambda r:(r[0],abs(r[1]-1)))
 return t,{'criterion':'calibration NLL only','temperature':t,'calibration_nll':loss,'grid':[{'temperature':t,'nll':loss} for loss,t in scores]}

def nli_metrics(p,y):
 y=np.asarray(y,dtype=int);pred=p.argmax(-1);c=np.zeros((3,3),dtype=int)
 for a,b in zip(y,pred):c[a,b]+=1
 per=[]
 for i in range(3):
  tp=c[i,i];precision=float(tp/c[:,i].sum()) if c[:,i].sum() else 0.;recall=float(tp/c[i].sum()) if c[i].sum() else 0.
  per.append({'label':LABELS[i],'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0.})
 return {'rows':len(y),'accuracy':float((pred==y).mean()),'macro_f1':float(np.mean([r['f1'] for r in per])),'nll':nll(p,y,'nli'),'confusion_matrix_true_rows_predicted_columns':c.tolist(),'labels':list(LABELS),'per_class':per}

def forecast_metrics(p,metadata):
 # Convert predictions back to original v04 rows; train excluded by evaluator.
 predictions=[{'row_index':r['source_row'],'probabilities':validate_output({'entrega_no_planeta':float(v[0]),'retorno_com_sobrevivencia':float(v[1])})} for r,v in zip(metadata,p) if r['split']!='train']
 supervision=[r['supervision'] for r in metadata]
 parts=[{'row_index':r['source_row'],'split':r['split'],'group':r['group']} for r in metadata]
 return predictions,evaluate(predictions,supervision,parts,[r['objective'] for r in metadata],1,1)

def train(package,work):
 package,work=Path(package),Path(work);_,rows=read_data(package);x,abc,cache=load_features(work)
 if cache['identity']['package_sha256']!=sha(package/'integridade.json'):raise ValueError('Features pertencem a outro pacote')
 protocol=json.loads((package/'protocolo.json').read_text());heads=work/'heads';heads.mkdir(exist_ok=True)
 summary={'model_training_executed':True,'features_real_phi4':True,'production_modified':False,'body_frozen':True,'test_used_for_fitting':False,'calibration_used_for_weights':False,'cache_identity':cache['identity'],'protocol_sha256':sha(package/'protocolo.json'),'tasks':{}}
 for task in ('nli','forecast'):
  ids=[i for i,r in enumerate(rows) if r['task']==task];meta=[rows[i] for i in ids];features=x[ids]
  partitions={s:np.array([i for i,r in enumerate(meta) if r['split']==s]) for s in ('train','calibration','test')}
  target=np.array([r['target'] for r in meta]);tr=partitions['train'];ca=partitions['calibration'];te=partitions['test']
  mean,scale=normalize(features[tr]);z=(features-mean)/scale
  op=protocol['optimization'];w,b,history=fit(z[tr],target[tr],task,seed=protocol['seed'],epochs=op['epochs'],lr=op['learning_rate'],l2=op['l2'])
  logits=z@w.T+b;raw=probabilities(logits,task);temperature,calibration=calibrate(logits[ca],target[ca],task);cal=probabilities(logits,task,temperature)
  with (heads/f'{task}.npz').open('wb') as f:np.savez_compressed(f,weight=w,bias=b,mean=mean,scale=scale,temperature=np.array(temperature))
  result={'rows':{s:len(a) for s,a in partitions.items()},'training_history':history,'calibration':calibration,'head_sha256':sha(heads/f'{task}.npz')}
  if task=='nli':
   baseline=probabilities(abc[ids],'nli')
   result['evaluation']={s:{'raw_head':nli_metrics(raw[a],target[a]),'calibrated_head':nli_metrics(cal[a],target[a]),'zero_shot_phi4_abc':nli_metrics(baseline[a],target[a]),'uniform':nli_metrics(np.full((len(a),3),1/3),target[a])} for s,a in partitions.items()}
   write(heads/'nli-predictions.json',[{'source_row':r['source_row'],'split':r['split'],'classification':LABELS[int(v.argmax())],'probabilities':{label:float(p) for label,p in zip(LABELS,v)}} for r,v in zip(meta,cal) if r['split']!='train'])
  else:
   _,raw_eval=forecast_metrics(raw,meta);predictions,cal_eval=forecast_metrics(cal,meta)
   # Constant prior fitted on train only; counterchecks a trivial majority shortcut.
   prior=float(target[tr].mean());constant=np.tile([prior,1-prior],(len(meta),1));_,base_eval=forecast_metrics(constant,meta)
   result['evaluation']={'raw_head':raw_eval,'calibrated_head':cal_eval,'train_prior_baseline':base_eval,'train_prior_probability_delivery':prior}
   write(heads/'forecast-predictions.json',predictions)
  summary['tasks'][task]=result
 artifact={'version':'mission-pilot-heads-v1','window_tokens':16384,'body_identity':cache['identity']['backend'],'package_sha256':sha(package/'integridade.json'),'nli_labels':list(LABELS),'probability_output_keys':['entrega_no_planeta','retorno_com_sobrevivencia'],'heads':{task:summary['tasks'][task]['head_sha256'] for task in ('nli','forecast')},'code_sha256':{name:sha(package/'ferramentas'/name) for name in ('phi4_portatil.py','treinar.py','inferir.py')},'inference_entrypoint':'ferramentas/inferir.py','not_deployed':True}
 write(heads/'artefato.json',artifact);write(work/'resultado.json',summary)
 print('Treinamento concluído. Resultados:',work/'resultado.json',flush=True)
 return summary

if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('step',choices=('extract','train'));p.add_argument('--package',type=Path,default=Path(__file__).parents[1]);p.add_argument('--work',type=Path,required=True);p.add_argument('--model-directory',type=Path);p.add_argument('--device',default='auto',choices=('auto','cpu','cuda','mps'));p.add_argument('--tile-rows',type=int,default=256);p.add_argument('--prefill-chunk',type=int);a=p.parse_args()
 if a.step=='extract':extract(a.package,a.work,a.model_directory,a.device,a.tile_rows,a.prefill_chunk)
 else:train(a.package,a.work)
