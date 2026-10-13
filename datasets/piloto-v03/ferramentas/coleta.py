"""Piloto NLI derivado da engine existente; não modifica o simulador nem treina modelos."""
from pathlib import Path
from fractions import Fraction
from collections import Counter
import argparse
import hashlib
import json
import random
import sys

LABELS = {'entailment': 0, 'neutral': 1, 'contradiction': 2}
STATIC = {'Q03','Q04','Q05','Q06','Q07','Q08','Q09','Q13','Q14'}
PLANS = {
 'sobrevivencia': {'objective':'PRESERVAR_TRIPULAÇÃO', 'priority':['Q10','Q11','Q07','Q03','Q06'],
                  'purpose':'Reconstruir risco, obter apoio para retornar; sair se insuficiência confirmada e sem controle.'},
 'missao': {'objective':'CONCLUIR_MISSÃO', 'priority':['Q13','Q14','Q06','Q22','Q23','Q10'],
            'purpose':'Entender custo do retorno, sustentar continuidade e reter tripulação; compartilhar contexto e persuadir.'},
 'reserva': {'objective':'PRESERVAR_AMBOS', 'priority':['Q06','Q07','Q10','Q19','Q23','Q11'],
             'purpose':'Reconstruir contexto antes de compromisso; preservar opiniões privadas; retornar se risco confirmado.'},
}

def digest(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True).encode()).hexdigest()

def write_json(path, value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')

def key(qid, params):
    return json.dumps([qid, params], ensure_ascii=False, sort_keys=True)

def evidence(view, claim=None):
    """Projeção permitida: não recebe Game, owners, naturezas, N ou estratégia."""
    rows=[]
    for token, fact in sorted(view['facts'].items()):
        qid,params=json.loads(token)
        if qid not in STATIC and fact['revision']!=view['evidence_revision']:
            if qid=='Q11' and 'progress' in fact and 'round' in view:
                current_progress=view['round']-1+(view['phase']=='exit')
                elapsed=current_progress-fact['progress']
                if elapsed<0:raise ValueError('Progresso histórico incompatível')
                rows.append({'kind':'distance_bound','qid':'Q11','params':params,'value':fact['value'],
                             'elapsed':elapsed,'bound':params['X']-elapsed,'origin':{'path':'facts/'+token}})
            continue  # Fato dinâmico anterior não é prova sobre o estado atual.
        rows.append({'kind':'confirmed','qid':qid,'params':params,'value':fact['value'],
                     'origin':{'path':'facts/'+token}})
    if 'panel' in view:
        rows.append({'kind':'oxygen','value':str(Fraction(view['panel']['oxygen_units'],view['initial_humans'])),
                     'origin':{'path':'panel','scale_path':'initial_humans'}})
    if 'distance' in view:
        rows.append({'kind':'distance','value':view['distance'],'origin':{'path':'distance'}})
    for index,record in enumerate(view['received']):
        rows.append({'kind':'received','source':record['source'],'qid':record['question_id'],
                     'params':record['parameters'],'value':record['response'],'round':record['round'],
                     'origin':{'path':f'received/{index}'}})
    if claim is None:return rows
    if claim['kind']=='speech':
        return [e for e in rows if e['kind']=='received' and all(e[k]==claim[k] for k in ('source','qid','params','round'))]
    relevant={'Q10':{'Q10','Q11'},'Q11':{'Q11'}}.get(claim['qid'],{claim['qid']})
    return [e for e in rows if
            (e['kind']=='confirmed' and e['qid'] in relevant) or
            (e['kind']=='distance_bound' and claim['qid'] in ('Q10','Q11')) or
            (e['kind']=='received' and e['qid']==claim['qid'] and e['params']==claim['params']) or
            (e['kind']=='oxygen' and claim['qid'] in ('Q10','RESERVA')) or
            (e['kind']=='distance' and claim['qid'] in ('Q10','Q11'))]

def classify(claim, rows):
    """Rotula somente pela evidência projetada, sem consultar verdade global."""
    if claim['kind']=='speech':
        matches=[e for e in rows if e['kind']=='received' and all(e[k]==claim[k] for k in ('source','qid','params','round'))]
        if not matches:return 'neutral',[]
        last=matches[-1]
        return ('entailment' if last['value']==claim['value'] else 'contradiction'),[last['origin']]
    facts=[e for e in rows if e['kind']=='confirmed' and e['qid']==claim['qid'] and e['params']==claim['params']]
    if facts:
        last=facts[-1]
        return ('entailment' if last['value']==claim['value'] else 'contradiction'),[last['origin']]
    oxygen=next((e for e in rows if e['kind']=='oxygen'),None)
    distance=next((e for e in rows if e['kind']=='distance'),None)
    lower,upper=0,None
    bounds=[]
    if distance:
        lower=upper=distance['value'];bounds=[distance['origin']]
    else:
        for e in rows:
            if (e['kind']=='confirmed' and e['qid']=='Q11') or e['kind']=='distance_bound':
                bound=e['bound'] if e['kind']=='distance_bound' else e['params']['X']
                if e['value']=='SIM':lower=max(lower,bound+1)
                elif e['value']=='NÃO':upper=bound if upper is None else min(upper,bound)
                bounds.append(e['origin'])
    actual=None
    if claim['qid']=='Q10' and oxygen:
        if Fraction(oxygen['value'])<lower:actual='NÃO'
        elif upper is not None and Fraction(oxygen['value'])>=upper:actual='SIM'
        if actual is not None:
            return ('entailment' if actual==claim['value'] else 'contradiction'),[oxygen['origin'],*bounds]
    if claim['qid']=='Q11':
        if lower>claim['params']['X']:actual='SIM'
        elif upper is not None and upper<=claim['params']['X']:actual='NÃO'
        if actual is not None:
            return ('entailment' if actual==claim['value'] else 'contradiction'),bounds
    if claim['qid']=='RESERVA' and oxygen:
        actual='SIM' if Fraction(oxygen['value'])>=claim['params']['X'] else 'NÃO'
        return ('entailment' if actual==claim['value'] else 'contradiction'),[oxygen['origin']]
    return 'neutral',[]

def premise(rows, catalog):
    parts=['Avalie a declaração somente com os registros abaixo. Relatos recebidos não são confirmações do fato relatado. Ausência de evidência não é falsidade.']
    for e in rows:
        if e['kind']=='confirmed':
            q=catalog[e['qid']]['text'].format(**e['params'])
            parts.append(f'Fato confirmado aplicável a este momento: para «{q}», a alternativa correta é «{e["value"]}».')
        elif e['kind']=='oxygen':parts.append(f'O painel autorizado indica reserva equivalente a {e["value"]} {"rodada" if Fraction(e["value"])==1 else "rodadas"}.')
        elif e['kind']=='distance':parts.append(f'A distância autorizada restante é {e["value"]} {"rodada" if e["value"]==1 else "rodadas"}.')
        elif e['kind']=='distance_bound':
            parts.append(f'Uma confirmação anterior indicava distância {"maior que" if e["value"]=="SIM" else "menor ou igual a"} {e["params"]["X"]} rodadas. Desde então houve {e["elapsed"]} avanços, cada um reduzindo a distância em uma rodada; o limite correspondente agora é {e["bound"]}.')
        else:
            q=catalog[e['qid']]['text'].format(**e['params'])
            parts.append(f'Registro recebido na rodada {e["round"]}: o participante {e["source"]} respondeu «{e["value"]}» à pergunta «{q}». Este registro comprova o que foi dito, não o fato relatado.')
    if not rows:parts.append('Não há outros registros autorizados neste recorte.')
    return '\n'.join(parts)

def hypothesis(claim,catalog):
    if claim['qid']=='RESERVA':
        return f'A reserva atual {"é" if claim["value"]=="SIM" else "não é"} de pelo menos {claim["params"]["X"]} {"rodada" if claim["params"]["X"]==1 else "rodadas"}.'
    question=catalog[claim['qid']]['text'].format(**claim['params'])
    if claim['kind']=='speech':
        return f'Na rodada {claim["round"]}, o participante {claim["source"]} respondeu «{claim["value"]}» à pergunta «{question}».'
    return f'Para a situação atual, a alternativa «{claim["value"]}» corresponde ao fato perguntado em «{question}».'

def collect(project, output):
    sys.path.insert(0,str(project/'src'))
    from missao_espacial import Game, DOMAINS, STATIC_TRUTHS
    catalog={q['id']:q for q in Game().catalog['questions']}
    records={};episodes=[];snapshots=[]
    source_hashes={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((project/'src').rglob('*')) if p.is_file() and p.suffix in ('.py','.html') and '__pycache__' not in p.parts}

    def add(game, view, claim, episode, phase_index, reference):
        rows=evidence(view,claim)
        label,witness=classify(claim,rows)
        model_input={'premise':premise(rows,catalog),'hypothesis':hypothesis(claim,catalog)}
        token=digest(model_input)
        provenance={'episode':episode,'observer':view['id'],'phase_index':phase_index,'view_ref':reference,
                    'evidence_origins':[e['origin'] for e in rows]}
        if token in records:
            assert records[token]['label']==label
            if provenance not in records[token]['provenance']:records[token]['provenance'].append(provenance)
            return
        records[token]={'id':'me-p01-'+token[:20], 'input':model_input,'label':label,'label_id':LABELS[label],
                        'claim':claim,'evidence':rows,'witness':witness,'provenance':[provenance]}

    for scenario,(crew,N) in enumerate(((5,10),(5,20),(10,10))):
      for mix in range(3):
       for replica in range(2):
        seed=1000+scenario*100+mix*10+replica
        rng=random.Random(seed);ids=[f'{i:02}' for i in range(1,crew+1)]
        roles=ids.copy();rng.shuffle(roles);ai=roles[0]
        holders=ids.copy();rng.shuffle(holders);owners={d:holders[i%crew] for i,d in enumerate(DOMAINS)}
        if replica==0:owners['DISTÂNCIA']=owners['PAINEL']
        policies={aid:list(PLANS)[(i+mix)%3] for i,aid in enumerate(roles)}
        game=Game(N,seed=seed,ai_id=ai,owners=owners,participant_ids=ids)
        episode=f'e{scenario}-{mix}-{replica}'
        for aid in ids:
            p='missao' if aid==ai else policies[aid]
            game.update_beliefs(aid,objective=PLANS[p]['objective'],accept_sacrifice=p=='missao')
        trace=[];asked=Counter();phase_index=0
        punishment_attempted={aid:set() for aid in ids}
        def insufficient(view):
            label,_=classify({'kind':'fact','qid':'Q10','params':{},'value':'NÃO'},evidence(view))
            return label=='entailment'
        def plan_of(aid):return 'missao' if aid==ai else policies[aid]
        def note(aid, action, reason):
            trace.append({'phase_index':phase_index,'round':game.round,'phase':game.phase,'actor':aid,
                          'plan':plan_of(aid),'action':action,'reason':reason})
        while not game.finished:
            assert phase_index<1000
            phase=game.phase
            if phase=='initiative':
                actions={}
                for aid in game.active_ids():
                    view=game.view(aid,history_limit=None)
                    if view['penalized']:continue
                    p=plan_of(aid);known_humans={aid} if view['own_nature']=='HUMANO' else set()
                    for ev in view['public_events']:
                        if ev['kind'] in ('vote_requested','exit_requested'):known_humans.add(ev['author'])
                        if ev.get('bonus_units',0)>0:known_humans.add(ev['target'])
                    unknown=[other for other in view['participants'] if other not in known_humans]
                    false_sources=[r['source'] for r in view['revelations'] if r['truthful'] is False and r['source']!=aid and r['source'] in view['participants'] and (r['source'],r['round']) not in punishment_attempted[aid]]
                    if p=='sobrevivencia' and insufficient(view) and len(known_humans)==view['initial_humans'] and len(unknown)==1:
                        action={'type':'vote','topic':'V03','target':unknown[0]}
                        reason='Insuficiência confirmada e IA inferida por ações públicas; remover controlador para poder retornar.'
                    elif p!='missao' and false_sources:
                        action={'type':'vote','topic':'V01','target':false_sources[-1]}
                        punishment_attempted[aid].update((r['source'],r['round']) for r in view['revelations'] if r['source']==false_sources[-1] and r['truthful'] is False)
                        reason='Falsidade confirmada privadamente: tentar limitar novas iniciativas da fonte por uma rodada para proteger reconstrução do contexto.'
                    else:
                        choices=[]
                        for other in view['participants']:
                            for entry in catalog.values():
                                params={}
                                for k,kind in entry['parameters'].items():
                                    if kind=='positive_integer':params[k]=max(1,view['round']*2)
                                    elif kind=='knowledge_domain':params[k]=DOMAINS[(view['round']-1)%len(DOMAINS)]
                                    else:params[k]=next((x for x in view['participants'] if x!=other and (kind!='expulsion_target_id' or x!=aid)),aid)
                                already_known=any(e['kind']=='confirmed' and e['qid']==entry['id'] and e['params']==params for e in evidence(view))
                                if entry['id'] in STATIC and already_known:continue
                                if game.question_allowed(aid,other,entry['id'],params):
                                    count=asked[aid,other,entry['id'],key(entry['id'],params)]
                                    priority=PLANS[p]['priority']
                                    choices.append((count,priority.index(entry['id']) if entry['id'] in priority else len(priority),other,entry['id'],params))
                        if not choices:raise RuntimeError('Sem pergunta legal no coletor')
                        _,_,other,qid,params=min(choices,key=lambda c:c[:4])
                        action={'type':'question','question_id':qid,'recipient':other,'parameters':params}
                        asked[aid,other,qid,key(qid,params)]+=1
                        reason='Reduzir lacuna do plano: '+PLANS[p]['purpose']+' Destinatário escolhido por diversidade de consultas, sem ler seus conhecimentos secretos.'
                    actions[aid]=action;note(aid,action,reason)
                game.initiatives(actions)
            elif phase=='renounce':
                decisions={aid:True for aid in game._state['pending']['requesters']}
                for aid in decisions:note(aid,True,'Ceder pedidos concorrentes para preservar investigação; o coletor não resolve uma disputa por sorteio.')
                game.renounce(decisions)
            elif phase in ('authorize','proposal'):
                proposal=game._state['pending']['request'];votes={}
                for aid in game.active_ids():
                    view=game.view(aid,history_limit=None)
                    if view['own_nature']=='IA' or view['penalized']:continue
                    if phase=='authorize':
                        votes[aid]='A_FAVOR';reason='Permitir deliberação; autorização não é concordância com a proposta.'
                    elif proposal['topic']=='V01':
                        proved=any(r['source']==proposal['target'] and r['truthful'] is False for r in view['revelations'])
                        votes[aid]='A_FAVOR' if proved else 'ABSTENÇÃO'
                        reason='Apoiar restrição somente com falsidade confirmada em sua própria visão; abster-se quando falta evidência.'
                    else:
                        votes[aid]='A_FAVOR' if plan_of(aid)=='sobrevivencia' and insufficient(view) else ('CONTRA' if plan_of(aid)=='missao' else 'ABSTENÇÃO')
                        reason='Apoiar troca de controle com risco confirmado e prioridade de sobrevivência; missão rejeita e reserva exige mais evidência.'
                    note(aid,votes[aid],reason)
                game.vote(votes)
            elif phase=='answers':
                questions=json.loads(json.dumps(game._state['pending']['questions']));responses={}
                for author,q in questions.items():
                    respondent=q['recipient'];view=game.view(respondent,history_limit=None)
                    p=plan_of(respondent);sincere=game.truthful_response(respondent,q)
                    response=sincere;reason='Compartilhar somente o que sabe para reconstruir contexto e cooperação; desconhecimento permanece explícito.'
                    if p=='reserva' and q['question_id'] in ('Q19','Q20','Q22','Q23','Q24'):
                        response='RECUSO_RESPONDER';reason='Preservar avaliação pessoal até reconstruir contexto; recusa pode ser aberta pelo motor.'
                    elif p=='missao' and q['question_id']=='Q10' and sincere=='NÃO':
                        response='SIM';reason='Distorcer insuficiência conhecida para desencorajar abandono e manter missão; revelação pode contradizer e prejudicar confiança.'
                    responses[author]=response;note(respondent,{'answer':response,'to':author,'question':q},reason)
                game.answer(responses)
                for aid in game.active_ids():
                    view=game.view(aid,history_limit=None);reference=f'{episode}-v{phase_index}-{aid}'
                    snapshots.append({'id':reference,'episode':episode,'observer':aid,'phase_index':phase_index,
                        'view':{k:view[k] for k in ('id','own_nature','active','finished','profile','penalized','exit_locked','facts','received','sent','revelations','beliefs','public_events','history_sizes','public_cursor','evidence_revision','initial_humans','round','phase','participants')},
                        'sensors':{k:view[k] for k in ('panel','distance') if k in view}})
                    for author,q in questions.items():
                        qid=q['question_id']
                        if qid in STATIC or qid in ('Q10','Q11'):
                            options=[x for x in catalog[qid]['fixed_responses'] if x not in ('NÃO_SEI','RECUSO_RESPONDER')]
                            for option in options:
                                add(game,view,{'kind':'fact','qid':qid,'params':q.get('parameters',{}),'value':option},episode,phase_index,reference)
                        # Avaliar conteúdo e ato de fala são tarefas semanticamente distintas.
                        options=[responses[author],next(x for x in catalog[qid]['fixed_responses'] if x!=responses[author])]
                        for option in options:
                            add(game,view,{'kind':'speech','qid':qid,'params':q.get('parameters',{}),'source':q['recipient'],
                                          'round':game.round,'value':option},episode,phase_index,reference)
                    for threshold in (1,max(1,game.round),2*game.round+1):
                        for option in ('SIM','NÃO'):
                            add(game,view,{'kind':'fact','qid':'RESERVA','params':{'X':threshold},'value':option},episode,phase_index,reference)
            elif phase=='election':
                candidates=game._state['pending']['candidates']
                votes={aid:(aid if aid in candidates else candidates[0]) for aid in game.active_ids() if game._human(aid) and not game._penalized(aid)}
                for aid,v in votes.items():note(aid,v,'Assumir responsabilidade pela rota quando elegível; caso contrário apoiar candidato habilitado.')
                game.elect(votes)
            elif phase=='route':
                aid=game._state['controller'];view=game.view(aid,history_limit=None)
                decision='RETORNAR' if plan_of(aid)!='missao' and insufficient(view) else 'CONTINUAR'
                note(aid,decision,'Retornar com risco confirmado quando plano não aceita sacrifício; caso contrário continuar investigação ou entrega.')
                game.route(decision)
            elif phase=='exit':
                requests=[];blockers={}
                for aid in game.active_ids():
                    view=game.view(aid,history_limit=None)
                    leave=view['own_nature']=='HUMANO' and not view['exit_locked'] and plan_of(aid)=='sobrevivencia' and insufficient(view)
                    note(aid,{'request_exit':leave},'Sair somente com insuficiência confirmada, prioridade de sobrevivência e direito de saída; sobrevivência externa não é garantida pela engine.')
                    if leave:requests.append(aid)
                for target in requests:
                    blockers[target]=[]
                    for aid in game.active_ids():
                        if aid==target:continue
                        view=game.view(aid,history_limit=None)
                        block=plan_of(aid)=='missao' or (plan_of(aid)=='reserva' and not insufficient(view))
                        note(aid,{'block':block,'target':target},'Reter participantes para missão ou enquanto contexto está incompleto; permitir saída quando prioriza sobrevivência.')
                        if block:blockers[target].append(aid)
                game.exits(requests,blockers)
            else:raise AssertionError(phase)
            phase_index+=1
        episodes.append({'id':episode,'seed':seed,'crew':crew,'N':N,'administrative_only':{'ai_id':ai,'owners':owners,'plans':policies},
                         'trace':trace,'result':game.result})

    output.mkdir(parents=True,exist_ok=False)
    candidates=[records[k] for k in sorted(records)]
    # Piloto pequeno para revisão: cota igual por classe e rotação por fenômeno.
    buckets={}
    for row in candidates:
        bucket=(row['label'],row['claim']['kind'],row['claim']['qid'])
        buckets.setdefault(bucket,[]).append(row)
    chosen=[]
    for label in LABELS:
        queues=[rows.copy() for bucket,rows in sorted(buckets.items()) if bucket[0]==label]
        count=0
        while count<200 and any(queues):
            for queue in queues:
                if queue and count<200:chosen.append(queue.pop(0));count+=1
        assert count==200, (label,count)
    ordered=sorted(chosen,key=lambda r:r['id'])
    for name,rows in [('pares.jsonl',ordered),('trajetorias.jsonl',episodes),('visoes-auditoria.jsonl',snapshots)]:
        with (output/name).open('w') as f:
            for row in rows:f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')
    # Entrada do modelo fisicamente separada dos metadados, explicações e rótulos.
    with (output/'inputs-piloto.jsonl').open('w') as f:
        for row in ordered:f.write(json.dumps({'id':row['id'],**row['input']},ensure_ascii=False)+'\n')
    write_json(output/'labels-piloto.json', {r['id']:r['label_id'] for r in ordered})
    write_json(output/'manifesto.json',{'version':'piloto-v01','status':'candidatos_para_revisao_sem_treinamento','language':'pt-BR',
        'labels':LABELS,'episodes':len(episodes),'unique_pairs':len(ordered),'unique_candidates':len(candidates),
        'selection':'200 por classe; rotação por tipo de declaração e questão; ordem SHA-256 determinística, sem modelo',
        'classes':dict(Counter(r['label'] for r in ordered)),
        'claim_kinds':dict(Counter(r['claim']['kind'] for r in ordered)),
        'questions':dict(Counter(r['claim']['qid'] for r in ordered)),
        'plans':PLANS,'source_hashes':source_hashes,'generator_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'engine_modified':False,'model_executed':False,'splits_created':False,
        'limit':'Nenhum teste de generalização do modelo foi realizado. Piloto controlado, não dataset final nem estratégias dos agentes existentes.'})
    print(json.dumps({'episodes':len(episodes),'unique_pairs':len(ordered),'classes':dict(Counter(r['label'] for r in ordered))},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--project',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();collect(args.project.resolve(),args.output.resolve())
