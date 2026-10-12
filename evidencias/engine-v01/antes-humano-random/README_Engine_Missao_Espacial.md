# Engine e agentes — missão espacial

Python 3.10 ou posterior, somente biblioteca padrão. A engine está em `missao_espacial.py`; o contrato de agentes em `agent_contract.py`; ciclo de vida e adaptação em `agent_session.py`; descoberta e vínculo em `carregar_agentes.py`. O notebook `06-Engine_Missao_Espacial_2026-2.ipynb` contém esses arquivos e os exemplos. Nenhum modelo é carregado nesta versão.

## Um módulo por implementação

```text
agent/
  humanoide.py
  humano_alpha.py
  humano_beta.py
  humano_gamma.py
  humano_delta.py
  _baseline.py
```

Cada módulo declara `NATURE` e uma fábrica `create_agent() -> Agent`. A fábrica cria uma instância independente para cada participante. Os módulos não declaram IDs. `humanoide.py` tem implementação própria e natureza IA; os demais são humanos. Natureza descreve o personagem, não a tecnologia: uma política humana pode usar a cabeça treinada. Não há sorteio de natureza ou implementação.

As implementações humanas herdam `HumanDefault` e sobrescrevem os métodos que precisam mudar. `BaselineAgent` permanece somente como referência mínima para testes e exemplos de contrato. Um exemplo completo de módulo humano:

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
| Novas observações | `observe(view) -> None` | Depois de cada fase concluída, com sua visão privada atualizada |
| Encerramento do agente | `on_finish(view, reason) -> None` | Uma vez: remoção ou término da partida |

`reason` é `FinishReason.REMOVED` ou `FinishReason.GAME_ENDED`. Agentes removidos deixam de receber observações e decisões. A retomada não repete o início de rodada nem o encerramento já registrado. Instâncias encerradas têm estado restaurado, mas não recebem novamente `on_resume` ou `on_finish`.

A memória pertence à instância, em `self.memory`. `load_state(state: dict) -> None` restaura e `save_state() -> dict` exporta estado JSON. Ambos podem ser sobrescritos, preservando o contrato. Chaves precisam ser textuais e valores serializáveis; objetos Python, enums, modelos e tensores não são automaticamente serializados. Pesos podem ser compartilhados entre instâncias, mas memória e ciclo de vida são independentes por participante.

A sessão persiste a memória no estado do jogo depois de cada fase, junto com o vínculo de implementação e os marcadores de rodada/encerramento. Esses metadados reservados não entram em `AgentView` nem no estado entregue a `load_state`. Não é necessário manipular `set_policy_state` nos módulos. No aplicativo, para alterar a memória de uma instância, use por exemplo `agents.agent("01").memory["counter"] = 7` e `agents.save(caminho)`.

A memória livre do agente não é o gabarito do motor. Fatos confirmados e crenças registradas pela engine permanecem separados dela. A API `game.update_beliefs` continua disponível ao aplicativo para registrar posições, como antes; não transformar um campo arbitrário de memória em verdade global.

## Carregar, executar e retomar

```python
from missao_espacial import Game
from carregar_agentes import load_agents, assign_agents, ai_id_for_assignment

implementations = load_agents("agent")
assignment = {
    "01": "humano_alpha", "02": "humano_beta", "03": "humanoide",
    "04": "humano_gamma", "05": "humano_delta",
}
game = Game(N=10, seed=17, ai_id=ai_id_for_assignment(implementations, assignment))
agents = assign_agents(game, implementations, assignment)  # AgentSession
agents.run_round()
agents.advance(checkpoint="partida.json")
agents.save("partida.json")

# Novo processo/runtime:
game = Game.load("partida.json")
agents = assign_agents(game, load_agents("agent"))
agents.run_round()
```

03 é só o rótulo deste exemplo. O ID pode ser alterado na configuração antes de uma nova partida, sem mudar o humanoide. `ai_id_for_assignment` identifica o único módulo IA escolhido; o seed não atribui natureza ou implementação. O vínculo é conferido contra a natureza do jogo e conservado no checkpoint. Vínculos diferentes, incompletos, módulo ausente ou natureza alterada são rejeitados sem substituir os participantes.

`agents.advance` executa uma fase; `agents.run_round` conclui a rodada atual; ambos retornam `None`. Resultado fica em `game.result`. Use a sessão para executar também observação, hooks e persistência de memória. A interface original `game.advance(raw_policies)` é preservada como API de baixo nível; ela não executa o ciclo de vida da sessão. O único componente que interpreta `request.kind` e converte retornos para esse protocolo é `ProtocolAdapter`.

Depois de editar código, reconecte com `agents = assign_agents(game, load_agents("agent"))`: recria instâncias, restaura memória e chama `on_resume`, sem reiniciar rodada, recursos ou vínculos. `load_agents` descobre módulos públicos `*.py`; arquivos iniciados por `_` são auxiliares. Imports relativos são suportados em um pacote isolado, sem alterar `sys.path`. `__init__.py` não é executado pelo carregador. Carregue na inicialização/reconexão, não a cada rodada.

O notebook prepara só arquivos ausentes, não sobrescreve implementações personalizadas e não mistura exemplos numa biblioteca já existente. Módulos antigos precisam migrar de `decide` para uma classe e uma fábrica. As versões anteriores estão em `evidencias/aula-05-2026-2/engine-v01/antes-ciclo-vida/`.

## Checkpoint e Colab

A recuperação preserva o último checkpoint concluído: fase, ações pendentes, catálogo, controlador, progresso, oxigênio, penalidades, conhecimentos, crenças, mensagens, revelações, cotas, memórias de agentes, vínculos e RNG da engine. `save` grava temporário e substitui o arquivo após concluir a escrita. Formato do jogo é versionado.

`agents.advance(checkpoint=path)` salva após a fase e seus hooks. `agents.run_round(checkpoint=path)` pode salvar após cada fase da rodada. Sem esse argumento, o estado continua em memória; salve depois de um lote conforme o custo aceitável. Código, conexões e pesos de modelos precisam ser reconectados em outro runtime. Aleatoriedade própria de uma implementação precisa entrar em seu `save_state/load_state`; não é o RNG da engine.

Variáveis persistem entre células enquanto o runtime Colab existir. Para sobreviver à exclusão desse runtime, monte armazenamento persistente e salve ali, por exemplo `/content/drive/MyDrive/missao-espacial/partida.json` depois de montar o Drive. Arquivos personalizados de `agent/` também precisam ser restaurados. Executar a célula `Game(...)` cria outra partida; carregar o checkpoint continua a existente. O notebook foi executado em Python local, ainda não no serviço Google Colab.

## Privacidade e regras preservadas

O objeto `Game`, `snapshot()` e o checkpoint são reservados ao motor/professor. `AgentView` contém somente o próprio papel, participantes presentes, eventos públicos, fatos autorizados, crenças registradas e suas mensagens/revelações. Não contém mapa de naturezas, controlador inicial, N global ou nomes de módulos. Respostas e revelações continuam privadas; perguntas realizadas, pedidos, votos e efeitos são públicos.

Por padrão a sessão fornece as últimas dez entradas de cada histórico; `history_limit=None` entrega todo o histórico autorizado. O checkpoint conserva o histórico completo. Essa janela limita custo de leitura, não apaga eventos anteriores. Recursos e histórico crescem conforme as rodadas; a execução das políticas determina o custo adicional.

Oxigênio é guardado em quartos inteiros: início `4N`, consumo `4`, bônus humano `N`, preservando `N/4` sem arredondar bônus. Menos de uma rodada inteira encerra a partida, com eventual fração residual registrada. Liberação, cotas e intervalos das perguntas usam os valores propostos do catálogo v03 e continuam configuráveis.

A engine aplica os quatro turnos, votação em duas etapas, renúncia, penalidade, eleição imediata, saída e bloqueios simultâneos. Penalizados respondem e observam, mas não exercem iniciativa e se abstêm. IA tem restrições próprias. O controlador humano que continua perde direito de saída. Não há rodada desgovernada. A guarda de eleição sem candidato elegível discutida anteriormente permanece inalterada nesta mudança de contrato.

Humanos podem sacrificar-se, nunca sair ou nunca expulsar. As implementações atuais usam heurísticas de investigação, confiança e inferência por eliminação. A cabeça treinada ainda não está conectada. Entrega de carga depois do encerramento não é simulada: `cargo_delivered=None` indica ausência de observação; retorno cancela a entrega. Não há um único rótulo de vencedor.

## Validação

Na raiz dos materiais:

```sh
python3 evidencias/aula-05-2026-2/engine-v01/test_agent_lifecycle.py
python3 evidencias/aula-05-2026-2/engine-v01/test_carregar_agentes.py
python3 evidencias/aula-05-2026-2/engine-v01/test_engine.py
python3 notebooks/06-exemplo-engine-missao-espacial.py
python3 evidencias/aula-05-2026-2/engine-v01/validar_notebook.py
```

Os testes de ciclo de vida exercitam tipos em todas as decisões, assinaturas, estado JSON, instâncias independentes, hooks, penalidade, privacidade, remoção, encerramento único e retomada em outro processo. Os testes do carregador cobrem descoberta, fábricas, natureza definida, vínculo explícito e reconexão. A suíte da engine verifica regras preexistentes. O notebook foi executado localmente.

O registro de 100.000 rodadas refere-se à engine com políticas simples, anterior ao novo ciclo de vida; não é apresentado como teste de escala da sessão nova. Não houve treinamento, geração de massa, inferência Phi-4 nem execução no Colab. O gerador `evidencias/aula-05-2026-2/engine-v01/gerar_notebook.py` sincroniza os arquivos embutidos no notebook.


## Comportamentos implementados — 12/10/2026

| Módulo | Classe | Decisão específica |
|---|---|---|
| `humanoide.py` | `HumanoidAgent` | Missão, perguntas, respostas sinceras, abstenção em votos/eleição, bloqueio de toda saída, sem pedido de voto ou saída. |
| `humano_alpha.py` | `SacrificingHuman` | Sobrescreve `prioritizes_mission`: aceita sacrifício, continua quando controlador e permanece a bordo. |
| `humano_beta.py` | `NeverExitHuman` | Sobrescreve `allows_exit`: jamais solicita saída; ainda pode expulsar a IA e retornar como controlador. |
| `humano_gamma.py` | `NeverExpelHuman` | Sobrescreve `allows_expulsion`: não solicita expulsão e vota contra propostas de expulsão; pode autorizar o debate. |
| `humano_delta.py` | `HumanDefault` | Quarto humano provisório, até a implementação com Phi-4. |

A base reutilizável está em `agent/_human_default.py`, excluída da descoberta de módulos públicos. As quatro implementações específicas solicitadas são o humanoide e as três variantes; o Default fornece a base e mantém a quinta vaga executável. Nenhum módulo declara ID. Os perfis de cenário existentes continuam respeitados.

**Escolhas heurísticas desta implementação:** o Default prioriza preservar a tripulação e retorna quando eleito controlador. Só pede saída se tiver evidência confirmada de insuficiência, respeitando a restrição de saída. Sacrifício altera essa prioridade para concluir a missão. Não há mentira programada neste primeiro comportamento: respostas usam fatos autorizados, histórico próprio ou opiniões declaradas; desconhecimento produz `NÃO_SEI`. Isso é uma política inicial, não uma nova regra do jogo.

A investigação distribui perguntas entre destinatários e temas, começando por missão, destino e oxigênio, depois acidente, carga, crise e intenções. `AgentView.available_questions` fornece candidatos legais sem parâmetros e Q11 com um limiar derivado da rodada pública; é um conjunto de investigação, não um inventário completo das combinações do catálogo. Questões parametrizadas restantes podem ser construídas explicitamente pelos módulos. A sessão consulta somente disponibilidade pelas regras, sem consultar a identidade ou o conhecimento do destinatário.

Confiança inicia neutra; cada revelação privada verdadeira soma 1 e cada falsa subtrai 2, sem contagem duplicada. Relatos não verificados não recebem esse peso. O agente guarda seus históricos privados na memória para responder mesmo após saírem da janela da visão. Pedidos públicos de votação/saída e bonificações por remoção comprovam humanos. Após comprovar os quatro humanos, infere o humanoide por eliminação e o Default pode propor sua expulsão. Não confunde abstenção, mentira ou recusa com prova de identidade.

Para V01, apoia punição de um agente com confiança negativa; rejeita a própria punição. Apoia V02. Para V03, só apoia expulsar a IA inferida, preservando as variantes. Autoriza a discussão de propostas separadamente da decisão sobre a proposta. Em disputa de solicitantes, cede se existir concorrente com confiança não negativa; as regras continuam permitindo que nenhuma votação aconteça. Não há garantia de convergência da negociação.

`declare_beliefs(view) -> dict` declara apenas posições próprias (objetivo, sacrifício, confiança e justificativa de expulsão), sincronizadas pela sessão com o mecanismo de revelação. O retorno padrão é vazio, preservando agentes existentes. Essa declaração não concede fatos ou identidades. Memórias, contagens e evidências são retomadas no checkpoint. Os métodos `prioritizes_mission`, `allows_exit`, `allows_expulsion` e `expulsion_vote` permitem novas variantes sem duplicar investigação e respostas.

Validação desta entrega: 99 testes automatizados, incluindo 85 testes anteriores e 14 cenários de comportamento. Notebook executado localmente; não executado no serviço Colab. Phi-4 e dados de treino pendentes. A validação histórica de 100.000 rodadas pertence às políticas mínimas anteriores e não mede estas heurísticas.
