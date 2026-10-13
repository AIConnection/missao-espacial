from pathlib import Path
from collections import Counter,defaultdict
import sys,json,gzip,hashlib,argparse,re
import os
ROOT=Path(os.environ.get('MISSION_DATASET_PROJECT',str(Path(__file__).resolve().parents[3])))
for p in (ROOT/'src',ROOT/'datasets/piloto-v03/ferramentas',ROOT/'treinamento/piloto-v01/pacote/ferramentas',ROOT/'datasets/piloto-v05/ferramentas',Path(__file__).parent):sys.path.insert(0,str(p))
from agent_contract import AgentView
from entrada_agente import InputBuilder,ObservationMemory
from decodificar_auditoria import decode_pair
from epistemico import classify,LABELS
from planos_v2 import MEANINGS,legacy
from contrato_v2 import validate_input

def read(p):
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(l) for l in f]
def normalized(x):
    refs={}
    def sub(m):refs.setdefault(m.group(),f'p{len(refs)+1}');return refs[m.group()]
    return re.sub(r'(?<!\w)p[1-9][0-9]*(?!\w)',sub,json.dumps(x,sort_keys=True,ensure_ascii=False))
def validate(folder,model_directory,replays=96):
    folder=Path(folder);model_directory=Path(model_directory)
    xs=read(folder/'inputs.jsonl.gz');meta=read(folder/'supervisao.jsonl');nli=read(folder/'auditoria/nli-rotulos.jsonl' if (folder/'auditoria/nli-rotulos.jsonl').exists() else folder/'auditoria/nli-rotulos.jsonl.gz');bindings=read(folder/'auditoria/forecast-vinculos.jsonl')
    with gzip.open(folder/'auditoria/contexts.json.gz','rt') as f:contexts=json.load(f)
    catalog=json.loads((folder/'matriz-cobertura.json').read_text())['catalog'];inputs=defaultdict(set);groups=defaultdict(set);fine=Counter()
    assert len(xs)==len(meta)==7410 and len(nli)==6834 and len(bindings)==576
    for i,(x,r) in enumerate(zip(xs,meta)):
        assert i==r['index'];inputs[r['split']].add(normalized(x));groups[r['split']].add(r['group'])
        assert set(x)==({'premise','hypothesis'} if r['task']=='nli' else {'context','candidate_plan'})
        if r['task']=='nli':
            row=nli[i];record=contexts[row['context_key']]
            b=InputBuilder(AgentView.from_engine(record['view']),catalog,nonce=row['family']+'-'+row['context_key'])
            assert b.nli(row['claim'])==x==row['input']
            label,_=classify(b.context,row['claim']);assert LABELS[label]==r['target']
            decoded,claim=decode_pair(x,catalog);label,_=classify(decoded,claim);assert LABELS[label]==r['target'],('serialized_semantics',i)
            bucket=str(r['round']) if r['round']<=6 else '7-12' if r['round']<=12 else '13+'
            fine[r['split'],r['kind'],bucket,r['phase'],r['target']]+=1
        else:
            validate_input(x);row=bindings[i-len(nli)];raw=row['binding']
            assert InputBuilder(AgentView.from_engine(raw['raw_view']),catalog,nonce=row['root']).forecast(raw['raw_plan'],MEANINGS)==x
    for a,b in (('train','calibration'),('train','test'),('calibration','test')):assert not inputs[a]&inputs[b] and not groups[a]&groups[b]
    for part,kind,bucket,phase,label in fine:assert len({fine[part,kind,bucket,phase,c] for c in range(3)})==1
    outcomes=read(folder/'auditoria/resultados-continuacoes.jsonl.gz');byrow=defaultdict(Counter)
    for r in outcomes:
        assert legacy.label_outcome(r['result'])==r['target'];byrow[r['row_index']][r['target']['final_direction']]+=1
    for j,row in enumerate(bindings):
        counts=sum((byrow[i] for i in row['source_rows']),Counter());supervision=meta[len(nli)+j]['supervision']
        assert dict(counts)==supervision['counts'] and sum(counts.values())==96
        assert meta[len(nli)+j]['target']==counts['PLANETA']/96
    # Reutiliza os mesmos mundos/semântica: nenhuma nova previsão ou estratégia é inventada.
    from populacoes_v2 import rollout_implementations
    worlds=read(folder/'auditoria/mundos.jsonl.gz');roots={r['key']:r for r in worlds if r['kind']=='root'};accepted={(r['root'],r['trial']):r for r in worlds if r['kind']=='world'}
    populations={r['name']:r for r in json.loads((folder/'regimes.json').read_text())}
    oldbinding={i:r for r in bindings for i in r['source_rows']}
    chosen={};ordered=sorted(outcomes,key=lambda r:hashlib.sha256(json.dumps(r,sort_keys=True).encode()).hexdigest())
    for r in ordered:
        for key in (('root',r['root']),('regime',r['regime']),('plan',r['plan_key'])):chosen.setdefault(key,r)
    selection={json.dumps(r,sort_keys=True):r for r in chosen.values()}
    for r in ordered:
        if len(selection)>=replays:break
        selection.setdefault(json.dumps(r,sort_keys=True),r)
    for r in selection.values():
        root=roots[r['root']];world=accepted[r['root'],r['trial']];binding=oldbinding[r['row_index']]['binding']
        replay=rollout_implementations(json.dumps(world['checkpoint'],ensure_ascii=False),r['behavior_seed'],root['observer'],root['goal'],binding['raw_plan'],populations[r['regime']])
        assert replay['result']==r['result'] and replay['phases']==r['phases']
    from transformers import AutoTokenizer
    from phi4_portatil import NLI_SYSTEM
    tok=AutoTokenizer.from_pretrained(model_directory,local_files_only=True,trust_remote_code=False);prefix=(folder/'prefixo-nli.txt').read_text().rstrip('\n');system=(folder/'system-forecast.txt').read_text().rstrip('\n')
    lengths=defaultdict(list)
    for x,r in zip(xs,meta):
        if r['task']=='nli':body=json.dumps({'premise':prefix+'\n\n'+x['premise'],'hypothesis':x['hypothesis']},ensure_ascii=False);instruction=NLI_SYSTEM
        else:body=json.dumps(x,ensure_ascii=False,sort_keys=True);instruction=system
        prompt=tok.apply_chat_template([{'role':'system','content':instruction},{'role':'user','content':body}],tokenize=False,add_generation_prompt=True);n=len(tok.encode(prompt,add_special_tokens=False));assert 0<n<=16384
        lengths[r['task']].append(n)
    report={'status':'passed','rows':len(xs),'nli_oracle_and_serialized_semantics_verified':len(nli),'agent_view_reproduction_verified':len(xs),'forecast_marginal_targets_verified':len(bindings),'forecast_terminal_results_verified':len(outcomes),'forecast_replays_executed':len(selection),'split_normalized_input_overlap':0,'split_group_overlap':0,'class_type_round_phase_balance_verified':True,'window_tokens':16384,'tokens':{k:{'min':min(v),'median':sorted(v)[len(v)//2],'max':max(v)} for k,v in lengths.items()},'truncation':False,'model_weights_executed':False}
    (folder/'validacao.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');m=json.loads((folder/'manifesto.json').read_text());m.update(status='validated',input_format='agent-view-compact',validation='validacao.json');(folder/'manifesto.json').write_text(json.dumps(m,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--model-directory',type=Path,required=True);p.add_argument('--replays',type=int,default=96);a=p.parse_args();validate(a.folder,a.model_directory,a.replays)
