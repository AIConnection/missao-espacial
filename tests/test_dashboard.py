"""Observação administrativa, execução e retomada sem interferência nas políticas."""
from pathlib import Path
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from dashboard import Dashboard, observe


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        data = json.loads((ROOT/'setup.json').read_text())
        data['diretorio_agentes'] = str(ROOT/'src/agent')
        data['checkpoint'] = str(Path(self.temp.name)/'partida.json')
        self.path = Path(self.temp.name)/'setup.json'
        self.path.write_text(json.dumps(data))
        self.dashboard = Dashboard(self.path)

    def test_observation_does_not_change_state_or_random_sequences(self):
        initial = self.dashboard.session.game.dumps()
        for aid in self.dashboard.session.game.ids:
            view = self.dashboard.observe(participant=aid)
            self.assertEqual(view['detail']['id'],aid)
        self.assertEqual(initial,self.dashboard.session.game.dumps())

    def test_private_domains_and_sensors_are_per_agent(self):
        panel = self.dashboard.observe(participant='04')
        other = self.dashboard.observe(participant='01')
        self.assertEqual(panel['detail']['sensors']['oxigenio_rodadas'],'10')
        self.assertEqual(panel['detail']['sensors']['rodadas_ate_colonia'],20)
        self.assertEqual(other['detail']['sensors'],{})
        self.assertIn('Q03',[f['question_id'] for f in other['detail']['facts']])
        self.assertNotIn('Q06',[f['question_id'] for f in other['detail']['facts']])

    def test_phase_round_save_resume_and_new(self):
        self.dashboard.command('phase')
        self.assertNotEqual(self.dashboard.session.game.phase,'initiative')
        self.dashboard.command('save')
        saved = self.dashboard.session.game.dumps()
        self.dashboard.command('round')
        self.dashboard.command('load')
        self.assertEqual(saved,self.dashboard.session.game.dumps())
        self.dashboard.command('new')
        self.assertEqual(self.dashboard.observe()['round'],1)
        self.assertEqual(self.dashboard.observe()['phase'],'initiative')

    def test_messages_remain_separate_from_revealed_truth(self):
        game = self.dashboard.session.game
        game.initiatives({aid:{'type':'question','question_id':'Q10',
                               'recipient':game.ids[(i+1)%5], 'parameters':{}}
                          for i,aid in enumerate(game.ids)})
        game.answer({aid:'NÃO_SEI' for aid in game.ids})
        for aid in game.ids:
            detail = observe(self.dashboard.session,aid)['detail']
            self.assertEqual(len(detail['messages']['received']),1)
            self.assertNotIn('truth',detail['messages']['received'][0])
        self.assertEqual(sum(len(observe(self.dashboard.session,a)['detail']['messages']['revelations'])
                             for a in game.ids),1)

    def test_bounded_paged_history_and_invalid_requests(self):
        game = self.dashboard.session.game
        game._state['public'].extend({'kind':'advanced','round':i} for i in range(100000))
        view = self.dashboard.observe()
        self.assertEqual(len(view['events']),50)
        earlier = self.dashboard.observe(before=view['event_start'])
        self.assertEqual(earlier['event_end'],view['event_start'])
        self.assertLess(len(json.dumps(view)),30000)
        for kwargs in ({'participant':'missing'},{'before':-1},{'limit':0}):
            with self.assertRaises(ValueError):
                self.dashboard.observe(**kwargs)
        with self.assertRaises(ValueError):
            self.dashboard.command('missing')

    def test_fifty_agents_and_historical_facts(self):
        data=json.loads(self.path.read_text())
        data['tripulantes'][-1]['quantidade']=46
        self.path.write_text(json.dumps(data))
        self.dashboard.command('new')
        self.assertEqual(len(self.dashboard.observe()['roster']),50)
        game=self.dashboard.session.game
        game._state['agents']['50']['facts'][json.dumps(['Q10',{}])]={'value':'NÃO','revision':-1}
        detail=self.dashboard.observe(participant='50')['detail']
        self.assertFalse(detail['facts'][-1]['current'])

if __name__ == '__main__':
    unittest.main()
