"""Gera notebook autossuficiente a partir da engine e da política de demonstração."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
engine = (ROOT / 'src/missao_espacial.py').read_text()
runtime_sources = {name:(ROOT/'src'/name).read_text() for name in ('agent_contract.py','agent_session.py','carregar_agentes.py','setup_jogo.py')}
setup_data = json.loads((ROOT/'setup.json').read_text())
agent_sources = {p.name: p.read_text() for p in sorted((ROOT / 'src/agent').glob('*.py'))}
cells = []

def markdown(text):
    cells.append({'cell_type':'markdown','metadata':{},'source':text.splitlines(keepends=True)})

def code(text):
    cells.append({'cell_type':'code','execution_count':None,'metadata':{},'outputs':[], 'source':text.splitlines(keepends=True)})

markdown('''# Engine do jogo de missão espacial — aulas 05/06

Este notebook contém a engine completa em Python, sem instalações ou serviços externos. O setup configura rodadas, quantidade de tripulantes, papéis HUMANO/IA, implementações e conhecimentos. As políticas são heurísticas; a cabeça do Phi-4 e os dados de treino ainda serão preparados.

O estado inclui a fase, ações pendentes, oxigênio, penalidades, controlador, informações privadas e sorteios. A engine fica separada da política: cada agente recebe somente sua visão autorizada.

**Checkpoint e Colab:** variáveis persistem entre células enquanto o runtime existir. Para sobreviver a desconexões, salve em armazenamento persistente: depois de montar seu Google Drive no Colab, altere o caminho de checkpoint para uma pasta nele. O arquivo `partida.json` no armazenamento temporário do runtime não sobrevive à exclusão desse runtime. O checkpoint é reservado ao motor/professor e contém identidades e mensagens privadas.
''')
markdown('''## 1. Definir a engine

Esta célula define classes e catálogo. Executá-la não cria ou reinicia uma partida. O código corresponde ao arquivo distribuído `missao_espacial.py`.
''')
code('from pathlib import Path\nENGINE_SOURCE = ' + repr(engine) + '\n' + '''engine_path = Path("missao_espacial.py")
if not engine_path.exists():
    engine_path.write_text(ENGINE_SOURCE, encoding="utf-8")
from missao_espacial import Game, DEFAULT_CATALOG
''')
markdown("""## 2. Definir contrato e sessão de agentes

Cada implementação é uma classe `Agent` com métodos específicos e retornos definidos. `AgentSession` executa o ciclo de vida: início/retomada, início de rodada, observação após cada fase e encerramento quando o participante é removido ou o jogo termina. A memória de cada instância entra automaticamente no checkpoint.

Esta célula prepara os arquivos de infraestrutura. A engine mantém seu protocolo interno; o adaptador faz a conversão sem exigir `request["kind"]` nas implementações.
""")
code("RUNTIME_SOURCES = " + repr(runtime_sources) + "\n" + """
for filename, source in RUNTIME_SOURCES.items():
    path = Path(filename)
    if not path.exists():
        path.write_text(source, encoding="utf-8")
""")
markdown("""## 3. Preparar os arquivos de agentes

Cada arquivo da pasta `agent` define `NATURE` (`HUMANO` ou `IA`) e `create_agent()`, que devolve uma nova instância de `Agent`, sem declarar ID. A classe implementa métodos como `choose_initiative`, `answer_question`, `authorize_vote`, `vote_proposal` e `choose_route`, cada um com retorno específico. `humanoide.py` é a implementação própria da IA; os quatro módulos humanos têm sua natureza definida. O carregador lê a biblioteca, sem sortear natureza ou implementação.

`humano_random.py` oferece ações e respostas aleatórias entre alternativas legais e integra a configuração padrão. Seu RNG é independente e a sequência entra no checkpoint.

Os IDs são rótulos atribuídos na configuração externa. A engine recebe explicitamente o ID cujo módulo tem natureza IA; não escolhe qual implementação será a IA. O carregador confere a compatibilidade com o estado do jogo antes de conectar callbacks.

A preparação instala exemplos somente quando a pasta ainda não contém implementações. Não sobrescreve código existente nem acrescenta políticas de exemplo à biblioteca personalizada. Arquivos iniciados por `_` são auxiliares. Edite os arquivos no painel do Colab; as variantes humanas herdam HumanDefault e sobrescrevem decisões específicas. Os nomes dos módulos identificam implementações, sem associação obrigatória aos IDs.

Após editar, execute `agents = assign_agents(game, load_agents("src/agent"))` para reconectar, conservando o vínculo salvo e o estado da partida. Em outro runtime, restaure também os arquivos personalizados: o checkpoint guarda os vínculos, mas não o código. Os nomes de módulos não entram na visão entregue aos callbacks.
""")
code('from carregar_agentes import load_agents, assign_agents\nAGENT_SOURCES = ' + repr(agent_sources) + "\n" + """
agent_directory = Path("src/agent")
agent_directory.mkdir(parents=True, exist_ok=True)
has_implementations = any(not p.name.startswith('_') for p in agent_directory.glob('*.py'))
for filename, source in AGENT_SOURCES.items():
    target = agent_directory / filename
    if not target.exists() and (filename.startswith('_') or not has_implementations):
        target.write_text(source, encoding="utf-8")
implementations = load_agents(agent_directory)
print({"implementacoes_carregadas": list(implementations)})
""")
markdown('''## 4. Setup central e nova partida

Todas as escolhas estão em **setup.json**. Edite esse arquivo no painel do Colab: `rodadas`, grupos em `tripulantes` (quantidade, papel e implementação) e `conhecimentos`. A quantidade total é a soma dos grupos. Para 50 tripulantes, por exemplo, altere a quantidade do último grupo de 1 para 46. Para 100.000 rodadas, altere apenas `rodadas`. Pode repetir qualquer implementação humana; cada participante recebe sua própria instância.

Destino: 2 × rodadas. Bônus por humano removido: rodadas ÷ humanos iniciais. A maioria considera votos válidos daquela votação. A saída continua exigindo dois bloqueadores. Esses valores são derivados pelo motor, sem novos parâmetros.

Esta célula prepara o setup se ausente e imprime a configuração carregada. Reexecutá-la cria **uma nova partida**; use a célula de retomada para conservar uma partida existente. Para salvar no Drive, configure `checkpoint` em setup.json com o caminho persistente.
''')
code('import json\nDEFAULT_SETUP = '+repr(setup_data)+'\n'+'''from setup_jogo import GameSetup
setup_path = Path("setup.json")
if not setup_path.exists():
    setup_path.write_text(json.dumps(DEFAULT_SETUP, ensure_ascii=False, indent=2), encoding="utf-8")
setup = GameSetup.load(setup_path)
print(json.dumps(setup.summary(), ensure_ascii=False, indent=2))
agents = setup.start()
game = agents.game
checkpoint = setup.checkpoint
print({"rodada": game.round, "fase": game.phase})
''')
markdown('''## 5. Executar e salvar entre fases

Executamos três rodadas e depois a escolha de perguntas da próxima rodada. O checkpoint conserva a fase efetivamente alcançada: perguntas, votação ou encerramento. As decisões do humano aleatório podem encerrar a partida antes dessas três rodadas.

`agents.advance(checkpoint=caminho)` salva após a fase concluída, incluindo as observações e memórias dos agentes. `agents.run_round(checkpoint=caminho)` pode salvar após cada fase da rodada. Use a sessão para executar também os hooks; a interface antiga da engine fica apenas como API de baixo nível. Salvar com frequência protege progresso, mas o histórico completo torna o arquivo maior ao longo da partida.
''')
code('''for _ in range(3):
    if game.finished:
        break
    agents.run_round()
if not game.finished:
    agents.advance(checkpoint=checkpoint)
else:
    agents.save(checkpoint)
print({"rodada": game.round, "fase": game.phase, "checkpoint": str(checkpoint)})
''')
markdown('''## 6. Retomar

Esta célula carrega o estado salvo, inclusive a fase atual e os sorteios. Em um novo runtime, execute primeiro a definição da engine e preparação dos módulos de agentes, configure `checkpoint` e execute esta carga. Callbacks e modelos precisam ser reconectados; a memória JSON de cada instância é restaurada por `load_state`, e `on_resume` recebe somente sua visão autorizada. O início de rodada e o encerramento não são repetidos se já ocorreram antes do checkpoint.
''')
code('''game = Game.load(checkpoint)
agents = assign_agents(game, load_agents("src/agent"))
print({"rodada_retornada": game.round, "fase_retornada": game.phase})
''')
markdown('''## 7. Continuar em lotes

Executar novamente esta célula continua a mesma partida. O lote é uma conveniência de execução, não altera regras ou N. Cada lote salva um checkpoint; para checkpoint a cada fase, passe `checkpoint=checkpoint` a `agents.run_round`.

As visões entregues automaticamente às políticas têm as últimas dez entradas de cada histórico, mas o checkpoint conserva o histórico completo. Altere `history_limit` se a política exigir outra janela, ou use `None` para todo o histórico. Em simulações longas, ler o histórico inteiro a cada ação aumenta bastante o custo.
''')
code('''for _ in range(10000):
    if game.finished:
        break
    agents.run_round()
agents.save(checkpoint)
print({"rodada": game.round, "fase": game.phase, "encerrado": game.finished})
if game.finished:
    print(json.dumps(game.result, ensure_ascii=False, indent=2))
''')
markdown('''## 8. Inspecionar uma visão privada

O professor pode inspecionar uma visão; não encaminhe o checkpoint ou `snapshot()` aos agentes. `history_limit=None` permite consultar o histórico completo autorizado de um agente. O resultado distingue retorno, oxigênio e compromisso com a missão; não define um vencedor único e não afirma entrega da carga depois do encerramento.
''')
code('''view_01 = game.view("01")
print({"id": view_01["id"], "respostas_recebidas": view_01["history_sizes"]["received"],
       "revelacoes_recebidas": view_01["history_sizes"]["revelations"]})
''')
notebook={'cells':cells,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
 'language_info':{'name':'python'},'colab':{'name':'06-Engine_Missao_Espacial_2026-2.ipynb'}},'nbformat':4,'nbformat_minor':5}
# IDs estáveis para compatibilidade com leitores nbformat 4.5.
for i, cell in enumerate(cells):
    cell['id']=f'engine-{i:02d}'
path=ROOT/'notebooks/06-Engine_Missao_Espacial_2026-2.ipynb'
path.write_text(json.dumps(notebook,ensure_ascii=False,indent=1)+'\n')
print(path.name)
