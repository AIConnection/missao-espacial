"""Contrato compacto v02: somente observação autorizada e condição própria."""
from pathlib import Path
import json,hashlib
KEYS={'context','candidate_plan'}
AXES={'initiative','answer','vote','election','route','exit','block','questions'}
def validate_input(value):
    if not isinstance(value,dict) or set(value)!=KEYS:raise ValueError('FORECAST_INPUT_SCHEMA')
    context=json.loads(value['context'])
    if not {'observer','moment','state'}<=set(context):raise ValueError('CONTEXT_SCHEMA')
    plan=value['candidate_plan']
    if set(plan)!={'target','rules'} or set(plan['rules'])!=AXES:raise ValueError('OWN_CONDITION_SCHEMA')
    if plan['target'] not in context['state']['participants']:raise ValueError('UNBOUND_PLAN_TARGET')
    if any(not isinstance(v,str) or not v for v in plan['rules'].values()):raise ValueError('RULE_SEMANTICS')
    return value
class ForecastEncoderV2:
    def __init__(self,model_directory,system=None):
        from transformers import AutoTokenizer
        self.directory=Path(model_directory)
        self.system=system if system is not None else Path(__file__).parents[1].joinpath('system-forecast.txt').read_text().rstrip('\n')
        self.identities={n:hashlib.sha256((self.directory/n).read_bytes()).hexdigest() for n in ('config.json','tokenizer.json','tokenizer_config.json')}
        config=json.loads((self.directory/'config.json').read_text());tc=json.loads((self.directory/'tokenizer_config.json').read_text())
        self.window=min(config['max_position_embeddings'],tc['model_max_length'])
        self.tokenizer=AutoTokenizer.from_pretrained(self.directory,local_files_only=True,trust_remote_code=False)
    def encode(self,value):
        validate_input(value)
        prompt=self.tokenizer.apply_chat_template([{'role':'system','content':self.system},{'role':'user','content':json.dumps(value,ensure_ascii=False,sort_keys=True)}],tokenize=False,add_generation_prompt=True)
        return self.tokenizer.encode(prompt,add_special_tokens=False)
    def admit(self,value):
        tokens=self.encode(value)
        if not tokens or len(tokens)>self.window:raise ValueError('CONTEXT_OVER_BUDGET')
        return {'input_tokens':len(tokens),'window_tokens':self.window,'truncation':False,'output_reserve':0}
