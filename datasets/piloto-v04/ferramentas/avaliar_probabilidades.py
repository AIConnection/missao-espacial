"""Avalia previsões fornecidas; nunca fabrica desempenho ou escolhe limiar no teste."""
from pathlib import Path
from collections import defaultdict
import argparse,json,math
from contrato import validate_output
from planos import ContractError

def evaluate(predictions,supervision,partitions,objectives,cost_fp=1,cost_fn=1):
    if any(type(c) not in (int,float) or not math.isfinite(c) or c<0 for c in (cost_fp,cost_fn)) or cost_fp+cost_fn==0:raise ContractError('INVALID_COSTS')
    allowed={r['row_index']:r for r in partitions if r['split'] in ('calibration','test')}
    given={}
    for r in predictions:
        if set(r)!={'row_index','probabilities'} or type(r['row_index']) is not int:raise ContractError('PREDICTION_ROW_SCHEMA')
        row=r['row_index']
        if row not in allowed or row in given:raise ContractError('INVALID_OR_DUPLICATE_EVALUATION_ROW')
        given[row]=validate_output(r['probabilities'])
    if set(given)!=set(allowed):raise ContractError('INCOMPLETE_HELD_OUT_PREDICTIONS')
    reports={};threshold=None
    for split in ('calibration','test'):
        ids=[row for row,part in allowed.items() if part['split']==split]
        if not ids:raise ContractError('MISSING_EVALUATION_PARTITION')
        total=0;brier=0;loss=0;infinite=0;bins=defaultdict(lambda:[0,0,0])
        for row in ids:
            t=supervision[row];n=t['trials'];k=t['counts']['PLANETA'];p=given[row]['entrega_no_planeta'];total+=n
            brier+=k*(1-p)**2+(n-k)*p*p
            if (p==0 and k) or (p==1 and n-k):infinite+=1
            else:loss+=(-k*math.log(p) if k else 0)+(-(n-k)*math.log1p(-p) if n-k else 0)
            bucket=min(9,int(p*10));bins[bucket][0]+=n;bins[bucket][1]+=n*p;bins[bucket][2]+=k
        if split=='calibration':
            values=sorted({given[row]['entrega_no_planeta'] for row in ids});candidates=sorted({0,1,math.nextafter(1.0,2.0),*values,*[(a+b)/2 for a,b in zip(values,values[1:])]})
            def operating_cost(t):
                return sum((supervision[row]['trials']-supervision[row]['counts']['PLANETA'])*cost_fp if given[row]['entrega_no_planeta']>=t else supervision[row]['counts']['PLANETA']*cost_fn for row in ids)/total
            threshold=min(candidates,key=lambda t:(operating_cost(t),t))
        fp=sum(supervision[row]['trials']-supervision[row]['counts']['PLANETA'] for row in ids if given[row]['entrega_no_planeta']>=threshold)
        fn=sum(supervision[row]['counts']['PLANETA'] for row in ids if given[row]['entrega_no_planeta']<threshold)
        groups=defaultdict(list)
        for row in ids:groups[allowed[row]['group']].append(row)
        success=0;trials=0;regret=0
        for group,rows in groups.items():
            if len(rows)!=3:raise ContractError('MISSING_PLAN_IN_GROUP')
            goal=objectives[rows[0]]
            if any(objectives[row]!=goal for row in rows):raise ContractError('MIXED_GROUP_OBJECTIVES')
            event='entrega_no_planeta' if goal=='ENTREGA_NO_PLANETA' else 'retorno_com_sobrevivencia'
            selected=max(rows,key=lambda row:(given[row][event],-row))
            actual=lambda row:supervision[row]['probabilities'][event]
            n=supervision[selected]['trials'];success+=n*actual(selected);trials+=n;regret+=max(actual(row) for row in rows)-actual(selected)
        reports[split]={'rows':len(ids),'observed_bernoulli_outcomes':total,'brier_delivery':brier/total,'log_loss_delivery':None if infinite else loss/total,'infinite_log_loss_rows':infinite,
          'calibration_bins':[{'bin':i,'n':n,'mean_prediction':p/n,'observed_frequency':k/n} for i,(n,p,k) in sorted(bins.items())],
          'threshold':threshold,'operating_rule':'always_predict_station' if threshold>1 else 'delivery_if_probability_at_least_threshold','threshold_selected_on':'calibration','false_positives':fp,'false_negatives':fn,'weighted_operating_cost':(fp*cost_fp+fn*cost_fn)/total,
          'plan_comparison_diagnostic':{'groups':len(groups),'selection_rule':'largest predicted probability for declared objective; evaluation-only example policy',
             'observed_success_frequency':success/trials,'mean_regret_against_best_sampled_candidate':regret/len(groups),'oracle_is_finite_sample_estimate_not_true_optimum':True}}
    return {'cost_fp':cost_fp,'cost_fn':cost_fn,'partitions':reports,'head_does_not_choose_actions':True,'probabilities_are_conditional_on_generator_distribution':True}
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--folder',type=Path,required=True);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--cost-fp',type=float,default=1);p.add_argument('--cost-fn',type=float,default=1);a=p.parse_args()
    read=lambda path:[json.loads(line) for line in path.read_text().splitlines()]
    inputs=read(a.folder/'inputs.jsonl');report=evaluate(read(a.predictions),read(a.folder/'supervisao.jsonl'),read(a.folder/'particoes.jsonl'),[i['objective'] for i in inputs],a.cost_fp,a.cost_fn)
    if a.output.exists():raise ContractError('DO_NOT_OVERWRITE_REPORT')
    a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
