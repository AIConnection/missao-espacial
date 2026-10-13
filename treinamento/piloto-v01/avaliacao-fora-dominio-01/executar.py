"""Inference-only OOD evaluation. Uses the exported head through its original loader."""
from pathlib import Path
import argparse,json,sys,time,hashlib,warnings,math

def digest(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--project',type=Path,default=Path('/Users/alexandre/projects/missao-espacial'))
 p.add_argument('--model-directory',type=Path,required=True)
 p.add_argument('--device',default='auto')
 p.add_argument('--data',type=Path,default=Path(__file__).parent)
 a=p.parse_args();b=a.data
 package=a.project/'treinamento/piloto-v01/pacote';heads=a.project/'treinamento/piloto-v01/execucao-local-01/heads'
 protocol=json.loads((b/'protocolo.json').read_text())
 for name,h in protocol['data_sha256'].items():assert digest(b/name)==h
 inputs=[json.loads(l) for l in (b/'inputs.jsonl').read_text().splitlines()]
 supervision=[json.loads(l) for l in (b/'supervisao.jsonl').read_text().splitlines()]
 assert len(inputs)==len(supervision)==30
 if (b/'previsoes.jsonl').exists():raise ValueError('Execução já existe; usar diretório novo para repetir.')
 head_before=digest(heads/'nli.npz')
 sys.path.insert(0,str(package/'ferramentas'))
 import numpy as np
 from inferir import PilotPredictor,head_probabilities
 from treinar import LABELS
 started=time.monotonic()
 print('Carregando somente corpo público Phi-4 e cabeça NLI exportada da Missão Espacial.',flush=True)
 model=PilotPredictor(package,heads,a.model_directory,a.device)
 original_features=model.backend.features
 capture={}
 def observe(tokens):
  x,abc=original_features(tokens);capture['feature']=x;return x,abc
 model.backend.features=observe
 (b/'features').mkdir(exist_ok=False)
 all_results=[]
 with (b/'previsoes.jsonl').open('x') as out:
  for i,value in enumerate(inputs):
   t=time.monotonic();tokens=model.backend.encode_nli(value,model.prefix)
   assert 0<len(tokens)<=model.backend.window
   # Public prediction contract: only classification. No label or audit metadata is passed.
   with warnings.catch_warnings(record=True) as ws:
    warnings.simplefilter('always');output=model.predict('nli',value)
    assert set(output)=={'classification'} and output['classification'] in LABELS
    x=capture.pop('feature');probs=head_probabilities(heads/'nli.npz',x,'nli')
   assert np.isfinite(probs).all() and abs(float(probs.sum())-1)<1e-10
   assert output['classification']==LABELS[int(probs.argmax())]
   np.savez_compressed(b/'features'/f'{i:02}.npz',features=x)
   # Probabilities stay in the evaluation audit, outside the API output.
   expected=supervision[i]['expected']
   result={'index':i,'case_id':supervision[i]['case_id'],'family':supervision[i]['family'],'expected':expected,
    'output':output,'correct':output['classification']==expected,'tokens':len(tokens),'no_truncation':True,
    'elapsed_seconds':time.monotonic()-t,'audit_probabilities':{k:float(v) for k,v in zip(LABELS,probs)},
    'warnings':[str(w.message) for w in ws]}
   out.write(json.dumps(result,ensure_ascii=False,allow_nan=False)+'\n');out.flush();all_results.append(result)
   print(json.dumps({k:result[k] for k in ['index','family','expected','output','correct','tokens','elapsed_seconds']},ensure_ascii=False),flush=True)
 assert digest(heads/'nli.npz')==head_before
 for name,h in protocol['data_sha256'].items():assert digest(b/name)==h
 cm=[[0]*3 for _ in LABELS];loss=0
 for r in all_results:
  j=LABELS.index(r['expected']);cm[j][LABELS.index(r['output']['classification'])]+=1
  loss-=math.log(max(1e-12,r['audit_probabilities'][r['expected']]))
 per=[]
 for j,label in enumerate(LABELS):
  tp=cm[j][j];fp=sum(row[j] for row in cm)-tp;fn=sum(cm[j])-tp
  pr=tp/(tp+fp) if tp+fp else 0;rc=tp/(tp+fn) if tp+fn else 0
  per.append({'label':label,'precision':pr,'recall':rc,'f1':2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0})
 paired=[]
 for r,s in zip(all_results,supervision):
  if 'paired_base' not in s:continue
  base=next(rr for rr,ss in zip(all_results,supervision) if ss['family']==s['family'] and ss['expected']==s['expected'] and ss['variant']=='base')
  paired.append({'base_index':base['index'],'variant_index':r['index'],'expected':r['expected'],
   'same_classification':base['output']==r['output'],'both_correct':base['correct'] and r['correct']})
 metrics={'rows':30,'families':8,'accuracy':sum(r['correct'] for r in all_results)/30,'macro_f1':sum(r['f1'] for r in per)/3,
  'nll_audit_only':loss/30,'confusion_matrix_true_rows_predicted_columns':cm,'labels':list(LABELS),'per_class':per,
  'base_cases_accuracy':sum(r['correct'] for r,s in zip(all_results,supervision) if s['variant']=='base')/24,
  'by_family':{f:{'rows':sum(r['family']==f for r in all_results),'correct':sum(r['family']==f and r['correct'] for r in all_results)} for f in sorted({r['family'] for r in all_results})}}
 report={'actual_phi4_forward':True,'original_predictor_used':True,'head_unchanged':True,'head_sha256':head_before,
  'body_identity':model.backend.identity,'original_prefix_sha256':digest(package/'dados/prefixo-nli.txt'),'data_sha256':protocol['data_sha256'],
  'model_received_only_premise_and_hypothesis':True,'output_contract':{'classification':'suporte | insuficiente | contradição'},
  'normalization_and_temperature_reused':True,'no_training_or_calibration':True,'maximum_tokens':max(r['tokens'] for r in all_results),
  'all_contexts_fit_without_truncation':True,'total_elapsed_seconds':time.monotonic()-started,'metrics':metrics,'paired_variants':paired,
  'numeric_warnings_observed':sum(bool(r['warnings']) for r in all_results),'limits':protocol['limits']}
 (b/'resultado.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print('CONCLUÍDO: '+json.dumps(metrics,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
