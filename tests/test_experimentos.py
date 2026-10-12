from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from experimentos import Aggregate, ExperimentJob, Metrics, RunningStats, load_plan, rate, run_plan
from setup_jogo import GameSetup
from carregar_agentes import assign_agents, load_agents
from missao_espacial import Game
from agent_contract import AgentContractError, Answer


class ExperimentTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name)
        data=json.loads((ROOT/'setup.json').read_text())
        data['diretorio_agentes']=str(ROOT/'src/agent')
        data['checkpoint']=str(self.directory/'checkpoint.json')
        self.setup_path=self.directory/'setup.json'
        self.setup_path.write_text(json.dumps(data))
        self.path=self.directory/'experimentos.json'
        self.plan={'setup_base':'setup.json','partidas_por_cenario':4,'seed_base':17,'diretorio_resultados':'resultados',
                   'cenarios':[{'nome':'A','alteracoes':{}},{'nome':'B','alteracoes':{}}]}
        self.path.write_text(json.dumps(self.plan))

    def session(self,seed=42):
        setup=GameSetup.load(self.setup_path)
        return setup.start(agent_seeds={aid:seed+i for i,aid in enumerate(setup.assignment)})

    def test_paired_identical_cases_are_reproducible_before_hooks(self):
        report=run_plan(self.path)
        self.assertEqual(report['status'],'complete',report['errors'])
        self.assertEqual([s['completed'] for s in report['scenarios']],[4,4])
        comparison=report['comparisons'][0]
        self.assertEqual(comparison['paired_games'],4)
        for key in ('rounds','questions','answers'):
            self.assertEqual(comparison['deltas'][key]['min'],0)
            self.assertEqual(comparison['deltas'][key]['max'],0)
        records=[json.loads(line) for line in (Path(report['directory'])/'partidas.jsonl').read_text().splitlines()]
        for replica in range(4):
            first,second=[r for r in records if r['replication']==replica]
            for key in ('result','questions','requested_questions','answers','revelations','votes','removals'):
                self.assertEqual(first[key],second[key],key)
            self.assertTrue(all(first['agent_seed_control'].values()))
        self.assertFalse((self.directory/'checkpoint.json').exists())

    def test_metrics_do_not_change_decisions_and_capture_every_answer(self):
        session=self.session();initial=session.game.dumps()
        Metrics(session)
        self.assertEqual(initial,session.game.dumps())
        control=assign_agents(Game.loads(initial),load_agents(ROOT/'src/agent'))
        metrics=Metrics(session)
        while not session.game.finished:metrics.advance()
        while not control.game.finished:control.advance()
        self.assertEqual(session.game.dumps(),control.game.dumps())
        record=metrics.record(0,42,0,0)
        actual=sum(len(a['received']) for a in session.game._state['agents'].values())
        self.assertEqual(sum(r['count'] for r in record['answers']),actual)
        self.assertEqual(sum(record['questions'].values()),actual)
        self.assertEqual(sum(r['count'] for r in record['revelations']),sum(len(a['revelations']) for a in session.game._state['agents'].values()))
        self.assertGreaterEqual(record['rounds'],record['progress'])

    def test_unrevealed_answers_are_also_classified_by_preanswer_oracle(self):
        session=self.session();game=session.game
        game.initiatives({aid:{'type':'question','question_id':'Q06','recipient':'02' if aid!='02' else '01','parameters':{}}
                         for aid in game.ids})
        metrics=Metrics(session)
        metrics.advance()
        self.assertEqual(sum(metrics.answers.values()),5)
        self.assertEqual(sum(metrics.revelations.values()),1)
        self.assertTrue(any(key[-1]=='verdade' for key in metrics.answers))

    def test_requested_questions_cancelled_by_vote_are_not_answers(self):
        session=self.session();metrics=Metrics(session)
        # Políticas reais sem saída voluntária para manter a execução observável.
        while not session.game.finished:metrics.advance()
        for q,asked in metrics.questions.items():
            self.assertLessEqual(asked,metrics.requested[q])
        self.assertEqual(sum(metrics.questions.values()),sum(metrics.answers.values()))

    def test_running_statistics_and_wilson_bounds(self):
        stats=RunningStats()
        self.assertIsNone(stats.summary()['mean'])
        for n in (1,2,3):stats.add(n)
        result=stats.summary()
        self.assertEqual(result['mean'],2)
        self.assertEqual(result['sd'],1)
        self.assertEqual(result['min'],1);self.assertEqual(result['max'],3)
        self.assertLess(result['mean_ci95'][0],2)
        self.assertEqual(rate(0,0)['rate'],None)
        self.assertGreater(rate(0,10)['ci95'][1],0)
        self.assertLess(rate(10,10)['ci95'][0],1)

    def test_normalization_and_missing_denominators(self):
        agg=Aggregate('empty');summary=agg.summary()
        self.assertEqual(summary['completed'],0)
        self.assertIsNone(summary['truth_rate']['rate'])
        self.assertIsNone(summary['metrics']['rounds']['mean'])

    def test_plan_changes_preserve_base_and_validate_rules(self):
        original=self.setup_path.read_bytes()
        self.plan['cenarios'][1]['alteracoes']={'rodadas':20}
        self.path.write_text(json.dumps(self.plan));plan=load_plan(self.path)
        self.assertEqual(plan['cases'][1]['setup'].rounds,20)
        self.assertEqual(self.setup_path.read_bytes(),original)
        for changes in ({'seed':1},{'rodadas':0},{'missing':3}):
            self.plan['cenarios'][1]['alteracoes']=changes
            self.path.write_text(json.dumps(self.plan))
            with self.assertRaises(ValueError):load_plan(self.path)

    def test_cancel_does_not_count_partial_game_and_persists_report(self):
        checks=[]
        def cancelled():
            checks.append(1);return len(checks)>2
        report=run_plan(self.path,cancelled=cancelled)
        self.assertEqual(report['status'],'cancelled')
        self.assertEqual(sum(s['completed'] for s in report['scenarios']),0)
        self.assertTrue((Path(report['directory'])/'relatorio.json').exists())

    def test_failed_game_is_reported_not_counted(self):
        # Uma implementação configurada inexistente falha ao iniciar a partida.
        data=json.loads(self.setup_path.read_text());data['tripulantes'][-1]['implementacao']='inexistente'
        self.setup_path.write_text(json.dumps(data))
        report=run_plan(self.path)
        self.assertEqual(report['status'],'failed')
        self.assertTrue(report['errors'])
        self.assertEqual(sum(s['completed'] for s in report['scenarios']),0)
        data['diretorio_agentes']=str(self.directory/'diretorio_inexistente')
        self.setup_path.write_text(json.dumps(data))
        report=run_plan(self.path)
        self.assertEqual(report['status'],'failed')
        self.assertEqual(report['errors'][0]['type'],'AgentLoadError')
        self.assertTrue((Path(report['directory'])/'relatorio.json').exists())

    def test_job_keeps_interactive_game_separate_and_recovers_report(self):
        session=self.session();before=session.game.dumps()
        job=ExperimentJob(self.path);job.start();job.worker.join(timeout=10)
        self.assertFalse(job.worker.is_alive())
        self.assertEqual(job.snapshot()['status'],'complete')
        self.assertEqual(before,session.game.dumps())
        recovered=ExperimentJob(self.path).snapshot()
        self.assertEqual(recovered['completed'],8)
        self.assertEqual(recovered['report']['scenarios'][0]['completed'],4)

    def test_refusal_of_known_fact_is_not_a_lie_or_unknown(self):
        session=self.session();game=session.game
        session.agent('02').answer_question=lambda view,q:Answer('RECUSO_RESPONDER')
        session.agent('01').answer_question=lambda view,q:Answer('NÃO_SEI')
        game.initiatives({aid:{'type':'question','question_id':'Q06','recipient':'02' if aid!='02' else '01','parameters':{}}
                         for aid in game.ids})
        metrics=Metrics(session);metrics.advance()
        by_status={key[-1]:n for key,n in metrics.answers.items()}
        self.assertEqual(by_status['recusa_sabe'],4)
        self.assertEqual(by_status['nao_sei_verdadeiro'],1)

    def test_invalid_seed_contract_and_undeclared_randomness(self):
        from carregar_agentes import Implementation
        from agent.humano_random import RandomHuman
        setup=GameSetup.load(self.setup_path)
        registry=load_agents(ROOT/'src/agent')
        class Undeclared(RandomHuman):
            def configure_seed(self,seed):return False
        registry['humano_random']=Implementation('HUMANO',Undeclared)
        seeds={aid:1 for aid in setup.assignment}
        session=setup.start(agent_seeds=seeds,implementations=registry)
        self.assertFalse(session.seed_control['05'])
        metrics=Metrics(session)
        while not session.game.finished:metrics.advance()
        agg=Aggregate('test');agg.add(metrics.record(0,1,0,0))
        self.assertEqual(agg.summary()['uncontrolled_agents'],['05'])
        class BadSeed(RandomHuman):
            def configure_seed(self,seed):return 1
        registry['humano_random']=Implementation('HUMANO',BadSeed)
        with self.assertRaises(AgentContractError):setup.start(agent_seeds=seeds,implementations=registry)
        with self.assertRaises(AgentContractError):setup.start(agent_seeds=['05'])

    def test_variable_crew_and_rounds_are_measured_without_fixed_denominators(self):
        data=json.loads(self.setup_path.read_text())
        data['rodadas']=20;data['tripulantes'][-1]['quantidade']=46
        self.setup_path.write_text(json.dumps(data))
        self.plan['partidas_por_cenario']=1
        self.path.write_text(json.dumps(self.plan))
        report=run_plan(self.path)
        self.assertEqual(report['status'],'complete',report['errors'])
        self.assertEqual([c['completed'] for c in report['scenarios']],[1,1])
        self.assertEqual(report['comparisons'][0]['deltas']['rounds']['mean'],0)
        self.assertEqual(report['comparisons'][0]['deltas']['answers']['mean'],0)
        self.assertEqual(report['effective_setups']['A']['rodadas'],20)
        self.assertIsNone(report['comparisons'][0]['deltas']['seconds']['mean_ci95'])
        total_answers=sum(r['count'] for r in report['scenarios'][0]['answers'])
        self.assertGreater(total_answers,20)
        self.assertEqual(sum(r['count'] for r in report['scenarios'][0]['stages'] if r['kind']=='answer'),total_answers)

    def test_invalid_experiment_plan_does_not_break_interactive_dashboard(self):
        from dashboard import Dashboard
        self.path.write_text('{invalid json')
        dashboard=Dashboard(self.setup_path)
        self.assertEqual(dashboard.observe()['round'],1)
        self.assertEqual(dashboard.experiments.state['status'],'failed')
        with self.assertRaises(ValueError):dashboard.experiments.snapshot()

    def test_early_job_failure_does_not_display_old_success_as_new_result(self):
        from unittest.mock import patch
        run_plan(self.path)
        job=ExperimentJob(self.path)
        with patch('experimentos.run_plan',side_effect=ValueError('Carga de módulo falhou')):
            job.start();job.worker.join(timeout=10)
        state=job.snapshot()
        self.assertEqual(state['status'],'failed')
        self.assertIn('Carga de módulo falhou',state['error'])
        self.assertIsNone(state['report'])
        self.assertEqual(state['completed'],0)

    def test_clear_zeroes_current_series_and_keeps_archived_comparisons(self):
        report=run_plan(self.path,name='Primeiro experimento')
        files={p.name:p.read_bytes() for p in Path(report['directory']).iterdir()}
        job=ExperimentJob(self.path);job.clear()
        state=job.snapshot()
        self.assertEqual(state['completed'],0);self.assertIsNone(state['report'])
        self.assertTrue(all(r['archived'] for r in state['reports']))
        restored=ExperimentJob(self.path).snapshot()
        self.assertEqual(restored['completed'],0);self.assertIsNone(restored['report'])
        selected=job.snapshot(Path(report['directory']).name)
        self.assertEqual(selected['view']['name'],'Primeiro experimento')
        self.assertEqual(selected['view']['completed'],8)
        for name,data in files.items():self.assertEqual((Path(report['directory'])/name).read_bytes(),data)
        comparison=job.compare(Path(report['directory']).name,'A',Path(report['directory']).name,'B')
        self.assertTrue(all(r['delta']==0 for r in comparison['metrics'] if r['metric'] in ('rounds','progress','questions_per_round')))

    def test_new_experiment_after_clear_starts_fresh(self):
        run_plan(self.path,name='Antigo')
        job=ExperimentJob(self.path);job.clear();job.start('Novo');job.worker.join(timeout=10)
        state=job.snapshot()
        self.assertEqual(state['completed'],8)
        self.assertEqual(state['report']['name'],'Novo')
        self.assertEqual(len(state['reports']),2)
        self.assertEqual(sum(r['archived'] for r in state['reports']),1)

    def test_clear_is_blocked_during_running_worker(self):
        import threading
        from unittest.mock import patch
        entered=threading.Event();release=threading.Event();original=run_plan
        def gated(*args,**kwargs):
            entered.set();release.wait(timeout=5);return original(*args,**kwargs)
        job=ExperimentJob(self.path)
        with patch('experimentos.run_plan',side_effect=gated):
            job.start();self.assertTrue(entered.wait(timeout=2))
            try:
                with self.assertRaisesRegex(ValueError,'encerramento'):job.clear()
            finally:release.set();job.worker.join(timeout=10)
        self.assertEqual(job.snapshot()['status'],'complete')

    def test_clear_is_blocked_for_unfinished_external_report(self):
        report=run_plan(self.path)
        report['status']='running'
        (Path(report['directory'])/'relatorio.json').write_text(json.dumps(report))
        job=ExperimentJob(self.path)
        with self.assertRaisesRegex(ValueError,'encerramento'):job.clear()

    def test_historical_comparison_is_segregated_and_descriptive(self):
        first=run_plan(self.path,name='Antes')
        self.plan['cenarios'][0]['alteracoes']={'rodadas':20}
        self.path.write_text(json.dumps(self.plan))
        second=run_plan(self.path,name='Depois')
        job=ExperimentJob(self.path)
        a,b=Path(first['directory']).name,Path(second['directory']).name
        self.assertNotEqual(a,b)
        self.assertEqual(job.snapshot(a)['view']['name'],'Antes')
        comparison=job.compare(a,'A',b,'A')
        self.assertEqual(comparison['setup_a']['rodadas'],10)
        self.assertEqual(comparison['setup_b']['rodadas'],20)
        self.assertEqual(comparison['a']['completed'],4)
        self.assertEqual(comparison['b']['completed'],4)
        for r in comparison['metrics']:
            self.assertAlmostEqual(r['delta'],r['b']-r['a'])
        self.assertNotIn('mean_ci95',comparison)
        for q in {r['question'] for r in comparison['answers']}:
            rows=[r for r in comparison['answers'] if r['question']==q]
            if any(r['a_rate'] is not None for r in rows):self.assertAlmostEqual(sum(r['a_rate'] or 0 for r in rows),1)
        with self.assertRaises(ValueError):job.read_report('../setup.json')
        with self.assertRaises(ValueError):job.compare(a,'inexistente',b,'A')

    def test_clear_does_not_touch_interactive_session_or_checkpoint(self):
        from dashboard import Dashboard
        dashboard=Dashboard(self.setup_path);dashboard.command('save')
        before=dashboard.session.game.dumps();checkpoint=(self.directory/'checkpoint.json').read_bytes()
        run_plan(self.path);dashboard.experiments.clear()
        self.assertEqual(dashboard.session.game.dumps(),before)
        self.assertEqual((self.directory/'checkpoint.json').read_bytes(),checkpoint)

    def test_new_experiment_name_is_validated(self):
        job=ExperimentJob(self.path)
        for name in ('',123,'x'*121):
            with self.assertRaises(ValueError):job.start(name)

    def test_seed_cannot_replace_checkpoint_random_sequence(self):
        session=self.session()
        with self.assertRaises(AgentContractError):
            assign_agents(Game.loads(session.game.dumps()),load_agents(ROOT/'src/agent'),agent_seeds={aid:1 for aid in session.game.ids})

if __name__=='__main__':unittest.main()
