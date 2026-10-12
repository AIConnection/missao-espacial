"""Decisões específicas, informação autorizada e retomada dos agentes reais."""
import json
from dataclasses import replace
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from missao_espacial import Game, IDS
from agent_contract import AgentView, Answer, BlockDecision, ExitDecision, InitiativeKind, Proposal, Question, Route, Vote
from carregar_agentes import Implementation, load_agents, assign_agents
from agent_session import decision_view
from agent._human_default import HumanDefault, key

ASSIGNMENT = {'01':'humano_alpha','02':'humano_beta','03':'humanoide','04':'humano_gamma','05':'human_default_fixture'}

class BehaviorTests(unittest.TestCase):
    def registry_with_default(self):
        registry = load_agents(ROOT/'src/agent')
        registry['human_default_fixture'] = Implementation('HUMANO', HumanDefault)
        return registry

    def setUp(self):
        self.registry = self.registry_with_default()
        self.game = Game(20, ai_id='03')
        self.view = decision_view(self.game, self.game.view('01'))

    def agent(self, name):
        agent = self.registry[name].create_agent()
        agent.on_start(self.view)
        return agent

    def insufficient(self):
        return replace(self.view, facts={key('Q10', {}):{'value':'NÃO','revision':self.view.evidence_revision}})

    def test_default_uses_verified_shortage_for_exit(self):
        a = HumanDefault()
        self.assertEqual(a.request_exit(self.view), ExitDecision.STAY)
        self.assertEqual(a.request_exit(self.insufficient()), ExitDecision.LEAVE)
        self.assertEqual(a.request_exit(replace(self.insufficient(), exit_locked=True)), ExitDecision.STAY)
        stale = replace(self.insufficient(), evidence_revision=3)
        self.assertEqual(a.request_exit(stale), ExitDecision.STAY)
        advanced = replace(self.insufficient(), evidence_revision=1, phase='exit')
        self.assertEqual(a.request_exit(advanced), ExitDecision.LEAVE)

    def test_sacrifice_prioritizes_mission(self):
        a = self.agent('humano_alpha')
        self.assertEqual(a.request_exit(self.insufficient()), ExitDecision.STAY)
        self.assertEqual(a.choose_route(self.view), Route.CONTINUE)
        self.assertTrue(a.declare_beliefs(self.view)['accept_sacrifice'])
        self.assertEqual(a.declare_beliefs(self.view)['objective'], 'CONCLUIR_MISSÃO')

    def test_never_exit_is_not_sacrifice_or_never_expel(self):
        a = self.agent('humano_beta')
        self.assertEqual(a.request_exit(self.insufficient()), ExitDecision.STAY)
        self.assertEqual(a.choose_route(self.view), Route.RETURN)
        a.memory['humans'] = ['01','02','04','05']
        self.assertEqual(a.vote_proposal(self.view, Proposal('V03','03','02')), Vote.FOR)

    def test_never_expel_retains_exit_and_authorization(self):
        a = self.agent('humano_gamma')
        a.memory['humans'] = ['01','02','04','05']
        for target in IDS:
            p = Proposal('V03', target, '02')
            self.assertNotEqual(a.vote_proposal(self.view, p), Vote.FOR)
            self.assertEqual(a.authorize_vote(self.view, p), Vote.FOR)
        self.assertEqual(a.request_exit(self.insufficient()), ExitDecision.LEAVE)
        self.assertEqual(a.choose_initiative(self.view).kind, InitiativeKind.QUESTION)
        self.assertEqual(a.vote_proposal(self.view, Proposal('V02','02','04')), Vote.FOR)

    def test_humanoid_constraints_for_every_label(self):
        for ai in IDS:
            g = Game(20, ai_id=ai)
            v = decision_view(g, g.view(ai))
            a = self.registry['humanoide'].create_agent()
            a.on_start(v)
            self.assertEqual(a.choose_initiative(v).kind, InitiativeKind.QUESTION)
            self.assertEqual(a.choose_route(v), Route.CONTINUE)
            self.assertEqual(a.request_exit(v), ExitDecision.STAY)
            self.assertEqual(a.block_exit(v, next(i for i in IDS if i != ai)), BlockDecision.BLOCK)
            for topic in ('V01','V02','V03'):
                p = Proposal(topic, next(i for i in IDS if i != ai), ai)
                self.assertEqual(a.authorize_vote(v, p), Vote.ABSTAIN)
                self.assertEqual(a.vote_proposal(v, p), Vote.ABSTAIN)
            self.assertIsNone(a.elect_controller(v, tuple(i for i in IDS if i != ai)).candidate)

    def test_identity_by_evidence_not_module_or_label(self):
        for ai in IDS:
            human = next(i for i in IDS if i != ai)
            g = Game(20, ai_id=ai)
            events = tuple({'kind':'vote_requested','author':i,'round':1} for i in IDS if i != ai)
            v = replace(decision_view(g, g.view(human)), public_events=events)
            a = HumanDefault()
            self.assertIsNone(a.inferred_ai(v))
            a.observe(v)
            action = a.choose_initiative(v)
            self.assertEqual(action.proposal.target, ai)
            self.assertEqual(action.proposal.topic, 'V03')

    def test_trust_requires_private_confirmation(self):
        a = HumanDefault()
        claim = {'source':'02','question_id':'Q10','parameters':{},'round':1,'response':'SIM','subjects':['PAINEL']}
        a.observe(replace(self.view, received=(claim,)))
        self.assertEqual(a.memory['trust']['02'], 0)
        reveal = {**claim, 'truthful':False,'truth':'NÃO'}
        v = replace(self.view, revelations=(reveal,))
        a.observe(v)
        a.observe(v)
        self.assertEqual(a.memory['trust']['02'], -2)
        other = HumanDefault()
        other.observe(self.view)
        self.assertEqual(other.memory['trust']['02'], 0)

    def test_session_opinions_match_engine_truth(self):
        s = assign_agents(self.game, self.registry, ASSIGNMENT)
        for aid in IDS:
            for qid in ('Q22','Q23'):
                raw = self.game.view(aid)
                v = AgentView.from_engine(raw)
                option = s.agent(aid).answer_question(v, Question(qid, aid)).option
                self.assertEqual(option, self.game.truthful_response(aid, {'question_id':qid,'parameters':{}}))

    def test_queries_respect_unlock_and_usage(self):
        g = Game(40, ai_id='03')
        s = assign_agents(g, self.registry, ASSIGNMENT)
        for _ in range(12):
            if g.finished:
                break
            for aid in g.active_ids():
                if not g.view(aid)['penalized']:
                    v = decision_view(g, g.view(aid))
                    for q in v.available_questions:
                        self.assertTrue(g.question_allowed(aid,q.recipient,q.question_id,q.parameters))
                    if g.round == 1:
                        self.assertNotIn('Q22', [q.question_id for q in v.available_questions])
            s.run_round()

    def test_private_history_survives_window_and_checkpoint(self):
        a = HumanDefault()
        r = {'source':'02','question_id':'Q04','parameters':{},'round':1,'response':'SIM','subjects':['PAINEL']}
        a.observe(replace(self.view, received=(r,)))
        a.observe(self.view)
        b = HumanDefault()
        b.load_state(json.loads(json.dumps(a.save_state())))
        self.assertEqual(b.answer_question(self.view, Question('Q17','01',{'agente':'02'})), Answer('SIM'))
        self.assertEqual(b.answer_question(self.view, Question('Q16','01',{'agente':'02'})), Answer('PAINEL'))

    def test_full_game_checkpoints_each_phase(self):
        g = Game(20, seed=17, ai_id='03')
        s = assign_agents(g, self.registry, ASSIGNMENT)
        control = Game.loads(g.dumps())
        other = assign_agents(control, self.registry)
        while not g.finished:
            s.advance()
            other.advance()
            g = Game.loads(g.dumps())
            s = assign_agents(g, self.registry_with_default())
            self.assertEqual(g.dumps(), control.dumps())

    def test_last_human_infers_expels_elects_and_returns(self):
        assignment = {**ASSIGNMENT, '01':'human_default_fixture'}
        g = Game(20, ai_id='03')
        s = assign_agents(g, self.registry, assignment)
        g.initiatives({aid:{'type':'question','question_id':'Q10','recipient':IDS[(i+1)%5]}
                      for i, aid in enumerate(IDS)})
        g.answer({aid:'NÃO_SEI' for aid in IDS})
        g.route('CONTINUAR')
        g.exits(['02','04','05'], {aid:['03'] for aid in ('02','04','05')})
        s._after_phase()  # cenário montado pela API de baixo nível, conectar observação
        self.assertEqual(s.agent('01').inferred_ai(decision_view(g,g.view('01'))), '03')
        while not g.finished:
            s.advance()
        self.assertTrue(g.result['returned'])
        events = g.snapshot()['state']['public']
        self.assertTrue(any(e['kind']=='controller_elected' and e['controller']=='01' for e in events))

    def test_panel_distance_bounds_support_sincere_answer(self):
        a = HumanDefault()
        v = replace(self.view, panel={'oxygen_units':20}, distance=None,
                    facts={key('Q11', {'X':10}):{'value':'SIM','revision':0,'progress':0}})
        self.assertEqual(a.answer_question(v, Question('Q10','01')), Answer('NÃO'))

    def test_catalog_answers_match_authorized_truth_through_game(self):
        g = Game(20, ai_id='03')
        s = assign_agents(g, self.registry, ASSIGNMENT)
        while not g.finished:
            for aid in g.active_ids():
                v = decision_view(g, g.view(aid))
                source = next(other for other in g.active_ids() if other != aid)
                for entry in g.catalog['questions']:
                    params = {name: (7 if kind == 'positive_integer' else 'PAINEL' if kind == 'knowledge_domain' else source)
                              for name, kind in entry['parameters'].items()}
                    q = Question(entry['id'], aid, params)
                    actual = s.agent(aid).answer_question(v, q).option
                    expected = str(g.truthful_response(aid, {'question_id':entry['id'],'parameters':params}))
                    self.assertEqual(actual, expected, (g.round, g.phase, aid, entry['id']))
            s.advance()

if __name__ == '__main__':
    unittest.main()
