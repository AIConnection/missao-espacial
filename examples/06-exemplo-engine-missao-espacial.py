"""Exemplo automático para conferir turnos/checkpoint, sem modelo treinado.

No Colab, coloque missao_espacial.py no diretório do notebook e importe Game.
As políticas heurísticas investigam e decidem; a cabeça do Phi-4 permanece pendente.
"""
from pathlib import Path
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"src"))
from missao_espacial import Game, DEFAULT_CATALOG
from setup_jogo import GameSetup


from agent._baseline import BaselineAgent
from agent_session import ProtocolAdapter

# Compatibilidade para os testes antigos da API de callbacks da engine.
# Os módulos de agentes e a demonstração abaixo usam métodos específicos.
baseline = ProtocolAdapter(BaselineAgent(), DEFAULT_CATALOG)
from carregar_agentes import load_agents, assign_agents


def demonstration(checkpoint):
    setup = GameSetup.load(ROOT/'setup.json')
    initial_agents = setup.start()
    initial = initial_agents.game
    implementations = load_agents(setup.agent_directory)
    initial_state = initial.dumps()  # inclui o RNG próprio do agente aleatório
    uninterrupted = Game.loads(initial_state)
    agents = assign_agents(uninterrupted, implementations)
    while not uninterrupted.finished:
        agents.run_round()

    partial = Game.loads(initial_state)
    agents = assign_agents(partial, implementations)
    agents.advance()  # salva após a iniciativa: perguntas ou autorização de votação
    checkpoint_phase = partial.phase
    agents.agent(initial.ids[0]).memory['note'] = 'checkpoint após a iniciativa'
    agents.save(checkpoint)
    resumed = Game.load(checkpoint)
    agents = assign_agents(resumed, load_agents(setup.agent_directory))
    assert resumed.phase == checkpoint_phase
    while not resumed.finished:
        agents.run_round()
    # A anotação extra da política não altera o jogo; comparar os efeitos observáveis.
    assert resumed.result == uninterrupted.result
    assert resumed.snapshot()['state']['public'] == uninterrupted.snapshot()['state']['public']
    assert [resumed.view(a, history_limit=None)['revelations'] for a in initial.ids] == [
        uninterrupted.view(a, history_limit=None)['revelations'] for a in initial.ids]
    return {'resumed_equals_uninterrupted': True, 'checkpoint_phase': checkpoint_phase,
            'result': resumed.result, 'policy_memory': resumed.view(initial.ids[0])['policy_state']}


if __name__ == '__main__':
    import tempfile
    with tempfile.TemporaryDirectory() as directory:
        print(json.dumps(GameSetup.load(ROOT/'setup.json').summary(), ensure_ascii=False, indent=2))
        print(json.dumps(demonstration(Path(directory) / 'partida.json'), ensure_ascii=False, indent=2))
