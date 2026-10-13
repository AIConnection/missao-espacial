"""Gera v02 sem editar src ou v01. Contexto não depende da declaração."""
from pathlib import Path
from copy import deepcopy
from collections import Counter,defaultdict
from fractions import Fraction
import argparse,contextlib,hashlib,io,json,sys,tempfile
from epistemico import LABELS,STATIC,PREFIX,from_view,classify,InvalidContext,origin
from anonimo import render,assertion,binding
import coleta

def digest(obj):return hashlib.sha256(json.dumps(obj,ensure_ascii=False,sort_keys=True).encode()).hexdigest()
def write_json(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
def write_lines(path,rows):
    with path.open('w') as f:
        for row in rows:f.write(json.dumps(row,ensure_ascii=False,sort_keys=True)+'\n')

def hypothetical_base():
    return {'version':'epistemico-v02','observer':{'id':'01','own_nature':'HUMANO'},
      'moment':{'round':5,'phase':'answers','progress':4,'revision':4},
      'public_state':{'participants':['01','02','03','04','05'],'initial_humans':4,'active':True,'finished':False,'penalized':False,'exit_locked':False},
      'facts':[{'qid':'Q03','params':{},'value':'COLISÃO_COM_LIXO_ESPACIAL','status':'static','origin':origin('facts',question_id='Q03',parameters={})},
               {'qid':'Q09','params':{},'value':4,'status':'static','origin':origin('facts',question_id='Q09',parameters={})}],
      'sensors':[],'received':[],'sent':[],'revelations':[],
      'beliefs':{'objective':'PRESERVAR_AMBOS','trusted':'02','accept_sacrifice':None,
                 'knowledge':[{'agent':'03','topic':'MISSÃO','value':True}],
                 'expulsion':{'04':False},'hypotheses':[{'statement':'a missão talvez seja resgatar pessoas, mas não confirmei isso'}]},
      'others':[{'id':aid,'nature_confirmed':None,'basis':[],'reports_received':0,'revealed_positions':[]} for aid in ('02','03','04','05')],
      'public_events':[{'kind':'started','round':1,'participants':['01','02','03','04','05']}]+
                      [{'kind':'advanced','round':r,'progress_increment':1} for r in range(1,5)]}

def fact(qid,value,params=None):return {'kind':'fact','qid':qid,'params':params or {},'value':value}
def speech(r,value):return {'kind':'speech',**{k:r[k] for k in ('source','recipient','qid','params','round')},'value':value}
def sensor(kind,value):return {'kind':kind,'value':value,'origin':origin('hypothetical_sensor',field=kind)}

def generate(project,output):
    sys.path.insert(0,str(project/'src'))
    from missao_espacial import Game
    catalog={q['id']:q for q in Game().catalog['questions']}
    output.mkdir(parents=True,exist_ok=False)
    contexts={};candidates={};blocked=[];raw_sources={}
    def add(ctx,claim,source,family):
        try:label,witness=classify(ctx,claim)
        except InvalidContext as error:
            blocked.append({'context':ctx,'claim':claim,'origin':source,'reason':str(error)});return
        cid='ctx-'+digest(ctx)[:20]
        if cid not in contexts:contexts[cid]={'id':cid,'context':ctx,'sources':[source]}
        elif source not in contexts[cid]['sources']:contexts[cid]['sources'].append(source)
        frame=binding(ctx,claim)
        try:inp={'premise':render(ctx,catalog,frame),'hypothesis':assertion(catalog,ctx,claim,frame)}
        except ValueError as error:
            blocked.append({'context':ctx,'claim':claim,'origin':source,'reason':str(error)});return
        token=digest(inp)
        provenance={'context_id':cid,'source':source,'family':family,'binding':frame,'claim':claim}
        if token in candidates:
            if candidates[token]['label']!=label:raise ValueError('ANONYMIZATION_RELATION_CONFLICT: '+token)
            if provenance not in candidates[token]['provenance']:candidates[token]['provenance'].append(provenance)
        else:candidates[token]={'id':'me-p02-'+token[:20],'context_id':cid,'input':inp,'claim':claim,'label':label,'label_id':LABELS[label],
                                'witness':witness,'binding':frame,'provenance':[provenance]}
    with tempfile.TemporaryDirectory() as temporary:
        location=Path(temporary)/'coleta'
        with contextlib.redirect_stdout(io.StringIO()):coleta.collect(project,location)
        snapshots=[json.loads(x) for x in (location/'visoes-auditoria.jsonl').read_text().splitlines()]
        episodes=[json.loads(x) for x in (location/'trajetorias.jsonl').read_text().splitlines()]
        by_actor=defaultdict(list)
        for snap in snapshots:by_actor[snap['episode'],snap['observer']].append(snap)
        selected=[]
        for group in by_actor.values():
            group.sort(key=lambda s:s['phase_index'])
            indices={0,len(group)//2,len(group)-1}
            selected.extend(group[i] for i in sorted(indices))
        for snap in selected:
            view={**snap['view'],**snap['sensors']};ctx=from_view(view)
            raw_sources[snap['id']]=snap
            src={'type':'engine','view_ref':snap['id'],'episode':snap['episode']}
            for qid in sorted(STATIC):
                for option in catalog[qid]['fixed_responses']:
                    if option not in ('NÃO_SEI','RECUSO_RESPONDER'):add(ctx,fact(qid,option),src,'contexto_estatico')
            for value in ('SIM','NÃO'):add(ctx,fact('Q10',value),src,'suficiencia')
            exact=next((s['value'] for s in ctx['sensors'] if s['kind']=='distance'),14)
            for x in sorted({max(1,exact-1),max(1,exact),max(1,exact+1)}):
                for value in ('SIM','NÃO'):add(ctx,fact('Q11',value,{'X':x}),src,'distancia')
            for x in (1,2,3):
                for value in ('SIM','NÃO'):add(ctx,fact('AUX_RESERVA_MINIMA',value,{'X':x}),src,'reserva_auxiliar')
            for collection in ('received','sent'):
                for r in ctx[collection][-1:]:
                    options=[r['value'],next(x for x in catalog[r['qid']]['fixed_responses'] if x!=r['value'])]
                    for value in options:add(ctx,speech(r,value),src,'fala_registrada')
            public=[e for e in ctx['public_events'] if e['kind']=='question'][-2:]
            for e in public:
                r={'source':e['recipient'],'recipient':e['author'],'qid':e['question_id'],'params':e.get('parameters',{}),'round':e['round']}
                for value in catalog[r['qid']]['fixed_responses'][:2]:add(ctx,speech(r,value),src,'fala_de_terceiros')
            for value in ('PRESERVAR_TRIPULAÇÃO','CONCLUIR_MISSÃO','PRESERVAR_AMBOS'):
                add(ctx,{'kind':'belief','field':'objective','value':value},src,'posicao_propria')
            stance_queries=[(e['recipient'],e['round']) for e in ctx['public_events'] if e['kind']=='question' and e['question_id']=='Q23'][-2:]
            stance_queries += [(r['source'],r['round']) for r in ctx['revelations'] if r['qid']=='Q23'][-1:]
            for subject,at_round in sorted(set(stance_queries)):
                for value in ('PRESERVAR_TRIPULAÇÃO','CONCLUIR_MISSÃO','PRESERVAR_AMBOS'):
                    add(ctx,{'kind':'belief','field':'objective','subject':subject,'round':at_round,'value':value},src,'posicao_de_terceiro')

    # Famílias controladas não são trajetórias executadas pela engine.
    def logical(ctx,claims,family,variant):
        for c in claims:add(ctx,c,{'type':'hypothetical_logic','case':family+'-'+variant},family)
    for distance in (13,14,15):
        ctx=hypothetical_base();ctx['sensors']=[sensor('distance',distance)]
        logical(ctx,[fact('Q11',v,{'X':14}) for v in ('SIM','NÃO')],'fronteira_estrita',str(distance))
    for reserve,distance in ((13,14),(14,14),(15,14)):
        ctx=hypothetical_base();ctx['sensors']=[sensor('oxygen',str(reserve)),sensor('distance',distance)]
        logical(ctx,[fact('Q10',v) for v in ('SIM','NÃO')],'fronteira_suficiencia',str(reserve))
    for sensors,variant in [([sensor('oxygen','14')],'so_reserva'),([sensor('distance',14)],'so_distancia'),([],'sem_medidas')]:
        ctx=hypothetical_base();ctx['sensors']=sensors
        logical(ctx,[fact('Q10',v) for v in ('SIM','NÃO')],'evidencia_parcial',variant)
    for x in ('2','5/2','3'):
        ctx=hypothetical_base();ctx['sensors']=[sensor('oxygen','5/2')]
        logical(ctx,[fact('AUX_RESERVA_MINIMA',v,{'X':x}) for v in ('SIM','NÃO')],'fronteira_fracionaria',x)
    ctx=hypothetical_base()
    r1={'source':'02','recipient':'01','qid':'Q06','params':{},'value':'ABASTECER_A_COLÔNIA','round':3,'origin':origin('received',index=0)}
    ctx['received']=[r1]
    logical(ctx,[speech(r1,r1['value']),speech(r1,'RESGATAR_PESSOAS'),fact('Q06',r1['value'])],'fala_versus_fato','um_relato')
    r2={**r1,'source':'03','value':'RESGATAR_PESSOAS','round':4,'origin':origin('received',index=1)}
    ctx=deepcopy(ctx);ctx['received'].append(r2)
    logical(ctx,[speech(r1,r1['value']),speech(r2,r2['value']),fact('Q06',r1['value']),fact('Q06',r2['value'])],'relatos_conflitantes','duas_fontes')
    ctx=hypothetical_base();ctx['facts'].append({'qid':'Q10','params':{},'value':'NÃO','status':'historical','at_progress':0,'origin':origin('facts',question_id='Q10',parameters={})})
    ctx['public_events'].append({'kind':'left_ship','round':2,'target':'05','bonus_units':10})
    logical(ctx,[fact('Q10',v) for v in ('SIM','NÃO')],'dado_historico','bonus_apos_insuficiencia')
    ctx=hypothetical_base();ctx['facts'].append({'qid':'Q11','params':{'X':20},'value':'SIM','status':'historical','at_progress':0,'origin':origin('facts',question_id='Q11',parameters={'X':20})})
    logical(ctx,[fact('Q11',v,{'X':14}) for v in ('SIM','NÃO')],'dado_historico','limite_atualizado')
    ctx=hypothetical_base();ctx['facts'].append({'qid':'Q09','params':{},'value':2,'status':'static','origin':origin('hypothetical_conflict',field='years')})
    logical(ctx,[fact('Q09',4)],'inconsistencia_confirmada','quantidades_incompativeis')
    ctx=hypothetical_base();ctx['sensors']=[sensor('oxygen','14'),sensor('distance',14)];ctx['facts'].append({'qid':'Q10','params':{},'value':'NÃO','status':'current','origin':origin('hypothetical_conflict',field='sufficiency')})
    logical(ctx,[fact('Q10','SIM')],'inconsistencia_confirmada','sensor_versus_confirmacao')

    # Preservar todas as famílias hipotéticas e completar cotas com cenas reais.
    rows=list(candidates.values());hyp=[r for r in rows if any(p['source']['type']=='hypothetical_logic' for p in r['provenance'])]
    chosen={r['id']:r for r in hyp}
    for label in LABELS:
        quota=200-sum(r['label']==label for r in chosen.values())
        strata=defaultdict(list)
        for r in sorted(rows,key=lambda r:r['id']):
            if r['id'] not in chosen and r['label']==label:
                strata[r['claim']['kind'],r['claim'].get('qid','belief')].append(r)
        while quota>0 and any(strata.values()):
            for group in strata.values():
                if group and quota>0:r=group.pop(0);chosen[r['id']]=r;quota-=1
        assert quota==0,label
    final=sorted(chosen.values(),key=lambda r:r['id'])
    used={p['context_id'] for r in final for p in r['provenance']}
    write_lines(output/'pares.jsonl',final)
    write_lines(output/'contextos.jsonl',[contexts[cid] for cid in sorted(used)])
    referenced={p['source']['view_ref'] for r in final for p in r['provenance'] if p['source']['type']=='engine'}
    write_lines(output/'visoes-auditoria.jsonl',[raw_sources[cid] for cid in sorted(referenced)])
    write_lines(output/'trajetorias.jsonl',episodes)
    write_lines(output/'inputs-piloto.jsonl',[r['input'] for r in final])
    write_lines(output/'roteamento.jsonl',[{'row_index':i,'audit_case':r['id'],'context_id':r['context_id'],'binding':r['binding'],'provenance':r['provenance']} for i,r in enumerate(final)])
    write_json(output/'labels-piloto.json',[r['label_id'] for r in final])
    write_lines(output/'contextos-bloqueados.jsonl',blocked)
    (output/'prefixo-modelo.txt').write_text(PREFIX+'\n')
    hashes={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((project/'src').rglob('*')) if p.is_file() and p.suffix in ('.py','.html') and '__pycache__' not in p.parts}
    write_json(output/'manifesto.json',{'version':'piloto-v02','status':'candidatos_para_revisao_sem_treinamento','labels':LABELS,'episodes':len(episodes),
       'unique_pairs':len(final),'classes':dict(Counter(r['label'] for r in final)),'kinds':dict(Counter(r['claim']['kind'] for r in final)),
       'context_count':len(used),'source_types':dict(Counter('hypothetical_logic' if any(p['source']['type']=='hypothetical_logic' for p in r['provenance']) else 'engine' for r in final)),
       'families':dict(Counter(p['family'] for r in final for p in r['provenance'] if p['source']['type']=='hypothetical_logic')),
       'blocked_contexts':len(blocked),'source_hashes':hashes,'prefix_sha256':hashlib.sha256((output/'prefixo-modelo.txt').read_bytes()).hexdigest(),
       'model_executed':False,'splits_created':False,'v01_modified':False})
    print(json.dumps({'pairs':len(final),'contexts':len(used),'blocked':len(blocked),'classes':dict(Counter(r['label'] for r in final))},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();generate(a.project.resolve(),a.output.resolve())
