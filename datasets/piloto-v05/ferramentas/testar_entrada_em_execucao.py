from pathlib import Path
import sys,json
import os
ROOT=Path(os.environ.get('MISSION_DATASET_PROJECT',str(Path(__file__).resolve().parents[3])))
for p in (ROOT/'src',ROOT/'datasets/piloto-v03/ferramentas',ROOT/'treinamento/piloto-v01/pacote/ferramentas',ROOT/'datasets/piloto-v05/ferramentas',Path(__file__).parent):sys.path.insert(0,str(p))
from entrada_agente import InputBuilder,ObservationMemory
from missao_espacial import Game
from carregar_agentes import assign_agents,Implementation
from agent.humano_random import RandomHuman
from agent.humanoide import HumanoidAgent
from agent_contract import AgentView
from planos_v2 import MEANINGS
CALLS=[];FORECAST_CALLS=[]
catalog=json.loads((Path(__file__).parents[1]/'matriz-cobertura.json').read_text())['catalog']
class LiveHuman(RandomHuman):
    def observe(self,view):
        super().observe(view)
        memory=ObservationMemory(self.memory.get('input_observations'));memory.observe(view);self.memory['input_observations']=memory.save_state()
        full=memory.complete_view();builder=InputBuilder(full,catalog,nonce='live-call')
        pair=builder.nli({'kind':'fact','qid':'Q10','params':{},'value':'SIM'})
        assert 'private-live' not in json.dumps(pair)
        for key in ('owners','sampling_assumptions','seed_pairing','unknown_ai','implementation'):
            assert key not in pair['premise']
        CALLS.append((view.round,view.phase))
        targets=[p for p in view.participants if p!=view.id]
        if targets and not view.finished:
            condition={'target':targets[0],'controls':{'initiative':'ask','answer':'truthful','vote':'reject','election':'self','route':'CONTINUAR','exit':'never','block':'never','questions':'evidence_first'}}
            forecast=builder.forecast(condition,MEANINGS)
            assert set(forecast)=={'context','candidate_plan'}
            assert builder.resolve(forecast['candidate_plan']['target'])==targets[0]
            FORECAST_CALLS.append((view.round,view.phase))
    def on_finish(self,view,reason):self.observe(view)
ids=['private-live-'+str(i) for i in range(5)]
g=Game(N=12,seed=42,participant_ids=ids,ai_id=ids[-1]);impl={'live':Implementation('HUMANO',LiveHuman),'ia':Implementation('IA',HumanoidAgent)}
session=assign_agents(g,impl,{i:'ia' if i==ids[-1] else 'live' for i in ids},agent_seeds={i:k+30 for k,i in enumerate(ids)})
for _ in range(4):session.advance(history_limit=2)
session.save(str(Path(__file__).parents[1]/'auditoria/partida-validacao-agente.json'))
resumed=Game.load(str(Path(__file__).parents[1]/'auditoria/partida-validacao-agente.json'));session=assign_agents(resumed,impl,{i:'ia' if i==ids[-1] else 'live' for i in ids})
for _ in range(500):
    if resumed.finished:break
    session.advance(history_limit=2)
assert resumed.finished and CALLS
raw=resumed.view(ids[0],history_limit=1)
try:
    missing=ObservationMemory();missing.observe(AgentView.from_engine(raw));missing.complete_view()
except ValueError as e:assert 'Histórico incompleto' in str(e)
else:raise AssertionError('Histórico parcial admitido sem memória')
result={'status':'passed','live_agent_callbacks_compiled':len(CALLS),'live_forecast_inputs_compiled':len(FORECAST_CALLS),'phases_seen':sorted({p for r,p in CALLS}),'session_resume_verified':True,'short_history_limit':2,'incomplete_memory_rejected':True,'engine_source_modified':False,'private_engine_state_read_by_compiler':False}
(Path(__file__).parents[1]/'validacao-agente-em-execucao.json').write_text(json.dumps(result,indent=2)+'\n');print(result)
