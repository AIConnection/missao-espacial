import sys,json,unittest
from pathlib import Path
from copy import deepcopy
sys.path.insert(0,'/Users/alexandre/projects/missao-espacial/src')
from missao_espacial import Game
from planos import *
from validar_planos import replay_trace
from contrato import validate_output
from avaliar_probabilidades import evaluate

class PlanTests(unittest.TestCase):
    def setUp(self):
        self.ids=['A','B','C','D','E'];self.spec={'ids':self.ids,'engine_seed':12,'own_domains':['ACIDENTE'],'variant':0,'N':10}
        self.game,self.preferences=start_world(Game,10,12,self.ids,'A',['ACIDENTE'],41,0)
    def test_third_party_private_history_is_resampled_without_changing_known_history(self):
        steps=prefix_round(self.game,self.preferences,0);goal='ENTREGA_NO_PLANETA';self.game.update_beliefs('A',objective=GOALS[goal]);view=observed(self.game,'A')
        histories=set();recipients=set()
        for i in range(12):
            sampled,_,meta=sample_world(Game,self.spec,steps,'A',goal,view,digest(['latent-past',i]))
            self.assertEqual(observed(sampled,'A'),view)
            histories.add(canonical(meta['unknown_past_answers']));recipients.add(canonical(meta['past_revelation_recipients']))
        self.assertGreater(len(histories),1)
        if not view['revelations']:self.assertGreater(len(recipients),1)

    def test_removed_participant_election_vote_still_uses_anonymous_reference(self):
        ids=['OBSERVER','REMOVED_PARTICIPANT','OTHER_C','OTHER_D','OTHER_E'];g,p=start_world(Game,10,12,ids,ids[0],['ACIDENTE'],41,0);ctx=observed(g,ids[0])
        ctx['public_state']['participants'].remove(ids[1]);ctx['public_events'].append({'kind':'controller_elected','round':1,'controller':ids[2],'votes':{ids[0]:ids[1]}})
        f=ReferenceFrame(ctx,nonce='x');binding={'observer':ids[0],'source':None,'recipient':ids[0],'references':f.to_reference}
        text=render(ctx,{q['id']:q for q in g.catalog['questions']},binding)
        self.assertNotIn('REMOVED_PARTICIPANT',text);self.assertIn(f.ref(ids[1]),text)
    def test_unadapted_view_fields_and_other_phases_are_rejected(self):
        g=self.game;g.update_beliefs('A',objective=GOALS['ENTREGA_NO_PLANETA']);view=g.view('A',history_limit=None);catalog={q['id']:q for q in g.catalog['questions']};p=plans('B','ENTREGA_NO_PLANETA')[0]
        view['available_queries']=['additional_knowledge']
        with self.assertRaises(ContractError):prepare_input(view,catalog,'ENTREGA_NO_PLANETA',p)
        view=g.view('A',history_limit=None);view['phase']='answers'
        with self.assertRaises(ContractError):prepare_input(view,catalog,'ENTREGA_NO_PLANETA',p)

    def test_future_chance_is_resampled_without_changing_observation(self):
        g=self.game;goal='ENTREGA_NO_PLANETA';g.update_beliefs('A',objective=GOALS[goal]);view=observed(g,'A')
        a,_,_=sample_world(Game,self.spec,[],'A',goal,view,'trial-A');b,_,_=sample_world(Game,self.spec,[],'A',goal,view,'trial-B')
        self.assertEqual(observed(a,'A'),view);self.assertEqual(observed(b,'A'),view)
        self.assertNotEqual(a.snapshot()['rng_state'],b.snapshot()['rng_state'])

    def test_audit_serialization_preserves_arbitrary_participant_order(self):
        ids=['Z','Q','B','L','A'];g,p=start_world(Game,10,12,ids,'Z',['ACIDENTE'],41,0)
        restored=load_checkpoint(Game,json.loads(canonical(g.snapshot())))
        self.assertEqual(list(restored.ids),ids)
        self.assertEqual(restored.snapshot(),g.snapshot())

    def test_uncompiled_actor_capabilities_are_blocked(self):
        g=self.game;g.update_beliefs('A',objective=GOALS['ENTREGA_NO_PLANETA']);view=g.view('A',history_limit=None);view['own_nature']='IA'
        with self.assertRaises(ContractError):prepare_input(view,{q['id']:q for q in g.catalog['questions']},'ENTREGA_NO_PLANETA',plans('B','ENTREGA_NO_PLANETA')[0])
    def test_constant_negative_operating_point_is_available(self):
        labels=[{'trials':4,'counts':{'PLANETA':0,'ESTAÇÃO_ESPACIAL':4},'probabilities':{'entrega_no_planeta':0,'retorno_com_sobrevivencia':1}} for i in range(6)]
        partitions=[{'row_index':i,'split':'calibration' if i<3 else 'test','group':'c' if i<3 else 't'} for i in range(6)]
        pred=[{'row_index':i,'probabilities':{'entrega_no_planeta':1,'retorno_com_sobrevivencia':0}} for i in range(6)]
        info=evaluate(pred,labels,partitions,['RETORNO_COM_SOBREVIVENCIA']*6)
        self.assertEqual(info['partitions']['calibration']['operating_rule'],'always_predict_station')
        self.assertEqual(info['partitions']['test']['weighted_operating_cost'],0)

    def test_output_is_normalized_probabilities_without_action(self):
        self.assertEqual(validate_output({'entrega_no_planeta':.2,'retorno_com_sobrevivencia':.8})['entrega_no_planeta'],.2)
        for value in ({'action':'RETORNAR'}, {'entrega_no_planeta':.7,'retorno_com_sobrevivencia':.7}, {'entrega_no_planeta':float('nan'),'retorno_com_sobrevivencia':1}, {'entrega_no_planeta':True,'retorno_com_sobrevivencia':0}):
            with self.assertRaises(ContractError):validate_output(value)
    def test_unadapted_memory_and_clipped_history_block_inference(self):
        g=self.game;g.update_beliefs('A',objective=GOALS['ENTREGA_NO_PLANETA']);catalog={q['id']:q for q in g.catalog['questions']};view=g.view('A',history_limit=None);p=plans('B','ENTREGA_NO_PLANETA')[0]
        view['policy_state']={'extra_knowledge':'something'}
        with self.assertRaises(ContractError):prepare_input(view,catalog,'ENTREGA_NO_PLANETA',p,'x')
        view=g.view('A',history_limit=None);view['public_events']=[]
        with self.assertRaises(ValueError):prepare_input(view,catalog,'ENTREGA_NO_PLANETA',p,'x')
    def test_threshold_chosen_on_calibration_not_test(self):
        labels=[{'row_index':i,'trials':10,'counts':{'PLANETA':10 if i<3 else 0,'ESTAÇÃO_ESPACIAL':0 if i<3 else 10},'probabilities':{'entrega_no_planeta':1 if i<3 else 0,'retorno_com_sobrevivencia':0 if i<3 else 1}} for i in range(6)]
        partitions=[{'row_index':i,'split':'calibration' if i<3 else 'test','group':'c' if i<3 else 't'} for i in range(6)]
        pred=[{'row_index':i,'probabilities':{'entrega_no_planeta':.6,'retorno_com_sobrevivencia':.4}} for i in range(6)]
        info=evaluate(pred,labels,partitions,['ENTREGA_NO_PLANETA']*6)
        self.assertEqual(info['partitions']['calibration']['threshold'],info['partitions']['test']['threshold'])
        self.assertGreater(info['partitions']['test']['weighted_operating_cost'],0)
    def test_incomplete_predictions_do_not_produce_performance_report(self):
        with self.assertRaises(ContractError):evaluate([],[],[{'row_index':0,'split':'test','group':'x'}],[])

    def test_plan_and_goal_are_explicit_without_metadata_features(self):
        g=self.game;g.update_beliefs('A',objective=GOALS['ENTREGA_NO_PLANETA']);p=plans('B','ENTREGA_NO_PLANETA')[0]
        inp,meta=build_input(g,'A','ENTREGA_NO_PLANETA',p,'reference-test')
        self.assertEqual(inp['objective'],'ENTREGA_NO_PLANETA');self.assertIn(inp['candidate_plan']['target'],meta['references'].values())
        self.assertNotIn('nonce',inp);self.assertNotIn('preferences',inp);self.assertNotIn('checkpoint',inp)
    def test_unknown_target_or_program_is_blocked(self):
        g=self.game;g.update_beliefs('A',objective=GOALS['ENTREGA_NO_PLANETA']);p=plans('ABSENT','ENTREGA_NO_PLANETA')[0]
        with self.assertRaises(ContractError):build_input(g,'A','ENTREGA_NO_PLANETA',p,'x')
        p=plans('B','ENTREGA_NO_PLANETA')[0];p['route']='RETORNAR'
        with self.assertRaises(ContractError):build_input(g,'A','ENTREGA_NO_PLANETA',p,'x')
    def test_goal_must_match_observer_declaration(self):
        with self.assertRaises(ContractError):build_input(self.game,'A','ENTREGA_NO_PLANETA',plans('B','ENTREGA_NO_PLANETA')[0],'x')
    def test_hidden_world_must_reproduce_full_view(self):
        goal='ENTREGA_NO_PLANETA';g=self.game;g.update_beliefs('A',objective=GOALS[goal]);view=observed(g,'A')
        new,prefs,meta=sample_world(Game,self.spec,[],'A',goal,view,'conditional-test')
        self.assertEqual(observed(new,'A'),view)
        self.assertNotEqual(new.snapshot()['state']['owners'],g.snapshot()['state']['owners'])
    def test_incompatible_view_is_not_relabelled_as_failure(self):
        goal='ENTREGA_NO_PLANETA';g=self.game;g.update_beliefs('A',objective=GOALS[goal]);view=observed(g,'A');view['received']=[{'not':'actual'}]
        with self.assertRaises(ContractError):sample_world(Game,self.spec,[],'A',goal,view,2,max_attempts=3)
    def test_history_replayed_before_acceptance(self):
        steps=prefix_round(self.game,self.preferences,0);goal='RETORNO_COM_SOBREVIVENCIA';self.game.update_beliefs('A',objective=GOALS[goal]);view=observed(self.game,'A')
        sampled,prefs,meta=sample_world(Game,self.spec,steps,'A',goal,view,45)
        self.assertEqual(observed(sampled,'A'),view);self.assertTrue(view['received'])
    def test_root_and_order_of_plans_do_not_change_rollouts(self):
        g=self.game;g.update_beliefs('A',objective=GOALS['ENTREGA_NO_PLANETA']);checkpoint=g.dumps();ps=plans('B','ENTREGA_NO_PLANETA')
        first=[continuation(Game,checkpoint,self.preferences,123,'A','ENTREGA_NO_PLANETA',p) for p in ps]
        reversed_results=[continuation(Game,checkpoint,self.preferences,123,'A','ENTREGA_NO_PLANETA',p) for p in reversed(ps)]
        self.assertEqual(first,list(reversed(reversed_results)));self.assertEqual(g.dumps(),checkpoint)
    def test_logged_reactions_reproduce_exact_terminal_result(self):
        g=self.game;g.update_beliefs('A',objective=GOALS['RETORNO_COM_SOBREVIVENCIA']);checkpoint=g.dumps()
        run=continuation(Game,checkpoint,self.preferences,81,'A','RETORNO_COM_SOBREVIVENCIA',plans('B','RETORNO_COM_SOBREVIVENCIA')[1])
        self.assertEqual(replay_trace(Game,json.loads(checkpoint),run['trace']),run['result'])
    def test_censored_simulation_is_an_error_not_a_negative_label(self):
        g=self.game;g.update_beliefs('A',objective=GOALS['ENTREGA_NO_PLANETA'])
        with self.assertRaises(ContractError):continuation(Game,g.dumps(),self.preferences,1,'A','ENTREGA_NO_PLANETA',plans('B','ENTREGA_NO_PLANETA')[0],max_phases=0)
    def test_direction_is_controlled_by_candidate_route_when_eligible(self):
        g=self.game
        # Estado de fronteira após remoção da IA e eleição, pelas APIs da engine.
        ai=next(a for a in g.ids if g.view(a)['own_nature']=='IA')
        actions={a:{'type':'question','question_id':'Q10','recipient':self.ids[(i+1)%5]} for i,a in enumerate(self.ids)}
        actions['A']={'type':'vote','topic':'V03','target':ai};g.initiatives(actions)
        humans=[a for a in g.ids if g.view(a)['own_nature']=='HUMANO'];g.vote({a:'A_FAVOR' for a in humans});g.vote({a:'A_FAVOR' for a in humans});g.elect({a:'A' for a in g.active_ids()})
        g.update_beliefs('A',objective=GOALS['RETORNO_COM_SOBREVIVENCIA'])
        run=continuation(Game,g.dumps(),self.preferences,99,'A','RETORNO_COM_SOBREVIVENCIA',plans('B','RETORNO_COM_SOBREVIVENCIA')[0])
        self.assertTrue(run['result']['returned']);self.assertTrue(run['result']['human_survival_aboard'])
    def test_recency_does_not_ask_same_question_forever(self):
        g=self.game;view=g.view('A',history_limit=None);a=question_action(g,view,'B',['Q10','Q11','Q23'])
        view['received'].append({'question_id':'Q10','source':'B','round':g.round})
        b=question_action(g,view,'B',['Q10','Q11','Q23']);self.assertNotEqual(a['question_id'],b['question_id'])
    def test_epistemic_unknown_is_not_opposition(self):
        view=self.game.view('A',history_limit=None)
        self.assertIsNone(recent_position(view,'B'))
        view['received'].append({'source':'B','question_id':'Q23','response':'CONCLUIR_MISSÃO','round':1})
        self.assertIsNone(recent_position(view,'B'))
    def test_counts_and_intervals_are_from_observed_events(self):
        c=Counts()
        for reason in ('returned','oxygen_exhausted','only_ai'):
            c.add({'reason':reason,'returned':reason=='returned','mission_commitment':reason!='returned','cargo_delivered':reason!='returned','delivery_observed':reason!='returned','human_survival_aboard':True if reason=='returned' else None})
        v=c.export();self.assertEqual(v['trials'],3);self.assertEqual(v['probabilities']['entrega_no_planeta'],2/3)
        self.assertLess(v['wilson_95']['entrega_no_planeta'][0],2/3);self.assertGreater(v['wilson_95']['entrega_no_planeta'][1],2/3)

if __name__=='__main__':unittest.main()
