"""Um agente específico contra humanos aleatórios, com controle pareado."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,json,gzip,time,hashlib,shutil
from planos_v2 import ROOT,Game,DOMAINS,digest,draw,canonical,legacy
from populacoes_v2 import registry
from carregar_agentes import assign_agents
from experimentos import Metrics

SPECIFIC=('humano_alpha','humano_beta','humano_gamma','evidence','pressure','pressure_keep')
GOALS=tuple(legacy.GOALS)
def run(output,repetitions=20):
    output.mkdir(parents=True,exist_ok=False);records=[];start=time.monotonic();implementations=registry()
    with gzip.open(output/'observacoes-focais.jsonl.gz','wt') as vf:
        for goal in GOALS:
            for name in ('humano_random',)+SPECIFIC:
                if name=='humano_alpha' and goal!='ENTREGA_NO_PLANETA':continue
                for rep in range(100,100+repetitions):
                    size=[3,5,8,10][rep%4];N=[8,12,20][rep%3];ids=[f'benchmark-private-{rep}-{i}' for i in range(size)]
                    rng=draw('matched-benchmark-world',rep);ai=rng.choice(ids);focal=next(a for a in ids if a!=ai)
                    shuffled=list(ids);rng.shuffle(shuffled);owners={d:shuffled[i%size] for i,d in enumerate(DOMAINS)}
                    assignment={a:'humanoide' if a==ai else name if a==focal else 'humano_random' for a in ids}
                    profiles={a:{'sacrifice':j%2==0} for j,a in enumerate(ids)};profiles[focal]={'sacrifice':goal=='ENTREGA_NO_PLANETA'}
                    game=Game(N,seed=99000+rep,participant_ids=ids,ai_id=ai,owners=owners,profiles=profiles);game.update_beliefs(focal,objective=legacy.GOALS[goal])
                    seeds={a:int(digest(['matched-benchmark-behavior',rep,j])[:15],16) for j,a in enumerate(ids)}
                    session=assign_agents(game,implementations,assignment,agent_seeds=seeds)
                    assert game.view(focal,history_limit=None)['beliefs']['objective']==legacy.GOALS[goal],('objective_mismatch',name,goal)
                    metrics=Metrics(session);began=time.monotonic()
                    for step in range(2000):
                        if game.finished:break
                        if game.view(focal,history_limit=1)['active']:
                            vf.write(canonical({'implementation':name,'objective':goal,'replication':rep,'family':f'benchmark-{goal}-{rep}-{name}','view':game.view(focal,history_limit=None)})+'\n')
                        metrics.advance()
                    assert game.finished,'CENSORED_BENCHMARK'
                    row=metrics.record(rep,99000+rep,time.monotonic()-began,0)
                    row.update(implementation=name,objective=goal,focal=focal,N=N,participants=size,assignment=assignment,profiles=profiles,owners=owners,agent_seeds=seeds,success=int(game.result['cargo_delivered'] if goal=='ENTREGA_NO_PLANETA' else game.result['returned']))
                    records.append(row)
                print(canonical({'implementation':name,'objective':goal,'games':len(records),'seconds':round(time.monotonic()-start,1)}),flush=True)
    with gzip.open(output/'partidas.jsonl.gz','wt') as f:
        for r in records:f.write(canonical(r)+'\n')
    controls={(r['objective'],r['replication']):r for r in records if r['implementation']=='humano_random'};comparisons=[]
    for goal in GOALS:
        for name in SPECIFIC:
            cases=[r for r in records if r['objective']==goal and r['implementation']==name]
            if not cases:continue
            differences=[r['success']-controls[goal,r['replication']]['success'] for r in cases];bootrng=draw('paired-bootstrap',goal,name)
            bootstrap=sorted(sum(bootrng.choice(differences) for _ in differences)/len(differences) for _ in range(5000))
            comparisons.append({'implementation':name,'objective':goal,'games':len(cases),'specific_successes':sum(r['success'] for r in cases),'random_control_successes':sum(controls[goal,r['replication']]['success'] for r in cases),'paired_mean_difference':sum(differences)/len(differences),'better':differences.count(1),'equal':differences.count(0),'worse':differences.count(-1),'paired_bootstrap_95':[bootstrap[125],bootstrap[4874]],'mean_rounds':sum(r['rounds'] for r in cases)/len(cases),'elections':sum(r['events'].get('controller_elected',0) for r in cases)})
    report={'games':len(records),'replications_per_comparison':repetitions,'comparisons':comparisons,'control':'Only focal implementation changes; initial world, focal objective, profiles, nature, owners, engine RNG seed and seeds per participant are paired. Different behavior can consume random streams in different orders.','uncertainty':'Exploratory paired bootstrap over game worlds; not independent-answer binomial inference or proof of optimal strategy.','filter_rule':'No deletion by victory/defeat. Validate context, anonymity, completeness, token budget; select by evidence type and temporal coverage; preserve a benchmark before fitting.','used_for_training':False,'model_executed':False,'individual_external_survival_evaluated':False,'excluded_incompatible_goal':{'humano_alpha':'RETORNO_COM_SOBREVIVENCIA: implementação declara objetivo de missão.'}}
    sources=output/'fontes';sources.mkdir()
    for name in ('agentes_experimentais.py','comparar_contra_aleatorios.py'):shutil.copy2(Path(__file__).with_name(name),sources/name)
    report['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sources.glob('*.py')}
    (output/'comparacao.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(canonical({'complete':True,'games':len(records)}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--repetitions',type=int,default=20);a=p.parse_args();run(a.output,a.repetitions)
