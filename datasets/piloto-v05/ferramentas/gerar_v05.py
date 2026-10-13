"""Massa v05: contrastes NLI, planos composicionais, regimes e testes congelados."""
from pathlib import Path
from copy import deepcopy
from collections import Counter,defaultdict
from concurrent.futures import ProcessPoolExecutor
import argparse,gzip,hashlib,json,os,re,sys,time,math
from planos_v2 import *
from populacoes_v2 import POPULATIONS,describe_population,rollout_implementations
sys.path.insert(0,str(ROOT/'datasets/piloto-v03/ferramentas'))
import gerar_cobertura as coverage
from gerar_piloto import fact,speech
from epistemico import classify,STATIC,LABELS,InvalidContext,PREFIX

class Union:
    def __init__(self):self.p={}
    def find(self,x):
        self.p.setdefault(x,x)
        if self.p[x]!=x:self.p[x]=self.find(self.p[x])
        return self.p[x]
    def join(self,a,b):
        a,b=self.find(a),self.find(b)
        if a!=b:self.p[max(a,b)]=min(a,b)

def normalize_input(value):
    mapping={}
    def replace(m):
        name=m.group(0)
        if name not in mapping:mapping[name]=f'person-{len(mapping)}'
        return mapping[name]
    return re.sub(r'participante temporário \d+',replace,canonical(value))

def context_key(ctx):
    frame=ReferenceFrame(ctx,nonce='semantic-key-v05');binding={'observer':ctx['observer']['id'],'source':None,'recipient':ctx['observer']['id'],'referent':None,**frame.routing()}
    catalog={q['id']:q for q in Game().catalog['questions']}
    return digest(normalize_input(render(ctx,catalog,binding)))

def write(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def lines(p,rows):
    with p.open('w') as f:
        for row in rows:f.write(canonical(row)+'\n')
def append_gz(f,x):f.write(canonical(x)+'\n')

def roots():
    specs=[];phases=('initiative','answers','renounce','authorize','proposal','election','route','exit')
    patterns=[[],['ACIDENTE'],['MISSÃO','CARGA'],['PAINEL'],['DISTÂNCIA'],['PAINEL','DISTÂNCIA'],['CRISE'],list(DOMAINS)]
    for round_number in range(1,7):
        for phase_index,wanted in enumerate(phases):
            i=len(specs);size=[3,5,8,10][(round_number+phase_index)%4];N=[8,12,20][(round_number+phase_index)%3]
            ids=[f'private-{i:03}-{a:02}' for a in range(size)]
            spec={'family':f'context-family-{i:03}','ids':ids,'N':N,'engine_seed':35000+i,'own_domains':patterns[(round_number+phase_index)%8],'variant':i%2,'construction':wanted,'round':round_number}
            g,prefs=legacy.start_world(Game,N,spec['engine_seed'],ids,ids[0],spec['own_domains'],digest(['root-v05',i]),spec['variant']);steps=[]
            def step(method,args):
                getattr(g,method)(*args) if method=='exits' else getattr(g,method)(args)
                steps.append({'method':method,'arguments':deepcopy(args)})
            def asks():return {a:question(g,g.view(a,history_limit=None),ids[(j+1)%size],'catalog_forward') for j,a in enumerate(ids)}
            def answers():step('answer',{a:g.truthful_response(q['recipient'],q) for a,q in g._state['pending']['questions'].items()})
            for k in range(round_number-1):
                step('initiatives',asks());answers();step('route','CONTINUAR');step('exits',[[],{}])
            if wanted in ('answers',):step('initiatives',asks())
            elif wanted in ('renounce','authorize','proposal','election','route','exit'):
                target=g._state['controller'];acts=asks();humans=[a for a in ids if g._human(a)]
                acts[ids[0]]={'type':'vote','topic':'V03','target':target}
                if wanted=='renounce':acts[next(a for a in humans if a!=ids[0])]={'type':'vote','topic':'V03','target':target}
                step('initiatives',acts)
                if wanted in ('proposal','election','route','exit'):step('vote',{a:'A_FAVOR' for a in humans})
                if wanted in ('election','route','exit'):step('vote',{a:'A_FAVOR' for a in humans})
                if wanted in ('route','exit'):step('elect',{a:ids[0] for a in g.active_ids() if g._human(a)})
                if wanted=='exit':step('route','CONTINUAR')
            assert not g.finished and g.phase==wanted and g.round==round_number,(i,wanted,g.phase,g.round)
            specs.append((spec,g,prefs,steps))
    return specs

def catalog_case(ids,qid,params,answer,index):
    r=1+(index%6);game=Game(2*r,seed=50000+index,participant_ids=ids,ai_id=ids[-1])
    def asks():return {a:question(game,game.view(a,history_limit=None),ids[(j+1)%len(ids)],'catalog_forward') for j,a in enumerate(ids)}
    def answers(override=False):
        pending=game._state['pending']['questions'];game.answer({a:answer if override and a==ids[0] else game.truthful_response(q['recipient'],q) for a,q in pending.items()})
    for k in range(r-1):
        preamble={a:{'type':'question','question_id':'Q11','recipient':ids[(j+1)%len(ids)],'parameters':{'X':1000100+k}} for j,a in enumerate(ids)}
        game.initiatives(preamble);answers();game.route('CONTINUAR');game.exits([],{})
    actions=asks();actions[ids[0]]={'type':'question','question_id':qid,'recipient':ids[1],'parameters':params};game.initiatives(actions);answers(True)
    desired=('route','exit','initiative','answers','renounce','authorize','proposal','election')[(index//6)%8]
    if desired!='route':game.route('CONTINUAR')
    if desired not in ('route','exit'):
        game.exits([],{})
        if desired!='initiative':
            acts=asks()
            if desired!='answers':
                acts[ids[0]]={'type':'vote','topic':'V03','target':ids[-1]}
                if desired=='renounce':acts[ids[1]]={'type':'vote','topic':'V03','target':ids[-1]}
            game.initiatives(acts)
            if desired in ('proposal','election'):game.vote({a:'A_FAVOR' for a in game.active_ids() if game._human(a)})
            if desired=='election':game.vote({a:'A_FAVOR' for a in game.active_ids() if game._human(a)})
    assert game.phase==desired,(index,desired,game.phase)
    return game,r

# Cada processo retorna apenas resultados compactos; checkpoints são guardados uma vez por mundo.
def run_batch(job):
    checkpoint,seed,observer,goal,plans,regime=job
    result=[]
    for p in plans:
        r=rollout_implementations(checkpoint,seed,observer,goal,p,regime)
        result.append({'result':r['result'],'target':r['target'],'phases':r['phases']})
    return result

def generate(output,trials=32,nli_per_class=2000,workers=4,nli_only=False,experiments_directory=None):
    output.mkdir(parents=True,exist_ok=False);audit=output/'auditoria';audit.mkdir();write(output/'manifesto.json',{'status':'building'})
    start=time.monotonic();legacy.ASSUMPTIONS['N_prior']=[4,8,12,20]
    planspec=make_plan_matrix();specs=roots();union=Union();seen_context={};pairs={};blocked=[];catalog_slots=[];contexts={}
    catalog={q['id']:q for q in Game().catalog['questions']}
    with gzip.open(ROOT/'treinamento/piloto-v01/pacote/dados/inputs.jsonl.gz','rt') as f:old_inputs=[json.loads(l) for l in f]
    old_meta=[json.loads(l) for l in (ROOT/'treinamento/piloto-v01/pacote/dados/supervisao.jsonl').read_text().splitlines()]
    frozen_nli={digest(normalize_input(old_inputs[i])) for i,r in enumerate(old_meta) if r['task']=='nli' and r['split']!='train'}
    cache={}
    def add(view,claim,family,kind,slot=None,origin_kind="controlled"):
        try:
            if cache.get('view') is not view:
                ctx=from_view(view);ckey=context_key(ctx);frame=legacy.ReferenceFrame(ctx,nonce=digest(['frame-v05',family,ckey]));cache.clear();cache.update(view=view,ctx=ctx,ckey=ckey,frame=frame,premises={})
            ctx=cache['ctx'];frame=cache['frame'];label,witness=classify(ctx,claim)
            b=__import__('anonimo').binding(ctx,claim);b.update(frame.routing())
            binding_key=canonical(b)
            if binding_key not in cache['premises']:cache['premises'][binding_key]=render(ctx,catalog,b)
            inp={'premise':cache['premises'][binding_key],'hypothesis':__import__('anonimo').assertion(catalog,ctx,claim,b)}
        except (InvalidContext,ValueError,KeyError) as e:
            blocked.append({'family':family,'kind':kind,'reason':str(e)});return
        for aid in view['public_events'][0]['participants']:
            assert aid not in canonical(inp),'Raw identity leaked'
        ckey=cache['ckey'];union.find(family)
        if ckey in seen_context:union.join(family,seen_context[ckey])
        else:seen_context[ckey]=family
        key=digest(normalize_input(inp))
        if key in frozen_nli:return
        if key in pairs:
            assert pairs[key]['target']==LABELS[label]
            union.join(family,pairs[key]['family']);return
        contexts[ckey]={'context':ctx,'view':view}
        pairs[key]={'input':inp,'target':LABELS[label],'family':family,'context_key':ckey,'kind':kind,'claim':claim,'witness':witness,'slot':slot,'origin_kind':origin_kind,'round':view['round'],'phase':view['phase']}
    # Novos episódios legais que cobrem todas as alternativas discretas de cada questão.
    probe_index=0
    for size in (3,5,8,12):
        ids=[f'probe-private-{size}-{i:02}' for i in range(size)]
        configured=Game(participant_ids=ids)
        for q in configured.catalog['questions']:
            for params in coverage.parameter_cases(q,ids):
                for j,answer in enumerate(q['fixed_responses']):
                    probe_index+=1;family=f'catalog-probe-{probe_index:05}'
                    game,record_round=catalog_case(ids,q['id'],params,answer,probe_index)
                    record={'source':ids[1],'recipient':ids[0],'qid':q['id'],'params':params,'round':record_round,'value':answer}
                    slot={'participants':size,'qid':q['id'],'params':params,'response':answer}
                    for actor,value in [(ids[0],answer),(ids[0],q['fixed_responses'][(j+1)%len(q['fixed_responses'])]),(ids[2],answer)]:
                        add(game.view(actor,history_limit=None),speech(record,value),family,'speech',slot)
                    catalog_slots.append(slot)
    print(canonical({'stage':'catalog_probes','episodes':probe_index,'pairs':len(pairs)}),flush=True)
    # Fronteiras executadas na engine: distância 14/15, reserva=distância,
    # e visões com apenas um sensor. Reutilizar grupos de sondas mantém isolamento.
    for probe in range(24):
        ids=[f'edge-private-{probe}-{i}' for i in range(3)];observer=ids[2]
        own=[['PAINEL','DISTÂNCIA'],['PAINEL'],['DISTÂNCIA'],[]][probe%4]
        owners={d:observer if d in own else ids[0] for d in DOMAINS}
        game=Game(8,seed=67000+probe,participant_ids=ids,ai_id=observer,owners=owners)
        rounds=1 if (probe//4)%2==0 else 2
        for step in range(rounds):
            acts={a:question(game,game.view(a,history_limit=None),ids[(j+1)%3],'catalog_forward') for j,a in enumerate(ids)}
            game.initiatives(acts)
            if game.phase=='answers':game.answer({a:game.truthful_response(q['recipient'],q) for a,q in game._state['pending']['questions'].items()})
            game.route('CONTINUAR');requests=ids[:2] if step==rounds-1 else []
            game.exits(requests,{a:[] for a in requests})
        view=game.view(observer,history_limit=None);family=f'catalog-probe-{probe+1:05}'
        for value in ('SIM','NÃO'):
            add(view,fact('Q10',value),family,'oxygen')
            for bound in (13,14,15):add(view,fact('Q11',value,{'X':bound}),family,'boundary')
    # Contextos novos em várias fases; caminhada executada com políticas variadas.
    for spec,base,prefs,steps in specs:
        game=legacy.load_checkpoint(Game,base.dumps());policy=Policy(game,digest(['nli-policy',spec['family']]),spec['ids'][0],'ENTREGA_NO_PLANETA',{'target':spec['ids'][1],'controls':planspec[int(spec['family'][-3:])%len(planspec)]['controls']},REGIMES[int(spec['family'][-3:])%3])
        observed_phases=set()
        for phase in range(80):
            if game.finished:break
            if game.phase not in observed_phases or game.round in (2,4):
                observed_phases.add(game.phase)
                for actor in [a for a in game.active_ids() if a in (spec['ids'][0],spec['ids'][1],spec['ids'][-1])]:
                    view=game.view(actor,history_limit=None)
                    if view['round']==1 and len(view['public_events'])==1:continue
                    for qid in STATIC:
                        for option in catalog[qid]['fixed_responses']:
                            if option not in ('NÃO_SEI','RECUSO_RESPONDER'):add(view,fact(qid,option),spec['family'],'fact')
                    for value in ('SIM','NÃO'):
                        add(view,fact('Q10',value),spec['family'],'oxygen')
                        distance=view.get('distance',14)
                        for bound in sorted({1,13,14,15,max(1,distance-1),max(1,distance),max(1,distance+1)}):
                            add(view,fact('Q11',value,{'X':bound}),spec['family'],'boundary')
                    ctx=from_view(view)
                    for collection in ('received','sent'):
                        for r in ctx[collection][-2:]:
                            values=[r['value']]+[v for v in catalog[r['qid']]['fixed_responses'] if v!=r['value']][:1]
                            for value in values:add(view,speech(r,value),spec['family'],'speech')
                    strangers=[p for p in game.ids if p!=actor]
                    if len(strangers)>=2:
                        for value in ('PRESERVAR_TRIPULAÇÃO','CONCLUIR_MISSÃO','PRESERVAR_AMBOS'):
                            record={'source':strangers[0],'recipient':strangers[1],'qid':'Q23','params':{},'round':view['round'],'value':value}
                            add(view,speech(record,value),spec['family'],'speech')
                    for value in ('PRESERVAR_TRIPULAÇÃO','CONCLUIR_MISSÃO','PRESERVAR_AMBOS'):
                        add(view,{'kind':'belief','field':'objective','value':value},spec['family'],'belief')
                        for person in [p for p in game.ids if p!=actor][:2]:
                            add(view,{'kind':'belief','field':'objective','subject':person,'round':view['round'],'value':value},spec['family'],'belief')
                        for opened in ctx['revelations'][-2:]:
                            if opened['qid']=='Q23':add(view,{'kind':'belief','field':'objective','subject':opened['source'],'round':opened['round'],'value':value},spec['family'],'belief')
            game.advance({a:policy for a in game.ids},history_limit=None)
    if experiments_directory is not None:
        sampled=Counter()
        with gzip.open(experiments_directory/'observacoes.jsonl.gz','rt') as stream:
            for line in stream:
                observation=json.loads(line);view=observation['view']
                if view['round']==1 and len(view['public_events'])==1:continue
                key=(observation['family'],str(view['round']) if view['round']<=6 else '7-12' if view['round']<=12 else '13+',view['phase'])
                if sampled[key]>=2:continue
                sampled[key]+=1;family=observation['family'];ctx=from_view(view)
                for qid in STATIC:
                    for option in catalog[qid]['fixed_responses']:
                        if option not in ('NÃO_SEI','RECUSO_RESPONDER'):add(view,fact(qid,option),family,'fact',origin_kind='experiment')
                for value in ('SIM','NÃO'):
                    add(view,fact('Q10',value),family,'oxygen',origin_kind='experiment')
                    for bound in (1,13,14,15):add(view,fact('Q11',value,{'X':bound}),family,'boundary',origin_kind='experiment')
                for collection in ('received','sent'):
                    for record in ctx[collection][-2:]:
                        for value in [record['value']]+[v for v in catalog[record['qid']]['fixed_responses'] if v!=record['value']][:1]:add(view,speech(record,value),family,'speech',origin_kind='experiment')
                strangers=[p for p in view['public_events'][0]['participants'] if p!=view['id']]
                if len(strangers)>=2:
                    for value in ('PRESERVAR_TRIPULAÇÃO','CONCLUIR_MISSÃO','PRESERVAR_AMBOS'):
                        record={'source':strangers[0],'recipient':strangers[1],'qid':'Q23','params':{},'round':view['round'],'value':value}
                        add(view,speech(record,value),family,'speech',origin_kind='experiment')
                for value in ('PRESERVAR_TRIPULAÇÃO','CONCLUIR_MISSÃO','PRESERVAR_AMBOS'):
                    add(view,{'kind':'belief','field':'objective','value':value},family,'belief',origin_kind='experiment')
                    for person in strangers[:2]:add(view,{'kind':'belief','field':'objective','subject':person,'round':view['round'],'value':value},family,'belief',origin_kind='experiment')
        print(canonical({'stage':'actual_implementations','observations':sum(sampled.values()),'pairs':len(pairs)}),flush=True)
    print(canonical({'stage':'nli_candidates','pairs':len(pairs),'blocked':len(blocked)}),flush=True)
    # Unir famílias que têm uma mesma observação, antes de escolher partições.
    for spec,base,prefs,steps in specs:
        ctx=from_view(base.view(spec['ids'][0],history_limit=None));ck=context_key(ctx);union.find(spec['family'])
        if ck in seen_context:union.join(spec['family'],seen_context[ck])
        else:seen_context[ck]=spec['family']
    components=sorted({union.find(x) for x in union.p});draw('splits-v05').shuffle(components)
    splitmap={c:'test' if i%20<3 else 'calibration' if i%20<6 else 'train' for i,c in enumerate(components)}
    def split(family):return splitmap[union.find(family)]
    buckets=defaultdict(list)
    for r in pairs.values():buckets[split(r['family']),r['target']].append(r)
    nli=[];allocation={}
    weights={'fact':.30,'speech':.30,'boundary':.25,'belief':.10,'oxygen':.05}
    def temporal(r):return (str(r['round']) if r['round']<=6 else '7-12' if r['round']<=12 else '13+',r['phase'])
    for part,ratio in [('train',.7),('calibration',.15),('test',.15)]:
        requested=int(nli_per_class*ratio);typed=defaultdict(list)
        for label in range(3):
            for r in buckets[part,label]:typed[label,r['kind'],temporal(r)].append(r)
        cells={kind:sorted({cell for label,k,cell in typed if k==kind}) for kind in weights}
        caps={(kind,cell):min(len(typed[label,kind,cell]) for label in range(3)) for kind in weights for cell in cells[kind]}
        kind_caps={kind:sum(caps[kind,cell] for cell in cells[kind]) for kind in weights}
        if sum(kind_caps.values())<requested:raise ValueError(f'Insufficient balanced temporal pool {part}: {kind_caps}')
        quotas={kind:0 for kind in weights}
        for _ in range(requested):
            eligible=[kind for kind in weights if quotas[kind]<kind_caps[kind]]
            kind=max(eligible,key=lambda k:(weights[k]*requested-quotas[k],k));quotas[kind]+=1
        cell_quotas={key:0 for key in caps}
        for kind,n in quotas.items():
            for _ in range(n):
                eligible=[cell for cell in cells[kind] if cell_quotas[kind,cell]<caps[kind,cell]]
                cell=min(eligible,key=lambda cell:(cell_quotas[kind,cell],cell));cell_quotas[kind,cell]+=1
        allocation[part]={'per_class':quotas,'capacity_per_class':kind_caps,'temporal_per_class':[{'kind':kind,'round_bucket':cell[0],'phase':cell[1],'count':n,'capacity':caps[kind,cell]} for (kind,cell),n in cell_quotas.items()]}
        for label in range(3):
            for (kind,cell),n in cell_quotas.items():
                pool=typed[label,kind,cell];draw('nli-choice-v05',part,label,kind,cell).shuffle(pool)
                # Misturar observações naturais e sondas; preservar a distribuição temporal.
                pool.sort(key=lambda r:r['origin_kind']!='experiment')
                for r in pool[:n]:nli.append({**r,'split':part,'group':union.find(r['family'])})
    draw('shuffle-nli-v05').shuffle(nli)
    lines(audit/'nli-rotulos.jsonl',nli);write(audit/'contexts.json',contexts);write(audit/'blocked.json',blocked);write(output/'balanceamento-nli.json',allocation)
    if nli_only:
        lines(output/'nli-inputs.jsonl',[r['input'] for r in nli]);lines(output/'nli-supervisao.jsonl',[{'task':'nli','index':i,'target':r['target'],'split':r['split'],'group':r['group'],'family':r['family'],'kind':r['kind'],'origin_kind':r['origin_kind'],'round':r['round'],'phase':r['phase']} for i,r in enumerate(nli)]);return
    forecast=[];meta=[];rollouts=0;worlds_count=0;changed=0
    with gzip.open(audit/'mundos.jsonl.gz','wt') as wf,gzip.open(audit/'resultados-continuacoes.jsonl.gz','wt') as rf,ProcessPoolExecutor(max_workers=workers) as pool:
        for root_index,(spec,base,prefs,steps) in enumerate(specs):
            observer=spec['ids'][0];part=split(spec['family']);available=[p for p in planspec if part=='test' or p['split']!='test' and (part=='calibration' or p['split']=='train')]
            candidates=available
            if part=='train':
                available=[candidates[(root_index*5+j)%len(candidates)] for j in range(6)]
            else:
                novel=[p for p in candidates if p['split']==part];seen=[p for p in candidates if p['split']=='train'];n=3 if part=='test' else 2
                available=[novel[(root_index+j)%len(novel)] for j in range(n)]+[seen[(root_index*5+j)%len(seen)] for j in range(6-n)]
            for goal in legacy.GOALS:
                root=legacy.load_checkpoint(Game,base.dumps());root.update_beliefs(observer,objective=legacy.GOALS[goal]);expected=legacy.observed(root,observer)
                targets=[a for a in root.active_ids() if a!=observer];target=targets[root_index%len(targets)]
                plans=[{'target':target,'controls':p['controls']} for p in available]
                rootkey=f'{spec["family"]}-{goal}'
                checkpoint=base.dumps()
                rootaudit={'key':rootkey,'family':spec['family'],'group':union.find(spec['family']),'split':part,'spec':spec,'prefix':steps,'checkpoint':json.loads(root.dumps()),'observer':observer,'goal':goal}
                append_gz(wf,{'kind':'root',**rootaudit})
                accepted=[]
                for t in range(trials):
                    seed=digest(['world-v05',rootkey,t]);world,pop,worldmeta=legacy.sample_world(Game,spec,steps,observer,goal,expected,seed)
                    accepted.append(world.dumps());worlds_count+=1
                    append_gz(wf,{'kind':'world','root':rootkey,'trial':t,'checkpoint':json.loads(world.dumps()),'sampling':worldmeta})
                for regime_base in POPULATIONS:
                    regime=deepcopy(regime_base)
                    if part=='test' and regime['name']=='mix2':regime['ai_weights']=[0.,1.]
                    start_rows=len(forecast)
                    for plan,p in zip(plans,available):
                        inp,binding=model_input(root,observer,goal,plan,{},digest(['aliases-v05',rootkey]))
                        inp['sampling_assumptions'].pop('future_behavior');inp['sampling_assumptions']['population_distribution']=describe_population(regime)
                        inp['sampling_assumptions']['future_behavior_scope']='Continuações hipotéticas com implementações distintas; as posições futuras podem mudar conforme a política. Não é previsão independente de hipóteses sobre terceiros.'
                        inp['sampling_assumptions']['pairing']=describe_population(regime)['seed_pairing']
                        for aid in spec['ids']:assert aid not in canonical(inp),'Identity in features'
                        forecast.append(inp);meta.append({'split':part,'group':union.find(spec['family']),'family':spec['family'],'plan_key':p['key'],'plan_partition':p['split'],'regime':regime['name'],'goal':goal,'root':rootkey,'binding':binding})
                    jobs=[(check,digest(['rollout-v05',rootkey,regime['name'],t]),observer,goal,plans,regime) for t,check in enumerate(accepted)]
                    counts=[legacy.Counts() for p in plans]
                    for t,results in enumerate(pool.map(run_batch,jobs,chunksize=1)):
                        if len({r['target']['mission_success'] for r in results})>1:changed+=1
                        for j,r in enumerate(results):
                            counts[j].add(r['result']);rollouts+=1
                            append_gz(rf,{'root':rootkey,'regime':regime['name'],'trial':t,'row_index':start_rows+j,'behavior_seed':jobs[t][1],'plan_key':available[j]['key'],**r})
                    for j,c in enumerate(counts):meta[start_rows+j]['supervision']=c.export();meta[start_rows+j]['target']=c.export()['probabilities']['entrega_no_planeta']
            print(canonical({'stage':'forecast','root':root_index+1,'roots':len(specs),'rows':len(forecast),'rollouts':rollouts,'seconds':round(time.monotonic()-start,1)}),flush=True)
    # Congelar referências v1 sem usá-las para ajuste, inclusive OOD original.
    reference=output/'comparacao-v01';reference.mkdir()
    reserved=[(i,x,r) for i,(x,r) in enumerate(zip(old_inputs,old_meta)) if r['split']=='test']
    lines(reference/'inputs.jsonl',[x for i,x,r in reserved]);lines(reference/'supervisao.jsonl',[dict(r,index=j,legacy_index=i) for j,(i,x,r) in enumerate(reserved)])
    for name in ('inputs.jsonl','supervisao.jsonl','protocolo.json'):
        (reference/('ood-'+name)).write_bytes((ROOT/'treinamento/piloto-v01/avaliacao-fora-dominio-01'/name).read_bytes())
    allinputs=[r['input'] for r in nli]+forecast
    allmeta=[{'task':'nli','target':r['target'],'split':r['split'],'group':r['group'],'family':r['family'],'kind':r['kind'],'origin_kind':r['origin_kind'],'round':r['round'],'phase':r['phase']} for r in nli]+[dict(r,task='forecast') for r in meta]
    for i,r in enumerate(allmeta):r['index']=i
    with gzip.open(output/'inputs.jsonl.gz','wt') as f:
        for r in allinputs:f.write(canonical(r)+'\n')
    # Binding e estado secreto são removidos da supervisão pública; continuam só em auditoria.
    lines(audit/'forecast-vinculos.jsonl',meta)
    publicmeta=[{k:v for k,v in r.items() if k!='binding'} for r in allmeta]
    lines(output/'supervisao.jsonl',publicmeta);write(output/'planos-matriz.json',planspec);write(output/'regimes.json',POPULATIONS)
    (output/'prefixo-nli.txt').write_text(PREFIX+'\n');(output/'system-forecast.txt').write_text(FORECAST_SYSTEM+'\n')
    write(output/'matriz-cobertura.json',{'catalog':catalog,'executed_question_response_probes':catalog_slots,'nli':dict(Counter(r['kind'] for r in nli)),'nli_phases':dict(Counter(contexts[r['context_key']]['context']['moment']['phase'] for r in nli)),'plan_axes':AXES,'pairwise_plan_training_coverage_complete':True,'unseen_plan_compositions':sum(p['split']=='test' for p in planspec),'forecast_root_phases':dict(Counter(g.phase for s,g,p,steps in specs)),'state_space_exhaustion':False})
    sourcehash={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'src').rglob('*.py') if '__pycache__' not in p.parts}
    write(output/'manifesto.json',{'version':'mass-v05-training-v02','status':'generated_not_validated','rows':len(allinputs),'nli_rows':len(nli),'forecast_rows':len(forecast),'nli_classes':dict(Counter(r['target'] for r in nli)),'split_task_counts':dict(Counter(r['task']+'-'+r['split'] for r in publicmeta)),'initial_contexts':len(specs),'context_components':len(components),'candidate_compositions':len(planspec),'regimes':len(POPULATIONS),'trials_per_example':trials,'compatible_worlds':worlds_count,'engine_rollouts':rollouts,'paired_trials_with_different_outcomes':changed,'source_sha256':sourcehash,'model_executed':False,'training_executed':False,'forecast_rollout_executor':'actual_implementations_protocol_v2','experimental_observations':str(experiments_directory) if experiments_directory else None,'universal_generalization_proven':False,'legacy_data_modified':False,'legacy_forecast_runtime_accepts_extended_plans':False,'split_method':'union of episode families and canonical observations before subsampling; novel compositions excluded from train and calibration','sampler_is_full_bayesian_posterior':False,'sampling_prior':legacy.ASSUMPTIONS})
    print(canonical({'complete_generation':True,'rows':len(allinputs),'seconds':round(time.monotonic()-start,1)}),flush=True)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);a.add_argument('--trials',type=int,default=32);a.add_argument('--nli-per-class',type=int,default=2000);a.add_argument('--workers',type=int,default=4);a.add_argument('--nli-only',action='store_true');a.add_argument('--experiments-directory',type=Path);args=a.parse_args();generate(args.output,args.trials,args.nli_per_class,args.workers,args.nli_only,args.experiments_directory)
