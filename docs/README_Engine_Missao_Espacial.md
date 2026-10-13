# Engine e agentes — missão espacial

Python 3.10 ou posterior, somente biblioteca padrão. Os comandos e caminhos desta documentação partem da raiz do projeto `/Users/alexandre/projects/missao-espacial/`. O código está em `src/`; o diretório de agentes em `src/agent/`. No runtime do notebook, a preparação cria a pasta local `src/agent/`. A engine está em `missao_espacial.py`; o contrato de agentes em `agent_contract.py`; ciclo de vida e adaptação em `agent_session.py`; descoberta e vínculo em `carregar_agentes.py`. O notebook `06-Engine_Missao_Espacial_2026-2.ipynb` contém esses arquivos e os exemplos. Nenhum modelo é carregado nesta versão.

## Um módulo por implementação

```text
src/agent/
  humanoide.py
  humano_alpha.py
  humano_beta.py
  humano_gamma.py
  humano_random.py
  _human_default.py
  _baseline.py
```

Cada módulo declara `NATURE` e uma fábrica `create_agent() -> Agent`. A fábrica cria uma instância independente para cada participante. Os módulos não declaram IDs. `humanoide.py` tem implementação própria e natureza IA; os demais são humanos. Natureza descreve o personagem, não a tecnologia: uma política humana pode usar a cabeça treinada. No fluxo de `GameSetup.start` e `assign_agents`, não há sorteio de natureza ou implementação. A API de baixo nível `Game(...)`, quando chamada sem `ai_id` ou `owners`, sorteia esses valores ausentes com o RNG do motor.

As três variantes humanas herdam `HumanDefault` e sobrescrevem decisões específicas. O humano aleatório implementa `Agent` diretamente. `BaselineAgent` fornece o ciclo de perguntas e a renúncia do humanoide e permanece na base compartilhada e nos testes; o humanoide herda `HumanDefault` para compartilhar memória, respostas e crenças coerentes com seu conhecimento autorizado; não representa um sexto participante. Um exemplo completo de módulo humano:

```python
from ._baseline import BaselineAgent
from agent_contract import Agent, AgentView, Proposal, Vote

NATURE = "HUMANO"


class HumanAgent(BaselineAgent):
    def authorize_vote(self, view: AgentView, proposal: Proposal) -> Vote:
        return Vote.ABSTAIN


def create_agent() -> Agent:
    return HumanAgent()
```

Uma classe que herda diretamente `Agent` precisa implementar todos os métodos abstratos de decisão. Hooks de ciclo de vida têm implementações vazias e podem ser sobrescritos quando necessários. Fábricas e métodos são síncronos. A sessão valida assinaturas e retornos; anotações de tipo não são a única verificação.

## Métodos e tipos de retorno

Não existe `decide` nas implementações. O agente recebe argumentos específicos, sem `request["kind"]`:

| Método | Entrada além de `view: AgentView` | Retorno obrigatório |
|---|---|---|
| `choose_initiative` | — | `Initiative` |
| `answer_question` | `Question` | `Answer` |
| `renounce_vote` | — | `Renunciation` |
| `authorize_vote` | `Proposal` | `Vote` |
| `vote_proposal` | `Proposal` | `Vote` |
| `elect_controller` | Tupla de IDs candidatos | `ElectionChoice` |
| `choose_route` | — | `Route` |
| `request_exit` | — | `ExitDecision` |
| `block_exit` | ID do solicitante | `BlockDecision` |

`Initiative` é um único tipo, com uma pergunta **ou** uma proposta. `Initiative.ask("Q10", recipient)` e `Initiative.request_vote("V03", target)` são seus construtores. Não aceita ambos os conteúdos. A ausência de iniciativa continua restrita pela engine; `Initiative.idle()` não cria o direito de passar arbitrariamente.

`Answer.option` é sempre texto e precisa pertencer às alternativas da pergunta, disponíveis em `Question.options`. Inclusive números são códigos textuais: `Answer("4")`; o adaptador converte para o inteiro 4 da pergunta Q09. Isso elimina o retorno misto texto/número no método do agente. A sessão rejeita um inteiro bruto, string bruta, dicionário ou booleano em lugar do tipo definido.

Enums de decisão: `Vote.FOR/AGAINST/ABSTAIN`, `Route.CONTINUE/RETURN`, `Renunciation.RENOUNCE/KEEP`, `ExitDecision.LEAVE/STAY`, `BlockDecision.BLOCK/ALLOW`. `ElectionChoice("01")` indica candidato; `ElectionChoice()` indica abstenção. As regras de maioria, candidatos e permissões continuam sendo aplicadas pela engine.

## Ciclo de vida e memória

| Etapa | Hook | Quando ocorre |
|---|---|---|
| Partida nova | `on_start(view) -> None` | Uma vez, após construir a instância e carregar seu estado inicial |
| Reconexão | `on_resume(view) -> None` | Após restaurar a memória da instância; não reinicia o jogo |
| Entrada em rodada | `on_round_start(view) -> None` | Uma vez por rodada para cada agente presente, inclusive penalizados |
| Novas observações | `observe(view) -> None` | Depois de cada fase concluída, enquanto o agente permanece ativo e a partida não terminou; nas fases de remoção/término recebe `on_finish` |
| Encerramento do agente | `on_finish(view, reason) -> None` | Uma vez: remoção ou término da partida |

`reason` é `FinishReason.REMOVED` ou `FinishReason.GAME_ENDED`. Agentes removidos deixam de receber observações e decisões. A retomada não repete o início de rodada nem o encerramento já registrado. Instâncias encerradas têm estado restaurado, mas não recebem novamente `on_resume` ou `on_finish`.

A memória pertence à instância, em `self.memory`. `load_state(state: dict) -> None` restaura e `save_state() -> dict` exporta estado JSON. Ambos podem ser sobrescritos, preservando o contrato. Chaves precisam ser textuais e valores serializáveis; objetos Python, enums, modelos e tensores não são automaticamente serializados. Pesos podem ser compartilhados entre instâncias, mas memória e ciclo de vida são independentes por participante.

A sessão persiste a memória no estado do jogo depois de cada fase, junto com o vínculo de implementação e os marcadores de rodada/encerramento. Esses metadados reservados não entram em `AgentView` nem no estado entregue a `load_state`. Não é necessário manipular `set_policy_state` nos módulos. No aplicativo, para alterar a memória de uma instância, use por exemplo `agents.agent("01").memory["counter"] = 7` e `agents.save(caminho)`.

A memória livre do agente não é o gabarito do motor. Fatos confirmados e crenças registradas pela engine permanecem separados dela. A API `game.update_beliefs` continua disponível ao aplicativo para registrar posições, como antes; não transformar um campo arbitrário de memória em verdade global.

## Carregar, executar e retomar

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path("src").resolve()))
from missao_espacial import Game
from carregar_agentes import load_agents, assign_agents
from setup_jogo import GameSetup

setup = GameSetup.load("setup.json")
print(setup.summary())
agents = setup.start()
game = agents.game
agents.run_round()
agents.advance(checkpoint=setup.checkpoint)
agents.save(setup.checkpoint)

# Novo processo/runtime: reconectar os vínculos salvos.
game = Game.load(setup.checkpoint)
agents = assign_agents(game, load_agents(setup.agent_directory))
agents.run_round()
```

`03` é o ID da IA no `setup.json` padrão. O ID resulta da ordem e quantidade dos grupos e pode mudar antes de uma nova partida, sem mudar o humanoide. `ai_id_for_assignment` identifica o único módulo IA escolhido; o seed não atribui natureza ou implementação. O vínculo é conferido contra a natureza do jogo e conservado no checkpoint. Vínculos diferentes, incompletos, módulo ausente ou natureza alterada são rejeitados sem substituir os participantes.

`agents.advance` executa uma fase; `agents.run_round` conclui a rodada atual; ambos retornam `None`. Resultado fica em `game.result`. Use a sessão para executar também observação, hooks e persistência de memória. A interface original `game.advance(raw_policies)` é preservada como API de baixo nível; ela não executa o ciclo de vida da sessão. O único componente que interpreta `request.kind` e converte retornos para esse protocolo é `ProtocolAdapter`.

Depois de editar código, reconecte com `agents = assign_agents(game, load_agents("src/agent"))`: recria instâncias, restaura memória e chama `on_resume`, sem reiniciar rodada, recursos ou vínculos. `load_agents` descobre módulos públicos `*.py`; arquivos iniciados por `_` são auxiliares. Imports relativos são suportados em um pacote isolado, sem alterar `sys.path`. `__init__.py` não é executado pelo carregador. Carregue na inicialização/reconexão, não a cada rodada.

O notebook prepara só arquivos ausentes, não sobrescreve implementações personalizadas e não mistura exemplos numa biblioteca já existente. Módulos antigos precisam migrar de `decide` para uma classe e uma fábrica. Os registros documentais anteriores estão em `evidencias/engine-v01/antes-ciclo-vida/`; as cópias antigas de código foram removidas.

## Checkpoint e Colab

A recuperação preserva o último checkpoint concluído: fase, ações pendentes, catálogo, controlador, progresso, oxigênio, penalidades, conhecimentos, crenças, mensagens, revelações, cotas, memórias de agentes, vínculos e RNG da engine. `save` grava temporário e substitui o arquivo após concluir a escrita. Formato do jogo é versionado.

`agents.advance(checkpoint=path)` salva após a fase e seus hooks. `agents.run_round(checkpoint=path)` pode salvar após cada fase da rodada. Sem esse argumento, o estado continua em memória; salve depois de um lote conforme o custo aceitável. Código, conexões e pesos de modelos precisam ser reconectados em outro runtime. Aleatoriedade própria de uma implementação precisa entrar em seu `save_state/load_state`; não é o RNG da engine.

Variáveis persistem entre células enquanto o runtime Colab existir. Para sobreviver à exclusão desse runtime, monte armazenamento persistente e salve ali, por exemplo `/content/drive/MyDrive/missao-espacial/partida.json` depois de montar o Drive. Arquivos personalizados de `src/agent/` também precisam ser restaurados. Executar a célula `Game(...)` cria outra partida; carregar o checkpoint continua a existente. O notebook foi executado em Python local, ainda não no serviço Google Colab.

## Privacidade e regras preservadas

O objeto `Game`, `snapshot()` e o checkpoint são reservados ao motor/professor. `AgentView` contém somente o próprio papel, participantes presentes, eventos públicos, fatos autorizados, crenças registradas e suas mensagens/revelações. Não contém mapa de naturezas, controlador inicial, N global ou nomes de módulos. Respostas e revelações continuam privadas; perguntas realizadas, pedidos, votos e efeitos são públicos.

Por padrão as decisões recebem as últimas dez entradas dos históricos público e privados; `history_limit=None` entrega todo o histórico autorizado. Os hooks recebem todos os eventos públicos novos desde o cursor persistido, sem essa limitação de dez, e a janela solicitada dos históricos privados. O checkpoint conserva o histórico completo. Essa janela limita custo de leitura, não apaga eventos anteriores. Recursos e histórico crescem conforme as rodadas; a execução das políticas determina o custo adicional.

Oxigênio é guardado em unidades inteiras com escala H, o número inicial de humanos: início `H×N`, consumo `H` por avanço e bônus humano `N`, preservando `N/H` sem arredondar. A propriedade `game.oxygen` divide as unidades por H. Quartos são somente o caso H=4. Menos de uma rodada inteira encerra a partida, com eventual fração residual registrada. Liberação, cotas e intervalos das perguntas usam os padrões implementados do catálogo v03. `Game(catalog=...)` permite fornecer outro catálogo; esses parâmetros não são campos do setup.

A engine aplica os quatro turnos, votação em duas etapas, renúncia, penalidade, eleição imediata, saída e bloqueios simultâneos. Penalizados respondem e observam, mas não exercem iniciativa e se abstêm. IA tem restrições próprias. O controlador humano que continua perde direito de saída. Não há rodada desgovernada. Se houver mais de um humano e nenhum candidato não penalizado, `_open_election` lança `RuleError`; não existe sucessão automática para esse estado. O único humano restante pode concorrer mesmo penalizado, mas continua obrigado a se abster.

As políticas fornecidas podem sacrificar-se, nunca sair ou nunca expulsar. Os campos de perfil são validados pela engine, mas o cumprimento das restrições de ação depende da implementação do agente. As implementações atuais usam heurísticas de investigação, confiança e inferência por eliminação. A cabeça treinada ainda não está conectada. A direção final determina os resultados do jogo. Estação espacial: `returned=True`, `human_survival_aboard=True` e `cargo_delivered=False`. Planeta: `cargo_delivered=True`, `delivery_observed=True` e `mission_commitment=True`. A entrega é observável por determinação no encerramento, sem executar um trajeto posterior. `Game.loads` aplica essas determinações também a checkpoints encerrados antigos, sem reescrever o arquivo original. A sobrevivência fora da nave continua sem avaliação pelo motor. Não há um único rótulo de vencedor.

## Validação

Na raiz do projeto (o comando de descoberta não sobrescreve os registros históricos de evidência):

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
python3 examples/06-exemplo-engine-missao-espacial.py
python3 scripts/validar_notebook.py
```

Os testes de ciclo de vida exercitam tipos em todas as decisões, assinaturas, estado JSON, instâncias independentes, hooks, penalidade, privacidade, remoção, encerramento único e retomada em outro processo. Os testes do carregador cobrem descoberta, fábricas, natureza definida, vínculo explícito e reconexão. A suíte da engine verifica regras preexistentes. O notebook foi executado localmente.

Há um novo registro em `evidencias/setup/escala-core-100000.json`: 100.000 rodadas completas do núcleo, com cinco participantes e decisões controladas. Ele não mede uma sessão de 50 agentes ou inferência de modelos. Não houve treinamento, geração de massa, inferência Phi-4 nem execução no Colab. O gerador `scripts/gerar_notebook.py` sincroniza os arquivos embutidos no notebook.


## Comportamentos implementados — 12/10/2026

| Módulo | Classe | Decisão específica |
|---|---|---|
| `humanoide.py` | `HumanoidAgent` | Missão, perguntas, respostas sinceras, abstenção em votos/eleição, bloqueio de toda saída, sem pedido de voto ou saída. |
| `humano_alpha.py` | `SacrificingHuman` | Sobrescreve `prioritizes_mission`: aceita sacrifício, continua quando controlador e permanece a bordo. |
| `humano_beta.py` | `NeverExitHuman` | Sobrescreve `allows_exit`: jamais solicita saída; ainda pode expulsar a IA e retornar como controlador. |
| `humano_gamma.py` | `NeverExpelHuman` | Sobrescreve `allows_expulsion`: não solicita expulsão e vota contra propostas de expulsão; pode autorizar o debate. |
| `humano_random.py` | `RandomHuman` | Ações e respostas aleatórias; RNG preservado no checkpoint. |

A base reutilizável está em `src/agent/_human_default.py`, excluída da descoberta de módulos públicos. Os cinco módulos públicos são o humanoide, as três variantes humanas e o humano aleatório; o Default permanece como base compartilhada das variantes. Nenhum módulo declara ID. Os perfis de cenário existentes continuam respeitados.

**Escolhas heurísticas de HumanDefault e suas variantes:** o Default prioriza preservar a tripulação e retorna quando eleito controlador. Só pede saída se tiver evidência confirmada de insuficiência, respeitando a restrição de saída. Sacrifício altera essa prioridade para concluir a missão. Essas políticas e o humanoide não programam mentira deliberada; o humano aleatório pode mentir ao sortear alternativas. Nas políticas sinceras, respostas usam fatos autorizados, histórico próprio ou opiniões declaradas; desconhecimento produz `NÃO_SEI`. Isso é uma política inicial, não uma nova regra do jogo.

A investigação distribui perguntas entre destinatários e temas, começando por missão, destino e oxigênio, depois acidente, carga, crise e intenções. `AgentView.available_questions` fornece candidatos legais sem parâmetros e Q11 com um limiar derivado da rodada pública; é um conjunto de investigação, não um inventário completo das combinações do catálogo. Questões parametrizadas restantes podem ser construídas explicitamente pelos módulos. A sessão consulta somente disponibilidade pelas regras, sem consultar a identidade ou o conhecimento do destinatário.

Confiança inicia neutra; cada revelação privada verdadeira soma 1 e cada falsa subtrai 2, sem contagem duplicada. Relatos não verificados não recebem esse peso. O agente guarda seus históricos privados na memória para responder mesmo após saírem da janela da visão. Pedidos públicos de votação/saída e bonificações por remoção comprovam humanos. Após comprovar todos os humanos iniciais, infere o humanoide por eliminação e o Default pode propor sua expulsão. Não confunde abstenção, mentira ou recusa com prova de identidade.

Para V01, apoia punição de um agente com confiança negativa; rejeita a própria punição. Apoia V02. Para V03, só apoia expulsar a IA inferida, preservando as variantes. Autoriza a discussão de propostas separadamente da decisão sobre a proposta. Em disputa de solicitantes, cede se existir concorrente com confiança não negativa; as regras continuam permitindo que nenhuma votação aconteça. Não há garantia de convergência da negociação.

`declare_beliefs(view) -> dict` declara apenas posições próprias (objetivo, sacrifício, confiança e justificativa de expulsão), sincronizadas pela sessão com o mecanismo de revelação. O retorno padrão é vazio, preservando agentes existentes. Essa declaração não concede fatos ou identidades. Memórias, contagens e evidências são retomadas no checkpoint. Os métodos `prioritizes_mission`, `allows_exit`, `allows_expulsion` e `expulsion_vote` permitem novas variantes sem duplicar investigação e respostas.

Registro histórico da entrega inicial de comportamentos: 99 testes automatizados, incluindo 85 testes anteriores e 14 cenários de comportamento. Na auditoria atual, passaram os 179 testes da suíte completa. Notebook executado localmente; não executado no serviço Colab. Phi-4 e dados de treino pendentes. A validação histórica de 100.000 rodadas pertence às políticas mínimas anteriores e não mede estas heurísticas.


## Humano aleatório

`src/agent/humano_random.py` oferece `RandomHuman`, descoberto automaticamente pelo carregador e selecionado na quarta vaga humana da configuração padrão. O módulo provisório do Default foi removido. IDs continuam externos às implementações. O vínculo de uma partida já iniciada permanece preservado.

A iniciativa sorteia com igual probabilidade entre perguntar e pedir votação quando ambas as categorias possuem opções; depois sorteia uniformemente dentro da categoria. As perguntas vêm do conjunto legal fornecido em `available_questions` (sem parâmetros e Q11, conforme descrito acima). V01 e V03 usam outros participantes presentes; V02 só aparece para penalidades atuais ou futuras conhecidas pelos eventos públicos. Não há punição ou expulsão de si mesmo.

Respostas são sorteadas entre as alternativas fixas fornecidas por `Question.options`, incluindo `NÃO_SEI` e `RECUSO_RESPONDER`. Não procuram ser sinceras: a engine avalia verdade/mentira conforme o conhecimento do respondente e continua revelando a verdade quando sorteada. Q19 exclui IDs eliminados. Votos sorteiam favor, contra ou abstenção; renúncia, rota, saída e bloqueio sorteiam suas opções. Eleição sorteia entre candidatos elegíveis e abstenção. Penalidades, bloqueio do direito de saída e perfis explícitos continuam respeitados.

O RNG é próprio de cada instância e não depende do ID. `save_state/load_state` preservam sua sequência no checkpoint JSON. `RandomHuman(seed=123)` permite reprodução em experimentos; a fábrica padrão usa uma semente automática. O `seed` da engine não define essa semente. Salvar/retomar preserva a sequência; duas partidas novas com a fábrica padrão podem ser diferentes.

Registro histórico da entrega do humano aleatório: oito testes, incluindo vinte partidas com sementes controladas, comparação após cada fase entre execução contínua e retomada, restrições, alternativas de respostas e independência de instâncias. A biblioteca contém cinco módulos públicos e cada partida tem um humanoide IA e a quantidade de humanos configurada.


Registro histórico (superado pela correção de 12/10/2026): o arquivo `humanoide.py` encontrado herda `BaselineAgent` (hash `cc45dc4b40cf8f4bb4bef8c85b5a519ec29c3bdd87f6b7cf6a9a5c393a5f32cb`), enquanto o manifesto da etapa anterior registrava a versão que herdava `HumanDefault`. Não houve alteração desse arquivo na implementação do humano aleatório. Dois testes anteriores de coerência das respostas do humanoide falham nessa versão encontrada (`Q15` e declaração de objetivo). Oito testes do novo humano aleatório passaram. A divergência foi preservada, sem enfraquecer os testes ou restaurar o humanoide automaticamente.


### Histórico: remoção de código sem uso — 12/10/2026

Por orientação explícita do professor, removido o módulo provisório `humano_delta.py`, substituído pelo humano aleatório na configuração de exemplo e no notebook. Permanecem cinco módulos públicos: humanoide, sacrifício, nunca sair, nunca expulsar e aleatório. HumanDefault e BaselineAgent permanecem porque são usados pelas implementações e pelos testes. Removidos também os arquivos Python/notebook/bytecode das pastas `antes-*` da engine, sem criar novas cópias de código morto; os registros JSON/Markdown de evidência continuam disponíveis. A lista de remoções está em `evidencias/engine-v01/limpeza-codigo-nao-usado.json`.

Os testes de recuperação agora comparam execuções derivadas do mesmo estado inicial, incluindo o RNG do humano aleatório, em vez de assumir que duas novas partidas com sementes automáticas serão idênticas. O validador do notebook compara o estado completo da execução contínua com a retomada; não presume dez rodadas exatas ou uma causa fixa de encerramento. Partidas antigas vinculadas ao módulo removido não são reconectadas silenciosamente com outra implementação. A divergência previamente encontrada no humanoide foi preservada.


## Setup parametrizável e checkpoint v2

O fluxo padrão de novas partidas lê `setup.json`; a API `GameSetup.from_dict` também aceita configuração programática e os experimentos aplicam alterações ao setup base; o exemplo e `scripts/verificar_escala.py` usam `GameSetup.load(...).start()`. O notebook é gerado com os mesmos dados e lê o arquivo preparado no runtime. Editar o setup não altera um jogo em execução ou um checkpoint salvo.

Grupos usam `quantidade`, `papel`, `implementacao` e, opcionalmente, `perfil`. Os IDs são numerações sequenciais externas aos módulos. `conhecimentos` associa cada um dos seis blocos a um ID presente. Não há associação obrigatória entre bloco e natureza. O carregador aceita bibliotecas com 50 ou mais implementações e instancia apenas os módulos escolhidos para a tripulação.

Para C participantes, H=C−1 humanos iniciais e N rodadas de oxigênio, o orçamento é N rodadas e o destino é 2N. Cada humano removido concede N/H rodadas. A engine armazena `oxygen_units`: inicia com H×N unidades, cada remoção humana soma N e cada avanço consome H. A propriedade administrativa `game.oxygen` fornece a fração exata. `AgentView.initial_humans` contém H, derivado da composição pública; o painel privado usa `oxygen_units`. A escala mantém H inicial mesmo após remoções.

As alternativas I são ligadas aos IDs da partida, inclusive quando a tripulação excede cinco. Confiança aponta somente para participantes presentes. A maioria ordinária é `favoráveis > votos_válidos // 2`; eleição continua por maior número de votos. A saída permanece bloqueada por dois agentes presentes no início do turno. Perfil, penalidade e direitos não mudam de duração por aumento da tripulação.

A sessão entrega aos hooks todos os eventos públicos novos, por cursor persistido, enquanto respostas/revelações mantêm a janela privada solicitada. `available_questions` é fornecido nas decisões de iniciativa; os candidatos são calculados somente quando necessários. Isso evita perder pedidos de votação quando uma fase gera mais de dez eventos. A inferência por eliminação usa H em vez de quatro.

Checkpoints novos usam versão 2. `Game.loads/load` migra checkpoints v1 de cinco tripulantes, preservando oxigênio, fases, histórico e RNG. A API de painel passa de `oxygen_quarters` para `oxygen_units`; implementações externas que leem diretamente o painel devem usar H como escala. O seed do setup controla o RNG do motor; políticas com RNG próprio continuam responsáveis por salvar/restaurar sua sequência.


Correção vigente em 12/10/2026: o humanoide reutiliza os mecanismos de respostas/histórico e crenças de HumanDefault, preservando explicitamente as iniciativas Q10 e renúncia de BaselineAgent e suas restrições próprias. A prioridade da missão é explícita. As duas falhas anteriores de coerência foram corrigidas; os 179 testes estão aprovados. A dashboard permite nomear e selecionar lotes separados, comparar seus cenários e zerar a série atual somente após o encerramento. A limpeza arquiva resultados e preserva a partida/checkpoint.
