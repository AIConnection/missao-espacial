"""Executa o jogo do setup central e registra contagens/tempo observados."""
from pathlib import Path
import hashlib
import json
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from setup_jogo import GameSetup

setup = GameSetup.load(ROOT/'setup.json')
print(json.dumps(setup.summary(), ensure_ascii=False, indent=2), flush=True)
agents = setup.start()
game = agents.game
start = time.perf_counter()
while not game.finished:
    agents.run_round()
    if game.round % 25000 == 0 and not game.finished:
        print(f'Rodada {game.round}', flush=True)
agents.save(setup.checkpoint)
result = {
    'engine_sha256': hashlib.sha256((ROOT/'src/missao_espacial.py').read_bytes()).hexdigest(),
    'N': setup.rounds, 'crew': len(game.ids), 'rounds_completed': game.result['progress'],
    'seconds': round(time.perf_counter()-start, 3), 'result': game.result,
    'private_answers': sum(len(a['received']) for a in game._state['agents'].values()),
    'private_revelations': sum(len(a['revelations']) for a in game._state['agents'].values()),
    'scope': 'configured policies from setup.json; game may end earlier or gain oxygen rounds',
}
(ROOT/'evidencias/setup/execucao-configurada.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2), flush=True)
