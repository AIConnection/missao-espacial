"""Fechamento: cobertura categórica obrigatória e referências preservadas da v1."""
from pathlib import Path
from collections import Counter
from copy import deepcopy
from concurrent.futures import ProcessPoolExecutor
import json,gzip,shutil,argparse,hashlib
from gerar_v05 import context_key,normalize_input,catalog_case,run_batch,write,lines,append_gz
from planos_v2 import *
from populacoes_v2 import POPULATIONS,describe_population
from epistemico import classify,LABELS
from gerar_piloto import speech
import gerar_cobertura as coverage
import anonimo

def readlines(p):
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(l) for l in f]
def finish(base,output,experiments,benchmark,workers=4):
    manifest=json.loads((base/'manifesto.json').read_text());assert manifest['status']=='generated_not_validated'
    shutil.copytree(base,output);audit=output/'auditoria';legacy.ASSUMPTIONS['N_prior']=[4,8,12,20]
    inputs=readlines(output/'inputs.jsonl.gz');meta=readlines(output/'supervisao.jsonl');nli=readlines(audit/'nli-rotulos.jsonl');contexts=json.loads((audit/'contexts.json').read_text());catalog={q['id']:q for q in Game().catalog['questions']}
    # Corrigir somente a representação nova, preservando todos os artefatos anteriores.
    kept={};known={};nli_inputs=[];nli_meta=[];repaired=0
    for row in nli:
        view=contexts[row['context_key']]['view'];ctx=from_view(view);ck=context_key(ctx)
        if ctx!=contexts[row['context_key']]['context']:
            frame=ReferenceFrame(ctx,nonce=digest(['frame-v05',row['family'],ck]));b=anonimo.binding(ctx,row['claim']);b.update(frame.routing())
            label,witness=classify(ctx,row['claim']);assert LABELS[label]==row['target'];row.update(input={'premise':render(ctx,catalog,b),'hypothesis':anonimo.assertion(catalog,ctx,row['claim'],b)},context_key=ck,witness=witness);repaired+=1
        kept[ck]={'context':ctx,'view':view};known[ck]=(row['group'],row['split']);nli_inputs.append(row['input']);nli_meta.append({k:row[k] for k in ('target','split','group','family','kind','origin_kind','round','phase')})
    forecast_inputs=[x for x,r in zip(inputs,meta) if r['task']=='forecast'];forecast_meta=[r for r in meta if r['task']=='forecast'];fore_binding=readlines(audit/'forecast-vinculos.jsonl')
    # Bloco obrigatório cobre alternativas e a grade finita declarada de parâmetros.
    ids=[f'coverage-private-{i}' for i in range(3)];configured=Game(participant_ids=ids);coverage_rows=[];dedup={normalize_input(x) for x in nli_inputs};case_index=200000
    for q in configured.catalog['questions']:
        parameter_grid=coverage.parameter_cases(q,ids)
        if q['id']=='Q11':parameter_grid=[{'X':x} for x in (1,13,14,15,16,17,1000000)]
        for params in parameter_grid:
            for k,answer in enumerate(q['fixed_responses']):
                for attempt in range(100):
                    case_index+=1;g,record_round=catalog_case(ids,q['id'],params,answer,case_index)
                    record={'source':ids[1],'recipient':ids[0],'qid':q['id'],'params':params,'round':record_round,'value':answer};pending=[];bindings=[]
                    for actor,value in ((ids[0],answer),(ids[0],q['fixed_responses'][(k+1)%len(q['fixed_responses'])]),(ids[2],answer)):
                        view=g.view(actor,history_limit=None);ctx=from_view(view);ck=context_key(ctx);claim=speech(record,value);label,witness=classify(ctx,claim)
                        pending.append((view,ctx,ck,claim,LABELS[label],witness))
                    assert [x[4] for x in pending]==[0,2,1]
                    if all(ck not in known or known[ck][1]=='train' for view,ctx,ck,c,y,w in pending):break
                else:raise ValueError('Cannot isolate mandatory catalog case')
                family=f'mandatory-catalog-{case_index}';group=next((known[ck][0] for v,ctx,ck,c,y,w in pending if ck in known),family)
                for view,ctx,ck,claim,target,witness in pending:
                    frame=ReferenceFrame(ctx,nonce=digest(['frame-v05',family,ck]));b=anonimo.binding(ctx,claim);b.update(frame.routing());inp={'premise':render(ctx,catalog,b),'hypothesis':anonimo.assertion(catalog,ctx,claim,b)}
                    key=normalize_input(inp)
                    # Os três membros entram juntos para manter balanceamento.
                    bindings.append((view,ctx,ck,claim,target,witness,inp,key))
                if any(key in dedup for v,ctx,ck,c,y,w,x,key in bindings):continue
                for view,ctx,ck,claim,target,witness,inp,key in bindings:
                    dedup.add(key);kept[ck]={'context':ctx,'view':view};known[ck]=(group,'train');r={'input':inp,'target':target,'split':'train','group':group,'family':family,'kind':'speech','origin_kind':'mandatory_catalog','round':view['round'],'phase':view['phase'],'context_key':ck,'claim':claim,'witness':witness,'slot':{'qid':q['id'],'params':params,'response':answer}}
                    nli.append(r);nli_inputs.append(inp);nli_meta.append({k:r[k] for k in ('target','split','group','family','kind','origin_kind','round','phase')})
                coverage_rows.append({'qid':q['id'],'params':params,'response':answer,'group':group})
    lines(audit/'nli-rotulos.jsonl',nli);write(audit/'contexts.json',kept);write(output/'cobertura-obrigatoria.json',coverage_rows)
    extra_rollouts=0;worlds_added=0
    lines(audit/'forecast-vinculos.jsonl',fore_binding);allinputs=nli_inputs+forecast_inputs;allmeta=[dict(r,task='nli') for r in nli_meta]+[dict(r,task='forecast') for r in forecast_meta]
    for i,r in enumerate(allmeta):r['index']=i
    with gzip.open(output/'inputs.jsonl.gz','wt') as f:
        for x in allinputs:f.write(canonical(x)+'\n')
    lines(output/'supervisao.jsonl',allmeta);(output/'system-forecast.txt').write_text(FORECAST_SYSTEM+'\n');write(output/'regimes.json',POPULATIONS)
    shutil.copytree(experiments,output/'experimentos');shutil.copytree(benchmark,output/'benchmark-contra-aleatorios')
    ref=output/'comparacao-v01';refheads=ref/'heads-v01';refheads.mkdir()
    for name in ('nli.npz','forecast.npz'):shutil.copy2(ROOT/'treinamento/piloto-v01/execucao-local-01/heads'/name,refheads/name)
    shutil.copy2(ROOT/'treinamento/piloto-v01/execucao-local-01/resultado.json',ref/'resultado-treino-v01.json');shutil.copy2(ROOT/'treinamento/piloto-v01/avaliacao-fora-dominio-01/resultado.json',ref/'resultado-ood-v01.json')
    manifest.update(rows=len(allinputs),nli_rows=len(nli_inputs),forecast_rows=len(forecast_inputs),nli_classes=dict(Counter(r['target'] for r in nli_meta)),split_task_counts=dict(Counter(r['task']+'-'+r['split'] for r in allmeta)),initial_contexts=48,compatible_worlds=manifest['compatible_worlds']+worlds_added,engine_rollouts=manifest['engine_rollouts']+extra_rollouts,forecast_cutoffs=[1,2,3,4,5,6],terminal_progress_contexts_corrected=repaired,mandatory_catalog_rows=len(nli)-6000,experimental_observations='experimentos/observacoes.jsonl.gz',forecast_rollout_executor='actual_implementations_protocol_v2',implementation_holdout_proven=False,status='generated_not_validated')
    write(output/'manifesto.json',manifest);print(canonical({'assembly_complete':True,'rows':len(allinputs),'nli':len(nli_inputs),'forecast':len(forecast_inputs)}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--experiments-directory',type=Path,required=True);p.add_argument('--benchmark-directory',type=Path,required=True);p.add_argument('--workers',type=int,default=4);a=p.parse_args();finish(a.base,a.output,a.experiments_directory,a.benchmark_directory,a.workers)
