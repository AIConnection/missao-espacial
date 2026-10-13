import argparse,ast,hashlib,json,sys
from pathlib import Path
from epistemico import PREFIX,STATIC,from_view,validate,InvalidContext

from anonimo import render,assertion,binding
from referencias import ReferenceFrame

class ContextContractError(ValueError):
    def __init__(self, code, details):
        self.code,self.details=code,details
        super().__init__(code+': '+str(details))

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

class ContextGuard:
    def __init__(self, model_directory, runtime_source):
        from transformers import AutoTokenizer
        self.model_directory=Path(model_directory)
        self.runtime_source=Path(runtime_source)
        paths=[self.model_directory/n for n in ('config.json','tokenizer.json','tokenizer_config.json')]+[self.runtime_source]
        self.identities={str(p):sha(p) for p in paths}
        cfg=json.loads(paths[0].read_text());tok=json.loads(paths[2].read_text())
        self.max_tokens=min(cfg['max_position_embeddings'],tok['model_max_length'])
        if self.max_tokens!=16384:raise ContextContractError('CONTEXT_BACKEND_MISMATCH',self.max_tokens)
        self.tokenizer=AutoTokenizer.from_pretrained(self.model_directory,local_files_only=True,trust_remote_code=False)
        tree=ast.parse(self.runtime_source.read_text())
        self.system=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='SYSTEM' for t in node.targets))
        backend=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Phi4Backend')
        declared=next(ast.literal_eval(n.value) for n in backend.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='max_length' for t in n.targets))
        if declared!=self.max_tokens:raise ContextContractError('CONTEXT_BACKEND_MISMATCH',declared)

    @classmethod
    def from_contract(cls,path):
        saved=json.loads(Path(path).read_text())
        guard=cls(saved['model_directory'],saved['runtime_source'])
        if guard.identities!=saved['identities'] or guard.max_tokens!=saved['window_tokens'] or saved.get('prefix_sha256')!=hashlib.sha256(PREFIX.encode()).hexdigest():
            raise ContextContractError('CONTEXT_BACKEND_CHANGED','Identidade difere do contrato persistido')
        return guard

    def encode(self, pair):
        user=json.dumps({'premise':PREFIX+'\n\n'+pair['premise'],'hypothesis':pair['hypothesis']},ensure_ascii=False)
        prompt=self.tokenizer.apply_chat_template([{'role':'system','content':self.system},{'role':'user','content':user}],tokenize=False,add_generation_prompt=True)
        return self.tokenizer.encode(prompt,add_special_tokens=False)

    def validate(self,pair,*,required_evidence_ids,included_evidence_ids,output_reserve=0):
        if type(output_reserve) is not int or output_reserve<0:
            raise ContextContractError('CONTEXT_INVALID_RESERVE',output_reserve)
        for name,expected in self.identities.items():
            if sha(Path(name))!=expected:raise ContextContractError('CONTEXT_BACKEND_CHANGED',name)
        required=set(required_evidence_ids);included=set(included_evidence_ids)
        if not required<=included:
            raise ContextContractError('CONTEXT_INCOMPLETE_EVIDENCE',sorted(required-included))
        count=len(self.encode(pair))
        if count+output_reserve>self.max_tokens:
            raise ContextContractError('CONTEXT_OVER_BUDGET',{'input':count,'output_reserve':output_reserve,'max':self.max_tokens})
        return {'status':'admitted','input_tokens':count,'output_reserve':output_reserve,
                'window_tokens':self.max_tokens,'remaining_tokens':self.max_tokens-count-output_reserve,
                'truncation':False,'required_evidence_ids':sorted(required)}

    def prepare(self,ctx,claim,catalog,*,expected_context=None,output_reserve=0,provided_binding=None):
        if expected_context is not None and ctx!=expected_context:
            raise ContextContractError('CONTEXT_INCOMPLETE_CONTEXT','Contexto difere da memória autorizada integral')
        if claim['kind'] not in ('fact','speech','belief') or (claim['kind']=='fact' and claim['qid'] not in STATIC|{'Q10','Q11','AUX_RESERVA_MINIMA'}):
            raise ContextContractError('CONTEXT_UNSUPPORTED_CLAIM',claim)
        try:validate(ctx)
        except InvalidContext as error:raise ContextContractError('CONTEXT_INCONSISTENT',str(error)) from error
        expected_binding=binding(ctx,claim)
        if provided_binding is None:
            frame={**expected_binding,**ReferenceFrame(ctx).routing()}
        else:
            if any(provided_binding.get(k)!=v for k,v in expected_binding.items()):raise ContextContractError('CONTEXT_ROUTING_MISMATCH','Vínculo externo não corresponde à declaração')
            frame=provided_binding
        try:pair={'premise':render(ctx,catalog,frame),'hypothesis':assertion(catalog,ctx,claim,frame)}
        except ValueError as error:raise ContextContractError('CONTEXT_ANONYMIZATION_REQUIRED',str(error)) from error
        # Completude é conferida pela comparação da estrutura integral, não por uma lista autodeclarada.
        result=self.validate(pair,required_evidence_ids=[],included_evidence_ids=[],output_reserve=output_reserve)
        result['routing_only']=frame
        result['context_sha256']=hashlib.sha256(json.dumps(ctx,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        return pair,result

    def prepare_snapshot(self,snapshot,claim,catalog,provided_context=None,provided_binding=None):
        expected=from_view({**snapshot['view'],**snapshot['sensors']})
        pair,result=self.prepare(expected if provided_context is None else provided_context,claim,catalog,expected_context=expected,provided_binding=provided_binding)
        result['session']=snapshot['episode'];result['observer']=snapshot['observer'];result['view_ref']=snapshot['id']
        return pair,result

def audit(folder,project,guard):
    sys.path.insert(0,str(project/'src'))
    from missao_espacial import Game
    catalog={q['id']:q for q in Game().catalog['questions']}
    contexts={c['id']:c for c in map(json.loads,(folder/'contextos.jsonl').read_text().splitlines())}
    snapshots={s['id']:s for s in map(json.loads,(folder/'visoes-auditoria.jsonl').read_text().splitlines())}
    rows=[json.loads(x) for x in (folder/'pares.jsonl').read_text().splitlines()]
    admissions=[];blocked=[]
    for row in rows:
        ctx=contexts[row['context_id']]['context']
        try:
            p=row['provenance'][0]['source']
            if p['type']=='engine':pair,admission=guard.prepare_snapshot(snapshots[p['view_ref']],row['claim'],catalog,ctx,row['binding'])
            else:pair,admission=guard.prepare(ctx,row['claim'],catalog,provided_binding=row['binding'])
            assert pair==row['input']
            admissions.append({'id':row['id'],**admission})
        except ContextContractError as error:blocked.append({'id':row['id'],'code':error.code,'details':error.details})
    counts=sorted(a['input_tokens'] for a in admissions)
    sample=rows[0]['input'];n=len(guard.encode(sample));checks=[]
    guard.validate(sample,required_evidence_ids=[],included_evidence_ids=[],output_reserve=guard.max_tokens-n);checks.append('limite inclusivo')
    for expected,kwargs in [('CONTEXT_OVER_BUDGET',{'output_reserve':guard.max_tokens-n+1}),('CONTEXT_INCOMPLETE_EVIDENCE',{'required_evidence_ids':['a'],'included_evidence_ids':[]})]:
        try:guard.validate(sample,**({'required_evidence_ids':[],'included_evidence_ids':[]}|kwargs))
        except ContextContractError as e:assert e.code==expected
        else:raise AssertionError(expected)
        checks.append(expected)
    snapshot=next(iter(snapshots.values()));ctx=from_view({**snapshot['view'],**snapshot['sensors']})
    damaged=json.loads(json.dumps(ctx));damaged['public_events']=[]
    try:guard.prepare_snapshot(snapshot,{'kind':'fact','qid':'Q09','params':{},'value':4},catalog,damaged)
    except ContextContractError as e:assert e.code=='CONTEXT_INCOMPLETE_CONTEXT'
    else:raise AssertionError('Não permitir remover informação de outra pergunta para caber')
    checks.append('contexto integral truncado bloqueado')
    try:guard.validate({'premise':'Texto longo. '*20000,'hypothesis':'A nave continua.'},required_evidence_ids=[],included_evidence_ids=[])
    except ContextContractError as e:assert e.code=='CONTEXT_OVER_BUDGET'
    else:raise AssertionError('Entrada extensa não pode ser truncada')
    checks.append('estouro sem truncamento')
    tree=ast.parse(guard.runtime_source.read_text());cls=next(x for x in tree.body if isinstance(x,ast.ClassDef) and x.name=='Phi4Backend')
    fn=next(x for x in cls.body if isinstance(x,ast.FunctionDef) and x.name=='_encode')
    ns={'json':json,'SYSTEM':guard.system};exec(compile(ast.Module(body=[fn],type_ignores=[]),str(guard.runtime_source),'exec'),ns)
    assert ns['_encode'](guard,PREFIX+'\n\n'+sample['premise'],sample['hypothesis'])==guard.encode(sample)
    checks.append('prefixo e contexto codificados como no runtime local')
    result={'window_tokens':guard.max_tokens,'admitted_pairs':len(admissions),'blocked_pairs':len(blocked),
            'min_input_tokens':counts[0],'median_input_tokens':counts[len(counts)//2],'p95_input_tokens':counts[int(.95*(len(counts)-1))],
            'max_input_tokens':counts[-1],'output_reserve':0,'reservation_reason':'Classificação por logits, sem geração de texto.',
            'model_directory':str(guard.model_directory),'runtime_source':str(guard.runtime_source),'identities':guard.identities,
            'prefix_sha256':hashlib.sha256(PREFIX.encode()).hexdigest(),'tests_passed':checks,'model_executed':False,'deployed_to_simulator':False}
    (folder/'contexto-validacao.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    ContextGuard.from_contract(folder/'contexto-validacao.json');checks.append('contrato persistido reaberto')
    (folder/'contexto-validacao.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    for name,data in [('contexto-admissao.jsonl',admissions),('contexto-bloqueios.jsonl',blocked)]:
        with (folder/name).open('w') as f:
            for r in data:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--project',type=Path,required=True)
    p.add_argument('--model-directory',type=Path,required=True);p.add_argument('--runtime-source',type=Path,required=True)
    a=p.parse_args();audit(a.folder,a.project,ContextGuard(a.model_directory,a.runtime_source))
