"""Contrato de admissão: cobertura tipada e orçamento real do tokenizer Phi-4 local."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import sys

from gerar_piloto import STATIC, evidence, premise, hypothesis

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
        if guard.identities!=saved['identities'] or guard.max_tokens!=saved['window_tokens']:
            raise ContextContractError('CONTEXT_BACKEND_CHANGED','Identidade difere do contrato persistido')
        return guard

    def encode(self, pair):
        user=json.dumps({'premise':pair['premise'],'hypothesis':pair['hypothesis']},ensure_ascii=False)
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

    def prepare(self,view,claim,catalog):
        if claim['kind'] not in ('fact','speech') or (claim['kind']=='fact' and claim['qid'] not in STATIC|{'Q10','Q11','RESERVA'}):
            raise ContextContractError('CONTEXT_UNSUPPORTED_CLAIM',claim)
        rows=evidence(view,claim)
        required=[json.dumps(e['origin'],sort_keys=True,ensure_ascii=False) for e in rows]
        pair={'premise':premise(rows,catalog),'hypothesis':hypothesis(claim,catalog)}
        return pair,self.validate(pair,required_evidence_ids=required,included_evidence_ids=required)

def audit(folder,project,guard):
    sys.path.insert(0,str(project/'src'))
    from missao_espacial import Game
    catalog={q['id']:q for q in Game().catalog['questions']}
    rows=[json.loads(x) for x in (folder/'pares.jsonl').read_text().splitlines()]
    views={v['id']:v for v in map(json.loads,(folder/'visoes-auditoria.jsonl').read_text().splitlines())}
    results=[]
    for row in rows:
        origin=views[row['provenance'][0]['view_ref']]
        pair,admission=guard.prepare({**origin['view'],**origin['sensors']},row['claim'],catalog)
        assert pair==row['input']
        results.append({'id':row['id'],**admission})
    counts=sorted(r['input_tokens'] for r in results)
    sample=rows[0]['input'];base=len(guard.encode(sample))
    # Limite inclusivo, estouro e omissão são controles operacionais, não classes NLI.
    guard.validate(sample,required_evidence_ids=['a'],included_evidence_ids=['a'],output_reserve=guard.max_tokens-base)
    for expected,kwargs in [
        ('CONTEXT_OVER_BUDGET',dict(required_evidence_ids=[],included_evidence_ids=[],output_reserve=guard.max_tokens-base+1)),
        ('CONTEXT_INCOMPLETE_EVIDENCE',dict(required_evidence_ids=['a','b'],included_evidence_ids=['a']))]:
        try:guard.validate(sample,**kwargs)
        except ContextContractError as error:assert error.code==expected
        else:raise AssertionError(expected)
    try:guard.validate({'premise':'Texto longo. '*20000,'hypothesis':'A nave continua.'},required_evidence_ids=[],included_evidence_ids=[])
    except ContextContractError as error:assert error.code=='CONTEXT_OVER_BUDGET'
    else:raise AssertionError('Entrada extensa deve ser bloqueada, não truncada')
    # Conferir igualdade com a função real _encode sem importar/carregar os pesos.
    tree=ast.parse(guard.runtime_source.read_text())
    cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Phi4Backend')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_encode')
    ns={'json':json,'SYSTEM':guard.system}
    exec(compile(ast.Module(body=[fn],type_ignores=[]),str(guard.runtime_source),'exec'),ns)
    assert ns['_encode'](guard,sample['premise'],sample['hypothesis'])==guard.encode(sample)
    result={'window_tokens':guard.max_tokens,'admitted_pairs':len(results),'min_input_tokens':counts[0],
            'median_input_tokens':counts[len(counts)//2],'p95_input_tokens':counts[int(.95*(len(counts)-1))],
            'max_input_tokens':counts[-1],'model_directory':str(guard.model_directory),'runtime_source':str(guard.runtime_source),
            'identities':guard.identities,'output_reserve':0,'reservation_reason':'Classificação por logits, sem geração de tokens, conforme runtime local.',
            'tests_passed':['limite inclusivo','um token acima bloqueado','evidência ausente bloqueada','texto extenso bloqueado sem truncamento','encode idêntico ao runtime local','600 entradas completas reconstituídas'],
            'model_executed':False,'deployed_to_simulator':False,'scope':'Predicados tipados do piloto; não prova recuperação semântica de toda declaração livre ou de toda decisão.'}
    (folder/'contexto-validacao.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    frozen=ContextGuard.from_contract(folder/'contexto-validacao.json')
    assert frozen.encode(sample)==guard.encode(sample)
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        tampered={**result,'window_tokens':16383}
        target=Path(directory)/'contrato.json';target.write_text(json.dumps(tampered))
        try:ContextGuard.from_contract(target)
        except ContextContractError as error:assert error.code=='CONTEXT_BACKEND_CHANGED'
        else:raise AssertionError('Contrato divergente deve bloquear admissão')
    result['tests_passed']+=['reabertura do contrato persistido','contrato divergente bloqueado']
    (folder/'contexto-validacao.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (folder/'contexto-admissao.jsonl').open('w') as f:
        for r in results:f.write(json.dumps(r,ensure_ascii=False)+'\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--project',type=Path,required=True)
    p.add_argument('--model-directory',type=Path,required=True);p.add_argument('--runtime-source',type=Path,required=True)
    a=p.parse_args();audit(a.folder,a.project,ContextGuard(a.model_directory,a.runtime_source))
