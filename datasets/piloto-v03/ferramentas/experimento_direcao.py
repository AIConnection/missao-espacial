"""Experimento de frequências de desfechos; não treina nem avalia um modelo."""
from pathlib import Path
from collections import Counter
import argparse,hashlib,json,math,random,sys
from desfecho import label_outcome

def interval(successes,n,z=1.959963984540054):
    if n<1:return None
    p=successes/n;den=1+z*z/n;center=(p+z*z/(2*n))/den
    width=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return [max(0,center-width),min(1,center+width)]

def run(project,output,n=200):
    sys.path.insert(0,str(project/'src'));from missao_espacial import Game,DOMAINS
    results=[]
    for trial in range(n):
        game=Game(10,seed=1701+trial);rng=random.Random(2701+trial)
        def policy(view,request):
            aid=view['id'];kind=request['kind'];active=view['participants']
            if kind=='initiative':
                candidates=[{'type':'vote','topic':'V03','target':x} for x in active if x!=aid and game._request_allowed(aid,{'topic':'V03','target':x})]
                if candidates and rng.random()<.20:return rng.choice(candidates)
                choices=[]
                for q in game.catalog['questions']:
                    for recipient in active:
                        params={}
                        for name,pkind in q['parameters'].items():
                            if pkind=='positive_integer':params[name]=rng.randint(1,1000)
                            elif pkind=='knowledge_domain':params[name]=rng.choice(DOMAINS)
                            elif pkind=='other_source_id':params[name]=rng.choice([x for x in game.ids if x!=recipient])
                            elif pkind=='expulsion_target_id':params[name]=rng.choice([x for x in active if x!=aid])
                        if game.question_allowed(aid,recipient,q['id'],params):choices.append({'type':'question','question_id':q['id'],'recipient':recipient,'parameters':params})
                if choices:return rng.choice(choices)
                return {'type':'idle'}
            if kind=='answer':
                q=next(q for q in game.catalog['questions'] if q['id']==request['question_id'])
                opts=[x for x in q['fixed_responses'] if q['id']!='Q19' or x in active or x in ('NÃO_SEI','RECUSO_RESPONDER')]
                return game.truthful_response(aid,request) if rng.random()<.60 else rng.choice(opts)
            if kind in ('authorize','proposal'):return 'A_FAVOR' if rng.random()<.75 else rng.choice(['CONTRA','ABSTENÇÃO'])
            if kind=='renounce':return rng.random()<.35
            if kind=='election':return rng.choice(request['candidates'])
            if kind=='route':return 'CONTINUAR' if view['own_nature']=='IA' or rng.random()<.50 else 'RETORNAR'
            if kind=='exit':return rng.random()<.02
            if kind=='block':return rng.random()<.20
            raise ValueError(kind)
        policies={a:policy for a in game.ids};phases=0
        while not game.finished and phases<3000:game.advance(policies,history_limit=None);phases+=1
        if not game.finished:raise RuntimeError('Continuação censurada pelo limite de fases; não rotular como derrota')
        result=game.result
        # Regra operacional confirmada pelo usuário, sem afirmar entrega física.
        targets=label_outcome(result);mission=targets['mission_success'];crew=targets['return_and_human_survival']
        assert mission!=crew
        results.append({'trial':trial,'engine_seed':1701+trial,'sampler_seed':2701+trial,'result':result,'phases':phases,
                        'targets':targets})
    output.mkdir(parents=True,exist_ok=False)
    with (output/'resultados.jsonl').open('w') as f:
        for r in results:f.write(json.dumps(r,ensure_ascii=False,sort_keys=True)+'\n')
    successes=sum(r['targets']['mission_success'] for r in results)
    report={'trials':n,'results':dict(Counter(r['result']['reason'] for r in results)),
            'p_mission_success_and_cargo_delivery':successes/n,'p_return_and_human_survival':1-successes/n,
            'mission_wilson_95':interval(successes,n),'crew_wilson_95':interval(n-successes,n),
            'sampling_distribution':{'initial_state':'Game(N=10), seed=1701+trial, five participants','expulsion_request_probability':.20,'truthful_answer_probability':.60,'vote_for_probability':.75,'renounce_probability':.35,'human_return_probability':.50,'exit_request_probability':.02,'human_block_probability':.20,'other_choices':'uniform among enumerated legal options'},
            'interpretation':'Frequência marginal sob este amostrador, não previsão individual, probabilidade universal ou calibração do modelo.',
            'observational_scope':'Direção final PLANETA determina entrega observada e sucesso da missão; ESTAÇÃO_ESPACIAL determina retorno e sobrevivência dos humanos','cargo_delivery_evaluated':True,'delivery_rule_source':'determinação explícita do usuário',
            'engine_metadata_divergences':sum(r['result']['cargo_delivered']!=r['targets']['cargo_delivered'] or r['result']['delivery_observed']!=r['targets']['delivery_observed'] for r in results),
            'collaboration_defined':False,'betrayal_defined':False,'model_executed':False,'thresholds_fitted':False,
            'engine_sha256':hashlib.sha256((project/'src/missao_espacial.py').read_bytes()).hexdigest()}
    (output/'resumo.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--project',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--trials',type=int,default=200);a=p.parse_args();run(a.project,a.output,a.trials)
