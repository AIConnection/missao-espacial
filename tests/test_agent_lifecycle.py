"""Tipos por etapa, hooks, isolamento, exclusão, retomada e checkpoint de memória."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from missao_espacial import Game, IDS, DOMAINS, DEFAULT_CATALOG
from agent_contract import (
    Agent, AgentContractError, AgentView, Answer, BlockDecision, ElectionChoice,
    ExitDecision, FinishReason, Initiative, Proposal, Question, Renunciation, Route, Vote,
)
from agent_session import ProtocolAdapter, BINDING_KEY, CLOSED_KEY
from carregar_agentes import load_agents, assign_agents, Implementation, ai_id_for_assignment
from agent._baseline import BaselineAgent

ASSIGNMENT={'01':'human','02':'human','03':'ai','04':'human','05':'human'}


class RecordingAgent(BaselineAgent):
    def on_start(self,view):
        self.memory['starts']=self.memory.get('starts',0)+1

    def on_resume(self,view):
        self.memory['resumes']=self.memory.get('resumes',0)+1

    def on_round_start(self,view):
        self.memory.setdefault('rounds',[]).append(view.round)

    def observe(self,view):
        self.memory['observations']=self.memory.get('observations',0)+1
        self.memory['last_received']=view.history_sizes['received']
        self.memory['last_revealed']=view.history_sizes['revelations']

    def choose_initiative(self,view):
        self.memory['initiatives']=self.memory.get('initiatives',0)+1
        return super().choose_initiative(view)

    def on_finish(self,view,reason):
        self.memory.setdefault('finishes',[]).append(reason.value)


def registry(factory=RecordingAgent):
    return {'human':Implementation('HUMANO',factory),'ai':Implementation('IA',factory)}


def make_session(N=10,factory=RecordingAgent):
    g=Game(N,seed=17,ai_id='03')
    return g,assign_agents(g,registry(factory),ASSIGNMENT)


class LifecycleTests(unittest.TestCase):
    def view(self,aid='01'):
        return AgentView.from_engine(Game(10,ai_id='03').view(aid))

    def test_methods_have_one_return_type_and_no_dispatch_in_modules(self):
        agent=BaselineAgent()
        view=self.view()
        cases=[(agent.choose_initiative(view),Initiative),
               (agent.answer_question(view,Question('Q10','01',author='02')),Answer),
               (agent.renounce_vote(view),Renunciation),
               (agent.authorize_vote(view,Proposal('V01','02','04')),Vote),
               (agent.vote_proposal(view,Proposal('V01','02','04')),Vote),
               (agent.elect_controller(view,('01','02')),ElectionChoice),
               (agent.choose_route(view),Route),(agent.request_exit(view),ExitDecision),
               (agent.block_exit(view,'02'),BlockDecision)]
        for result,expected in cases:
            self.assertIsInstance(result,expected)
        for path in (ROOT/'src/agent').glob('*.py'):
            source=path.read_text()
            self.assertNotIn('def decide(',source)
            self.assertNotIn('request[',source)
            self.assertNotIn('AGENT_ID =',source)

    def test_adapter_dispatch_and_serialization_for_all_stages(self):
        g=Game(10,ai_id='03')
        adapter=ProtocolAdapter(BaselineAgent(),g.catalog)
        view=g.view('01')
        proposal={'author':'02','topic':'V01','target':'04'}
        cases=[({'kind':'initiative'}, {'type':'question','question_id':'Q10','recipient':'02','parameters':{}}),
               ({'kind':'answer','question_id':'Q10','recipient':'01','author':'02'}, 'NÃO_SEI'),
               ({'kind':'renounce'},True),({'kind':'authorize','proposal':proposal},'ABSTENÇÃO'),
               ({'kind':'proposal','proposal':proposal},'ABSTENÇÃO'),
               ({'kind':'election','candidates':['01','02']},'01'),
               ({'kind':'route'},'CONTINUAR'),({'kind':'exit'},False),({'kind':'block','target':'02'},False)]
        for request,expected in cases:
            self.assertEqual(adapter(view,request),expected)

    def test_numeric_answer_is_always_text_in_agent_and_integer_in_engine(self):
        class NumericAgent(BaselineAgent):
            def answer_question(self,view,question):
                assert question.options == ('1','2','4','8','NÃO_SEI','RECUSO_RESPONDER')
                return Answer('4')
        adapter=ProtocolAdapter(NumericAgent(),DEFAULT_CATALOG)
        response=adapter(Game(10).view('01'),{'kind':'answer','question_id':'Q09','recipient':'01','author':'02'})
        self.assertEqual(response,4)
        self.assertIs(type(response),int)
        with self.assertRaises(AgentContractError):
            Answer(4)

    def test_initiative_has_exclusive_payload(self):
        from agent_contract import InitiativeKind
        with self.assertRaises(AgentContractError):
            Initiative(InitiativeKind.QUESTION,Question('Q10','02'),Proposal('V01','02'))
        self.assertIsInstance(Initiative.request_vote('V03','03'),Initiative)
        self.assertIsInstance(Initiative.idle(),Initiative)
        with self.assertRaises(AgentContractError):
            Initiative.ask('Q10','02',[])

    def test_raw_returns_are_rejected_in_every_method(self):
        specs=[('choose_initiative', {'kind':'initiative'}, {}),
               ('answer_question',{'kind':'answer','question_id':'Q10','recipient':'01','author':'02'},'NÃO_SEI'),
               ('renounce_vote',{'kind':'renounce'},True),
               ('authorize_vote',{'kind':'authorize','proposal':{'author':'02','topic':'V01','target':'04'}},'ABSTENÇÃO'),
               ('vote_proposal',{'kind':'proposal','proposal':{'author':'02','topic':'V01','target':'04'}},'ABSTENÇÃO'),
               ('elect_controller',{'kind':'election','candidates':['01']},'01'),
               ('choose_route',{'kind':'route'},'CONTINUAR'),
               ('request_exit',{'kind':'exit'},False),('block_exit',{'kind':'block','target':'02'},False)]
        for method,request,value in specs:
            with self.subTest(method=method):
                cls=type('InvalidAgent',(BaselineAgent,),{method:lambda *args,v=value:v})
                adapter=ProtocolAdapter(cls(),DEFAULT_CATALOG)
                with self.assertRaisesRegex(AgentContractError,method):
                    adapter(Game(10).view('01'),request)

    def test_lifecycle_hooks_and_state_restore(self):
        g,session=make_session()
        for aid in IDS:
            self.assertEqual(session.agent(aid).memory['starts'],1)
            self.assertEqual(session.agent(aid).memory['rounds'],[1])
        session.run_round()
        before=session.agent('01').memory.copy()
        self.assertEqual(before['initiatives'],1)
        self.assertEqual(before['rounds'],[1,2])
        saved=g.dumps()
        restored=Game.loads(saved)
        resumed=assign_agents(restored,registry())
        self.assertEqual(resumed.agent('01').memory['starts'],1)
        self.assertEqual(resumed.agent('01').memory['resumes'],1)
        self.assertEqual(resumed.agent('01').memory['rounds'],[1,2])
        self.assertEqual(resumed.agent('01').memory['initiatives'],1)
        resumed.run_round()
        self.assertEqual(resumed.agent('01').memory['initiatives'],2)
        self.assertEqual(resumed.agent('01').memory['rounds'],[1,2,3])

    def test_instances_are_independent_when_implementation_is_reused(self):
        g,session=make_session()
        self.assertEqual(len({id(session.agent(aid)) for aid in IDS}),5)
        session.agent('01').memory['private']='only one'
        self.assertNotIn('private',session.agent('02').memory)
        with tempfile.TemporaryDirectory() as directory:
            session.save(Path(directory)/'state.json')
        self.assertNotIn('private',g.view('02')['policy_state'])

    def test_invalid_or_shared_factory_instance_is_rejected_without_binding(self):
        for factory in (lambda:None,lambda:shared):
            shared=BaselineAgent()
            g=Game(10,ai_id='03')
            before=g.dumps()
            with self.assertRaises(AgentContractError):
                assign_agents(g,registry(factory),ASSIGNMENT)
            self.assertEqual(g.dumps(),before)

    def test_signature_and_async_methods_fail_before_start(self):
        class WrongSignature(BaselineAgent):
            def choose_route(self):
                return Route.CONTINUE
        class AsyncAgent(BaselineAgent):
            async def choose_route(self,view):
                return Route.CONTINUE
        for factory in (WrongSignature,AsyncAgent):
            with self.assertRaises(AgentContractError):
                make_session(factory=factory)

    def test_invalid_state_and_void_hook_return_are_rejected(self):
        class BadState(BaselineAgent):
            def save_state(self):
                return {'not_json':object()}
        class BadHook(BaselineAgent):
            def on_start(self,view):
                return True
        for factory in (BadState,BadHook):
            g=Game(10,ai_id='03')
            before=g.dumps()
            with self.assertRaises(AgentContractError):
                assign_agents(g,registry(factory),ASSIGNMENT)
            self.assertEqual(g.dumps(),before)

    def test_metadata_does_not_enter_context_or_agent_state(self):
        g,session=make_session()
        for aid in IDS:
            view=session._view(aid)
            self.assertFalse(hasattr(view,'policy_state'))
            self.assertNotIn(BINDING_KEY,session.agent(aid).memory)
            self.assertNotIn(CLOSED_KEY,session.agent(aid).memory)
        self.assertFalse(hasattr(session._view('01'),'controller'))

    def test_post_answer_observation_has_only_own_messages_and_revelations(self):
        g,session=make_session()
        session.advance()
        session.advance()
        self.assertEqual(g.phase,'route')
        self.assertTrue(all(session.agent(a).memory['last_received']==1 for a in IDS))
        self.assertEqual(sum(session.agent(a).memory['last_revealed'] for a in IDS),1)

    def test_active_agent_cannot_have_closed_marker(self):
        g,session=make_session()
        memory=g.view('01')['policy_state']
        memory[CLOSED_KEY]=True
        g.set_policy_state('01',memory)
        before=g.dumps()
        with self.assertRaisesRegex(AgentContractError,'participante ativo'):
            assign_agents(g,registry())
        self.assertEqual(g.dumps(),before)

    def test_finish_once_and_finished_checkpoint_does_not_repeat_finish(self):
        g,session=make_session(N=1)
        session.run_round()
        for aid in IDS:
            self.assertEqual(session.agent(aid).memory['finishes'],['game_ended'])
        before=g.dumps()
        session.advance()
        self.assertEqual(g.dumps(),before)
        resumed=assign_agents(Game.loads(before),registry())
        for aid in IDS:
            self.assertEqual(resumed.agent(aid).memory['finishes'],['game_ended'])
            self.assertNotIn('resumes',resumed.agent(aid).memory)
        self.assertEqual(resumed.game.dumps(),before)

    def test_removal_closes_agent_without_more_observations(self):
        class Leaving(RecordingAgent):
            def request_exit(self,view):
                return ExitDecision.LEAVE if view.id=='01' else ExitDecision.STAY
        g,session=make_session(factory=Leaving)
        session.run_round()
        self.assertFalse(g.view('01')['active'])
        self.assertEqual(session.agent('01').memory['finishes'],['removed'])
        observations=session.agent('01').memory['observations']
        session.run_round()
        self.assertEqual(session.agent('01').memory['observations'],observations)
        self.assertEqual(session.agent('01').memory['finishes'],['removed'])

    def test_penalized_agent_observes_and_answers_but_cannot_initiate(self):
        class Punishing(RecordingAgent):
            def choose_initiative(self,view):
                if view.id=='01' and view.round==1:
                    return Initiative.request_vote('V01','02')
                return super().choose_initiative(view)
            def authorize_vote(self,view,proposal):
                return Vote.FOR
            def vote_proposal(self,view,proposal):
                return Vote.FOR
            def answer_question(self,view,question):
                self.memory['answers']=self.memory.get('answers',0)+1
                return super().answer_question(view,question)
        g,session=make_session(factory=Punishing)
        session.run_round()
        self.assertTrue(g.view('02')['penalized'])
        initiatives=session.agent('02').memory['initiatives']
        observations=session.agent('02').memory['observations']
        session.run_round()
        self.assertEqual(session.agent('02').memory['initiatives'],initiatives)
        self.assertEqual(session.agent('02').memory['answers'],1)
        self.assertGreater(session.agent('02').memory['observations'],observations)

    def test_vote_election_and_human_route_use_specific_methods(self):
        class Expelling(RecordingAgent):
            def choose_initiative(self,view):
                return Initiative.request_vote('V03','03') if view.id=='01' else super().choose_initiative(view)
            def authorize_vote(self,view,proposal):
                self.memory['authorized']=True
                return Vote.FOR
            def vote_proposal(self,view,proposal):
                self.memory['voted']=True
                return Vote.FOR
            def elect_controller(self,view,candidates):
                self.memory['elected']=True
                return ElectionChoice('01')
            def choose_route(self,view):
                return Route.RETURN
        g,session=make_session(factory=Expelling)
        session.run_round()
        self.assertEqual(g.result['reason'],'returned')
        self.assertEqual(session.agent('03').memory['finishes'],['removed'])
        self.assertTrue(session.agent('01').memory['authorized'])
        self.assertTrue(session.agent('01').memory['voted'])
        self.assertTrue(session.agent('01').memory['elected'])

    def test_session_checkpoint_includes_latest_memory_after_phase(self):
        g,session=make_session()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            session.advance(checkpoint=path)
            restored=Game.load(path)
            self.assertEqual(restored.phase,'answers')
            self.assertEqual(restored.dumps(),g.dumps())
            self.assertEqual(restored.view('01')['policy_state']['initiatives'],1)

    def test_shipped_agents_fresh_process_resume_is_identical(self):
        assignment={'01':'humano_alpha','02':'humano_beta','03':'humanoide','04':'humano_gamma','05':'humano_random'}
        impl=load_agents(ROOT/'src/agent')
        g=Game(10,seed=17,ai_id=ai_id_for_assignment(impl,assignment))
        session=assign_agents(g,impl,assignment)
        session.advance()
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'state.json'
            session.save(path)
            while not g.finished:
                session.run_round()
            code="""import sys, hashlib
sys.path.insert(0,sys.argv[1])
from missao_espacial import Game
from carregar_agentes import load_agents, assign_agents
g=Game.load(sys.argv[3])
s=assign_agents(g,load_agents(sys.argv[2]))
while not g.finished:
    s.run_round()
print(hashlib.sha256(g.dumps().encode()).hexdigest())
"""
            completed=subprocess.run([sys.executable,'-c',code,str(ROOT/'src'),str(ROOT/'src/agent'),str(path)],
                                     check=True,capture_output=True,text=True)
            self.assertEqual(completed.stdout.strip(),hashlib.sha256(g.dumps().encode()).hexdigest())


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LifecycleTests))
    (ROOT/'evidencias/engine-v01/resultado-ciclo-vida.json').write_text(json.dumps(
        {'tests_run':result.testsRun,'passed':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors),
         'scope':'typed agent methods, lifecycle, private observation, independent instances, automatic JSON memory and checkpoints'},indent=2)+'\n')
    raise SystemExit(not result.wasSuccessful())
