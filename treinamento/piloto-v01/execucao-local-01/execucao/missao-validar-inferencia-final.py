from pathlib import Path
import sys,json,time,numpy as np
P=Path('/Users/alexandre/projects/missao-espacial/treinamento/piloto-v01/pacote')
W=Path('/private/tmp/missao-espacial-treino-real-04')
sys.path.insert(0,str(P/'ferramentas'))
from treinar import read_data,LABELS,load_features
from inferir import PilotPredictor,head_probabilities
inputs,rows=read_data(P)
model=PilotPredictor(P,W/'heads','/Users/alexandre/crivo/assets/phi4')
x,_,_=load_features(W)
checks=[]
for task,target in [('nli',i) for i in range(3)]+[('forecast',None)]:
 candidates=[r for r in rows if r['task']==task and r['split']=='test' and (target is None or r['target']==target)]
 def tokens(r):return model.encoder.encode(inputs[r['index']]) if task=='forecast' else model.backend.encode_nli(inputs[r['index']],model.prefix)
 r=min(candidates,key=lambda r:len(tokens(r)))
 start=time.monotonic();out=model.predict(task,inputs[r['index']])
 cached=head_probabilities(W/'heads'/f'{task}.npz',x[r['index']],task)
 if task=='nli':assert out=={'classification':LABELS[int(cached.argmax())]}
 else:assert max(abs(out[k]-cached[j]) for j,k in enumerate(('entrega_no_planeta','retorno_com_sobrevivencia')))<1e-4
 checks.append({'task':task,'index':r['index'],'tokens':len(tokens(r)),'output':out,'elapsed_seconds':time.monotonic()-start,'matches_saved_feature_prediction':True})
 print(json.dumps(checks[-1],ensure_ascii=False),flush=True)
(W/'validacao-inferencia.json').write_text(json.dumps({'actual_phi4_forward':True,'original_portable_loader':True,'device':str(model.backend.device),'checks':checks},ensure_ascii=False,indent=2)+'\n')
