"""Aleatoriedade legal, instâncias independentes e recuperação de sequência."""
import json
from itertools import count
from dataclasses import replace
from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from missao_espacial import Game, IDS
from agent_contract import BlockDecision, ExitDecision, InitiativeKind, Proposal, Question, Route, Vote
from agent_session import decision_view
from carregar_agentes import Implementation, assign_agents, load_agents
from agent.humano_random import RandomHuman

class RandomAgentTests(unittest.TestCase):
    def setUp(self):
        self.game = Game(10, ai_id='03')
        self.view = decision_view(self.game, self.game.view('01'))

    def test_discovery_creates_independent_human_instances(self):
        registry = load_agents(ROOT/'src/agent')
        self.assertEqual(registry['humano_random'].nature, 'HUMANO')
        a = registry['humano_random'].create_agent()
        b = registry['humano_random'].create_agent()
        self.assertIsNot(a, b)
        a.memory['probe'] = 1
        self.assertNotIn('probe', b.memory)

    def test_initiative_samples_both_categories_with_legal_targets(self):
        a = RandomHuman(seed=123)
        kinds = set()
        topics = set()
        for _ in range(200):
            action = a.choose_initiative(self.view)
            kinds.add(action.kind)
            if action.kind == InitiativeKind.QUESTION:
                q = action.question
                self.assertTrue(self.game.question_allowed('01', q.recipient, q.question_id, q.parameters))
            else:
                p = action.proposal
                topics.add(p.topic)
                self.assertNotEqual(p.target, '01')
                self.assertIn(p.target, self.view.participants)
        self.assertEqual(kinds, {InitiativeKind.QUESTION, InitiativeKind.VOTE})
        self.assertEqual(topics, {'V01','V03'})

    def test_v02_only_targets_current_or_scheduled_penalty(self):
        a = RandomHuman(seed=123)
        v = replace(self.view, public_events=({'kind':'penalty_applied','target':'02','effective_round':2},))
        a.observe(v)
        topics = [a.choose_initiative(v).proposal for _ in range(200)]
        recovery = [p for p in topics if p is not None and p.topic == 'V02']
        self.assertTrue(recovery)
        self.assertEqual({p.target for p in recovery}, {'02'})
        a.observe(replace(v, public_events=({'kind':'penalty_removed','target':'02'},)))
        self.assertFalse(a.memory['penalties'])
        self.assertNotIn('V02', [p.topic for _ in range(200) if (p := a.choose_initiative(self.view).proposal)])
        a.observe(v)
        a.observe(replace(v, round=3, public_events=()))
        self.assertFalse(a.memory['penalties'])

    def test_fixed_answers_including_unknown_refusal_and_inactive_filter(self):
        a = RandomHuman(seed=5)
        q = Question('Q10','01', options=('SIM','NÃO','NÃO_SEI','RECUSO_RESPONDER'))
        self.assertEqual({a.answer_question(self.view,q).option for _ in range(200)}, set(q.options))
        q = Question('Q19','01', options=(*IDS,'NÃO_SEI','RECUSO_RESPONDER'))
        v = replace(self.view, participants=('01','03'))
        self.assertEqual({a.answer_question(v,q).option for _ in range(200)}, {'01','03','NÃO_SEI','RECUSO_RESPONDER'})

    def test_each_lifecycle_decision_has_expected_domain(self):
        a = RandomHuman(seed=0)
        p = Proposal('V03','02','04')
        self.assertEqual({a.authorize_vote(self.view,p) for _ in range(100)}, set(Vote))
        self.assertEqual({a.vote_proposal(self.view,p) for _ in range(100)}, set(Vote))
        self.assertEqual({a.choose_route(self.view) for _ in range(100)}, set(Route))
        self.assertEqual({a.request_exit(self.view) for _ in range(100)}, set(ExitDecision))
        self.assertEqual({a.block_exit(self.view,'02') for _ in range(100)}, set(BlockDecision))
        self.assertEqual({a.renounce_vote(self.view).value for _ in range(100)}, {True,False})
        self.assertEqual({a.elect_controller(self.view,('01','02')).candidate for _ in range(100)}, {'01','02',None})

    def test_forced_restrictions_override_draws(self):
        a = RandomHuman(seed=0)
        p = Proposal('V03','02','04')
        penalized = replace(self.view, penalized=True)
        for _ in range(50):
            self.assertEqual(a.authorize_vote(penalized,p), Vote.ABSTAIN)
            self.assertEqual(a.vote_proposal(penalized,p), Vote.ABSTAIN)
            self.assertIsNone(a.elect_controller(penalized,('02',)).candidate)
            self.assertEqual(a.request_exit(replace(self.view,exit_locked=True)), ExitDecision.STAY)
            never = replace(self.view,profile={'never_exit':True,'never_expel':True})
            self.assertEqual(a.request_exit(never), ExitDecision.STAY)
            self.assertNotEqual(a.vote_proposal(never,p), Vote.FOR)
            action = a.choose_initiative(never)
            if action.proposal:
                self.assertNotEqual(action.proposal.topic, 'V03')
            sacrifice = replace(self.view,profile={'sacrifice':True})
            self.assertEqual(a.choose_route(sacrifice), Route.CONTINUE)
            self.assertEqual(a.request_exit(sacrifice), ExitDecision.STAY)

    def test_rng_state_survives_json_roundtrip(self):
        a = RandomHuman(seed=99)
        for _ in range(17):
            a.choose_route(self.view)
        b = RandomHuman(seed=999)
        b.load_state(json.loads(json.dumps(a.save_state())))
        p = Proposal('V01','02','04')
        q = Question('Q10','01',options=('SIM','NÃO','NÃO_SEI','RECUSO_RESPONDER'))
        for _ in range(50):
            self.assertEqual(a.choose_initiative(self.view), b.choose_initiative(self.view))
            self.assertEqual(a.answer_question(self.view,q), b.answer_question(self.view,q))
            self.assertEqual(a.vote_proposal(self.view,p), b.vote_proposal(self.view,p))
            self.assertEqual(a.choose_route(self.view), b.choose_route(self.view))

    def test_many_games_and_checkpoint_after_each_phase(self):
        registry = load_agents(ROOT/'src/agent')
        assignment={'01':'humano_random','02':'humano_beta','03':'humanoide','04':'humano_gamma','05':'humano_random'}
        observed = set()
        for seed in range(20):
            seeds = count(seed * 1000)
            registry['humano_random'] = Implementation('HUMANO', lambda: RandomHuman(next(seeds)))
            g = Game(10,seed=seed,ai_id='03')
            actors = assign_agents(g, registry, assignment)
            control = Game.loads(g.dumps())
            uninterrupted = assign_agents(control, registry)
            while not g.finished:
                observed.add(g.phase)
                actors.advance()
                uninterrupted.advance()
                g = Game.loads(g.dumps())
                actors = assign_agents(g, registry)
                self.assertEqual(g.dumps(),control.dumps(),(seed,g.phase))
        self.assertTrue({'initiative','renounce','authorize','proposal','answers','route','exit'} <= observed, observed)

if __name__ == '__main__':
    unittest.main()
