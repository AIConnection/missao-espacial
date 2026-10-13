"""Planos executáveis e continuações pareadas; nunca escolhe um plano ótimo."""
from copy import deepcopy
from pathlib import Path
from collections import Counter
import hashlib,json,math,random
from epistemico import from_view
from anonimo import render
from referencias import ReferenceFrame
from desfecho import label_outcome

GOALS={'ENTREGA_NO_PLANETA':'CONCLUIR_MISSÃO','RETORNO_COM_SOBREVIVENCIA':'PRESERVAR_TRIPULAÇÃO'}
ASSUMPTIONS={
 'states':'Reamostrar estados iniciais, respostas privadas entre terceiros e destinatários ocultos de revelação; fixar histórico público e mensagens conhecidas pelo observador; aceitar visão integral idêntica. Proposta filtrada por compatibilidade, sem ponderação Bayesiana pela verossimilhança das respostas conhecidas.',
 'N_prior':[8,10,12], 'unknown_ai':'uniform among other participants',
 'unknown_owners':'uniform among participants excluding observer for domains the observer does not initially own',
 'human_preferences':{'return':0.4,'delivery':0.4,'decide_after_evidence':0.2},
 'answer_correct_from_own_knowledge_probability':0.75,
 'random_expulsion_request_probability':0.12,
 'unknown_target_vote_for_probability':0.35,
 'renounce_probability':0.35,'unknown_intention_route_return_probability':0.5,
 'unknown_past_answers':'same 0.75 sincerity mechanism using sender knowledge; known sent/received responses are fixed as observed',
 'unknown_past_revelation_recipients':'condition only on whether observer received a revelation; otherwise uniform among other question authors',
 'future_engine_chance':'independent RNG state sampled at forecast cutoff; past observations preserved',
 'seed_pairing':'same accepted world, resampled future-engine RNG and keyed behavior draws for all candidate plans within each trial'}
SYSTEM='''Avalie consequências do plano candidato sob as hipóteses de amostragem fornecidas. A direção final PLANETA determina carga entregue e entrega observável. A direção final ESTAÇÃO ESPACIAL determina retorno e sobrevivência humana. Os dois desfechos de direção são exclusivos e exaustivos para partidas encerradas. Fatos, relatos, posições declaradas e suposições têm estatutos distintos. Não descubra identidades; referências pessoais são temporárias nesta chamada. Não selecione ações ou um plano. A saída probabilística é entrega_no_planeta e retorno_com_sobrevivencia, valores entre zero e um cuja soma é um. As três classes de evidência pertencem à tarefa epistemológica separada; não equivalem a estas probabilidades. Reserva e distância são medidas em rodadas; suficiência usa reserva >= distância. Cada avanço consome uma rodada de reserva e de distância. Com H humanos iniciais e reserva inicial N, remover um humano acrescenta N/H rodadas; remover a IA não acrescenta reserva. A IA mantém a missão e não solicita votação nem saída. Pedidos de expulsão exigem autorização e proposta aprovadas por maioria dos votos válidos; expulsar o controlador provoca eleição enquanto o jogo estiver ativo. O controlador humano que continua perde o direito de saída voluntária. Dois bloqueadores impedem saída, com oposição automática da IA. Retorno é permitido enquanto há oxigênio disponível e encerra o jogo com sobrevivência humana. A continuidade encerra em direção ao planeta e determina entrega observada mesmo quando o encerramento ocorre por esgotamento. Posições abertas referem-se ao instante da resposta; não confirmam uma intenção futura imutável.'''

class ContractError(ValueError):pass

def canonical(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(obj):return hashlib.sha256(canonical(obj).encode()).hexdigest()
def rng(*keys):return random.Random(digest(keys))
def observed(game,observer):return from_view(game.view(observer,history_limit=None))
def initial(game):return game.snapshot()['state']
def wilson(k,n):
    if not n:raise ContractError('NO_OBSERVED_OUTCOMES')
    z=1.959963984540054;p=k/n;den=1+z*z/n;c=(p+z*z/(2*n))/den
    d=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,c-d),min(1,c+d)]

def learned_goal(game,aid,preference,view=None):
    view=game.view(aid,history_limit=None) if view is None else view
    if preference=='decide_after_evidence' and not game.finished and view['active']:
        answer=game.truthful_response(aid,{'question_id':'Q10','parameters':{}})
        if answer in ('SIM','NÃO'):
            goal='CONCLUIR_MISSÃO' if answer=='SIM' else 'PRESERVAR_TRIPULAÇÃO'
            if view['beliefs']['objective']!=goal:
                game.update_beliefs(aid,objective=goal)
                return {'objective':goal}
    return {}

def start_world(Game,N,seed,ids,observer,own_domains,random_seed,variant):
    draw=rng(random_seed);others=[a for a in ids if a!=observer]
    ai=draw.choice(others);owners={d:observer if d in own_domains else draw.choice(others) for d in ('ACIDENTE','MISSÃO','CARGA','PAINEL','DISTÂNCIA','CRISE')}
    game=Game(N,seed=seed,participant_ids=ids,ai_id=ai,owners=owners)
    preferences={observer:'decide_after_evidence'}
    for aid in others:
        preference='delivery' if aid==ai else draw.choices(['return','delivery','decide_after_evidence'],weights=[.4,.4,.2])[0]
        preferences[aid]=preference
        game.update_beliefs(aid,objective={'return':'PRESERVAR_TRIPULAÇÃO','delivery':'CONCLUIR_MISSÃO','decide_after_evidence':'PRESERVAR_AMBOS'}[preference])
    # Suposição inicial explícita, não fato. Distingue contextos da matriz sem usar IDs como feature.
    key=json.dumps([ids[1],{'assunto':'MISSÃO'}],ensure_ascii=False,sort_keys=True)
    game.update_beliefs(observer,knowledge={key:bool(variant)})
    return game,preferences

def warm(game,preferences):
    for aid in game.active_ids():learned_goal(game,aid,preferences[aid])

def prefix_round(game,preferences,variant):
    warm(game,preferences)
    qid='Q10' if game.round==1 else ('Q11' if game.round==2 else 'Q23')
    params={'X':12 if variant else 18} if qid=='Q11' else {}
    ids=game.active_ids();actions={a:{'type':'question','question_id':qid,'recipient':ids[(i+1+variant)%len(ids)],'parameters':params} for i,a in enumerate(ids)}
    game.initiatives(actions);warm(game,preferences)
    pending=game.snapshot()['state']['pending']['questions']
    answers={a:game.truthful_response(q['recipient'],q) for a,q in pending.items()}
    game.answer(answers);game.route('CONTINUAR');game.exits([], {})
    return [{'method':'initiatives','arguments':actions},{'method':'answer','arguments':answers},
            {'method':'route','arguments':'CONTINUAR'},{'method':'exits','arguments':[[],{}]}]

def replay(game,preferences,steps):
    for s in steps:
        if s['method'] in ('initiatives','answer'):warm(game,preferences)
        if s['method']=='exits':game.exits(*deepcopy(s['arguments']))
        else:getattr(game,s['method'])(deepcopy(s['arguments']))

def replay_known_history(game,preferences,steps,observer,expected,seed):
    known={}
    try:
        for field in ('received','sent'):
            for r in expected[field]:known[(r['round'],r['source'],r['recipient'],r['qid'],canonical(r['params']))]=r['value']
    except (KeyError,TypeError):raise ContractError('INVALID_KNOWN_HISTORY') from None
    observed_revelation_rounds={r['round'] for r in expected['revelations']}
    sampled_unknown=[];sampled_recipients=[]
    for step_index,s in enumerate(steps):
        method=s['method']
        if method in ('initiatives','answer'):warm(game,preferences)
        if method=='answer':
            questions=game.snapshot()['state']['pending']['questions'];answers={}
            for author,q in questions.items():
                key=(game.round,q['recipient'],author,q['question_id'],canonical(q['parameters']))
                if key in known:answers[author]=known[key]
                else:
                    draw=rng(seed,step_index,author,'unknown-past-response')
                    if draw.random()<.75:answers[author]=game.truthful_response(q['recipient'],q)
                    else:answers[author]=draw.choice(game._entry(q['question_id'])['fixed_responses'])
                    sampled_unknown.append({'round':game.round,'author':author,'source':q['recipient'],'response':answers[author]})
            authors=list(questions)
            chosen=observer if game.round in observed_revelation_rounds else rng(seed,step_index,'unknown-past-reveal').choice([a for a in authors if a!=observer])
            # Condicionar somente o fato observado de receber/não receber abertura; não o destinatário secreto original.
            for selection_attempt in range(10000):
                draw=rng(seed,step_index,selection_attempt,'condition-reveal')
                state=draw.getstate()
                if draw.choice(authors)==chosen:
                    game._rng.setstate(state)
                    break
            else:raise ContractError('UNABLE_TO_CONDITION_REVELATION')
            sampled_recipients.append({'round':game.round,'author':chosen})
            game.answer(answers)
        elif method=='exits':game.exits(*deepcopy(s['arguments']))
        else:getattr(game,method)(deepcopy(s['arguments']))
    return {'unknown_past_answers':sampled_unknown,'past_revelation_recipients':sampled_recipients}

def sample_world(Game,spec,steps,observer,goal,expected,seed,max_attempts=4096):
    for attempt in range(max_attempts):
        choice=rng(seed,attempt);N=choice.choice(ASSUMPTIONS['N_prior'])
        game,prefs=start_world(Game,N,spec['engine_seed'],spec['ids'],observer,spec['own_domains'],digest([seed,attempt,'hidden']),spec['variant'])
        try:latent_history=replay_known_history(game,prefs,steps,observer,expected,digest([seed,attempt,'unknown-history']))
        except ValueError:continue  # Estado proposto não executa o histórico; não fabricar rótulo.
        if game.finished:continue
        game.update_beliefs(observer,objective=GOALS[goal])
        if observed(game,observer)==expected:
            snapshot=game.snapshot();snapshot['rng_state']=rng(seed,'future-engine-chance').getstate()
            game=load_checkpoint(Game,snapshot)
            assert observed(game,observer)==expected
            return game,prefs,{'attempts':attempt+1,'world_seed':seed,'N':N,'preferences':prefs,'future_rng_resampled':True,**latent_history}
    raise ContractError('NO_COMPATIBLE_WORLD')

PLAN_KEYS={'initiative','target','query_order','expulsion_condition','answer_rule','vote_rule','election_rule','route','exit_rule','block_rule'}
def plans(target,goal):
    common={'target':target,'query_order':['Q10','Q11','Q23','Q06'],'answer_rule':'truthful_using_own_knowledge',
            'vote_rule':'support_own_target_or_recently_confirmed_opposite_intention_else_abstain',
            'election_rule':'vote_for_self_if_eligible_else_abstain','route':'RETORNAR' if goal=='RETORNO_COM_SOBREVIVENCIA' else 'CONTINUAR',
            'block_rule':'block_recently_confirmed_same_intention'}
    return [dict(common,initiative='investigate_then_propose',expulsion_condition='only_recently_confirmed_opposite_intention',exit_rule='never'),
            dict(common,initiative='propose_then_investigate',expulsion_condition='target_active_and_not_recently_confirmed_same_intention',exit_rule='never'),
            dict(common,initiative='investigate',expulsion_condition='never',exit_rule='if_delivery_goal_and_confirmed_insufficient_oxygen')]

def validate_plan(plan,refs,goal):
    if set(plan)!=PLAN_KEYS:raise ContractError('PLAN_SCHEMA_MISMATCH')
    if plan['target'] not in refs:raise ContractError('UNKNOWN_PLAN_TARGET')
    if plan['initiative'] not in ('investigate_then_propose','propose_then_investigate','investigate'):raise ContractError('UNKNOWN_PLAN_OPCODE')
    if plan['route']!=('RETORNAR' if goal=='RETORNO_COM_SOBREVIVENCIA' else 'CONTINUAR'):raise ContractError('PLAN_GOAL_MISMATCH')
    if plan not in plans(plan['target'],goal):raise ContractError('UNSUPPORTED_PLAN_PROGRAM')

VIEW_KEYS={'id','own_nature','active','round','phase','finished','participants','initial_humans','profile','penalized','exit_locked','facts','received','sent','revelations','history_sizes','evidence_revision','beliefs','policy_state','public_events','public_cursor','panel','distance'}

def prepare_input(view,catalog,goal,plan,reference_nonce=None):
    if set(view)-VIEW_KEYS:raise ContractError('UNADAPTED_VIEW_FIELDS')
    if view.get('finished') or not view.get('active'):raise ContractError('NO_ACTIVE_PLANNING_CONTEXT')
    if view.get('phase')!='initiative':raise ContractError('UNSUPPORTED_FORECAST_PHASE')
    if view.get('own_nature')!='HUMANO':
        raise ContractError('UNSUPPORTED_FOCAL_CAPABILITIES')
    if view.get('policy_state'):
        raise ContractError('UNADAPTED_POLICY_MEMORY')
    if view.get('profile'):
        raise ContractError('PROFILE_NOT_COMPILED_IN_PLAN')
    observer=view['id']
    if goal not in GOALS:raise ContractError('UNKNOWN_GOAL')
    ctx=from_view(view)
    if ctx['beliefs']['objective']!=GOALS[goal]:raise ContractError('GOAL_NOT_DECLARED')
    frame=ReferenceFrame(ctx,nonce=reference_nonce)
    validate_plan(plan,frame.to_reference,goal)
    named=deepcopy(plan);named['target']=frame.ref(plan['target'])
    bind={'observer':observer,'source':None,'recipient':observer,'referent':None,**frame.routing()}
    rights={k:ctx['public_state'][k] for k in ('active','finished','penalized','exit_locked')}
    # Estado do próprio observador é necessário para entender a admissibilidade das ações.
    context=render(ctx,catalog,bind)+'\nESTADO ATUAL DO OBSERVADOR\n'+canonical(rights)
    inp={'context':context,'objective':goal,'candidate_plan':named,'forecast_target':'FINAL_DIRECTION_AT_GAME_TERMINAL','sampling_assumptions':ASSUMPTIONS}
    return inp,{'observer':observer,'references':frame.to_reference,'nonce':frame.nonce,'context':ctx,'raw_plan':plan}

def build_input(game,observer,goal,plan,reference_nonce=None):
    catalog={q['id']:q for q in game.catalog['questions']}
    return prepare_input(game.view(observer,history_limit=None),catalog,goal,plan,reference_nonce)

def recent_position(view,target):
    valid=[r for r in view['revelations'] if r['source']==target and r['question_id']=='Q23' and r['truth'] in GOALS.values() and view['round']-r['round']<=2]
    return valid[-1]['truth'] if valid else None

def question_action(game,view,target,qids):
    candidates=[target]+[a for a in view['participants'] if a not in (view['id'],target)]
    recent={(r['question_id'],r['source']) for r in view['received'] if view['round']-r['round']<=3}
    for respect_recency in (True,False):
        for recipient in candidates:
            for qid in qids:
                if respect_recency and (qid,recipient) in recent:continue
                parameters={'X':14} if qid=='Q11' else {}
                if game.question_allowed(view['id'],recipient,qid,parameters):return {'type':'question','question_id':qid,'recipient':recipient,'parameters':parameters}
    # Q11 admite repetição entre rodadas e qualquer inteiro positivo.
    for recipient in candidates:
        for x in (1,1000000):
            if game.question_allowed(view['id'],recipient,'Q11',{'X':x}):return {'type':'question','question_id':'Q11','recipient':recipient,'parameters':{'X':x}}
    return {'type':'idle'}

class Population:
    def __init__(self,game,preferences,seed,observer=None,goal=None,plan=None):
        self.game=game;self.preferences=preferences;self.seed=seed;self.observer=observer;self.goal=goal;self.plan=plan
        self.actor_order={a:i for i,a in enumerate(game.ids)};self.decisions=[]
    def policy(self,view,request):
        aid=view['id'];focal=aid==self.observer;g=self.game;kind=request['kind']
        changes={}
        if not focal:
            changes=learned_goal(g,aid,self.preferences[aid],view)
            if changes:view['beliefs'].update(changes)
        request_key=deepcopy(request)
        # Sorteios por participante/rodada/tipo; desvios de um plano não deslocam o RNG dos demais.
        def neutral(obj):
            if isinstance(obj,str):return f'actor-{self.actor_order[obj]}' if obj in self.actor_order else obj
            if isinstance(obj,list):return [neutral(x) for x in obj]
            if isinstance(obj,dict):return {k:neutral(v) for k,v in obj.items()}
            return obj
        draw=rng(self.seed,self.actor_order[aid],view['round'],kind,neutral(request_key))
        active=view['participants'];others=[a for a in active if a!=aid]
        objective=view['beliefs']['objective']
        if kind=='initiative':
            target=self.plan['target'] if focal else (draw.choice(others) if others else aid)
            known=recent_position(view,target);same=known==objective;opposite=known is not None and not same
            propose=False
            if focal:
                if self.plan['initiative']=='investigate_then_propose':propose=opposite
                elif self.plan['initiative']=='propose_then_investigate':propose=not same
            else:propose=opposite or draw.random()<.12
            action={'type':'vote','topic':'V03','target':target}
            if propose and g._request_allowed(aid,action):decision=action
            else:
                qids=self.plan['query_order'] if focal else (['Q23','Q10','Q11','Q06'] if draw.random()<.5 else ['Q10','Q11','Q23','Q06'])
                decision=question_action(g,view,target,qids)
        elif kind=='answer':
            if focal or draw.random()<.75:decision=g.truthful_response(aid,request)
            else:
                entry=g._entry(request['question_id']);options=[v for v in entry['fixed_responses'] if entry['id']!='Q19' or v in active or v in ('NÃO_SEI','RECUSO_RESPONDER')]
                decision=draw.choice(options)
        elif kind in ('authorize','proposal'):
            target=request['proposal']['target'];known=recent_position(view,target)
            if focal:decision='A_FAVOR' if target==self.plan['target'] or (known is not None and known!=objective) else 'ABSTENÇÃO'
            else:
                p=.85 if known is not None and known!=objective else (.05 if known==objective else .35)
                if target==aid:p=.10
                decision='A_FAVOR' if draw.random()<p else 'CONTRA'
        elif kind=='renounce':decision=False if focal else draw.random()<.35
        elif kind=='election':decision=aid if focal and aid in request['candidates'] else ('ABSTENÇÃO' if focal else draw.choice(request['candidates']))
        elif kind=='route':
            if view['own_nature']=='IA':decision='CONTINUAR'
            elif focal:decision=self.plan['route']
            elif objective=='PRESERVAR_TRIPULAÇÃO':decision='RETORNAR'
            elif objective=='CONCLUIR_MISSÃO':decision='CONTINUAR'
            else:decision='RETORNAR' if draw.random()<.5 else 'CONTINUAR'
        elif kind=='exit':
            enabled=(not focal or self.plan['exit_rule']=='if_delivery_goal_and_confirmed_insufficient_oxygen')
            decision=enabled and objective=='CONCLUIR_MISSÃO' and g.truthful_response(aid,{'question_id':'Q10','parameters':{}})=='NÃO'
        elif kind=='block':decision=recent_position(view,request['target'])==objective
        else:raise ContractError('UNKNOWN_ENGINE_REQUEST')
        self.decisions.append({'actor':aid,'request':request,'decision':decision,'belief_update':changes})
        return decision

def load_checkpoint(Game,payload):
    data=json.loads(payload) if isinstance(payload,str) else deepcopy(payload)
    # JSON de auditoria ordena chaves; a ordem nativa dos participantes é a do catálogo.
    ids=data['catalog']['response_sets']['I'];agents=data['state']['agents']
    if set(ids)!=set(agents):raise ContractError('INVALID_CHECKPOINT_PARTICIPANTS')
    data['state']['agents']={a:agents[a] for a in ids}
    return Game.loads(json.dumps(data,ensure_ascii=False))

def continuation(Game,checkpoint,preferences,seed,observer,goal,plan,max_phases=2000):
    game=load_checkpoint(Game,checkpoint);population=Population(game,preferences,seed,observer,goal,plan)
    policies={a:population.policy for a in game.ids};trace=[]
    for phase_index in range(max_phases):
        if game.finished:break
        before=len(population.decisions);phase=game.phase;round_number=game.round
        game.advance(policies,history_limit=None)
        trace.append({'phase':phase,'round':round_number,'decisions':population.decisions[before:]})
    if not game.finished:raise ContractError('CENSORED_CONTINUATION')
    target=label_outcome(game.result)
    return {'result':game.result,'target':target,'trace':trace,'engine_rng_at_root':digest(json.loads(checkpoint)['rng_state'])}

class Counts:
    def __init__(self):self.counts=Counter()
    def add(self,result):
        label=label_outcome(result);self.counts['PLANETA' if label['mission_success'] else 'ESTAÇÃO_ESPACIAL']+=1
    def export(self):
        n=sum(self.counts.values());k=self.counts['PLANETA']
        return {'trials':n,'counts':{'PLANETA':k,'ESTAÇÃO_ESPACIAL':n-k},'probabilities':{'entrega_no_planeta':k/n,'retorno_com_sobrevivencia':(n-k)/n},
                'wilson_95':{'entrega_no_planeta':wilson(k,n),'retorno_com_sobrevivencia':wilson(n-k,n)}}
