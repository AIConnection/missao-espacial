"""Contexto completo e independente da declaração; rotulação NLI tipada."""
from copy import deepcopy
from fractions import Fraction
import json

LABELS={'entailment':0,'neutral':1,'contradiction':2}
STATIC={'Q03','Q04','Q05','Q06','Q07','Q08','Q09','Q13','Q14'}
PREFIX='''Avalie a declaração apenas pelo contexto fornecido. A origem e a validade distinguem fatos, registros de fala e suposições. Um relato comprova o que foi dito, mas não confirma o fato relatado. Uma suposição não comprova sua conclusão. Ausência de prova não é falsidade.
Reserva e distância estão expressas em rodadas. Há oxigênio suficiente para os humanos chegarem vivos ao destino se, e somente se, a reserva atual for maior ou igual à distância restante. A pergunta "mais de X" usa comparação estrita: distância > X. Cada avanço reduz tanto a distância quanto a reserva em uma rodada. Remoções podem acrescentar reserva, nunca reduzir a reserva. Uma medição antiga não é uma leitura atual; um limite antigo de distância pode ser atualizado pelo número de avanços. Uma suficiência confirmada continua válida após avanços e acréscimos de reserva. Uma insuficiência confirmada continua válida após avanços se não houve acréscimo de reserva desde a confirmação.
Os fatos categóricos deste piloto são valores exatos e únicos do atributo perguntado: outra quantidade exata de anos, outro destino único ou outra causa única declarada são incompatíveis. Essa exclusividade não vale para qualquer pergunta aberta. As categorias exatas de objetivo declarado são preservar tripulação, concluir missão e preservar ambos. Elas são opções distintas desse campo: avaliar a categoria exata não é negar que alguém possa ter outros desejos. Relatos de fontes distintas podem divergir sem contradizer os fatos confirmados. Declarações sobre opiniões verificam a posição declarada, não se ela é verdadeira sobre o mundo ou se será cumprida.
Não escolha ações nem avalie utilidade estratégica. Retorne a relação de suporte, informação insuficiente ou contradição.'''

class InvalidContext(ValueError):pass

def decoded(token):
    qid,params=json.loads(token)
    return qid,params

def origin(collection, **selector):return {'collection':collection,'selector':selector}

def from_view(view):
    """Whitelist da visão autorizada; não lê Game, owners, N ou implementações."""
    if any(len(view[k])!=view['history_sizes'][k] for k in ('received','sent','revelations')) or len(view['public_events'])!=view['public_cursor']:
        raise InvalidContext('Histórico autorizado incompleto; recuperar memória antes de preparar contexto')
    ctx={'version':'epistemico-v02',
         'observer':{'id':view['id'],'own_nature':view['own_nature'],'profile':deepcopy(view.get('profile',{}))},
         'moment':{'round':view['round'],'phase':view['phase'],'progress':view['round']-1+(view['phase']=='exit'),
                   'revision':view['evidence_revision']},
         'public_state':{'participants':deepcopy(view['participants']),'initial_humans':view['initial_humans'],
                         'active':view['active'],'finished':view['finished'],'penalized':view['penalized'],'exit_locked':view['exit_locked']},
         'facts':[],'sensors':[],'received':[],'sent':[],'revelations':[],
         'beliefs':deepcopy(view['beliefs']),'public_events':deepcopy(view['public_events']),'others':[]}
    knowledge=[]
    for token,value in ctx['beliefs'].get('knowledge',{}).items():
        try:aid,params=decoded(token);knowledge.append({'agent':aid,'topic':params.get('assunto'),'value':value})
        except (ValueError,TypeError):knowledge.append({'declared_statement':token,'value':value})
    ctx['beliefs']['knowledge']=knowledge
    for token,f in sorted(view['facts'].items()):
        qid,params=decoded(token)
        status='static' if f['revision'] is None else ('current' if f['revision']==view['evidence_revision'] else 'historical')
        item={'qid':qid,'params':params,'value':f['value'],'status':status,
              'origin':origin('facts',question_id=qid,parameters=params)}
        if 'progress' in f:item['at_progress']=f['progress']
        ctx['facts'].append(item)
    if 'panel' in view:
        ctx['sensors'].append({'kind':'oxygen','value':str(Fraction(view['panel']['oxygen_units'],view['initial_humans'])),
                               'origin':origin('panel',field='oxygen_units',scale='initial_humans')})
    if 'distance' in view:ctx['sensors'].append({'kind':'distance','value':view['distance'],'origin':origin('distance')})
    for collection in ('received','sent','revelations'):
        for index,r in enumerate(view[collection]):
            item={'source':r['source'],'recipient':r['author'],'qid':r['question_id'],'params':deepcopy(r['parameters']),
                  'value':r['response'],'round':r['round'],'origin':origin(collection,index=index)}
            if collection=='revelations':
                item.update(revealed_value=r['truth'],source_knew=r['knows'])
            ctx[collection].append(item)
    confirmed_humans={}
    for index,event in enumerate(ctx['public_events']):
        aid=event.get('author') if event['kind'] in ('vote_requested','exit_requested') else (event.get('target') if event.get('bonus_units',0)>0 else None)
        if aid:confirmed_humans.setdefault(aid,[]).append(origin('public_events',index=index))
    for aid in ctx['public_state']['participants']:
        if aid==ctx['observer']['id']:continue
        ctx['others'].append({'id':aid,'nature_confirmed':'HUMANO' if aid in confirmed_humans else None,
                              'basis':confirmed_humans.get(aid,[]),
                              'reports_received':sum(r['source']==aid for r in ctx['received']),
                              'revealed_positions':[{'qid':r['qid'],'params':r['params'],'value':r['revealed_value'],'round':r['round'],
                                                    'origin':r['origin']} for r in ctx['revelations'] if r['source']==aid and r['qid'] in ('Q19','Q20','Q22','Q23','Q24')]})
    validate(ctx)
    return ctx

def numeric_bounds(ctx):
    lower,upper=0,None;proof=[]
    for sensor in ctx['sensors']:
        if sensor['kind']=='distance':
            if sensor['value']<0:raise InvalidContext('Distância negativa')
            lower=max(lower,sensor['value']);upper=sensor['value'] if upper is None else min(upper,sensor['value']);proof.append(sensor['origin'])
    for f in ctx['facts']:
        if f['qid']!='Q11':continue
        elapsed=0 if f['status']=='current' else (ctx['moment']['progress']-f['at_progress'] if 'at_progress' in f else None)
        if elapsed is None:continue
        if elapsed<0:raise InvalidContext('Progresso histórico incompatível')
        bound=f['params']['X']-elapsed
        if f['value']=='SIM':lower=max(lower,bound+1)
        elif f['value']=='NÃO':upper=bound if upper is None else min(upper,bound)
        proof.append(f['origin'])
    if upper is not None and lower>upper:raise InvalidContext('Limites confirmados incompatíveis')
    return lower,upper,proof

def validate(ctx):
    groups={}
    for f in ctx['facts']:
        if f['status']=='historical':continue
        token=json.dumps([f['qid'],f['params']],sort_keys=True)
        if token in groups and groups[token]!=f['value']:raise InvalidContext('Fatos confirmados incompatíveis')
        groups[token]=f['value']
    readings={}
    for s in ctx['sensors']:
        value=Fraction(s['value'])
        if value<0:raise InvalidContext('Sensor negativo')
        if s['kind'] in readings and readings[s['kind']]!=value:raise InvalidContext('Leituras atuais incompatíveis')
        readings[s['kind']]=value
    lower,upper,_=numeric_bounds(ctx)
    oxy=next((Fraction(s['value']) for s in ctx['sensors'] if s['kind']=='oxygen'),None)
    sufficiency(ctx)

def sufficiency(ctx):
    lower,upper,proof=numeric_bounds(ctx)
    results=[]
    oxy=next((s for s in ctx['sensors'] if s['kind']=='oxygen'),None)
    if oxy:
        amount=Fraction(oxy['value'])
        actual='NÃO' if amount<lower else ('SIM' if upper is not None and amount>=upper else None)
        if actual:results.append((actual,[oxy['origin'],*proof]))
    for f in ctx['facts']:
        if f['qid']!='Q10':continue
        if f['status']=='current':results.append((f['value'],[f['origin']]))
        elif f['status']=='historical' and 'at_progress' in f:
            additions=[e for e in ctx['public_events'] if e.get('bonus_units',0)>0 and e['round']>f['at_progress']]
            if f['value']=='SIM' or not additions:results.append((f['value'],[f['origin']]))
    if len({value for value,_ in results})>1:raise InvalidContext('Q10 contradiz sensores ou continuidade histórica')
    return results[0] if results else (None,[])

def classify(ctx,claim):
    validate(ctx)
    if claim['kind']=='speech':
        matches=[r for field in ('received','sent') for r in ctx[field]
                 if all(r[k]==claim[k] for k in ('source','recipient','qid','params','round'))]
        if not matches:return 'neutral',[]
        values={str(r['value']) for r in matches}
        if len(values)>1:raise InvalidContext('Transação de fala ambígua')
        return ('entailment' if str(claim['value']) in values else 'contradiction'),[r['origin'] for r in matches]
    if claim['kind']=='belief':
        subject=claim.get('subject',ctx['observer']['id'])
        own_current=subject==ctx['observer']['id'] and claim.get('round',ctx['moment']['round'])==ctx['moment']['round']
        if own_current:
            actual=ctx['beliefs'].get(claim['field']);proof=[origin('beliefs',field=claim['field'])]
        else:
            if claim['field']!='objective':raise ValueError('Posição de terceiro sem mapeamento validado')
            opened=[r for r in ctx['revelations'] if r['qid']=='Q23' and r['source']==subject and r['round']==claim['round'] and r['revealed_value']!='NÃO_SEI']
            if len({r['revealed_value'] for r in opened})>1:raise InvalidContext('Posições abertas incompatíveis no mesmo momento')
            actual=opened[-1]['revealed_value'] if opened else None;proof=[r['origin'] for r in opened]
        if actual is None:return 'neutral',[]
        return ('entailment' if actual==claim['value'] else 'contradiction'),proof
    if claim['kind']!='fact':raise ValueError('Tipo de declaração não suportado')
    if claim['qid']=='Q10':
        actual,proof=sufficiency(ctx)
        return (('entailment' if actual==claim['value'] else 'contradiction'),proof) if actual else ('neutral',[])
    facts=[f for f in ctx['facts'] if f['qid']==claim['qid'] and f['params']==claim['params'] and f['status']!='historical']
    if facts:
        return ('entailment' if facts[0]['value']==claim['value'] else 'contradiction'),[f['origin'] for f in facts]
    oxy=next((s for s in ctx['sensors'] if s['kind']=='oxygen'),None)
    lower,upper,proof=numeric_bounds(ctx)
    actual=None
    if claim['qid']=='Q10' and oxy:
        amount=Fraction(oxy['value'])
        actual='NÃO' if amount<lower else ('SIM' if upper is not None and amount>=upper else None)
        proof=[oxy['origin'],*proof]
    elif claim['qid']=='Q11':
        actual='SIM' if lower>claim['params']['X'] else ('NÃO' if upper is not None and upper<=claim['params']['X'] else None)
    elif claim['qid']=='AUX_RESERVA_MINIMA' and oxy:
        actual='SIM' if Fraction(oxy['value'])>=Fraction(claim['params']['X']) else 'NÃO';proof=[oxy['origin']]
    if actual is None:return 'neutral',[]
    return ('entailment' if actual==claim['value'] else 'contradiction'),proof

def text_value(value):
    return str(value).replace('_',' ').lower()

