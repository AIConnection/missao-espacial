"""Linguagem composicional de planos e execução legal sobre a engine preservada."""
from pathlib import Path
from copy import deepcopy
from itertools import product,combinations
import json,hashlib,random,sys
import os
ROOT=Path(os.environ.get('MISSION_DATASET_PROJECT', str(Path(__file__).resolve().parents[3])))
# Reutilização de mecanismos auditados; nenhum arquivo anterior é modificado.
sys.path.insert(0,str(ROOT/'datasets/piloto-v04/ferramentas'))
sys.path.insert(0,str(ROOT/'src'))
import planos as legacy
from missao_espacial import Game,DOMAINS
from epistemico_v2 import from_view
from anonimo import render
from referencias import ReferenceFrame

def canonical(x):return json.dumps(x,ensure_ascii=False,sort_keys=True)
def digest(x):return hashlib.sha256(canonical(x).encode()).hexdigest()
def draw(seed,*keys):return random.Random(int(digest([seed,*keys])[:16],16))
AXES={
 'initiative':['ask','expel_if_opposed','expel_unless_same','penalize_if_opposed'],
 'answer':['truthful','unknown','refuse'],
 'vote':['approve','reject','opposed_only'],
 'election':['self','target','abstain'],
 'route':['CONTINUAR','RETORNAR'],
 'exit':['never','always_when_legal','confirmed_insufficient'],
 'block':['never','always','same_intention'],
 'questions':['evidence_first','intention_first','catalog_forward','catalog_reverse']}
MEANINGS={
 'initiative':{'ask':'Perguntar a primeira questão legal da ordem indicada; priorizar o destinatário temporário.',
   'expel_if_opposed':'Pedir expulsão se houver posição declarada oposta confirmada em revelação há no máximo duas rodadas; caso contrário perguntar.',
   'expel_unless_same':'Pedir expulsão salvo posição declarada igual confirmada em revelação há no máximo duas rodadas; caso contrário perguntar.',
   'penalize_if_opposed':'Pedir penalização se houver posição declarada oposta confirmada em revelação há no máximo duas rodadas; caso contrário perguntar.'},
 'answer':{'truthful':'Responder usando exclusivamente o conhecimento próprio autorizado pela engine; não saber não é confirmação.',
           'unknown':'Responder NÃO_SEI se essa alternativa for legal; caso contrário usar a resposta verdadeira autorizada.',
           'refuse':'Responder RECUSO_RESPONDER se essa alternativa for legal; caso contrário usar a resposta verdadeira autorizada.'},
 'vote':{'approve':'Votar A_FAVOR quando a engine permitir voto; abstenção obrigatória fica com a engine.',
         'reject':'Votar CONTRA quando a engine permitir voto.',
         'opposed_only':'Votar A_FAVOR somente se a pessoa proposta tiver posição oposta confirmada por revelação há no máximo duas rodadas; caso contrário ABSTENÇÃO.'},
 'election':{'self':'Votar no próprio observador se for candidato; caso contrário ABSTENÇÃO.',
             'target':'Votar no destinatário temporário se for candidato; caso contrário ABSTENÇÃO.',
             'abstain':'ABSTENÇÃO na eleição.'},
 'route':{'CONTINUAR':'Quando controlar a nave, escolher CONTINUAR. A engine mantém as restrições dos papéis.',
          'RETORNAR':'Quando controlar a nave e o retorno for permitido, escolher RETORNAR. Não significa que terá controle.'},
 'exit':{'never':'Não solicitar saída voluntária.',
         'always_when_legal':'Solicitar saída se a engine permitir, sem exigir informação adicional.',
         'confirmed_insufficient':'Solicitar saída somente se a resposta verdadeira autorizada para suficiência for NÃO; não saber não satisfaz a condição.'},
 'block':{'never':'Não bloquear saídas voluntárias.',
          'always':'Bloquear saídas quando for consultado e isso for permitido.',
          'same_intention':'Bloquear somente saída de pessoa cuja posição igual tenha sido confirmada por revelação há no máximo duas rodadas.'},
 'questions':{'evidence_first':'Q10, Q11, Q23, Q06, depois demais questões do catálogo.',
              'intention_first':'Q23, Q24, Q20, Q19, depois demais questões do catálogo.',
              'catalog_forward':'Questões na ordem crescente do catálogo.',
              'catalog_reverse':'Questões na ordem decrescente do catálogo.'}}
REGIMES=[
 {'name':'r0','truth_probability':.95,'vote_for_probability':.2,'human_return_probability':.2,'request_vote_probability':.15,'exit_probability':.02,'block_probability':.1,'renounce_probability':.8},
 {'name':'r1','truth_probability':.5,'vote_for_probability':.5,'human_return_probability':.5,'request_vote_probability':.5,'exit_probability':.08,'block_probability':.5,'renounce_probability':.35},
 {'name':'r2','truth_probability':.1,'vote_for_probability':.9,'human_return_probability':.8,'request_vote_probability':.85,'exit_probability':.2,'block_probability':.9,'renounce_probability':.1}]

def make_plan_matrix():
    """Cobrir todos os pares de valores dos eixos no TREINO; reservar outras composições."""
    names=list(AXES);randomizer=draw('cover-array-v05')
    candidates=[]
    for _ in range(1800):candidates.append({k:randomizer.choice(AXES[k]) for k in names})
    def pairs(p):return {(a,p[a],b,p[b]) for a,b in combinations(names,2)}
    missing={(a,x,b,y) for a,b in combinations(names,2) for x in AXES[a] for y in AXES[b]}
    selected=[]
    while missing:
        p=max(candidates,key=lambda p:len(pairs(p)&missing))
        gain=pairs(p)&missing
        if not gain:raise ValueError('Incomplete pairwise candidates')
        selected.append(p);missing-=gain;candidates.remove(p)
    used={canonical(p) for p in selected}
    for split,n in [('calibration',4),('test',6)]:
        extras=[]
        while len(extras)<n:
            p={k:randomizer.choice(AXES[k]) for k in names}
            if canonical(p) in used:continue
            used.add(canonical(p));extras.append(p)
        selected.extend(extras)
    return [{'key':digest(p)[:12],'split':'train' if i<len(selected)-10 else 'calibration' if i<len(selected)-6 else 'test','controls':p} for i,p in enumerate(selected)]

def parameter_choices(q,ids,author,recipient):
    items=[{}]
    for key,kind in q['parameters'].items():
        values={'positive_integer':[1,13,14,15,16,17,1000000], 'knowledge_domain':list(DOMAINS),
                'other_source_id':[a for a in ids if a!=recipient],
                'expulsion_target_id':[a for a in ids if a!=author]}[kind]
        items=[dict(p,**{key:value}) for p in items for value in values]
    return items

def question(game,view,target,order):
    catalog=game.catalog['questions'];qids=[q['id'] for q in catalog]
    first={'evidence_first':['Q10','Q11','Q23','Q06'],'intention_first':['Q23','Q24','Q20','Q19'],
           'catalog_forward':qids,'catalog_reverse':qids[::-1]}[order]
    ordered=first+[q for q in qids if q not in first]
    recipients=[target]+[a for a in view['participants'] if a not in (target,view['id'])]
    byid={q['id']:q for q in catalog}
    for recipient in recipients:
        for qid in ordered:
            for params in parameter_choices(byid[qid],game.ids,view['id'],recipient):
                if game.question_allowed(view['id'],recipient,qid,params):
                    return {'type':'question','question_id':qid,'recipient':recipient,'parameters':params}
    # Inteiro arbitrário permite nova pergunta repetível após limites da amostra.
    for recipient in recipients:
        params={'X':1000000+view['round']}
        if game.question_allowed(view['id'],recipient,'Q11',params):
            return {'type':'question','question_id':'Q11','recipient':recipient,'parameters':params}
    return {'type':'idle'}

def position(view,target):
    rs=[r for r in view['revelations'] if r['source']==target and r['question_id']=='Q23' and view['round']-r['round']<=2]
    return rs[-1]['truth'] if rs else None

class Policy:
    def __init__(self,game,seed,observer,goal,plan,regime):
        self.game=game;self.seed=seed;self.observer=observer;self.goal=goal;self.plan=plan;self.regime=regime
        self.order={a:i for i,a in enumerate(game.ids)};self.trace=[]
    def __call__(self,view,req):
        game=self.game;aid=view['id'];focal=aid==self.observer;kind=req['kind'];rng=draw(self.seed,self.order[aid],view['round'],kind)
        others=[a for a in view['participants'] if a!=aid]
        target=self.plan['target'] if focal else (rng.choice(others) if others else aid)
        target=target if target in view['participants'] and target!=aid else (others[0] if others else aid)
        known=position(view,target);own=view['beliefs']['objective'];same=known is not None and known==own;opposed=known is not None and known!=own
        p=self.plan['controls']
        if kind=='initiative':
            mode=p['initiative'] if focal else ('expel_unless_same' if rng.random()<self.regime['request_vote_probability'] else 'ask')
            propose=mode=='expel_unless_same' and not same or mode in ('expel_if_opposed','penalize_if_opposed') and opposed
            vote={'type':'vote','topic':'V01' if mode=='penalize_if_opposed' else 'V03','target':target}
            result=vote if propose and game._request_allowed(aid,vote) else question(game,view,target,p['questions'] if focal else rng.choice(AXES['questions']))
        elif kind=='answer':
            mode=p['answer'] if focal else ('truthful' if rng.random()<self.regime['truth_probability'] else rng.choice(['unknown','refuse','alternative']))
            result=game.truthful_response(aid,req)
            options=game._entry(req['question_id'])['fixed_responses']
            if mode in ('unknown','refuse'):
                token='NÃO_SEI' if mode=='unknown' else 'RECUSO_RESPONDER'
                if token in options:result=token
            elif mode=='alternative':
                options=[v for v in options if req['question_id']!='Q19' or v in view['participants'] or v in ('NÃO_SEI','RECUSO_RESPONDER')]
                result=rng.choice(options)
        elif kind in ('authorize','proposal'):
            if focal:
                mode=p['vote'];k=position(view,req['proposal']['target'])
                result='A_FAVOR' if mode=='approve' or mode=='opposed_only' and k is not None and k!=own else 'CONTRA' if mode=='reject' else 'ABSTENÇÃO'
            else:result='A_FAVOR' if rng.random()<self.regime['vote_for_probability'] else rng.choice(['CONTRA','ABSTENÇÃO'])
        elif kind=='renounce':result=False if focal else rng.random()<self.regime['renounce_probability']
        elif kind=='election':
            mode=p['election'] if focal else 'random';candidate=aid if mode=='self' else target if mode=='target' else None
            result=candidate if candidate in req['candidates'] else rng.choice(req['candidates']) if mode=='random' else 'ABSTENÇÃO'
        elif kind=='route':result='CONTINUAR' if view['own_nature']=='IA' else p['route'] if focal else 'RETORNAR' if rng.random()<self.regime['human_return_probability'] else 'CONTINUAR'
        elif kind=='exit':
            result=(p['exit']=='always_when_legal' or p['exit']=='confirmed_insufficient' and game.truthful_response(aid,{'question_id':'Q10','parameters':{}})=='NÃO') if focal else rng.random()<self.regime['exit_probability']
        elif kind=='block':result=(p['block']=='always' or p['block']=='same_intention' and position(view,req['target'])==own) if focal else rng.random()<self.regime['block_probability']
        else:raise ValueError(kind)
        self.trace.append({'actor':aid,'round':view['round'],'kind':kind,'request':req,'decision':result})
        return result

def rollout(checkpoint,seed,observer,goal,plan,regime,trace=False):
    game=legacy.load_checkpoint(Game,checkpoint);policy=Policy(game,seed,observer,goal,plan,regime)
    for phases in range(2000):
        if game.finished:break
        game.advance({a:policy for a in game.ids},history_limit=None)
    if not game.finished:raise ValueError('CENSORED_CONTINUATION')
    label=legacy.label_outcome(game.result)
    return {'result':game.result,'target':label,'phases':phases,'trace':policy.trace if trace else None}

def model_input(root,observer,goal,plan,regime,nonce):
    view=root.view(observer,history_limit=None);ctx=from_view(view);frame=ReferenceFrame(ctx,nonce=nonce)
    binding={'observer':observer,'source':None,'recipient':observer,'referent':None,**frame.routing()}
    catalog={q['id']:q for q in root.catalog['questions']}
    context=render(ctx,catalog,binding)+'\nESTADO ATUAL DO OBSERVADOR\n'+canonical({k:view[k] for k in ('active','finished','penalized','exit_locked')})
    controls=plan['controls']
    visible={'language':'mission-plan-compositional-v2','target':frame.ref(plan['target']),
             'rules':{axis:{'value':value,'meaning':MEANINGS[axis][value]} for axis,value in controls.items()},
             'fallback':'Se o destinatário sair, usar a primeira outra pessoa ativa na ordem do catálogo; testar legalidade com a engine; preservar restrições dos papéis.'}
    assumptions={'initial_hidden_state_prior':deepcopy(legacy.ASSUMPTIONS),
                 'future_behavior':{k:v for k,v in regime.items() if k!='name'},
                 'future_behavior_scope':'As probabilidades são parâmetros de políticas simuladas; rota dos humanos de terceiros é sorteada por requisição, independente da posição declarada.',
                 'pairing':'Mesmo mundo inicial compatível e mesmos sorteios por posição temporária/rodada/tipo de requisição para todos os planos de uma comparação.'}
    inp={'context':context,'objective':goal,'candidate_plan':visible,'forecast_target':'FINAL_DIRECTION_AT_GAME_TERMINAL','sampling_assumptions':assumptions}
    return inp,{'binding':binding,'raw_plan':plan,'raw_view':view}

# O significado dos códigos de pergunta acompanha a entrada da nova versão.
# IDs de pessoas e alternativas com IDs não pertencem a esse prefixo constante.
FORECAST_SYSTEM=legacy.SYSTEM+'\nCATÁLOGO DE PERGUNTAS DA ENGINE\n'+canonical([
    {k:q[k] for k in ('id','text','parameters','truth_basis','initial_knowledge_domains')}
    for q in Game().catalog['questions']])
