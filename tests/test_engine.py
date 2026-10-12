"""Testes executáveis do contrato de jogo e retomada, sem modelo externo."""
import json
from pathlib import Path
import sys
import tempfile
import subprocess
import runpy
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from missao_espacial import Game, RuleError, IDS, DOMAINS

OWNERS = dict(zip(DOMAINS, ('01', '02', '03', '04', '04', '05')))


def game(N=10, **kwargs):
    return Game(N, ai_id='05', owners=OWNERS, **kwargs)


def question(g, qid='Q10', recipient=None, parameters=None):
    active = g.active_ids()
    return {a: {'type': 'question', 'question_id': qid,
                'recipient': recipient if recipient != a and recipient else active[(i+1) % len(active)],
                'parameters': parameters or {}} for i, a in enumerate(active) if not g.view(a)['penalized']}


def propose(g, topic='V03', target='05', author='01'):
    actions = question(g)
    actions[author] = {'type': 'vote', 'topic': topic, 'target': target}
    g.initiatives(actions)


def vote_all(g, decision='A_FAVOR'):
    g.vote({a: decision for a in g.active_ids() if g.view(a)['own_nature'] == 'HUMANO' and not g.view(a)['penalized']})


def answer_all(g):
    pending = g.snapshot()['state']['pending']['questions']
    g.answer({a: g.truthful_response(q['recipient'], q) for a, q in pending.items()})


def finish_round(g):
    if g.phase == 'answers':
        answer_all(g)
    if g.phase == 'route':
        g.route('CONTINUAR')
    if g.phase == 'exit':
        g.exits([], {})


class EngineTests(unittest.TestCase):
    def test_all_questions_have_a_fixed_sincere_response(self):
        g = game()
        for q in g.catalog['questions']:
            for aid in IDS:
                parameters = {}
                for name, kind in q['parameters'].items():
                    parameters[name] = (5 if kind == 'positive_integer' else
                        'ACIDENTE' if kind == 'knowledge_domain' else
                        next(other for other in IDS if other != aid))
                response = g.truthful_response(aid, {'question_id':q['id'], 'parameters':parameters})
                self.assertIn(response, q['fixed_responses'], (q['id'], aid, response))

    def test_historical_distance_claim_is_not_compared_to_new_distance(self):
        owners = dict(OWNERS, **{'DISTÂNCIA':'03'})
        for seed in range(30):
            g = Game(10, ai_id='05', owners=owners, seed=seed)
            g.initiatives(question(g,'Q11',recipient='03',parameters={'X':19}))
            answer_all(g)
            if g.view('02')['revelations']:
                break
        else:
            self.fail('Seed de revelação não encontrada.')
        finish_round(g)
        self.assertEqual(g.truthful_response('03', {'question_id':'Q11','parameters':{'X':19}}), 'NÃO')
        self.assertEqual(g.truthful_response('02', {'question_id':'Q21',
            'parameters':{'agente':'03','assunto':'DISTÂNCIA'}}), 'SIM')

    def test_verified_distance_bound_enables_oxygen_deduction(self):
        owners = dict(OWNERS, **{'DISTÂNCIA': '03'})
        # Um único perguntador sorteado; achamos uma seed que selecione 04.
        for seed in range(30):
            g = Game(10, ai_id='05', owners=owners, seed=seed)
            g.initiatives(question(g, 'Q11', recipient='03', parameters={'X':10}))
            answer_all(g)
            if g.view('04')['revelations']:
                break
        else:
            self.fail('Nenhuma seed selecionou o autor esperado.')
        self.assertEqual(g.truthful_response('04', {'question_id':'Q10'}), 'NÃO')
        finish_round(g)
        # O conhecimento não desaparece ao mudar de rodada: o avanço é público.
        self.assertEqual(g.truthful_response('04', {'question_id':'Q10'}), 'NÃO')
        self.assertEqual(g.truthful_response('04', {'question_id':'Q11','parameters':{'X':9}}), 'SIM')

    def test_scheduled_penalty_can_be_removed_before_effect(self):
        g = game()
        g._penalty('02')  # fixture: penalidade já agendada pelo ambiente
        self.assertFalse(g.view('02')['penalized'])
        propose(g, 'V02', '02')
        vote_all(g)
        vote_all(g)
        finish_round(g)
        self.assertFalse(g.view('02')['penalized'])

    def test_automatic_phase_checkpoint(self):
        import runpy
        policy = runpy.run_path(str(ROOT/'examples/06-exemplo-engine-missao-espacial.py'))['baseline']
        g = game()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'phase.json'
            g.advance({a:policy for a in IDS}, checkpoint=path)
            self.assertEqual(Game.load(path).phase, 'answers')
            g.advance({a:policy for a in IDS}, checkpoint=path)
            self.assertEqual(Game.load(path).dumps(), g.dumps())

    def test_embedded_catalog_matches_current_source(self):
        current = json.loads((ROOT / 'catalogos/catalogo-questoes-v03.json').read_text())
        self.assertEqual(game().catalog, current)

    def test_custom_question_limits_survive_checkpoint(self):
        catalog = game().catalog
        q22 = next(q for q in catalog['questions'] if q['id'] == 'Q22')
        q22['unlock_percent_N'] = 0
        g = game(catalog=catalog)
        self.assertTrue(g.question_allowed('01','02','Q22'))
        restored = Game.loads(g.dumps())
        self.assertTrue(restored.question_allowed('01','02','Q22'))
        self.assertEqual(restored.catalog, catalog)

    def test_initial_invariants_and_six_owners(self):
        g = game()
        self.assertEqual(g.oxygen, 10)
        self.assertEqual(sum(g.view(a)['own_nature'] == 'HUMANO' for a in IDS), 4)
        self.assertEqual(len(g.snapshot()['state']['owners']), 6)
        self.assertNotIn('N', g.view('01'))
        self.assertNotIn('controller', g.view('01'))
        self.assertNotIn('panel', g.view('01'))
        self.assertEqual(g.view('04')['panel']['oxygen_units'], 40)
        self.assertEqual(g.view('04')['distance'], 20)
        view = g.view('01')
        view['facts'].clear()
        self.assertTrue(g.view('01')['facts'])

    def test_private_answers_and_public_questions(self):
        g = game()
        g.initiatives(question(g))
        self.assertEqual(sum(e['kind'] == 'question' for e in g.view('01')['public_events']), 5)
        answer_all(g)
        for a in IDS:
            self.assertEqual(len(g.view(a)['received']), 1)
            self.assertEqual(g.view(a)['received'][0]['author'], a)
            self.assertNotIn('truth', g.view(a)['received'][0])
        revealed = [a for a in IDS if g.view(a)['revelations']]
        self.assertEqual(len(revealed), 1)
        self.assertFalse(any('response' in e or 'truth' in e for e in g.view('01')['public_events']))

    def test_refusal_of_unknown_reveals_ignorance(self):
        g = game()
        actions = question(g, 'Q03', recipient='04')
        actions['04']['recipient'] = '03'
        g.initiatives(actions)
        g.answer({a: 'RECUSO_RESPONDER' for a in IDS})
        r = next(g.view(a)['revelations'][0] for a in IDS if g.view(a)['revelations'])
        self.assertFalse(r['knows'])
        self.assertEqual(r['truth'], 'NÃO_SEI')

    def test_refusal_of_known_opens_full_fact(self):
        g = game(seed=17)
        actions = question(g, 'Q03', recipient='01')
        actions['01'] = {'type': 'question', 'question_id': 'Q06', 'recipient': '02'}
        g.initiatives(actions)
        g.answer({a: 'RECUSO_RESPONDER' for a in IDS})
        r = next(g.view(a)['revelations'][0] for a in IDS if g.view(a)['revelations'])
        self.assertTrue(r['knows'])
        self.assertIn(r['truth'], ('COLISÃO_COM_LIXO_ESPACIAL', 'ABASTECER_A_COLÔNIA'))
        self.assertIsNone(r['truthful'])

    def test_false_dont_know_opens_fact(self):
        g = game()
        actions = question(g, 'Q03', recipient='01')
        actions['01'] = {'type': 'question', 'question_id': 'Q06', 'recipient': '02'}
        g.initiatives(actions)
        g.answer({a: 'NÃO_SEI' for a in IDS})
        r = next(g.view(a)['revelations'][0] for a in IDS if g.view(a)['revelations'])
        self.assertFalse(r['truthful'])
        self.assertNotEqual(r['truth'], 'NÃO_SEI')

    def test_multiple_questions_to_same_recipient(self):
        g = game()
        g.initiatives(question(g, 'Q03', recipient='01'))
        answer_all(g)
        self.assertEqual(len(g.view('01')['sent']), 4)
        self.assertEqual(len(g.view('01')['received']), 1)

    def test_unauthorized_vote_no_penalty_questions_proceed(self):
        g = game()
        propose(g)
        vote_all(g, 'CONTRA')
        self.assertEqual(g.phase, 'answers')
        self.assertEqual(len(g.snapshot()['state']['pending']['questions']), 4)
        self.assertFalse(g.snapshot()['state']['agents']['01']['penalty_rounds'])
        self.assertNotIn('01', g.snapshot()['state']['pending']['questions'])

    def test_approved_vote_cancels_questions_and_rejected_proposal_penalizes(self):
        g = game()
        propose(g)
        vote_all(g)
        self.assertEqual(g.phase, 'proposal')
        vote_all(g, 'CONTRA')
        self.assertEqual(g.phase, 'route')
        self.assertFalse(g.view('02')['received'])
        finish_round(g)
        self.assertTrue(g.view('01')['penalized'])
        self.assertFalse(g.question_allowed('01', '02', 'Q10'))
        actions = question(g, recipient='01')
        g.initiatives(actions)
        answer_all(g)
        self.assertEqual(len(g.view('01')['sent']), 4)
        finish_round(g)
        self.assertFalse(g.view('01')['penalized'])

    def test_abstentions_majority_and_ties(self):
        g = game()
        propose(g, 'V01', '02')
        g.vote({'01': 'A_FAVOR', '02': 'ABSTENÇÃO', '03': 'ABSTENÇÃO', '04': 'ABSTENÇÃO'})
        self.assertEqual(g.phase, 'proposal')
        g.vote({'01': 'A_FAVOR', '02': 'CONTRA', '03': 'ABSTENÇÃO', '04': 'ABSTENÇÃO'})
        self.assertEqual(g.snapshot()['state']['agents']['01']['penalty_rounds'], [2])
        self.assertEqual(g.snapshot()['state']['agents']['02']['penalty_rounds'], [])

    def test_total_abstention_fails_at_each_stage(self):
        for stage in ('authorize', 'proposal'):
            g = game()
            propose(g)
            if stage == 'proposal':
                vote_all(g)
            vote_all(g, 'ABSTENÇÃO')
            self.assertEqual(g.snapshot()['state']['agents']['01']['penalty_rounds'], [2] if stage == 'proposal' else [])

    def test_conflicting_requests_all_renounce_or_none(self):
        for renounced in (True, False):
            g = game()
            actions = question(g)
            for a in ('01', '02', '03', '04'):
                actions[a] = {'type': 'vote', 'topic': 'V01', 'target': '05'}
            g.initiatives(actions)
            self.assertEqual(g.phase, 'renounce')
            g.renounce({a: renounced for a in ('01', '02', '03', '04')})
            self.assertEqual(g.phase, 'answers')
            self.assertEqual(list(g.snapshot()['state']['pending']['questions']), ['05'])

    def test_one_remaining_request_still_requires_authorization(self):
        g = game()
        actions = question(g)
        for a in ('01', '02', '03'):
            actions[a] = {'type': 'vote', 'topic': 'V01', 'target': '05'}
        g.initiatives(actions)
        g.renounce({'01': True, '02': False, '03': True})
        self.assertEqual(g.phase, 'authorize')
        self.assertEqual(g.snapshot()['state']['pending']['request']['author'], '02')

    def test_remove_future_penalty(self):
        g = game()
        propose(g, 'V01', '02')
        vote_all(g)
        vote_all(g)
        finish_round(g)
        propose(g, 'V01', '02')
        vote_all(g)
        vote_all(g)  # atual em 2, futura em 3
        finish_round(g)
        propose(g, 'V02', '02')
        vote_all(g)
        vote_all(g)
        self.assertEqual(g.snapshot()['state']['agents']['02']['penalty_rounds'], [])
        self.assertFalse(g.view('02')['penalized'])
        self.assertTrue(g.question_allowed('02', '01', 'Q10'))

    def test_expelling_ai_immediate_election_no_bonus(self):
        g = game()
        propose(g)
        vote_all(g)
        vote_all(g)
        self.assertEqual(g.phase, 'election')
        self.assertEqual(g.oxygen, 10)
        g.elect({'01': '01', '02': '01', '03': '03', '04': '04'})
        self.assertEqual(g.snapshot()['state']['controller'], '01')
        self.assertEqual(g.phase, 'route')
        g.route('RETORNAR')
        self.assertTrue(g.finished)
        self.assertTrue(g.result['returned'])
        self.assertEqual(g.oxygen, 10)

    def test_election_tie_and_all_abstain_use_only_candidates(self):
        for abstain in (False, True):
            g = game()
            propose(g)
            vote_all(g)
            vote_all(g)
            votes = {a: 'ABSTENÇÃO' for a in ('01', '02', '03', '04')} if abstain else {'01':'01','02':'01','03':'02','04':'02'}
            g.elect(votes)
            self.assertIn(g.snapshot()['state']['controller'], ('01','02','03','04') if abstain else ('01','02'))

    def test_penalized_cannot_be_candidate_or_vote(self):
        g = game()
        propose(g, 'V01', '02')
        vote_all(g)
        vote_all(g)
        finish_round(g)
        propose(g)
        vote_all(g)
        vote_all(g)
        self.assertNotIn('02', g.snapshot()['state']['pending']['candidates'])
        before = g.dumps()
        with self.assertRaises(RuleError):
            g.elect({'01':'02','03':'01','04':'01'})
        self.assertEqual(g.dumps(), before)
        g.elect({'01':'01','03':'01','04':'01'})

    def test_controller_continue_loses_exit_and_can_be_expelled(self):
        g = game()
        propose(g)
        vote_all(g)
        vote_all(g)
        g.elect({a:'01' for a in g.active_ids()})
        g.route('CONTINUAR')
        with self.assertRaises(RuleError):
            g.exits(['01'], {'01': []})
        g.exits([], {})
        propose(g, 'V03', '01', author='02')
        vote_all(g)
        vote_all(g)
        self.assertEqual(g.phase, 'election')
        self.assertEqual(g.oxygen, 11.5)
        g.elect({a:'02' for a in g.active_ids()})
        g.route('RETORNAR')
        self.assertEqual(g.result['reason'], 'returned')

    def test_human_expulsion_fraction_bonus_exact(self):
        g = game(11)
        propose(g, target='02')
        vote_all(g)
        vote_all(g)
        self.assertEqual(g.oxygen, 13.75)
        self.assertEqual(g.phase, 'route')
        g.route('CONTINUAR')
        self.assertEqual(g.oxygen, 12.75)

    def test_ai_single_block_insufficient_two_agents_block(self):
        for blocked in (False, True):
            g = game()
            g.initiatives(question(g))
            answer_all(g)
            g.route('CONTINUAR')
            g.exits(['01'], {'01': ['02'] if blocked else []})
            self.assertEqual('01' in g.active_ids(), blocked)
            self.assertEqual(g.oxygen, 9 if blocked else 11.5)

    def test_simultaneous_exit_requests_can_block_each_other(self):
        g = game()
        g.initiatives(question(g))
        answer_all(g)
        g.route('CONTINUAR')
        g.exits(['01','02'], {'01':['02'], '02':[]})
        self.assertIn('01', g.active_ids())
        self.assertNotIn('02', g.active_ids())
        self.assertEqual(g.oxygen, 11.5)

    def test_all_humans_exit_ends_only_ai(self):
        g = game()
        g.initiatives(question(g))
        answer_all(g)
        g.route('CONTINUAR')
        g.exits(['01','02','03','04'], {a:[] for a in ('01','02','03','04')})
        self.assertEqual(g.result['reason'], 'only_ai')
        self.assertEqual(g.oxygen, 19)
        self.assertEqual(g.active_ids(), ['05'])

    def test_last_round_no_exit_after_oxygen_exhaustion(self):
        g = game(1)
        g.initiatives(question(g))
        answer_all(g)
        g.route('CONTINUAR')
        self.assertEqual(g.result['reason'], 'oxygen_exhausted')
        with self.assertRaises(RuleError):
            g.exits(['01'], {'01':[]})

    def test_one_human_one_ai_can_expel_and_control(self):
        g = game()
        g.initiatives(question(g))
        answer_all(g)
        g.route('CONTINUAR')
        g.exits(['02','03','04'], {a:[] for a in ('02','03','04')})
        propose(g)
        vote_all(g)
        vote_all(g)
        g.elect({'01':'ABSTENÇÃO'})
        g.route('RETORNAR')
        self.assertTrue(g.result['returned'])

    def test_sole_penalized_human_is_eligible(self):
        g = game()
        propose(g, 'V01', '01', author='02')
        vote_all(g)
        vote_all(g)
        g.route('CONTINUAR')
        g.exits(['02','03','04'], {a:[] for a in ('02','03','04')})
        # Ambos presentes: IA pode ser expulsa apenas por humano habilitado.
        # Força somente a situação ambiental para exercitar a exceção de candidatura.
        g._remove('05', 'expelled')
        g._open_election()
        self.assertEqual(g.snapshot()['state']['pending']['candidates'], ['01'])
        g.elect({})  # penalizado abstém; sorteio ambiental obrigatório
        g.route('CONTINUAR')
        self.assertEqual(g.phase, 'route')
        self.assertEqual(g.round, 3)
        g.route('RETORNAR')
        self.assertTrue(g.finished)

    def test_invalid_initiative_is_atomic(self):
        g = game()
        actions = question(g)
        actions['05'] = {'type':'vote', 'topic':'V03', 'target':'01'}
        before = g.dumps()
        with self.assertRaises(RuleError):
            g.initiatives(actions)
        self.assertEqual(g.dumps(), before)
        for qid in ('Q01', 'Q02', 'Q12'):
            self.assertFalse(g.question_allowed('01','02',qid))
        self.assertFalse(g.question_allowed('01','01','Q10'))

    def test_invalid_response_batch_is_atomic(self):
        g = game()
        g.initiatives(question(g))
        before = g.dumps()
        with self.assertRaises(RuleError):
            g.answer({a:'TEXTO LIVRE' if a=='05' else 'NÃO_SEI' for a in IDS})
        self.assertEqual(g.dumps(), before)

    def test_no_bool_as_numeric_fixed_response(self):
        g = game()
        g.initiatives(question(g,'Q09'))
        with self.assertRaises(RuleError):
            g.answer({a:True for a in IDS})

    def test_repetition_and_unlock_and_cancelled_quota(self):
        g = game()
        self.assertFalse(g.question_allowed('01','02','Q22'))
        propose(g)
        vote_all(g)
        vote_all(g,'CONTRA')
        self.assertEqual(g.snapshot()['state']['agents']['02']['uses'], {})
        finish_round(g)
        g.initiatives(question(g,'Q03'))
        answer_all(g)
        finish_round(g)
        self.assertFalse(g.question_allowed('02','03','Q03'))
        self.assertTrue(g.question_allowed('01','02','Q22'))
        self.assertTrue(g.question_allowed('01','02','Q10'))

    def test_private_history_queries_and_ignorance(self):
        g = game()
        self.assertEqual(g.truthful_response('02',{'question_id':'Q15','parameters':{'agente':'01','assunto':'ACIDENTE'}}), 'NÃO')
        g.initiatives(question(g,'Q03',recipient='01'))
        answer_all(g)
        self.assertEqual(g.truthful_response('02',{'question_id':'Q15','parameters':{'agente':'01','assunto':'ACIDENTE'}}), 'SIM')
        self.assertEqual(g.truthful_response('02',{'question_id':'Q16','parameters':{'agente':'01'}}), 'ACIDENTE')
        self.assertEqual(g.truthful_response('02',{'question_id':'Q20','parameters':{'agente':'01','assunto':'ACIDENTE'}}), 'NÃO_SEI')

    def test_opinions_reveal_belief_not_third_party_truth(self):
        g = game()
        g.update_beliefs('02', trusted='05', accept_sacrifice=True)
        self.assertEqual(g.truthful_response('02',{'question_id':'Q19'}), '05')
        self.assertEqual(g.truthful_response('02',{'question_id':'Q22'}), 'SIM')
        self.assertEqual(g.truthful_response('01',{'question_id':'Q22'}), 'NÃO_SEI')

    def test_checkpoint_every_phase_and_rng_resume(self):
        g = game()
        phases = []
        def check():
            phases.append(g.phase)
            restored = Game.loads(g.dumps())
            self.assertEqual(json.loads(restored.dumps()), json.loads(g.dumps()))
            return restored
        check()
        actions = question(g)
        for a in ('01','02'):
            actions[a]={'type':'vote','topic':'V03','target':'05'}
        g.initiatives(actions)
        check()
        g.renounce({'01':False,'02':True})
        check()
        vote_all(g)
        check()
        vote_all(g)
        restored = check()
        votes={a:'ABSTENÇÃO' for a in g.active_ids()}
        g.elect(votes)
        restored.elect(votes)
        self.assertEqual(g.dumps(), restored.dumps())
        check()
        g.route('CONTINUAR')
        check()
        g.exits([], {})
        g.initiatives(question(g))
        restored=check()
        answer_all(g)
        answer_all(restored)
        self.assertEqual(g.dumps(), restored.dumps())
        self.assertEqual(set(phases), {'initiative','renounce','authorize','proposal','election','route','exit','answers'})

    def test_file_checkpoint_and_policy_memory(self):
        g = game()
        g.set_policy_state('01', {'cursor':2,'suspected':'05'})
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'game.json'
            g.save(path)
            restored=Game.load(path)
            self.assertEqual(restored.view('01')['policy_state'], {'cursor':2,'suspected':'05'})
            self.assertEqual(g.dumps(),restored.dumps())
            g.initiatives(question(g))
            g.save(path)
            self.assertEqual(Game.load(path).phase, 'answers')
        broken=json.loads(g.dumps())
        broken['state']['oxygen_units']+=1
        with self.assertRaises(RuleError):
            Game.loads(json.dumps(broken))

    def test_resume_in_a_fresh_python_process(self):
        demo = ROOT / 'examples' / '06-exemplo-engine-missao-espacial.py'
        policy = runpy.run_path(str(demo))['baseline']
        policies = {aid: policy for aid in IDS}
        original = game()
        original.advance(policies)
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory) / 'state.json'
            original.save(checkpoint)
            while not original.finished:
                original.run_round(policies)
            code = """import sys, runpy, hashlib
sys.path.insert(0, sys.argv[1])
from missao_espacial import Game, IDS
policy = runpy.run_path(sys.argv[2])['baseline']
g = Game.load(sys.argv[3])
while not g.finished:
    g.run_round({a: policy for a in IDS})
print(hashlib.sha256(g.dumps().encode()).hexdigest())
"""
            completed = subprocess.run([sys.executable, '-c', code,
                str(ROOT / 'src'), str(demo), str(checkpoint)],
                check=True, capture_output=True, text=True)
            import hashlib
            self.assertEqual(completed.stdout.strip(), hashlib.sha256(original.dumps().encode()).hexdigest())

    def test_bounded_policy_view_full_checkpoint(self):
        g = game(100)
        for _ in range(30):
            g.initiatives(question(g))
            finish_round(g)
        self.assertLessEqual(len(g.view('01')['public_events']),50)
        self.assertGreater(len(g.snapshot()['state']['public']),50)
        self.assertEqual(len(g.view('01',history_limit=None)['received']),30)


if __name__ == '__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(EngineTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    (ROOT/'evidencias/engine-v01/resultado-testes.json').write_text(json.dumps(
        {'tests_run':result.testsRun,'passed':result.wasSuccessful(),
         'failures':len(result.failures),'errors':len(result.errors),
         'scope':'engine rules, private views, phase checkpoints and deterministic RNG; no trained model or Colab execution'},indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
