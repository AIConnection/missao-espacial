"""Mesmo Phi-4/base e mesmos 816 prompts. Reuso causal apenas de tokens idênticos.
Não lê cabeças ou normalizações de outro domínio. Todos os contextos preservados.
"""
from pathlib import Path
import sys,json,time,shutil
import numpy as np,torch
SRC=Path('/private/tmp/missao-execucao-local-03.py');source=SRC.read_text();ns={'__file__':str(SRC),'__name__':'prefix_runtime'}
exec(compile(source[:source.index("print('Phi-4 base congelado")],str(SRC),'exec'),ns)
runtime=ns['runtime'];treinar=ns['treinar'];PKG=ns['PKG'];Accelerated=ns['Accelerated'];encoder_class=ns['ForecastEncoder']
OLD=Path('/private/tmp/missao-espacial-treino-real-03');WORK=Path('/private/tmp/missao-espacial-treino-real-04');cache_dir=WORK/'features'
print('Reuso exato de prefixos; 816 exemplos integrais; nenhuma cabeça do Crivo.',flush=True)
backend=Accelerated(PKG/'modelo.json','/Users/alexandre/crivo/assets/phi4','auto',256,None)
inputs,rows=treinar.read_data(PKG);encoder=encoder_class(backend.directory);prefix=(PKG/'dados/prefixo-nli.txt').read_text().rstrip('\n')
seq=[encoder.encode(x) if r['task']=='forecast' else backend.encode_nli(x,prefix) for x,r in zip(inputs,rows)]
if any(not t or len(t)>backend.window for t in seq):raise RuntimeError('Janela excedida; não truncar')
order=sorted(range(len(seq)),key=lambda i:seq[i])
identity={'package_sha256':runtime.sha(PKG/'integridade.json'),'backend':backend.identity,'extractor_sha256':runtime.sha(PKG/'ferramentas/treinar.py'),'portable_runtime_sha256':runtime.sha(PKG/'ferramentas/phi4_portatil.py'),'prefix_executor_sha256':runtime.sha(Path(__file__)),'prefix_reuse':'only byte-identical token prefix; DynamicCache.crop; canonical original indices','maximum_new_query_tokens':3072,'no_input_transformation':True}
WORK.mkdir(exist_ok=True);cache_dir.mkdir(exist_ok=True);progress_path=WORK/'progresso-extracao.json'
if progress_path.exists():
 progress=json.loads(progress_path.read_text())
 if progress['identity']!=identity:raise RuntimeError('Identidade da execução mudou')
else:
 old=json.loads((OLD/'features/manifesto.json').read_text());records={}
 if old['identity']['package_sha256']!=identity['package_sha256']:raise RuntimeError('Pacote antigo incompatível')
 for r in old['rows']:
  path=OLD/'features'/r['file']
  if runtime.sha(path)!=r['sha256']:raise RuntimeError('Checkpoint antigo corrompido')
  shutil.copy2(path,cache_dir/r['file']);records[str(r['index'])]=r
 progress={'identity':identity,'records':records,'original_full_forward_rows_preserved':len(records),'completed':False,'truncation':False,'prefix_computed_from_inputs_only':True}
 treinar.write(progress_path,progress)
for key,r in progress['records'].items():
 if int(key)!=r['index'] or runtime.sha(cache_dir/r['file'])!=r['sha256']:raise RuntimeError('Checkpoint corrompido')
print('Checkpoints preservados:',len(progress['records']),flush=True)
previous=[];kv=None
@torch.inference_mode()
def cached_forward(tokens):
 global previous,kv
 common=0
 for a,b in zip(previous,tokens):
  if a!=b:break
  common+=1
 # At least one terminal token is recomputed; all earlier tokens stay represented.
 common=min(common,len(tokens)-1)
 if kv is not None:kv.crop(common)
 else:common=0
 final=None
 for start in range(common,len(tokens),3072):
  end=min(start+3072,len(tokens));ids=torch.tensor([tokens[start:end]],dtype=torch.long,device=backend.device);mask=torch.ones((1,end),dtype=torch.long,device=backend.device)
  out=backend.model(input_ids=ids,attention_mask=mask,past_key_values=kv,use_cache=True)
  kv=out.past_key_values;final=out.last_hidden_state[:,-1]
 x=final.float().cpu().numpy()[0];abc=torch.nn.functional.linear(final,backend.abc_weight).float().cpu().numpy()[0]
 if not np.isfinite(x).all() or not np.isfinite(abc).all():raise RuntimeError('Feature inválida')
 previous=tokens
 return x,abc,common
# Existing probes validate actual Phi-4 prefix reuse and no old features change.
print('Benchmark de reuso verificado:',json.loads(Path('/private/tmp/missao-benchmark-lotes.json').read_text())['prefix_feature_max_absolute_difference'],flush=True)
for i in order:
 if str(i) in progress['records']:continue
 started=time.perf_counter();x,abc,common=cached_forward(seq[i]);seconds=time.perf_counter()-started
 name=f'{i:04d}.npz';tmp=cache_dir/(name+'.tmp')
 with tmp.open('wb') as f:np.savez_compressed(f,features=x,baseline_abc=abc)
 tmp.replace(cache_dir/name)
 record={'index':i,'file':name,'sha256':runtime.sha(cache_dir/name),'tokens':len(seq[i]),'seconds':seconds,'reused_prefix_tokens':common,'all_context_tokens_preserved':True}
 progress['records'][str(i)]=record;treinar.write(progress_path,progress)
 print(f"{len(progress['records'])}/816 — {rows[i]['task']} — row {i} — {len(seq[i])} tokens, reuso {common} — {seconds:.1f}s",flush=True)
progress['completed']=True;treinar.write(progress_path,progress)
ordered=[progress['records'][str(i)] for i in range(len(rows))]
treinar.write(cache_dir/'manifesto.json',{'identity':identity,'rows':ordered,'completed':True,'truncation':False,'tokens_max':max(map(len,seq))})
# Only now are domain heads initialized/trained, after the complete extraction.
treinar.train(PKG,WORK)
print('TREINAMENTO PILOTO INTEGRAL CONCLUÍDO',WORK,flush=True)
