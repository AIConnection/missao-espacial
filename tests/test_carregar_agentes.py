"""Módulos sem IDs; natureza definida; vínculo externo explícito e persistente."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from carregar_agentes import load_agents, assign_agents, ai_id_for_assignment, AgentLoadError, BINDING_KEY, Implementation
from missao_espacial import Game, IDS

NAMES=('humano_alpha','humano_beta','humano_gamma','humano_random','humanoide')
DEFAULT_ASSIGNMENT={'01':'humano_alpha','02':'humano_beta','03':'humanoide','04':'humano_gamma','05':'humano_random'}


class LoaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.directory=Path(self.temporary.name)/'agent'
        self.directory.mkdir()
        for name in NAMES:
            self.write(name,f"return '{name}'",'IA' if name=='humanoide' else 'HUMANO')

    def tearDown(self):
        self.temporary.cleanup()

    def write(self,name,body,nature='HUMANO'):
        import ast
        label=ast.literal_eval(body.removeprefix('return '))
        path=self.directory/f'{name}.py'
        path.write_text(f'NATURE="{nature}"\nfrom agent._baseline import BaselineAgent\n'
                        f'class FixtureAgent(BaselineAgent):\n    label={label!r}\n'
                        'def create_agent(): return FixtureAgent()\n')
        return path

    def new_game(self,registry=None,assignment=None):
        registry=registry or load_agents(self.directory)
        assignment=assignment or DEFAULT_ASSIGNMENT
        g=Game(10,seed=17,ai_id=ai_id_for_assignment(registry,assignment))
        return g,assign_agents(g,registry,assignment)

    def assignment(self,g):
        return {aid:g.view(aid)['policy_state'][BINDING_KEY] for aid in IDS}

    def test_registry_names_and_nature_are_independent_of_ids(self):
        registry=load_agents(self.directory)
        self.assertEqual(set(registry),set(NAMES))
        self.assertFalse(set(registry)&set(IDS))
        self.assertEqual(registry['humanoide'].nature,'IA')
        self.assertTrue(all(registry[n].nature=='HUMANO' for n in NAMES if n!='humanoide'))
        self.assertEqual({impl.create_agent().label for impl in registry.values()},set(NAMES))

    def test_directory_with_spaces_does_not_change_sys_path(self):
        directory=Path(self.temporary.name)/'outro diretório'/'agent'
        shutil.copytree(self.directory,directory)
        before=list(sys.path)
        self.assertEqual(len(load_agents(directory)),5)
        self.assertEqual(sys.path,before)

    def test_relative_helpers_and_private_files_are_not_implementations(self):
        (self.directory/'_shared.py').write_text('VALUE="ajudante"\n')
        (self.directory/'__init__.py').write_text('raise RuntimeError("não deve executar")\n')
        (self.directory/'humano_alpha.py').write_text('from ._shared import VALUE\nNATURE="HUMANO"\nfrom agent._baseline import BaselineAgent\nclass A(BaselineAgent): label=VALUE\ndef create_agent(): return A()\n')
        self.assertEqual(load_agents(self.directory)['humano_alpha'].create_agent().label,'ajudante')

    def test_missing_or_empty_directory(self):
        with self.assertRaisesRegex(AgentLoadError,'inexistente'):
            load_agents(self.directory/'não-existe')
        empty=self.directory/'empty'
        empty.mkdir()
        with self.assertRaisesRegex(AgentLoadError,'Nenhuma implementação'):
            load_agents(empty)

    def test_fixed_id_in_module_is_rejected(self):
        (self.directory/'humano_alpha.py').write_text('NATURE="HUMANO"\nAGENT_ID="01"\ndef create_agent(): return None\n')
        with self.assertRaisesRegex(AgentLoadError,'remova AGENT_ID'):
            load_agents(self.directory)

    def test_missing_or_invalid_nature(self):
        for source in ('', 'NATURE="OUTRA"\n'):
            (self.directory/'humano_alpha.py').write_text(source+'def create_agent(): return None\n')
            with self.assertRaisesRegex(AgentLoadError,'NATURE'):
                load_agents(self.directory)

    def test_missing_or_incompatible_policy(self):
        for source in ('VALUE=1','def create_agent(required): return None','async def create_agent(): return None'):
            (self.directory/'humano_alpha.py').write_text('NATURE="HUMANO"\n'+source+'\n')
            with self.assertRaises(AgentLoadError):
                load_agents(self.directory)

    def test_import_failure_identifies_file_and_cleans_package(self):
        (self.directory/'humano_gamma.py').write_text('raise RuntimeError("teste")\n')
        before={n for n in sys.modules if n.startswith('_mission_agents_')}
        with self.assertRaisesRegex(AgentLoadError,'humano_gamma.py'):
            load_agents(self.directory)
        self.assertEqual(before,{n for n in sys.modules if n.startswith('_mission_agents_')})

    def test_fast_edit_reloads_without_changing_old_callbacks(self):
        old=load_agents(self.directory)
        self.write('humano_alpha',"return 'other'")
        new=load_agents(self.directory)
        self.assertEqual(old['humano_alpha'].create_agent().label,'humano_alpha')
        self.assertEqual(new['humano_alpha'].create_agent().label,'other')

    def test_independent_directories_do_not_share_helpers(self):
        other=Path(self.temporary.name)/'other'
        shutil.copytree(self.directory,other)
        for directory,value in ((self.directory,'first'),(other,'second')):
            (directory/'_shared.py').write_text(f'VALUE="{value}"\n')
            (directory/'humano_alpha.py').write_text('from ._shared import VALUE\nNATURE="HUMANO"\nfrom agent._baseline import BaselineAgent\nclass A(BaselineAgent): label=VALUE\ndef create_agent(): return A()\n')
        self.assertEqual(load_agents(self.directory)['humano_alpha'].create_agent().label,'first')
        self.assertEqual(load_agents(other)['humano_alpha'].create_agent().label,'second')

    def test_assignment_is_explicit_and_not_randomized(self):
        registry=load_agents(self.directory)
        g,policies=self.new_game(registry)
        self.assertEqual(self.assignment(g),DEFAULT_ASSIGNMENT)
        self.assertEqual(g.view('03')['own_nature'],'IA')
        self.assertEqual(policies.agent('03').label,'humanoide')
        with self.assertRaisesRegex(AgentLoadError,'configuração explícita'):
            assign_agents(Game(10,ai_id='03'),registry)

    def test_humanoid_can_have_any_external_id_without_changing_modules(self):
        registry=load_agents(self.directory)
        for ai_id in IDS:
            remaining=[aid for aid in IDS if aid!=ai_id]
            assignment=dict(zip(remaining,NAMES[:4]))
            assignment[ai_id]='humanoide'
            g,policies=self.new_game(registry,assignment)
            self.assertEqual(ai_id_for_assignment(registry,assignment),ai_id)
            self.assertEqual(policies.agent(ai_id).label,'humanoide')
            self.assertEqual(g.view(ai_id)['own_nature'],'IA')
            self.assertEqual(sum(g.view(a)['own_nature']=='HUMANO' for a in IDS),4)

    def test_binding_preserves_existing_nature_and_engine_rng(self):
        registry=load_agents(self.directory)
        g=Game(10,seed=17,ai_id='03')
        original=g.snapshot()
        assign_agents(g,registry,DEFAULT_ASSIGNMENT)
        self.assertEqual(g.snapshot()['rng_state'],original['rng_state'])
        self.assertEqual({a:g.view(a)['own_nature'] for a in IDS},
                         {a:original['state']['agents'][a]['nature'] for a in IDS})

    def test_cross_nature_binding_rejected_before_mutation(self):
        registry=load_agents(self.directory)
        g=Game(10,ai_id='05')
        before=g.dumps()
        with self.assertRaisesRegex(AgentLoadError,'Natureza incompatível'):
            assign_agents(g,registry,DEFAULT_ASSIGNMENT)
        self.assertEqual(g.dumps(),before)

    def test_config_requires_exactly_one_ai(self):
        registry=load_agents(self.directory)
        for count in (0,2,5):
            assignment={a:('humanoide' if i<count else 'humano_alpha') for i,a in enumerate(IDS)}
            with self.assertRaisesRegex(AgentLoadError,'um humanoide IA e pelo menos um humano'):
                ai_id_for_assignment(registry,assignment)

    def test_human_implementation_can_be_reused_without_becoming_ai(self):
        registry=load_agents(self.directory)
        assignment={a:'humano_alpha' for a in IDS}
        assignment['03']='humanoide'
        g,policies=self.new_game(registry,assignment)
        self.assertEqual(policies.agent('03').label,'humanoide')
        self.assertTrue(all(policies.agent(a).label=='humano_alpha' for a in IDS if a!='03'))

    def test_metadata_hidden_and_policy_memory_preserved(self):
        from agent._baseline import BaselineAgent
        registry=load_agents(self.directory)
        received=[]
        class ObservingAgent(BaselineAgent):
            def on_start(self,view):
                received.append(dict(self.memory))
                assert not hasattr(view,'policy_state')
        registry['humano_alpha']=Implementation('HUMANO',ObservingAgent)
        g=Game(10,ai_id='03')
        g.set_policy_state('01',{'counter':7})
        session=assign_agents(g,registry,DEFAULT_ASSIGNMENT)
        self.assertEqual(received,[{'counter':7}])
        self.assertNotIn(BINDING_KEY,session.agent('01').memory)
        self.assertIn(BINDING_KEY,g.view('01')['policy_state'])

    def test_resume_preserves_binding_and_rejects_reassignment(self):
        registry=load_agents(self.directory)
        g,_=self.new_game(registry)
        saved=g.dumps()
        restored=Game.loads(saved)
        assign_agents(restored,load_agents(self.directory))
        self.assertEqual(restored.dumps(),saved)
        other=dict(DEFAULT_ASSIGNMENT)
        other['01'],other['02']=other['02'],other['01']
        with self.assertRaisesRegex(AgentLoadError,'diferente do checkpoint'):
            assign_agents(restored,registry,other)
        self.assertEqual(restored.dumps(),saved)

    def test_missing_saved_implementation_fails_without_remapping(self):
        registry=load_agents(self.directory)
        g,_=self.new_game(registry)
        del registry['humanoide']
        before=g.dumps()
        with self.assertRaisesRegex(AgentLoadError,'não está disponível'):
            assign_agents(g,registry)
        self.assertEqual(g.dumps(),before)

    def test_partial_assignment_does_not_get_replaced(self):
        g=Game(10,ai_id='03')
        g.set_policy_state('01',{BINDING_KEY:'humano_alpha'})
        before=g.dumps()
        with self.assertRaisesRegex(AgentLoadError,'incompleta'):
            assign_agents(g,load_agents(self.directory),DEFAULT_ASSIGNMENT)
        self.assertEqual(g.dumps(),before)

    def test_modified_saved_module_nature_is_rejected(self):
        registry=load_agents(self.directory)
        g,_=self.new_game(registry)
        registry['humanoide']=Implementation('HUMANO',registry['humanoide'].create_agent)
        before=g.dumps()
        with self.assertRaises(AgentLoadError):
            assign_agents(g,registry)
        self.assertEqual(g.dumps(),before)

    def test_started_game_without_binding_cannot_be_reassigned(self):
        g=Game(10,ai_id='03')
        g.initiatives({a:{'type':'question','question_id':'Q10','recipient':IDS[(i+1)%5]} for i,a in enumerate(IDS)})
        before=g.dumps()
        with self.assertRaisesRegex(AgentLoadError,'já iniciada'):
            assign_agents(g,load_agents(self.directory),DEFAULT_ASSIGNMENT)
        self.assertEqual(g.dumps(),before)

    def test_shipped_humanoid_has_own_implementation(self):
        from agent_contract import AgentView,BlockDecision,Proposal,Route,Vote
        registry=load_agents(ROOT/'src/agent')
        self.assertEqual(registry['humanoide'].nature,'IA')
        humanoid=registry['humanoide'].create_agent()
        human=registry['humano_alpha'].create_agent()
        view=AgentView.from_engine(Game(10,ai_id='03').view('03'))
        self.assertEqual(humanoid.block_exit(view,'01'),BlockDecision.BLOCK)
        self.assertEqual(human.block_exit(view,'01'),BlockDecision.ALLOW)
        self.assertEqual(humanoid.vote_proposal(view,Proposal('V01','01','02')),Vote.ABSTAIN)
        self.assertEqual(humanoid.choose_route(view),Route.CONTINUE)

    def test_shipped_agents_execute_and_resume_exactly(self):
        registry=load_agents(ROOT/'src/agent')
        initial,policies=self.new_game(registry)
        initial_state=initial.dumps()
        uninterrupted=Game.loads(initial_state)
        policies=assign_agents(uninterrupted,registry)
        while not uninterrupted.finished:
            policies.run_round()
        resumed=Game.loads(initial_state)
        policies=assign_agents(resumed,registry)
        for _ in range(3):
            policies.run_round()
        policies.advance()
        resumed=Game.loads(resumed.dumps())
        policies=assign_agents(resumed,load_agents(ROOT/'src/agent'))
        while not resumed.finished:
            policies.run_round()
        self.assertEqual(resumed.dumps(),uninterrupted.dumps())

    def test_resume_in_a_fresh_process_keeps_humanoid_and_assignment(self):
        registry=load_agents(ROOT/'src/agent')
        g,policies=self.new_game(registry)
        policies.advance()
        path=Path(self.temporary.name)/'state.json'
        g.save(path)
        while not g.finished:
            policies.run_round()
        code="""import sys, hashlib
sys.path.insert(0,sys.argv[1])
from missao_espacial import Game
from carregar_agentes import load_agents, assign_agents
g=Game.load(sys.argv[3])
p=assign_agents(g,load_agents(sys.argv[2]))
while not g.finished:
    p.run_round()
print(hashlib.sha256(g.dumps().encode()).hexdigest())
"""
        completed=subprocess.run([sys.executable,'-c',code,str(ROOT/'src'),str(ROOT/'src/agent'),str(path)],
                                 check=True,capture_output=True,text=True)
        self.assertEqual(completed.stdout.strip(),hashlib.sha256(g.dumps().encode()).hexdigest())


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LoaderTests))
    (ROOT/'evidencias/engine-v01/resultado-carregar-agentes.json').write_text(json.dumps(
        {'tests_run':result.testsRun,'passed':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),
         'scope':'declared nature, ID-free implementations, explicit binding, independent humanoid and checkpoint resume'},indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
