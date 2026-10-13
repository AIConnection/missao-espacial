"""Validação de supervisão, pareamento, privacidade, partições e replay da engine."""
from pathlib import Path
from collections import Counter,defaultdict
import argparse,hashlib,json,sys,gzip
from planos import *

def audit_stream(path):
    return path.open() if path.exists() else gzip.open(str(path)+'.gz','rt',encoding='utf-8')

def read(path):return [json.loads(x) for x in path.read_text().splitlines()]

def replay_trace(Game,checkpoint,trace):
    game=load_checkpoint(Game,checkpoint)
    for phase in trace:
        if game.finished:raise ContractError('TRACE_AFTER_TERMINAL')
        assert game.phase==phase['phase'] and game.round==phase['round']
        entries=iter(phase['decisions'])
        def recorded(view,request):
            try:item=next(entries)
            except StopIteration:raise ContractError('MISSING_DECISION') from None
            assert item['actor']==view['id'] and item['request']==request
            if item['belief_update']:game.update_beliefs(view['id'],**item['belief_update'])
            return deepcopy(item['decision'])
        game.advance({a:recorded for a in game.ids},history_limit=None)
        assert next(entries,None) is None
    assert game.finished
    return game.result

def verify(project,folder,replay_all=True):
    sys.path.insert(0,str(project/'src'));from missao_espacial import Game
    audit=folder/'auditoria';inputs=read(folder/'inputs.jsonl');supervision=read(folder/'supervisao.jsonl');routes=read(audit/'roteamento.jsonl');roots=read(audit/'raizes.jsonl');parts=read(folder/'particoes.jsonl')
    manifesto=json.loads((folder/'manifesto.json').read_text())
    for name,expected in manifesto['source_hashes'].items():assert hashlib.sha256((project/name).read_bytes()).hexdigest()==expected,name
    assert len(inputs)==len(supervision)==len(routes)==len(parts)==manifesto['rows']
    counts=defaultdict(Counter);worlds={};seen_pairings=defaultdict(set);semantic_splits=defaultdict(set)
    roots_by_group={r['group']:r for r in roots}
    for root in roots:
        for fingerprint in root['canonical_inputs']:semantic_splits[fingerprint].add(root['split'])
    assert all(len(splits)==1 for splits in semantic_splits.values()),'Equivalent canonical model input crosses partitions'
    family_splits=defaultdict(set)
    for part in parts:
        root=roots_by_group[part['group']];family_splits[root['split_family']].add(part['split']);assert part['split']==root['split']
    assert all(len(p)==1 for p in family_splits.values()) and set(p['split'] for p in parts)=={'train','calibration','test'}
    for row,(inp,label,route,part) in enumerate(zip(inputs,supervision,routes,parts)):
        assert set(inp)=={'context','objective','candidate_plan','forecast_target','sampling_assumptions'}
        assert label['row_index']==route['row_index']==part['row_index']==row
        root=roots_by_group[route['group']];game=load_checkpoint(Game,root['checkpoint'])
        expected,expected_route=build_input(game,route['observer'],root['goal'],route['raw_plan'],route['nonce'])
        assert inp==expected and route['context']==expected_route['context']
        refs=set(route['references'].values());assert inp['candidate_plan']['target'] in refs
        # IDs sentinela: renomear somente o vínculo/contexto da pessoa, sem tocar quantidades.
        ctx=deepcopy(route['context']);mapping={a:'PRIVATE_ID_'+str(i) for i,a in enumerate(route['references'])}
        def rename(obj):
            if isinstance(obj,list):return [rename(x) for x in obj]
            if not isinstance(obj,dict):return obj
            result={}
            for key,value in obj.items():
                if key in ('id','source','recipient','author','target','controller','agent','agente','alvo','trusted') and isinstance(value,str):result[key]=mapping.get(value,value)
                elif key in ('participants','candidates','blockers'):result[key]=[mapping.get(x,x) for x in value]
                elif key in ('votes','expulsion') and isinstance(value,dict):result[key]={mapping.get(k,k):mapping.get(v,v) if isinstance(v,str) else v for k,v in value.items()}
                elif key in ('value','revealed_value') and obj.get('qid')=='Q19':result[key]=mapping.get(value,value)
                else:result[key]=rename(value)
            return result
        changed=rename(ctx);changed['observer']['own_nature']='IA';changed['observer']['profile']={'never_exit':True}
        frame={'observer':mapping[route['observer']],'source':None,'recipient':mapping[route['observer']],'references':{mapping[a]:v for a,v in route['references'].items()}}
        oldframe={'observer':route['observer'],'source':None,'recipient':route['observer'],'references':route['references']}
        catalog={q['id']:q for q in game.catalog['questions']}
        assert render(changed,catalog,frame)==render(ctx,catalog,oldframe)
        assert 'PRIVATE_ID_' not in inp['context']
        assert label['trials']==manifesto['trials_per_candidate'] and sum(label['counts'].values())==label['trials']
        assert sum(label['probabilities'].values())==1
        for p in label['probabilities'].values():assert 0<=p<=1
    with audit_stream(audit/'mundos.jsonl') as stream:
        for line in stream:
            world=json.loads(line);assert world['id'] not in worlds
            game=load_checkpoint(Game,world['checkpoint']);root=roots_by_group[world['group']]
            assert digest(world['checkpoint'])==world['checkpoint_hash']
            expected=load_checkpoint(Game,root['checkpoint'])
            assert observed(game,root['observer'])==observed(expected,root['observer'])
            worlds[world['id']]=world
    future_states=defaultdict(set)
    for world in worlds.values():future_states[world['group']].add(digest(world['checkpoint']['rng_state']))
    assert all(len(states)==manifesto['trials_per_candidate'] for states in future_states.values()),'Future RNG states reused across independent trials'
    private_histories=defaultdict(set);hidden_recipients=defaultdict(set)
    for world in worlds.values():
        private_histories[world['group']].add(canonical(world['sampling']['unknown_past_answers']))
        unknown=[r for r in world['sampling']['past_revelation_recipients'] if r['author']!=roots_by_group[world['group']]['observer']]
        hidden_recipients[world['group']].add(canonical(unknown))
    for group,root in roots_by_group.items():
        if root['prefix']:assert len(private_histories[group])>1,'Unobserved third-party responses stayed fixed'
        ctx=observed(load_checkpoint(Game,root['checkpoint']),root['observer'])
        rounds=len(root['prefix'])//4
        if rounds>len(ctx['revelations']):assert len(hidden_recipients[group])>1,'Unobserved revelation recipients stayed fixed'
    replay_count=0
    with audit_stream(audit/'continuacoes.jsonl') as stream:
        for line in stream:
            run=json.loads(line);world=worlds[run['world']];assert run['checkpoint_hash']==world['checkpoint_hash']
            assert run['group']==world['group'] and run['trial']==world['trial']
            row=run['row_index'];assert routes[row]['group']==run['group'] and routes[row]['plan_index']==run['plan_index']
            assert run['target']==label_outcome(run['result'])
            counts[row]['PLANETA' if run['target']['mission_success'] else 'ESTAÇÃO_ESPACIAL']+=1
            key=(run['plan_index'],run['behavior_seed'],run['engine_rng_at_root'])
            assert key not in seen_pairings[run['world']]
            seen_pairings[run['world']].add(key)
            if replay_all:
                assert replay_trace(Game,world['checkpoint'],run['trace'])==run['result']
                replay_count+=1
    assert len(worlds)==manifesto['compatible_worlds']
    for entries in seen_pairings.values():
        assert len(entries)==3 and len({(seed,engine) for _,seed,engine in entries})==1
    for row,label in enumerate(supervision):
        assert dict(counts[row])=={k:v for k,v in label['counts'].items() if v},row
        assert label['probabilities']['entrega_no_planeta']==label['counts']['PLANETA']/label['trials']
    report={'rows_verified':len(inputs),'paired_worlds_verified':len(worlds),'rollouts_replayed':replay_count,'strict_authorized_view_compatibility':True,'reactions_and_belief_updates_replayed':True,'same_random_seeds_across_plans':True,'independent_future_engine_rng_between_trials':True,'third_party_private_past_resampled':True,'unknown_past_revelation_recipients_resampled':True,'input_identity_metamorphic_checks':len(inputs),'canonical_cross_partition_duplicates':0,'source_hashes_match':True,'train_calibration_test_families_separated':True,'model_executed':False,'thresholds_fitted':False}
    (folder/'validacao.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(canonical(report),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--folder',type=Path,required=True);a=p.parse_args();verify(a.project,a.folder)
