from pathlib import Path
from collections import defaultdict,Counter
import sys,json,gzip,hashlib,shutil,re
import numpy as np
import os
ROOT=Path(os.environ.get('MISSION_DATASET_PROJECT',str(Path(__file__).resolve().parents[3])))
for p in (ROOT/'src',ROOT/'datasets/piloto-v03/ferramentas',ROOT/'treinamento/piloto-v01/pacote/ferramentas',ROOT/'datasets/piloto-v05/ferramentas',Path(__file__).parent):sys.path.insert(0,str(p))
from entrada_agente import InputBuilder,ObservationMemory,canonical
from agent_contract import AgentView
from epistemico import classify,LABELS
from planos_v2 import MEANINGS,legacy

def read(p):
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(l) for l in f]
def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def lines(p,x):
    with (gzip.open(p,'wt') if p.suffix=='.gz' else p.open('w')) as f:
        for r in x:f.write(canonical(r)+'\n')
def normalized(x):
    refs={}
    def sub(m):
        refs.setdefault(m.group(),f'p{len(refs)+1}');return refs[m.group()]
    return re.sub(r'(?<!\w)p[1-9][0-9]*(?!\w)',sub,canonical(x))

def run(folder):
    OUT=Path(folder);source=OUT
    manifest=json.loads((OUT/'manifesto.json').read_text())
    if manifest.get('input_format')=='agent-view-compact':raise ValueError('Entradas já corrigidas; validar sem reprocessar')
    with gzip.open(OUT/'auditoria/contexts.json.gz','rt') as f:contexts=json.load(f)
    old_inputs=read(OUT/'inputs.jsonl.gz');old_meta=read(OUT/'supervisao.jsonl');nli=read(OUT/'auditoria/nli-rotulos.jsonl' if (OUT/'auditoria/nli-rotulos.jsonl').exists() else OUT/'auditoria/nli-rotulos.jsonl.gz')
    bindings=read(OUT/'auditoria/forecast-vinculos.jsonl');catalog=json.loads((OUT/'matriz-cobertura.json').read_text())['catalog']
    inputs=[];metadata=[];label_counts=Counter();proof={};nli_progress=0
    for i,row in enumerate(nli):
        record=contexts[row['context_key']];builder=InputBuilder(AgentView.from_engine(record['view']),catalog,nonce=row['family']+'-'+row['context_key'])
        assert builder.context==record['context']
        y,witness=classify(builder.context,row['claim']);assert LABELS[y]==row['target'] and witness==row['witness']
        pair=builder.nli(row['claim']);row['input']=pair;inputs.append(pair);metadata.append(old_meta[i]);label_counts[row['target']]+=1
        proof.setdefault(row['context_key'],record['view'])
    groups=defaultdict(list)
    for i,row in enumerate(bindings):groups[row['root'],row['plan_key']].append((i,row))
    assert len(groups)==576 and all(len(g)==3 for g in groups.values())
    result_rows=read(OUT/'auditoria/resultados-continuacoes.jsonl.gz');outcomes=defaultdict(dict)
    for r in result_rows:outcomes[r['row_index']][r['trial']]=r['target']['final_direction']
    merged=[];moments={}
    for new_index,((root,plan),members) in enumerate(groups.items()):
        index,first=members[0];b=first['binding'];builder=InputBuilder(AgentView.from_engine(b['raw_view']),catalog,nonce=root)
        inp=builder.forecast(b['raw_plan'],MEANINGS);trials=sorted(outcomes[index]);assert len(trials)==32
        for j,r in members:
            assert set(outcomes[j])==set(trials)
            other=InputBuilder(AgentView.from_engine(r['binding']['raw_view']),catalog,nonce=root).forecast(r['binding']['raw_plan'],MEANINGS)
            assert other==inp and r['split']==first['split']
        directions=[outcomes[j][t] for j,r in members for t in trials];counts=Counter(directions);p=counts['PLANETA']/len(directions)
        per_world=np.array([sum(outcomes[j][t]=='PLANETA' for j,r in members)/3 for t in trials])
        seed=int(hashlib.sha256((root+plan).encode()).hexdigest()[:16],16)
        boot=np.random.default_rng(seed).choice(per_world,size=(2000,32),replace=True).mean(1)
        low,high=np.quantile(boot,[.025,.975])
        supervision={'counts':dict(counts),'probabilities':{'entrega_no_planeta':p,'retorno_com_sobrevivencia':1-p},'trials':96,'independent_worlds':32,'uncertainty':{'method':'paired_world_bootstrap_2000','entrega_no_planeta':[float(low),float(high)],'retorno_com_sobrevivencia':[float(1-high),float(1-low)]}}
        meta={k:first[k] for k in ('family','goal','group','plan_key','plan_partition','root','split')}
        meta.update(task='forecast',regime='fixed_equal_mixture',target=p,supervision=supervision,round=b['raw_view']['round'],phase=b['raw_view']['phase'])
        inputs.append(inp);metadata.append(meta);merged.append(dict(meta,binding=b,source_rows=[j for j,r in members]))
    for i,r in enumerate(metadata):r['index']=i
    splits=defaultdict(set);ngroups=defaultdict(set);labels_by_input=defaultdict(set)
    for x,r in zip(inputs,metadata):
        key=normalized(x);splits[r['split']].add(key);ngroups[r['split']].add(r['group'])
        if r['task']=='nli':labels_by_input[key].add(r['target'])
    for a,b in (('train','calibration'),('train','test'),('calibration','test')):
        assert not splits[a]&splits[b],('overlapping_input',a,b,len(splits[a]&splits[b]))
        assert not ngroups[a]&ngroups[b]
    assert all(len(v)==1 for v in labels_by_input.values()),'Classificação conflitante para mesma entrada'
    lines(OUT/'inputs.jsonl.gz',inputs);lines(OUT/'supervisao.jsonl',metadata);lines(OUT/'auditoria/nli-rotulos.jsonl',nli);lines(OUT/'auditoria/forecast-vinculos.jsonl',merged)
    prefix=(source/'prefixo-nli.txt').read_text().strip()+'\nContexto e declaração são objetos JSON. Campos e coleções omitidos não fornecem evidência. p1, p2 etc. são referências temporárias desta chamada, sem identidade persistente. facts são confirmações com validity static/current/historical e progress quando disponível; sensors são leituras atuais; speech contém falas recebidas ou enviadas, sem duplicação, não fatos; revelations são aberturas daquele momento; beliefs são posições e suposições próprias; events são o histórico público. Tabelas usam columns e rows; questions define referências locais q1, q2 etc. Sem significado global. progress nulo significa não informado. Na declaração, kind fact avalia o fato, speech avalia o registro de fala, position avalia a posição declarada.\n'
    (OUT/'prefixo-nli.txt').write_text(prefix)
    system='Estime entrega_no_planeta e retorno_com_sobrevivencia, probabilidades complementares do término da partida, usando apenas o contexto autorizado e a condição de continuação própria em candidate_plan. Não produza ações ou planos. PLANETA determina entrega observável; ESTAÇÃO_ESPACIAL determina retorno com sobrevivência de humanos a bordo. Campos omitidos não são evidência. p1, p2 etc. distinguem pessoas somente nesta chamada. facts são confirmações; sensors são leituras atuais; speech contém falas; revelations são aberturas daquele momento; beliefs são posições e suposições; events são o histórico público. Falas não confirmam seu conteúdo factual. As regras de candidate_plan descrevem somente a continuação própria, sem identificar implementação de terceiros. Se o alvo sair, aplica-se a primeira outra pessoa ativa na ordem pública, respeitando legalidade.\n'+'Reserva e distância'+(source/'system-forecast.txt').read_text().split('Reserva e distância',1)[1].split('\n',1)[0].strip()+'\n'
    (OUT/'system-forecast.txt').write_text(system)
    manifest=json.loads((OUT/'manifesto.json').read_text());manifest.update(input_format='agent-view-compact',rows=len(inputs),forecast_rows=576,split_task_counts=dict(Counter(r['task']+'-'+r['split'] for r in metadata)),status='corrected_pending_validation',input_source='AgentView plus accumulated observed history; own candidate only',forecast_target_distribution='fixed equal mixture of three generating regimes; 96 continuations grouped in 32 paired worlds; regimes not input',forecast_rows_before_correction=1728,private_simulation_parameters_are_features=False)
    write(OUT/'manifesto.json',manifest)
    report={'nli_rows':len(nli),'nli_classes':dict(label_counts),'forecast_rows':576,'rollouts_preserved':len(result_rows),'split_normalized_input_overlap':0,'split_group_overlap':0,'oracle_labels_unchanged':True,'typed_agent_view_contexts_reproduced':len(proof),'features_from_private_engine_state':False}
    old_chars={t:sum(len(canonical(x)) for x,r in zip(old_inputs,old_meta) if r['task']==t)/sum(r['task']==t for r in old_meta) for t in ('nli','forecast')}
    new_chars={t:sum(len(canonical(x)) for x,r in zip(inputs,metadata) if r['task']==t)/sum(r['task']==t for r in metadata) for t in ('nli','forecast')}
    report['mean_input_characters']={t:{'before':old_chars[t],'after':new_chars[t],'reduction_fraction':1-new_chars[t]/old_chars[t]} for t in old_chars}
    write(OUT/'validacao-correcao.json',report);print(canonical(report),flush=True)
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args();run(args.folder)
