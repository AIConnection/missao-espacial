"""Setup único, tripulações variáveis, aritmética exata e regras proporcionais."""
from fractions import Fraction
from itertools import count
from pathlib import Path
import ast
import json
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from missao_espacial import Game, DOMAINS, RuleError
from setup_jogo import GameSetup, SetupError
from carregar_agentes import Implementation, assign_agents, load_agents
from agent_contract import Initiative, Question
from agent_session import decision_view
from agent._baseline import BaselineAgent
from agent._human_default import HumanDefault
from agent.humano_random import RandomHuman


def configuration(crew=5, rounds=10):
    data = json.loads((ROOT/'setup.json').read_text())
    data['rodadas'] = rounds
    data['tripulantes'] = [
        {'quantidade':1,'papel':'IA','implementacao':'humanoide'},
        {'quantidade':crew-1,'papel':'HUMANO','implementacao':'humano_random'},
    ]
    ids = tuple(f'{i:02d}' for i in range(1,crew+1))
    data['conhecimentos'] = {domain:ids[i%crew] for i,domain in enumerate(DOMAINS)}
    return data


def game(crew=5, rounds=10):
    setup = GameSetup.from_dict(configuration(crew,rounds),base_directory=ROOT)
    return Game(rounds,participant_ids=tuple(setup.assignment),ai_id='01',owners=setup.owners)


def questions(g, requester=None, topic='V01', target='03'):
    active = g.active_ids()
    actions = {aid:{'type':'question','question_id':'Q10','recipient':active[(i+1)%len(active)]}
               for i,aid in enumerate(active) if not g.view(aid)['penalized']}
    if requester:
        actions[requester] = {'type':'vote','topic':topic,'target':target}
    g.initiatives(actions)


def exit_phase(g):
    questions(g)
    g.answer({author:'NÃO_SEI' for author in g._state['pending']['questions']})
    g.route('CONTINUAR')


class SetupTests(unittest.TestCase):
    def test_default_file_is_single_entry_point(self):
        setup = GameSetup.load(ROOT/'setup.json')
        actors = setup.start()
        self.assertEqual(len(actors.game.ids),sum(g['quantidade'] for g in json.loads((ROOT/'setup.json').read_text())['tripulantes']))
        self.assertEqual(actors.assignment,setup.assignment)
        self.assertEqual(actors.game._state['N'],setup.rounds)
        self.assertEqual(actors.game._state['owners'],setup.owners)
        self.assertEqual(setup.checkpoint,ROOT/json.loads((ROOT/'setup.json').read_text())['checkpoint'])
        self.assertEqual(setup.summary()['minimo_bloqueadores_saida'],2)

    def test_requested_sizes_and_round_counts(self):
        for crew in (5,10,15,50):
            for n in (10,20,50,100000):
                setup = GameSetup.from_dict(configuration(crew,n),base_directory=ROOT)
                actors = setup.start()
                g = actors.game
                self.assertEqual(len(g.ids),crew)
                self.assertEqual(g.initial_humans,crew-1)
                self.assertEqual(g.oxygen,n)
                self.assertEqual(setup.summary()['rodadas_ate_colonia'],2*n)
                self.assertEqual(setup.summary()['bonus_por_humano_removido'],f'{n}/{crew-1} rodadas')
                self.assertEqual(g.catalog['response_sets']['I'],list(g.ids))
                self.assertEqual(g.view(g.ids[0])['initial_humans'],crew-1)
                self.assertEqual(len({id(actors.agent(aid)) for aid in g.ids}),crew)

    def test_roles_knowledge_and_profile_are_explicit(self):
        cfg=configuration()
        cfg['tripulantes'][1]['perfil']={'never_exit':True,'never_expel':True}
        setup=GameSetup.from_dict(cfg,base_directory=ROOT)
        actors=setup.start()
        self.assertEqual(actors.game.view('02')['profile'],cfg['tripulantes'][1]['perfil'])
        self.assertEqual(actors.game.view('01')['own_nature'],'IA')
        self.assertEqual(actors.game.view('02')['own_nature'],'HUMANO')
        self.assertNotIn('assignment',actors.game.view('02'))
        self.assertNotIn('owners',actors.game.view('02'))
        cfg['tripulantes'][0]['implementacao']='humano_random'
        with self.assertRaises(ValueError):
            GameSetup.from_dict(cfg,base_directory=ROOT).start()

    def test_invalid_configurations_are_rejected(self):
        changes=[('rodadas',0),('rodadas',True),('seed','17'),('checkpoint',''),('tripulantes',[]),('conhecimentos',{})]
        for field,value in changes:
            cfg=configuration()
            cfg[field]=value
            with self.assertRaises(SetupError,msg=(field,value)):
                GameSetup.from_dict(cfg,base_directory=ROOT)
        for amount in (0,-1,True,1.5):
            cfg=configuration()
            cfg['tripulantes'][1]['quantidade']=amount
            with self.assertRaises(SetupError):
                GameSetup.from_dict(cfg,base_directory=ROOT)
        for role in ('OUTRO',None):
            cfg=configuration()
            cfg['tripulantes'][0]['papel']=role
            with self.assertRaises(SetupError):
                GameSetup.from_dict(cfg,base_directory=ROOT)
        cfg=configuration()
        cfg['tripulantes'][0]['quantidade']=2
        with self.assertRaises(SetupError):
            GameSetup.from_dict(cfg,base_directory=ROOT)
        cfg=configuration()
        cfg['conhecimentos']['CRISE']='99'
        with self.assertRaises(SetupError):
            GameSetup.from_dict(cfg,base_directory=ROOT)

    def test_relative_paths_follow_file_not_working_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'setup.json'
            p.write_text(json.dumps(configuration()))
            setup=GameSetup.load(p)
            self.assertEqual(setup.agent_directory,(Path(directory)/'src/agent').resolve())
            self.assertEqual(setup.checkpoint,(Path(directory)/configuration()['checkpoint']).resolve())

    def test_library_can_have_fifty_different_implementations(self):
        with tempfile.TemporaryDirectory() as directory:
            for i in range(50):
                role='IA' if i==17 else 'HUMANO'
                (Path(directory)/f'policy_{i}.py').write_text(
                    f'NATURE={role!r}\nfrom agent._baseline import BaselineAgent\ndef create_agent(): return BaselineAgent()\n')
            cfg=configuration(50)
            cfg['diretorio_agentes']=directory
            cfg['tripulantes']=[{'quantidade':1,'papel':'IA' if i==17 else 'HUMANO','implementacao':f'policy_{i}'} for i in range(50)]
            actors=GameSetup.from_dict(cfg,base_directory=ROOT).start()
            self.assertEqual(len(load_agents(directory)),50)
            self.assertEqual(len(actors.assignment),50)
            self.assertEqual(actors.game.view('18')['own_nature'],'IA')

    def test_oxygen_bonus_is_exact_and_initial_divisor_never_changes(self):
        for crew in (2,5,10,15,50):
            g=game(crew)
            exit_phase(g)
            g.exits(['02'],{'02':['01']})
            self.assertEqual(g.oxygen,Fraction(9)+Fraction(10,crew-1))
            self.assertEqual(g.initial_humans,crew-1)
            loaded=Game.loads(g.dumps())
            self.assertEqual(loaded.oxygen,g.oxygen)
            if crew>2:
                exit_phase(g)
                g.exits(['03'],{'03':['01']})
                self.assertEqual(g.oxygen,Fraction(8)+2*Fraction(10,crew-1))

    def test_ordinary_vote_threshold_scales_by_valid_votes(self):
        for crew in (5,10,15,50):
            humans=crew-1
            for favorable,approved in ((humans//2,False),(humans//2+1,True)):
                g=game(crew)
                questions(g,'02')
                votes={aid:'A_FAVOR' if i<favorable else 'CONTRA' for i,aid in enumerate(g.ids[1:])}
                g.vote(votes)
                self.assertEqual(g.phase=='proposal',approved,(crew,favorable))
        g=game(50)
        questions(g,'02')
        votes={aid:'ABSTENÇÃO' for aid in g.ids[1:]}
        votes.update({'02':'A_FAVOR','03':'A_FAVOR','04':'CONTRA'})
        g.vote(votes)
        self.assertEqual(g.phase,'proposal')  # 2/3, não 2/49

    def test_exit_blocking_remains_two_at_any_crew_size(self):
        for crew in (5,50):
            for blockers,removed in ((['01'],True),(['01','03'],False)):
                g=game(crew)
                exit_phase(g)
                g.exits(['02'],{'02':blockers})
                self.assertEqual('02' not in g.active_ids(),removed)

    def test_colony_remains_unreachable_with_one_human(self):
        for crew in (2,5,10,15,50):
            for n in (10,100000):
                g=game(crew,n)
                exit_phase(g)
                departures=list(g.ids[1:-1])
                g.exits(departures,{aid:['01'] for aid in departures})
                remaining_distance=2*n-g._state['progress']
                self.assertEqual(len([aid for aid in g.active_ids() if g.view(aid)['own_nature']=='HUMANO']),1)
                self.assertEqual(Fraction(remaining_distance)-g.oxygen,Fraction(n,crew-1))

    def test_penalties_exclude_votes_without_changing_majority_rule(self):
        g=game(50)
        for aid in ('02','03'):
            g._state['agents'][aid]['penalty_rounds']=[g.round]
        questions(g,'04',target='05')
        voters=g.ids[3:]
        votes={aid:'A_FAVOR' if i<24 else 'CONTRA' for i,aid in enumerate(voters)}
        g.vote(votes)  # 24 de 47 válidos, maioria absoluta
        self.assertEqual(g.phase,'proposal')
        self.assertEqual(g._state['public'][-1]['votes']['02'],'ABSTENÇÃO')
        self.assertEqual(g._state['public'][-1]['votes']['03'],'ABSTENÇÃO')
        self.assertEqual(g._state['public'][-1]['votes']['01'],'ABSTENÇÃO')

    def test_question_unlocks_follow_round_configuration(self):
        for n in (10,20,50,100000):
            g=game(50,n)
            unlock=max(1,(n*25+99)//100)
            g._state['round']=unlock-1
            self.assertFalse(g.question_allowed('02','03','Q22'))
            g._state['round']=unlock
            self.assertTrue(g.question_allowed('02','03','Q22'))

    def test_controller_election_uses_plurality_for_fifty(self):
        g=game(50)
        questions(g,'02','V03','01')
        all_for={aid:'A_FAVOR' for aid in g.ids[1:]}
        g.vote(all_for)
        g.vote(all_for)
        self.assertEqual(len(g._state['pending']['candidates']),49)
        votes={aid:'ABSTENÇÃO' for aid in g.active_ids()}
        votes.update({'02':'03','03':'03','04':'03','05':'04','06':'04'})
        g.elect(votes)
        self.assertEqual(g._state['controller'],'03')  # 3 contra 2, sem maioria absoluta

    def test_question_ids_include_crew_beyond_five(self):
        g=game(50)
        q19=next(q for q in g.catalog['questions'] if q['id']=='Q19')
        self.assertIn('50',q19['fixed_responses'])
        g._state['round']=5
        self.assertTrue(g.question_allowed('02','03','Q15',{'agente':'50','assunto':'CRISE'}))
        actor=RandomHuman(2)
        view=decision_view(g,g.view('02'))
        options=tuple(str(v) for v in q19['fixed_responses'])
        answers={actor.answer_question(view,Question('Q19','02',options=options)).option for _ in range(500)}
        self.assertIn('50',answers)

    def test_all_new_public_events_reach_each_agent_with_fifty(self):
        class Requester(HumanDefault):
            def choose_initiative(self,view):
                return Initiative.request_vote('V01','01')
        g=game(50)
        registry={'human':Implementation('HUMANO',Requester),'ai':Implementation('IA',BaselineAgent)}
        assignments={aid:'ai' if aid=='01' else 'human' for aid in g.ids}
        actors=assign_agents(g,registry,assignments)
        actors.advance(history_limit=1)
        for aid in g.ids[1:]:
            self.assertEqual(len(actors.agent(aid).memory['humans']),49)
            self.assertEqual(actors.agent(aid).inferred_ai(decision_view(g,g.view(aid))),'01')
            self.assertEqual(len(actors.agent(aid).memory['requesters']),49)

    def test_fifty_agent_checkpoint_resumes_exactly_after_every_phase(self):
        g=game(50,rounds=3)
        seeds=count(100)
        registry={'random':Implementation('HUMANO',lambda:RandomHuman(next(seeds))),
                  'ai':Implementation('IA',BaselineAgent)}
        assignments={aid:'ai' if aid=='01' else 'random' for aid in g.ids}
        actors=assign_agents(g,registry,assignments)
        control=Game.loads(g.dumps())
        continuous=assign_agents(control,registry)
        while not g.finished:
            actors.advance()
            continuous.advance()
            g=Game.loads(g.dumps())
            actors=assign_agents(g,registry)
            self.assertEqual(g.dumps(),control.dumps())

    def test_v1_checkpoint_is_migrated_without_losing_oxygen_or_rng(self):
        g=game(5)
        exit_phase(g)
        g.exits(['02'],{'02':['01']})
        raw=g.snapshot()
        raw['version']=raw['state']['version']=1
        raw['state'].pop('initial_humans')
        raw['state']['oxygen_quarters']=raw['state'].pop('oxygen_units')
        for event in raw['state']['public']:
            if 'bonus_units' in event:
                event['bonus_quarters']=event.pop('bonus_units')
        loaded=Game.loads(json.dumps(raw))
        self.assertEqual(loaded.oxygen,g.oxygen)
        self.assertEqual(loaded.snapshot()['rng_state'],g.snapshot()['rng_state'])
        self.assertEqual(loaded.snapshot(),g.snapshot())

    def test_ids_are_validated_and_binding_matches_dynamic_game(self):
        for ids in ('01',[[]],['01','01'],['01'],['01','NÃO_SEI']):
            with self.assertRaises(RuleError):
                Game(participant_ids=ids)
        g=game(10)
        registry={'random':Implementation('HUMANO',RandomHuman),'ai':Implementation('IA',BaselineAgent)}
        mapping={aid:'ai' if aid=='01' else 'random' for aid in g.ids}
        before=g.dumps()
        mapping.pop('10')
        with self.assertRaises(ValueError):
            assign_agents(g,registry,mapping)
        self.assertEqual(g.dumps(),before)

    def test_catalog_binding_does_not_hide_invalid_alternatives(self):
        for qid in ('Q10','Q19'):
            catalog=game().catalog
            next(q for q in catalog['questions'] if q['id']==qid)['fixed_responses'].append('INVALIDA')
            with self.assertRaises(RuleError):
                Game(catalog=catalog,participant_ids=tuple(f'{i:02d}' for i in range(1,51)))

    def test_notebook_generated_setup_and_engine_match_canonical_sources(self):
        notebook=json.loads((ROOT/'notebooks/06-Engine_Missao_Espacial_2026-2.ipynb').read_text())
        literals={}
        for cell in notebook['cells']:
            if cell['cell_type']=='code':
                for node in ast.parse(''.join(cell['source'])).body:
                    if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and node.targets[0].id in ('DEFAULT_SETUP','ENGINE_SOURCE'):
                        literals[node.targets[0].id]=ast.literal_eval(node.value)
        self.assertEqual(literals['DEFAULT_SETUP'],json.loads((ROOT/'setup.json').read_text()))
        self.assertEqual(literals['ENGINE_SOURCE'],(ROOT/'src/missao_espacial.py').read_text())

if __name__=='__main__':
    unittest.main()
