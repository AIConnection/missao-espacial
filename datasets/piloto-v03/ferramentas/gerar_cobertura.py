"""Cobertura de alternativas de fala do catálogo executável; fonte preservada."""
from pathlib import Path
from copy import deepcopy
from collections import Counter
import argparse,hashlib,json,sys
from epistemico import from_view,classify,PREFIX,LABELS
from anonimo import binding,render,assertion
from referencias import ReferenceFrame
from gerar_piloto import digest,write_lines,write_json,speech

def options(game,qid):return next(q for q in game.catalog['questions'] if q['id']==qid)['fixed_responses']
def parameter_cases(q,ids):
    result=[{}]
    for key,kind in q['parameters'].items():
        vals={'positive_integer':[1,15,16,17,1000000],'knowledge_domain':['ACIDENTE','MISSÃO','CARGA','PAINEL','DISTÂNCIA','CRISE'],
              'other_source_id':[ids[0],ids[2]],'expulsion_target_id':[ids[1],ids[2]]}[kind]
        result=[dict(p,**{key:v}) for p in result for v in vals]
    return result

def engine_case(project,ids,qid,params,answer,case_index):
    from missao_espacial import Game
    game=Game(10,seed=case_index+901,ai_id=ids[-1],participant_ids=ids)
    # Rondas legais, sem modificar estado privado nem fonte.
    for prior in ('Q03','Q06','Q08','Q13'):
        actions={a:{'type':'question','question_id':prior,'recipient':ids[(i+2)%len(ids)]} for i,a in enumerate(ids)}
        game.initiatives(actions);game.answer({a:'RECUSO_RESPONDER' for a in ids})
        game.route('CONTINUAR');game.exits([], {})
    actions={a:{'type':'question','question_id':'Q11','recipient':ids[(i+1)%len(ids)],'parameters':{'X':16}} for i,a in enumerate(ids)}
    actions[ids[0]]={'type':'question','question_id':qid,'recipient':ids[1],'parameters':params}
    assert game.question_allowed(ids[0],ids[1],qid,params)
    game.initiatives(actions);responses={a:'NÃO_SEI' for a in ids};responses[ids[0]]=answer;game.answer(responses)
    return game,actions,responses

def generate(project,base,output):
    sys.path.insert(0,str(project/'src'));from missao_espacial import Game
    catalog={q['id']:q for q in Game().catalog['questions']}
    output.mkdir(exist_ok=False,parents=True)
    contexts={};snapshots={};pairs={};executed=[];coverage=[]
    def add(ctx,claim,source,coverage_slot=None):
        label,witness=classify(ctx,claim);frame=binding(ctx,claim)
        frame.update(ReferenceFrame(ctx,nonce=digest(['reference-frame-v03',source,claim])).routing())
        inp={'premise':render(ctx,catalog,frame),'hypothesis':assertion(catalog,ctx,claim,frame)}
        key=digest(inp);cid='ctx-'+digest(ctx)[:20];contexts[cid]={'id':cid,'context':ctx}
        prov={'context_id':cid,'source':source,'claim':claim,'binding':frame,'coverage_slot':coverage_slot}
        if key in pairs:
            if pairs[key]['label']!=label:raise ValueError('ANONYMIZATION_RELATION_CONFLICT: '+key)
            if prov not in pairs[key]['provenance']:pairs[key]['provenance'].append(prov)
        else:pairs[key]={'id':'me-p03-'+key[:20],'context_id':cid,'input':inp,'claim':claim,'binding':frame,'label':label,'label_id':LABELS[label],'witness':witness,'provenance':[prov]}
        return pairs[key]['id'],label
    oldcontexts={c['id']:c['context'] for c in map(json.loads,(base/'contextos.jsonl').read_text().splitlines())}
    snapshots.update({s['id']:s for s in map(json.loads,(base/'visoes-auditoria.jsonl').read_text().splitlines())})
    for r in map(json.loads,(base/'pares.jsonl').read_text().splitlines()):
        # Preservar também origens que foram deduplicadas na v02.
        for p in r['provenance']:
            cid=p['context_id'];c=p.get('claim',r['claim']);_,label=add(oldcontexts[cid],c,p['source'])
            assert label==r['label']
    case_index=0
    for size in (5,10):
        ids=[f'{i:02}' for i in range(1,size+1)];configured=Game(participant_ids=ids)
        for q in configured.catalog['questions']:
            for params in parameter_cases(q,ids):
                for option_index,answer in enumerate(q['fixed_responses']):
                    case_index+=1;game,actions,responses=engine_case(project,ids,q['id'],params,answer,case_index)
                    episode=f'cobertura-{case_index:05}';viewrefs={}
                    for observer in (ids[0],ids[2]):
                        view=game.view(observer,history_limit=None);ref=f'{episode}-{observer}'
                        sensors={k:view.pop(k) for k in ('panel','distance') if k in view}
                        snap={'id':ref,'episode':episode,'observer':observer,'view':view,'sensors':sensors}
                        snapshots[ref]=snap;viewrefs[observer]=ref
                    record={'source':ids[1],'recipient':ids[0],'qid':q['id'],'params':params,'round':5,'value':answer}
                    slot={'participant_count':size,'qid':q['id'],'parameters':params,'response':answer}
                    expected={};refs=[]
                    for observer,proposed,expected_label in [(ids[0],answer,'entailment'),
                        (ids[0],q['fixed_responses'][(option_index+1)%len(q['fixed_responses'])],'contradiction'),(ids[2],answer,'neutral')]:
                        snap=snapshots[viewrefs[observer]];ctx=from_view({**snap['view'],**snap['sensors']});claim=speech(record,proposed)
                        claimed_slot={**slot,'response':proposed}
                        caseid,label=add(ctx,claim,{'type':'engine','view_ref':snap['id'],'episode':episode},claimed_slot)
                        assert label==expected_label
                        refs.append({'audit_case':caseid,'label':label,'response':proposed})
                    executed.append({'id':episode,'kind':'legal_catalog_response_probe','participant_count':size,'N':10,'test_round':5,'question_id':q['id'],'parameters':params,'responses':responses,'initiatives':actions,'snapshot_refs':list(viewrefs.values()),'finished':False,'not_full_trajectory':True})
                    coverage.append({'slot':slot,'executed_episode':episode,'cases':refs})
    rows=sorted(pairs.values(),key=lambda r:r['id']);used={p['context_id'] for r in rows for p in r['provenance']}
    usedviews={p['source']['view_ref'] for r in rows for p in r['provenance'] if p['source']['type']=='engine'}
    write_lines(output/'pares.jsonl',rows);write_lines(output/'contextos.jsonl',[contexts[k] for k in sorted(used)])
    write_lines(output/'visoes-auditoria.jsonl',[snapshots[k] for k in sorted(usedviews)])
    write_lines(output/'inputs-piloto.jsonl',[r['input'] for r in rows]);write_json(output/'labels-piloto.json',[r['label_id'] for r in rows])
    write_lines(output/'roteamento.jsonl',[{'row_index':i,'audit_case':r['id'],'context_id':r['context_id'],'binding':r['binding'],'provenance':r['provenance']} for i,r in enumerate(rows)])
    write_lines(output/'execucoes-cobertura.jsonl',executed);write_lines(output/'matriz-cobertura.jsonl',coverage)
    (output/'prefixo-modelo.txt').write_text(PREFIX+'\n')
    sourcehash={str(p.relative_to(project)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((project/'src').rglob('*')) if p.is_file() and p.suffix in ('.py','.html') and '__pycache__' not in p.parts}
    write_json(output/'manifesto.json',{'version':'piloto-v03','unique_pairs':len(rows),'classes':dict(Counter(r['label'] for r in rows)),'catalog_questions':len(catalog),'executed_probes':len(executed),'contexts':len(used),'coverage_scope':'catalog_question_response_options_as_exact_speech_claims','participant_counts':[5,10],'parametric_exhaustion':False,'world_content_coverage_complete':False,'source_hashes':sourcehash,'model_executed':False,'training_performed':False,'agent_integration_performed':False,'previous_pilots_modified':False})
    print(json.dumps({'pairs':len(rows),'probes':len(executed),'classes':dict(Counter(r['label'] for r in rows))}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();generate(a.project,a.base,a.output)
