"""Estatísticas descritivas, células de cobertura e baselines sem executar modelo."""
from pathlib import Path
from collections import Counter,defaultdict
import json,gzip,argparse,math
from planos_v2 import ROOT,canonical

def lines(p):
    with (gzip.open(p,'rt') if p.suffix=='.gz' else p.open()) as f:return [json.loads(l) for l in f]
def analyze(folder,experiments):
    rows=lines(folder/'supervisao.jsonl');nli=[r for r in rows if r['task']=='nli'];forecast=[r for r in rows if r['task']=='forecast']
    counts=lambda xs:dict(Counter(xs))
    temporal=[{'split':p,'round_bucket':rb,'phase':phase,'kind':kind,'class':label,'count':n} for (p,rb,phase,kind,label),n in sorted(Counter((r['split'],str(r['round']) if r['round']<=6 else '7-12' if r['round']<=12 else '13+',r['phase'],r['kind'],r['target']) for r in nli).items())]
    roots={r['key']:r for r in lines(folder/'auditoria/mundos.jsonl.gz') if r['kind']=='root'}
    baseline=sum(r['target'] for r in forecast if r['split']=='train')/sum(r['split']=='train' for r in forecast)
    metrics={}
    for split in ('train','calibration','test'):
        rs=[r for r in forecast if r['split']==split];ps=[r['target'] for r in rs]
        metrics[split]={'rows':len(rs),'mean_planet_frequency':sum(ps)/len(ps),'exact_zero_rows':sum(p==0 for p in ps),'exact_one_rows':sum(p==1 for p in ps),'interior_rows':sum(0<p<1 for p in ps),'constant_probability_fitted_on_train':baseline,'mse_against_monte_carlo_estimate':sum((baseline-p)**2 for p in ps)/len(ps),'expected_bernoulli_brier':sum(p*(1-baseline)**2+(1-p)*baseline**2 for p in ps)/len(ps),'irreducible_bernoulli_variance':sum(p*(1-p) for p in ps)/len(ps)}
    experimental=json.loads((experiments/'estatisticas.json').read_text());summary=[]
    for name,rs in experimental['scenarios'].items():
        summary.append({'scenario':name,'games':rs['completed'],'returns':rs['outcomes']['returned']['count'],'return_ci95':rs['outcomes']['returned']['ci95'],'vote_requests':rs['events'].get('vote_requested',0),'elections':rs['events'].get('controller_elected',0),'questions':sum(q['asked'] for q in rs['questions']),'question_ids':[q['question'] for q in rs['questions'] if q['asked']],'answers_by_status':{}})
        status=Counter()
        for a in rs['answers']:status[a['status']]+=a['count']
        summary[-1]['answers_by_status']=dict(status)
    results=lines(folder/'auditoria/resultados-continuacoes.jsonl.gz');reason=counts(r['result']['reason'] for r in results)
    direction=counts(r['target']['final_direction'] for r in results)
    effects=defaultdict(dict)
    for r in forecast:effects[r['root'],r['regime']][r['plan_key']]=r['target']
    spreads=[max(v.values())-min(v.values()) for v in effects.values()]
    report={'nli_classes':counts(str(r['target']) for r in nli),'nli_origin':counts(r['origin_kind'] for r in nli),'nli_temporal':temporal,'forecast_baselines':metrics,'forecast_terminal_reasons':reason,'forecast_directions':direction,'forecast_root_round_phase':dict(Counter(f"{r['spec']['round']}/{r['spec']['construction']}" for r in roots.values())),'plan_comparison_groups':len(effects),'groups_with_different_estimated_probabilities':sum(s>0 for s in spreads),'mean_candidate_probability_range':sum(spreads)/len(spreads),'actual_games':experimental['games'],'actual_scenarios':summary,'natural_question_coverage':[q for q in sorted({q['id'] for q in __import__('missao_espacial').Game().catalog['questions']}) if not any(q in r['question_ids'] for r in summary)],'sample_statistics_are_not_universal_game_probabilities':True,'episodes_are_dependence_units_not_rows':True,'implementation_holdout_proven':False,'unseen_plan_compositions_reserved':True}
    (folder/'estatisticas.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(canonical({k:v for k,v in report.items() if k not in ('nli_temporal','actual_scenarios','forecast_root_round_phase')}),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--experiments-directory',type=Path,required=True);a=p.parse_args();analyze(a.folder,a.experiments_directory)
