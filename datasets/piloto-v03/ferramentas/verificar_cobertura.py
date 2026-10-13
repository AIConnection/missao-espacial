from pathlib import Path
from collections import Counter,defaultdict
from copy import deepcopy
import argparse,hashlib,json,sys,unittest
from epistemico import from_view,classify,LABELS
from anonimo import render,assertion,binding
from controles import rename
from testar_piloto import Semantics

def read(p):return list(map(json.loads,p.read_text().splitlines()))
def verify(project,folder):
    sys.path.insert(0,str(project/'src'));from missao_espacial import Game
    cat={q['id']:q for q in Game().catalog['questions']};rows=read(folder/'pares.jsonl');inputs=read(folder/'inputs-piloto.jsonl');labels=json.loads((folder/'labels-piloto.json').read_text())
    routes=read(folder/'roteamento.jsonl');contexts={c['id']:c['context'] for c in read(folder/'contextos.jsonl')};snaps={s['id']:s for s in read(folder/'visoes-auditoria.jsonl')}
    assert len(rows)==len(inputs)==len(labels)==len(routes)
    coverage=defaultdict(set);paramcoverage=defaultdict(set);anonymity_cases=0
    for index,(row,inp,route) in enumerate(zip(rows,inputs,routes)):
        assert set(inp)=={'premise','hypothesis'} and inp==row['input'];assert route['row_index']==index and route['audit_case']==row['id'];assert labels[index]==row['label_id']==LABELS[row['label']]
        for p in row['provenance']:
            ctx=contexts[p['context_id']];claim=p['claim'];frame=p['binding'];assert classify(ctx,claim)[0]==row['label']
            assert render(ctx,cat,frame)==inp['premise'] and assertion(cat,ctx,claim,frame)==inp['hypothesis']
            if p['source']['type']=='engine':
                s=snaps[p['source']['view_ref']];assert from_view({**s['view'],**s['sensors']})==ctx
            slot=p.get('coverage_slot')
            if slot:
                key=(slot['participant_count'],slot['qid'],json.dumps(slot['response'],ensure_ascii=False));coverage[key].add(row['label'])
                paramcoverage[(slot['participant_count'],slot['qid'],json.dumps(slot['parameters'],sort_keys=True,ensure_ascii=False),json.dumps(slot['response'],ensure_ascii=False))].add(row['label'])
        # Renomeação total: não procurar dígitos, pois quantidades devem continuar intactas.
        ctx=contexts[row['context_id']];mapping={a:f'SECRET_PERSON_{i}' for i,a in enumerate(ctx['public_state']['participants'])}
        altered=rename(ctx,mapping);claim=rename(row['claim'],mapping)
        # Q19 é valor relacional; renomear explícita e somente essa alternativa.
        altered['observer']['own_nature']='IA';altered['observer']['profile']={'never_exit':True}
        newframe=binding(altered,claim);newframe['references']={mapping.get(person,person):ref for person,ref in row['binding']['references'].items()}
        newpair={'premise':render(altered,cat,newframe),'hypothesis':assertion(cat,altered,claim,newframe)}
        assert newpair==inp and 'SECRET_PERSON_' not in json.dumps(newpair),row['id'];anonymity_cases+=1
    question_summary=[];missing=[]
    for size in (5,10):
        game=Game(participant_ids=[f'{i:02}' for i in range(1,size+1)])
        for q in game.catalog['questions']:
            count=0
            for response in q['fixed_responses']:
                key=(size,q['id'],json.dumps(response,ensure_ascii=False));seen=coverage[key]
                if seen!=set(LABELS):missing.append({'size':size,'qid':q['id'],'response':response,'classes':sorted(seen)})
                else:count+=1
            question_summary.append({'participant_count':size,'question_id':q['id'],'expected_responses':len(q['fixed_responses']),'covered_in_three_classes':count})
    assert not missing,missing
    assert all(seen==set(LABELS) for seen in paramcoverage.values())
    result={'unique_pairs':len(rows),'classes':dict(Counter(x['label'] for x in rows)),'questions':len(cat),'question_response_slots':len(coverage),'parameter_response_slots':len(paramcoverage),'covered_in_three_classes':len(coverage),'question_response_percent':100,'semantic_content_coverage_percent':None,'scope':'exact_registered_speech','configurations':[5,10],'anonymity_metamorphic_pairs':anonymity_cases,'parameter_exhaustion':False,'questions_summary':question_summary,'model_executed':False}
    (folder/'cobertura-validacao.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='questions_summary'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--folder',type=Path,required=True);a=p.parse_args()
    res=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(Semantics));assert res.wasSuccessful();verify(a.project,a.folder)
