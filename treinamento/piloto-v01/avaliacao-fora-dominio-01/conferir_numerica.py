from pathlib import Path
import json,math
import numpy as np
import torch
B=Path(__file__).parent
HEAD=Path('/Users/alexandre/projects/missao-espacial/treinamento/piloto-v01/execucao-local-01/heads/nli.npz')
pred=[json.loads(l) for l in (B/'previsoes.jsonl').read_text().splitlines()]
assert len(pred)==30
with np.load(HEAD,allow_pickle=False) as a:h={k:a[k].copy() for k in a.files}
labels=('suporte','insuficiente','contradição')
checks=[]
for r in pred:
 with np.load(B/'features'/f'{r["index"]:02}.npz',allow_pickle=False) as a:x=a['features']
 tx=torch.from_numpy(x.copy());mu=torch.from_numpy(h['mean']);scale=torch.from_numpy(h['scale']);w=torch.from_numpy(h['weight']);bias=torch.from_numpy(h['bias'])
 with torch.inference_mode():
  z=((tx-mu)/scale)@w.T+bias
  p=torch.softmax(z.double()/float(h['temperature']),dim=0).numpy()
  x64=tx.double();z64=((x64-mu.double())/scale.double())@w.double().T+bias.double()
  p64=torch.softmax(z64/float(h['temperature']),dim=0).numpy()
 assert all(np.isfinite(v).all() for v in (x,z.numpy(),p,z64.numpy(),p64))
 original=np.array([r['audit_probabilities'][k] for k in labels])
 checks.append({'index':r['index'],'torch_classification':labels[int(p.argmax())],'float64_classification':labels[int(p64.argmax())],
  'original_classification':r['output']['classification'],'torch_max_probability_difference':float(np.max(np.abs(p-original))),
  'float64_max_probability_difference':float(np.max(np.abs(p64-original)))})
 assert checks[-1]['torch_classification']==checks[-1]['float64_classification']==r['output']['classification']
report={'rows':30,'all_features_logits_probabilities_finite':True,'all_classifications_match_original_inference':True,
 'torch_max_probability_difference':max(r['torch_max_probability_difference'] for r in checks),
 'float64_max_probability_difference':max(r['float64_max_probability_difference'] for r in checks),'checks':checks,
 'scope':'CPU head arithmetic only; Phi-4 not rerun and no weights updated'}
(B/'validacao-numerica.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='checks'},ensure_ascii=False))
