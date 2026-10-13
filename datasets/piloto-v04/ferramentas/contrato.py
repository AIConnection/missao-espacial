"""Entrada autorizada, saída probabilística e orçamento verificável da futura cabeça."""
from pathlib import Path
import json,hashlib,math
from planos import SYSTEM,GOALS,ASSUMPTIONS,ContractError,prepare_input,validate_plan

INPUT_KEYS={'context','objective','candidate_plan','forecast_target','sampling_assumptions'}
OUTPUT_KEYS={'entrega_no_planeta','retorno_com_sobrevivencia'}

def validate_output(value):
    if not isinstance(value,dict) or set(value)!=OUTPUT_KEYS:raise ContractError('PROBABILITY_OUTPUT_SCHEMA')
    if any(type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1 for p in value.values()):raise ContractError('INVALID_PROBABILITY')
    if abs(sum(value.values())-1)>1e-9:raise ContractError('PROBABILITIES_NOT_NORMALIZED')
    return value

class ForecastEncoder:
    def __init__(self,model_directory):
        from transformers import AutoTokenizer
        self.directory=Path(model_directory)
        names=('config.json','tokenizer.json','tokenizer_config.json')
        self.identities={name:hashlib.sha256((self.directory/name).read_bytes()).hexdigest() for name in names}
        config=json.loads((self.directory/'config.json').read_text());token=json.loads((self.directory/'tokenizer_config.json').read_text())
        self.window=min(config['max_position_embeddings'],token['model_max_length'])
        self.tokenizer=AutoTokenizer.from_pretrained(self.directory,local_files_only=True,trust_remote_code=False)
    @classmethod
    def from_contract(cls,path):
        saved=json.loads(Path(path).read_text());encoder=cls(saved['model_directory'])
        if saved['tokenizer_identities']!=encoder.identities or saved['window_tokens']!=encoder.window or saved['system_sha256']!=hashlib.sha256(SYSTEM.encode()).hexdigest():raise ContractError('FORECAST_ENCODING_CONTRACT_CHANGED')
        return encoder
    def encode(self,value):
        if set(value)!=INPUT_KEYS or value['objective'] not in GOALS:raise ContractError('FORECAST_INPUT_SCHEMA')
        if value['sampling_assumptions']!=ASSUMPTIONS:raise ContractError('UNSUPPORTED_SAMPLING_ASSUMPTIONS')
        if not isinstance(value['context'],str):raise ContractError('INVALID_CONTEXT_TYPE')
        target=value['candidate_plan'].get('target')
        if not isinstance(target,str) or target not in value['context']:raise ContractError('UNBOUND_PLAN_TARGET')
        validate_plan(value['candidate_plan'],{target},value['objective'])
        if value['forecast_target']!='FINAL_DIRECTION_AT_GAME_TERMINAL':raise ContractError('UNSUPPORTED_FORECAST_TARGET')
        prompt=self.tokenizer.apply_chat_template([{'role':'system','content':SYSTEM},{'role':'user','content':json.dumps(value,ensure_ascii=False,sort_keys=True)}],tokenize=False,add_generation_prompt=True)
        return self.tokenizer.encode(prompt,add_special_tokens=False)
    def admit(self,value,output_reserve=0):
        if type(output_reserve) is not int or output_reserve<0:raise ContractError('INVALID_OUTPUT_RESERVE')
        for name,expected in self.identities.items():
            if hashlib.sha256((self.directory/name).read_bytes()).hexdigest()!=expected:raise ContractError('TOKENIZER_CHANGED')
        tokens=len(self.encode(value))
        if tokens+output_reserve>self.window:raise ContractError('CONTEXT_OVER_BUDGET')
        return {'input_tokens':tokens,'output_reserve':output_reserve,'window_tokens':self.window,'truncation':False}
    def prepare(self,view,catalog,goal,plan,*,expected_view=None,reference_nonce=None):
        if expected_view is not None and view!=expected_view:raise ContractError('CONTEXT_INCOMPLETE')
        value,routing=prepare_input(view,catalog,goal,plan,reference_nonce)
        return value,{'routing_only':routing,**self.admit(value)}

def audit(folder,model_directory):
    encoder=ForecastEncoder(model_directory)
    inputs=[json.loads(x) for x in (folder/'inputs.jsonl').read_text().splitlines()];admitted=[encoder.admit(x) for x in inputs]
    counts=sorted(x['input_tokens'] for x in admitted);sample=inputs[0];n=admitted[0]['input_tokens']
    encoder.admit(sample,encoder.window-n)
    try:encoder.admit(sample,encoder.window-n+1)
    except ContractError as e:assert str(e)=='CONTEXT_OVER_BUDGET'
    else:raise AssertionError('one token over budget was allowed')
    report={'admitted_rows':len(inputs),'window_tokens':encoder.window,'min_tokens':counts[0],'median_tokens':counts[len(counts)//2],'p95_tokens':counts[int(.95*(len(counts)-1))],'max_tokens':counts[-1],'truncation':False,'output_reserve':0,'reservation_reason':'Contrato de heads por logits, sem geração de texto; backend probabilístico ainda não integrado.',
      'model_directory':str(model_directory),'tokenizer_identities':encoder.identities,'system_sha256':hashlib.sha256(SYSTEM.encode()).hexdigest(),'inclusive_budget_test':True,'one_over_budget_blocked':True,'model_weights_executed':False,'existing_three_class_backend_supports_this_task':False}
    (folder/'contexto-validacao.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    ForecastEncoder.from_contract(folder/'contexto-validacao.json');report['saved_contract_reopened']=True
    (folder/'contexto-validacao.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--model-directory',type=Path,required=True);a=p.parse_args();audit(a.folder,a.model_directory)
