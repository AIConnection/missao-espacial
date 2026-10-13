from pathlib import Path
from copy import deepcopy
from collections import Counter
import argparse,hashlib,json,sys,time
from planos import *

def write_json(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def write_lines(p,rows):
    with p.open('w') as stream:
        for r in rows:stream.write(canonical(r)+'\n')

def generate(project,output,trials=32,family_limit=12):
    if trials<2:raise ContractError('At least two independent trials per candidate')
    if not 6<=family_limit<=12 or family_limit%2:raise ContractError('Use 6, 8, 10 or 12 cases; keep both variants of each independent split family')
    sys.path.insert(0,str(project/'src'));from missao_espacial import Game
    output.mkdir(parents=True,exist_ok=False);write_json(output/'manifesto.json',{'status':'incomplete_build'});audit=output/'auditoria';audit.mkdir()
    specs=[]
    for size in (5,10):
        for knowledge in (['ACIDENTE'],['MISSÃO','CARGA'],['PAINEL','DISTÂNCIA']):
            for variant in (0,1):
                index=len(specs);specs.append({'family':f'family-{index:02}','ids':[f'{i:02}' for i in range(1,size+1)],'N':10,'engine_seed':1700+index,'own_domains':knowledge,'variant':variant})
    specs=specs[:family_limit];order=[f'partition-family-{i:02}' for i in range(len(specs)//2)];rng('partition-v04').shuffle(order)
    parent_split={k:('test' if i==0 else 'calibration' if i==1 else 'train') for i,k in enumerate(order)}
    parent={s['family']:f'partition-family-{i//2:02}' for i,s in enumerate(specs)}
    split={k:parent_split[p] for k,p in parent.items()}
    inputs=[];targets=[];routes=[];comparisons=[];groups=[];roots=[];accepted_worlds=0;outcome_counts=Counter();total_attempts=0;effect_pairs=0;started=time.time()
    with (audit/'mundos.jsonl').open('w') as worlds, (audit/'continuacoes.jsonl').open('w') as continuations:
        for family_index,spec in enumerate(specs):
            observer=spec['ids'][0]
            base,prefs=start_world(Game,spec['N'],spec['engine_seed'],spec['ids'],observer,spec['own_domains'],digest(['base',spec['family']]),spec['variant'])
            steps=[]
            for elapsed in (0,2,4):
                while base.round-1<elapsed:steps.extend(prefix_round(base,prefs,spec['variant']))
                original=base.dumps()
                for goal in GOALS:
                    root=Game.loads(original);root.update_beliefs(observer,objective=GOALS[goal]);expected=observed(root,observer)
                    target=spec['ids'][1+(family_index%(len(spec['ids'])-1))]
                    candidates=plans(target,goal);group=f'{spec["family"]}-p{elapsed}-{goal}'
                    semantic_keys=[];counts=[Counts() for p in candidates];root_rows=[]
                    refs_nonce=digest(['references-v04',group])
                    for plan_index,plan in enumerate(candidates):
                        inp,binding=build_input(root,observer,goal,plan,refs_nonce)
                        row=len(inputs);inputs.append(inp);binding.update(row_index=row,group=group,split=split[spec['family']],plan_index=plan_index)
                        routes.append(binding);root_rows.append(row)
                        # Chave canônica da entrada sem a permutação transitória para verificar separação.
                        canoninp,_=build_input(root,observer,goal,plan,'canonical-reference-frame')
                        semantic_keys.append(digest(canoninp))
                    roots.append({'group':group,'family':spec['family'],'split_family':parent[spec['family']],'split':split[spec['family']],'source_spec':spec,'prefix':deepcopy(steps),'checkpoint':json.loads(root.dumps()),'observer':observer,'goal':goal,'rows':root_rows,'canonical_inputs':semantic_keys})
                    for trial in range(trials):
                        world_seed=digest(['compatible-world-v04',group,trial]);world,pop,metadata=sample_world(Game,spec,steps,observer,goal,expected,world_seed)
                        checkpoint=world.dumps();world_id=f'{group}-w{trial:03}';world_hash=digest(json.loads(checkpoint));total_attempts+=metadata['attempts'];accepted_worlds+=1
                        worlds.write(canonical({'id':world_id,'group':group,'trial':trial,'checkpoint':json.loads(checkpoint),'checkpoint_hash':world_hash,'sampling':metadata})+'\n')
                        results=[];behavior_seed=digest(['continuation-v04',group,trial])
                        for plan_index,plan in enumerate(candidates):
                            rollout=continuation(Game,checkpoint,pop,behavior_seed,observer,goal,plan)
                            counts[plan_index].add(rollout['result']);outcome_counts[rollout['result']['reason']]+=1
                            continuations.write(canonical({'world':world_id,'checkpoint_hash':world_hash,'group':group,'trial':trial,'plan_index':plan_index,'row_index':root_rows[plan_index],'behavior_seed':behavior_seed,**rollout})+'\n')
                            results.append(rollout['target']['mission_success'])
                        if len(set(results))>1:effect_pairs+=1
                    for row,counter in zip(root_rows,counts):targets.append({'row_index':row,**counter.export()})
                    probability=[c.export()['probabilities']['entrega_no_planeta'] for c in counts]
                    comparisons.append({'group':group,'rows':root_rows,'delivery_probabilities':probability,'paired_trials':trials,'same_world_and_behavior_seed':True})
                    groups.append({'group':group,'family':spec['family'],'split_family':parent[spec['family']],'split':split[spec['family']],'rows':root_rows,'elapsed':elapsed,'goal':goal})
                assert base.dumps()==original,'Branches mutated the root world'
            print(canonical({'family_completed':family_index+1,'families':len(specs),'inputs':len(inputs),'rollouts':accepted_worlds*3,'elapsed_seconds':round(time.time()-started,1)}),flush=True)
    targets.sort(key=lambda r:r['row_index']);assert [t['row_index'] for t in targets]==list(range(len(inputs)))
    write_lines(output/'inputs.jsonl',inputs);write_lines(output/'supervisao.jsonl',targets);write_lines(audit/'roteamento.jsonl',routes);write_lines(audit/'raizes.jsonl',roots);write_lines(audit/'comparacoes.jsonl',comparisons)
    write_lines(output/'particoes.jsonl',[{'row_index':r['row_index'],'split':r['split'],'group':r['group']} for r in routes])
    source_hashes={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (project/'src').rglob('*.py') if '__pycache__' not in p.parts}
    write_json(output/'manifesto.json',{'version':'piloto-v04','status':'generated_not_trained','rows':len(inputs),'families':len(specs),'independent_split_families':len(order),'paired_groups':len(groups),'candidate_programs':3,'trials_per_candidate':trials,'compatible_worlds':accepted_worlds,'rollouts':accepted_worlds*3,'sampling_attempts':total_attempts,'outcomes':dict(outcome_counts),'paired_trials_with_different_outcomes':effect_pairs,'partitions':dict(Counter(r['split'] for r in routes)),
      'source_hashes':source_hashes,'model_executed':False,'thresholds_fitted':False,'universal_strategy_generalization_proven':False,'hidden_sampler':ASSUMPTIONS,'checkpoint_contains_secrets':'audit_only'})
    (output/'system-modelo.txt').write_text(SYSTEM+'\n')
    print(canonical({'complete':True,'rows':len(inputs),'rollouts':accepted_worlds*3,'paired_different_outcomes':effect_pairs}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--trials',type=int,default=32);p.add_argument('--families',type=int,default=12);a=p.parse_args();generate(a.project,a.output,a.trials,a.families)
