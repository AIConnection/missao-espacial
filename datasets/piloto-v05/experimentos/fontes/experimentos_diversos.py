"""Partidas novas com implementações distintas e RNG controlado, sem treino."""
from pathlib import Path
from collections import Counter
import json,gzip,sys,argparse,time,hashlib
from planos_v2 import ROOT,Game,DOMAINS,digest,draw,canonical
from carregar_agentes import load_agents,Implementation,assign_agents
from agentes_experimentais import EvidenceAgent,PressureAgent,InvestigatingAI,KeepingPressureAgent
from experimentos import Metrics,Aggregate

SCENARIOS={
 'alpha_only':['humano_alpha'], 'beta_only':['humano_beta'], 'gamma_only':['humano_gamma'],
 'random_only':['humano_random'], 'evidence_only':['evidence'], 'pressure_only':['pressure'],
 'mixed_legacy':['humano_alpha','humano_beta','humano_gamma','humano_random'],
 'mixed_all':['humano_alpha','humano_beta','humano_gamma','humano_random','evidence','pressure'],
 'mixed_new_ai':['humano_random','evidence','pressure'],
 'pressure_keep_only':['pressure_keep'],
 'mixed_pressure_keep':['humano_random','evidence','pressure_keep']}

def run(output,repetitions=20):
    output.mkdir(parents=True,exist_ok=False)
    implementations=load_agents(ROOT/'src/agent');implementations.update(evidence=Implementation('HUMANO',EvidenceAgent),pressure=Implementation('HUMANO',PressureAgent),pressure_keep=Implementation('HUMANO',KeepingPressureAgent),investigating_ai=Implementation('IA',InvestigatingAI))
    rows=[];views=[];aggregates={name:Aggregate(name) for name in SCENARIOS};start=time.monotonic()
    for name,human_kinds in SCENARIOS.items():
        for rep in range(repetitions):
            # Mundo pareado entre cenários; N/tamanho/posse/RNG não dependem do nome.
            size=[3,5,8,10][rep%4];N=[8,12,20][rep%3];ids=[f'game-private-{rep}-{i}' for i in range(size)]
            seed=91000+rep;randomizer=draw('experiments-world',rep);ai=randomizer.choice(ids)
            shuffled=list(ids);randomizer.shuffle(shuffled);owners={d:shuffled[i%size] for i,d in enumerate(DOMAINS)}
            assignment={a:('investigating_ai' if name=='mixed_new_ai' else 'humanoide') if a==ai else human_kinds[j%len(human_kinds)] for j,a in enumerate(ids)}
            profiles={a:{'sacrifice':j%2==0} for j,a in enumerate(ids)}
            game=Game(N,seed=seed,participant_ids=ids,ai_id=ai,owners=owners,profiles=profiles)
            agent_seeds={a:int(digest(['behavior',rep,j])[:15],16) for j,a in enumerate(ids)}
            session=assign_agents(game,implementations,assignment,agent_seeds=agent_seeds);metrics=Metrics(session);began=time.monotonic()
            for phase_index in range(2000):
                if game.finished:break
                # Uma observação por pessoa e fase, com histórico autorizado integral.
                for a in game.active_ids():
                    if a==ai:continue
                    views.append({'scenario':name,'replication':rep,'family':f'experiment-{rep}-{name}','implementation':assignment[a],'view':game.view(a,history_limit=None)})
                metrics.advance()
            if not game.finished:raise ValueError('CENSORED_EXPERIMENT')
            row=metrics.record(rep,seed,time.monotonic()-began,0);row.update(scenario=name,assignment=assignment,N=N,participants=size)
            rows.append(row);aggregates[name].add(row)
        print(canonical({'scenario':name,'games':len(rows),'seconds':round(time.monotonic()-start,1)}),flush=True)
    with gzip.open(output/'partidas.jsonl.gz','wt') as f:
        for r in rows:f.write(canonical(r)+'\n')
    with gzip.open(output/'observacoes.jsonl.gz','wt') as f:
        for r in views:f.write(canonical(r)+'\n')
    report={'games':len(rows),'observations':len(views),'replications_per_scenario':repetitions,'scenarios':{k:v.summary() for k,v in aggregates.items()},'identities_in_training_features':False,'model_executed':False,'seed_pairing':'Mesmo N, tamanho, detentores, natureza, RNG da engine e seeds por posição; comportamento pode consumir RNG em sequências distintas. Comparação experimental de composições, não identidade pessoal.'}
    sources=output/'fontes';sources.mkdir();
    import shutil
    for name in ('agentes_experimentais.py','experimentos_diversos.py'):shutil.copy2(Path(__file__).with_name(name),sources/name)
    report['experimental_source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.glob('*.py')}
    report['engine_source_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').rglob('*.py')}
    (output/'estatisticas.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(canonical({'completed':True,'games':len(rows),'observations':len(views)}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--repetitions',type=int,default=20);a=p.parse_args();run(a.output,a.repetitions)
