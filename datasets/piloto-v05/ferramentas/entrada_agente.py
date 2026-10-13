"""Entrada compacta construída somente de AgentView e memória de observações.
A correspondência de pessoas e a condição candidata são mantidas pelo chamador.
Não recebe Game, checkpoint, atribuição de implementações ou estado privado.
"""
from pathlib import Path
from copy import deepcopy
from dataclasses import asdict
import json,random,secrets,sys,re
ROOT=Path(__file__).resolve().parents[3]
for directory in (ROOT/'src',ROOT/'datasets/piloto-v03/ferramentas',ROOT/'treinamento/piloto-v01/pacote/ferramentas'):
    if directory.is_dir():sys.path.insert(0,str(directory))
from agent_contract import AgentView
from epistemico_v2 import from_view
from referencias import participants

FIELDS=('id','own_nature','round','phase','active','finished','participants','penalized','exit_locked','facts','received','sent','revelations','beliefs','public_events','public_cursor','history_sizes','evidence_revision','initial_humans','profile','panel','distance')
PERSON_FIELDS={'source','recipient','author','target','controller','agent','agente','alvo','subject','trusted'}
PERSON_LISTS={'participants','candidates','blockers'}
PERSON_MAPS={'votes','expulsion'}

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def raw_view(view):
    if not isinstance(view,AgentView):raise TypeError('Exige AgentView recebido pela implementação do agente')
    raw={key:deepcopy(getattr(view,key)) for key in FIELDS if getattr(view,key) is not None}
    for key in ('participants','received','sent','revelations','public_events'):raw[key]=list(raw[key])
    return raw

class ObservationMemory:
    """Guarda as observações pelo índice da janela, sem recuperar estado da engine."""
    def __init__(self,state=None):self.state=deepcopy(state or {'records':{},'latest':None})
    def observe(self,view):
        raw=raw_view(view)
        if self.state['latest'] is not None and self.state['latest']['id']!=raw['id']:raise ValueError('Memória de outro observador')
        for field in ('received','sent','revelations','public_events'):
            total=raw['public_cursor'] if field=='public_events' else raw['history_sizes'][field]
            start=total-len(raw[field]);records=self.state['records'].setdefault(field,{})
            if start<0:raise ValueError('Janela inválida')
            for i,value in enumerate(raw[field],start):
                key=str(i)
                if key in records and records[key]!=value:raise ValueError('Observação alterada na mesma posição')
                records[key]=deepcopy(value)
        self.state['latest']=raw
    def complete_view(self):
        raw=deepcopy(self.state['latest'])
        if raw is None:raise ValueError('Sem observação')
        for field in ('received','sent','revelations','public_events'):
            total=raw['public_cursor'] if field=='public_events' else raw['history_sizes'][field]
            records=self.state['records'][field]
            if any(str(i) not in records for i in range(total)):raise ValueError('Histórico incompleto: restaurar memória própria; não consultar estado privado')
            raw[field]=[deepcopy(records[str(i)]) for i in range(total)]
        return AgentView.from_engine(raw)
    def save_state(self):return deepcopy(self.state)

class InputBuilder:
    def __init__(self,view,catalog,*,nonce=None):
        self.context=from_view(raw_view(view))
        self.catalog={q['id']:q for q in catalog['questions']} if 'questions' in catalog else catalog
        people=sorted(participants(self.context));slots=list(range(1,len(people)+1))
        random.Random(nonce if nonce is not None else secrets.token_hex(32)).shuffle(slots)
        self.routing={person:f'p{slot}' for person,slot in zip(people,slots)}
    def person(self,value):
        if value not in self.routing:raise ValueError('Referência fora das observações autorizadas')
        return self.routing[value]
    def resolve(self,reference):
        for person,ref in self.routing.items():
            if ref==reference:return person
        raise ValueError('Referência fora desta chamada')
    def map_people(self,value,key=None):
        if key in PERSON_FIELDS and isinstance(value,str):return self.person(value)
        if key in PERSON_LISTS:return [self.person(v) for v in value]
        if key in PERSON_MAPS:
            return {self.person(k):(self.person(v) if key=='votes' and isinstance(v,str) and v not in ('A_FAVOR','CONTRA','ABSTENÇÃO') else v) for k,v in value.items()}
        if isinstance(value,dict):return {k:self.map_people(v,k) for k,v in value.items()}
        if isinstance(value,(list,tuple)):return [self.map_people(v) for v in value]
        if isinstance(value,str) and value in self.routing:return self.person(value)
        return value
    def question(self,qid,params):
        if qid=='AUX_RESERVA_MINIMA':return f'A reserva atual é de pelo menos {params["X"]} rodadas?'
        return self.catalog[qid]['text'].format(**self.map_people(params))
    def answer(self,qid,value):
        return self.person(value) if qid=='Q19' and value not in ('NÃO_SEI','RECUSO_RESPONDER',None) else value
    def context_value(self):
        c=self.context
        out={'observer':self.person(c['observer']['id']),'moment':{k:c['moment'][k] for k in ('round','phase','progress')},
             'state':self.map_people(c['public_state'])}
        questions={}
        def question_ref(qid,params):
            text=self.question(qid,params)
            if text not in questions:questions[text]=f'q{len(questions)+1}'
            return questions[text]
        def table(columns,rows):return {'columns':columns,'rows':rows}
        if c['facts']:
            out['facts']=table(['question','value','validity','progress'],[[question_ref(f['qid'],f['params']),self.answer(f['qid'],f['value']),f['status'],f.get('at_progress')] for f in c['facts']])
        if c['sensors']:out['sensors']={s['kind']:s['value'] for s in c['sensors']}
        speech=[];seen=set()
        for field in ('received','sent'):
            for r in c[field]:
                row=[r['round'],self.person(r['source']),self.person(r['recipient']),question_ref(r['qid'],r['params']),self.answer(r['qid'],r['value'])]
                key=canonical(row)
                if key not in seen:speech.append(row);seen.add(key)
        if speech:out['speech']=table(['round','source','recipient','question','value'],speech)
        if c['revelations']:
            out['revelations']=table(['round','source','recipient','question','value','revealed_value','source_knew'],[[r['round'],self.person(r['source']),self.person(r['recipient']),question_ref(r['qid'],r['params']),self.answer(r['qid'],r['value']),self.answer(r['qid'],r['revealed_value']),r['source_knew']] for r in c['revelations']])
        beliefs={k:self.map_people(v,k) for k,v in c['beliefs'].items() if v is not None and v!=[] and v!={}}
        if beliefs:out['beliefs']=beliefs
        events=[]
        for event in c['public_events']:
            e={k:v for k,v in event.items() if k not in ('kind','round','question_id','parameters')}
            if event['kind']=='question':e['question']=question_ref(event['question_id'],event.get('parameters',{}))
            events.append([event['round'],event['kind'],self.map_people(e)])
        if events:out['events']=table(['round','kind','data'],events)
        if questions:out['questions']={ref:text for text,ref in questions.items()}
        text=canonical(out)
        for aid in self.routing:
            if aid not in self.routing.values() and not aid.isdecimal() and re.search(r'(?<!\w)'+re.escape(aid)+r'(?!\w)',text):raise ValueError('ID bruto presente na entrada')
        return out
    def nli(self,claim):
        c=deepcopy(claim);kind=c['kind']
        if kind=='belief':
            statement={'kind':'position','subject':self.person(c.get('subject',self.context['observer']['id'])),'field':c['field'],'value':c['value']}
            if 'round' in c:statement['round']=c['round']
        else:
            statement={'kind':kind,'question':self.question(c['qid'],c['params']),'value':self.answer(c['qid'],c['value'])}
            if kind=='speech':statement.update(source=self.person(c['source']),recipient=self.person(c['recipient']),round=c['round'])
        return {'premise':canonical(self.context_value()),'hypothesis':canonical(statement)}
    def forecast(self,candidate,meanings):
        # O candidato é uma condição própria que a implementação conhece.
        # Não é atribuição de comportamento a terceiros nem saída do modelo.
        rules={axis:meanings[axis][value].replace('oposta','de categoria diferente da própria') for axis,value in candidate['controls'].items()}
        def readable_question(match):
            text=self.catalog[match.group()]['text']
            return text.replace('{X}','o limite selecionado').replace('{agente}','a pessoa avaliada').replace('{alvo}','a pessoa avaliada').replace('{assunto}','o domínio avaliado')
        rules['questions']=re.sub(r'Q[0-9]{2}',readable_question,rules['questions'])
        return {'context':canonical(self.context_value()),'candidate_plan':{'target':self.person(candidate['target']),'rules':rules}}
