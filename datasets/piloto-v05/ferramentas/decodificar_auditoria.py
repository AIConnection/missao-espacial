"""Reconstrói a semântica tipada apenas do texto compacto para validar os rótulos."""
import json,re

def decode_question(text,catalog):
    if text.startswith('A reserva atual é de pelo menos '):return 'AUX_RESERVA_MINIMA',{'X':int(text.split('pelo menos ')[1].split(' rodadas')[0])}
    for qid,q in catalog.items():
        template=q['text'];keys=re.findall(r'{([^}]+)}',template);pattern=re.escape(template)
        for key in keys:pattern=pattern.replace(re.escape('{'+key+'}'),'(.*?)',1)
        m=re.fullmatch(pattern,text)
        if m:return qid,{k:int(v) if k=='X' else v for k,v in zip(keys,m.groups())}
    raise ValueError('Pergunta sem semântica pública: '+text)

def decode_pair(pair,catalog):
    value=json.loads(pair['premise']);claim=json.loads(pair['hypothesis']);questions=value.get('questions',{})
    def question(ref):return decode_question(questions.get(ref,ref),catalog)
    def records(table):return [dict(zip(table['columns'],row)) for row in table['rows']]
    ctx={'observer':{'id':value['observer']},'moment':value['moment'],'public_state':value['state'],'facts':[],'sensors':[],
         'received':[],'sent':[],'revelations':[],'beliefs':value.get('beliefs',{}),'public_events':[]}
    for i,f in enumerate(records(value.get('facts',{'columns':[],'rows':[]}))):
        qid,params=question(f['question']);item={'qid':qid,'params':params,'value':f['value'],'status':f['validity'],'origin':{'collection':'facts','index':i}}
        if f['progress'] is not None:item['at_progress']=f['progress']
        ctx['facts'].append(item)
    for kind,v in value.get('sensors',{}).items():ctx['sensors'].append({'kind':kind,'value':v,'origin':{'collection':'sensors','kind':kind}})
    for field,out in (('speech','received'),('revelations','revelations')):
        for i,r in enumerate(records(value.get(field,{'columns':[],'rows':[]}))):
            qid,params=question(r.pop('question'));r.update(qid=qid,params=params,origin={'collection':field,'index':i});ctx[out].append(r)
    for r in records(value.get('events',{'columns':[],'rows':[]})):
        e={'kind':r['kind'],'round':r['round'],**r['data']}
        if 'question' in e:e['question_id'],e['parameters']=question(e.pop('question'))
        ctx['public_events'].append(e)
    if claim['kind']=='position':claim['kind']='belief'
    else:claim['qid'],claim['params']=question(claim.pop('question'))
    return ctx,claim
