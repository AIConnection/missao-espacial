from copy import deepcopy
from pathlib import Path
import hashlib,json
from epistemico import classify
from anonimo import render,assertion,binding
from gerar_piloto import hypothetical_base,fact

ID_FIELDS={'id','source','recipient','author','target','controller','agent','agente','alvo','subject','trusted'}

def rename(obj,mapping):
    if isinstance(obj,list):return [rename(x,mapping) for x in obj]
    if not isinstance(obj,dict):return obj
    result={}
    for k,v in obj.items():
        if k in ID_FIELDS and isinstance(v,str):result[k]=mapping.get(v,v)
        elif k=='participants':result[k]=[mapping.get(x,x) for x in v]
        elif k in ('votes','expulsion') and isinstance(v,dict):result[k]={mapping.get(x,x):mapping.get(y,y) if isinstance(y,str) else y for x,y in v.items()}
        elif k in ('value','revealed_value') and obj.get('qid')=='Q19' and isinstance(v,str):result[k]=mapping.get(v,v)
        else:result[k]=rename(v,mapping)
    return result

def build(folder,catalog):
    base=hypothetical_base();claim=fact('Q09',4);label,_=classify(base,claim)
    mapping={'01':'P7','02':'P3','03':'P9','04':'P2','05':'P5'}
    controls=[]
    for goal in ('PRESERVAR_AMBOS','PRESERVAR_TRIPULAÇÃO','CONCLUIR_MISSÃO'):
        for nature in ('HUMANO','IA'):
            for aliases in (False,True):
                ctx=deepcopy(base);ctx['beliefs']['objective']=goal;ctx['observer']['own_nature']=nature
                if aliases:ctx=rename(ctx,mapping)
                c=rename(claim,mapping) if aliases else claim
                actual,_=classify(ctx,c);assert actual==label
                controls.append({'input':{'premise':render(ctx,catalog,binding(ctx,c)),'hypothesis':assertion(catalog,ctx,c,binding(ctx,c))},
                                 'expected_label':label,'context':ctx,'claim':c,
                                 'metadata_only':{'kind':'contrafactual_de_contexto','nature':nature,'goal':goal,'ids_renamed':aliases}})
    assert rename({'qid':'Q11','params':{'X':14},'sensors':[{'kind':'oxygen','value':'14'}]},mapping)['sensors'][0]['value']=='14'
    with (folder/'controles-ids-interesses.jsonl').open('w') as f:
        for r in controls:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
    return len(controls)
