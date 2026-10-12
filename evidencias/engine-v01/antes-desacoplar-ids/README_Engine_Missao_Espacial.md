# Engine Python — missão espacial

Arquivos: `missao_espacial.py` (engine autossuficiente), `06-exemplo-engine-missao-espacial.py` (cinco políticas de demonstração) e `06-Engine_Missao_Espacial_2026-2.ipynb` (células de execução e retomada). Requer Python 3.10 ou posterior; usa somente a biblioteca padrão. Não altera Crivo nem carrega a cabeça treinada. O carregador externo `carregar_agentes.py` lê as implementações da pasta `agent/`; não modifica a engine.

## Executar localmente ou no Colab

```python
from missao_espacial import Game

game = Game(N=10, seed=17)
# policies: um callback (view, request) -> decisão para cada ID 01 a 05
# game.run_round(policies)
game.save("partida.json")

# Em outro processo/runtime, depois de importar a engine:
game = Game.load("partida.json")
# Reconectar callbacks/modelos antes de continuar:
# game.run_round(policies, checkpoint="partida.json")
```

O notebook contém a engine embutida e pode ser aberto sem fazer upload de outros arquivos. Foi executado localmente; ainda não foi executado no serviço Google Colab. Executar a célula `Game(...)` cria uma nova partida; importar/definir a classe não reinicia objetos existentes. A célula de lote continua o objeto atual.

No Colab, a memória entre células dura enquanto o runtime existir. Um arquivo na pasta temporária do runtime também pode desaparecer quando ele for excluído. Para recuperação depois de desconexões, monte armazenamento persistente e escolha ali o caminho de checkpoint. Por exemplo, após montar o Drive: `/content/drive/MyDrive/missao-espacial/partida.json`.

`save` escreve um arquivo temporário e substitui o anterior após concluir a escrita. O checkpoint inclui fase, ações pendentes, catálogo efetivo, participantes, controlador, oxigênio, progresso, penalidades, fatos, crenças, mensagens privadas, revelações, cotas de perguntas, memória JSON das políticas e estado do gerador aleatório. O formato tem versão; versões incompatíveis são rejeitadas.

A recuperação preserva o último checkpoint concluído. Escolha a frequência de salvamento conforme o custo aceitável: `advance(..., checkpoint=path)` salva após cada fase; `run_round(..., checkpoint=path)` salva após cada fase daquela rodada; chamadas sem esse argumento mantêm o estado em memória e permitem salvar ao fim de um lote. O código de callbacks, pesos de modelos e conexões externas não é serializado: precisam ser reconectados. Uma política com aleatoriedade própria deve guardar esse estado em `set_policy_state`; o RNG preservado automaticamente é o da engine.

## Um arquivo Python por agente

Estrutura distribuída:

```text
notebooks/
  missao_espacial.py
  carregar_agentes.py
  agent/
    agente_01.py
    agente_02.py
    agente_03.py
    agente_04.py
    agente_05.py
    _baseline.py
```

Cada arquivo de agente tem este contrato:

```python
AGENT_ID = "01"


def decide(view, request):
    # Sua implementação: regras, máquina de estados ou uso de modelo aprendido.
    # Devolva a decisão exigida por request["kind"], conforme os comandos abaixo.
    if request["kind"] == "route":
        return "CONTINUAR"
    # Implementar também os outros kinds que este participante pode receber.
```

Esse trecho apresenta o contrato, não uma política completa. Os cinco arquivos distribuídos contêm callbacks completos apoiados na política simples `_baseline.py`; cada arquivo pode ser editado independentemente para criar outro comportamento.

```python
from carregar_agentes import load_agents

policies = load_agents("agent")
game.run_round(policies)

# Após editar arquivos, reconectar sem alterar o objeto game:
policies = load_agents("agent")

# Após restaurar um checkpoint:
game = Game.load("partida.json")
policies = load_agents("agent")
game.run_round(policies)
```

O carregador descobre os arquivos `*.py` diretamente no diretório indicado. O nome do arquivo não determina o ID: a declaração `AGENT_ID` faz o vínculo. Devem existir exatamente as implementações dos IDs 01 a 05, inclusive para reconectar uma partida na qual algum participante já foi eliminado. IDs duplicados, ausentes ou inválidos e funções incompatíveis causam `AgentLoadError`, com indicação do problema. O ID não fixa a natureza humano/IA, definida pelo estado do jogo.

Arquivos que começam por `_` são auxiliares, não agentes; `__init__.py` não é executado pelo carregador. Para compartilhar código na pasta, use imports relativos, como `from ._baseline import decide`. Cada carregamento usa um pacote isolado, permitindo diretórios diferentes sem misturar implementações e sem alterar `sys.path`. Carregue uma vez na inicialização ou na reconexão, não a cada rodada. Edições dos módulos principais são lidas na nova chamada; o objeto de jogo não é recriado nem modificado pelo carregamento.

No notebook, a preparação cria somente arquivos ausentes e preserva edições existentes. Em um runtime novo, restaure também os arquivos personalizados de `agent/`: o checkpoint contém o estado do jogo e a memória JSON das políticas, mas não o código de seus módulos, variáveis globais de módulos ou pesos de modelos. Para continuar exatamente a mesma política, reconecte a mesma versão de seus arquivos.

## Estado e privacidade

O objeto `Game`, `snapshot()` e o checkpoint são reservados ao motor/professor. Políticas recebem cópias de `view(id)`, com o próprio papel, conhecimento autorizado, mensagens enviadas/recebidas, revelações recebidas e eventos públicos. O ID do controlador inicial, mapa de naturezas, N global, detentores e verdades de outros agentes não são fornecidos nessa visão.

Perguntas realizadas, pedidos, votos e efeitos são públicos. A resposta chega somente ao perguntador; uma revelação por rodada de perguntas chega somente ao perguntador sorteado. A recusa abre a verdade pertinente à pergunta quando o emissor sabe; desconhecimento real é revelado como `NÃO_SEI`. Abertura de crença confere o estado de crença do emissor, não o conhecimento real de terceiros.

Respostas não reveladas permanecem alegações. Apenas fatos revelados viram conhecimento confirmado do destinatário. Q11 permite deduções verificáveis sobre limites de distância; esses limites acompanham o progresso e podem permitir ao detentor do painel concluir a insuficiência do oxigênio. Relatos sobre terceiros não concedem transcrições ou revelações privadas de terceiros.

As visões automáticas de `advance`/`run_round` usam uma janela de dez registros de cada histórico por padrão. `history_limit=None` fornece toda a memória autorizada; `view(id, public_since=cursor)` permite ler eventos públicos incrementais. O histórico completo continua no estado e no checkpoint. Arquivos e memória crescem com a quantidade de eventos; a janela limita leitura da política, não apaga eventos antigos.

## Comandos por fase

| Fase | Método | Entrada |
|---|---|---|
| `initiative` | `initiatives` | ID → pergunta com destinatário/parâmetros, ou pedido V01/V02/V03 com alvo |
| `renounce` | `renounce` | Cada solicitante → booleano de renúncia |
| `authorize`, `proposal` | `vote` | Humanos habilitados → `A_FAVOR`, `CONTRA`, `ABSTENÇÃO` |
| `answers` | `answer` | ID do perguntador → alternativa fixa da pergunta |
| `election` | `elect` | Humanos habilitados → ID de candidato ou `ABSTENÇÃO` |
| `route` | `route` | `CONTINUAR` ou `RETORNAR`, decisão do controlador |
| `exit` | `exits` | IDs solicitantes + solicitante → IDs dos bloqueadores |

Os métodos exigem a fase correta. Votos da IA e penalizados são abstenções automáticas; se informados, só podem ser abstenção. Penalizados respondem. Iniciativas e respostas são recebidas em lotes e conferidas antes de aplicar efeitos, evitando que a ordem de entrega altere respostas da mesma fase.

`advance(policies)` consulta os callbacks e executa uma fase; `run_round(policies)` conclui a rodada atual. O pedido ao callback informa `kind` e os parâmetros necessários. A eleição interrompe o fluxo imediatamente após expulsão de controlador. Todos os humanos presentes sem penalidade atual são candidatos, com a exceção do penalizado único sobrevivente. Não há etapa adicional de candidatura ou votação para autorizar a eleição.

`question_allowed(author, recipient, qid, parameters)` consulta disponibilidade sem olhar natureza ou conhecimento do destinatário. `truthful_response(recipient, question)` é um helper reservado do motor para produzir uma resposta sincera usando o conhecimento desse respondente; não retorna a verdade global quando o agente desconhece o assunto. `update_beliefs` registra crenças da política antes de responder sobre posições/intenção. A engine não produz intenções a partir de rótulos do classificador.

## Convenções da primeira implementação

- Oxigênio é guardado em quartos de rodada inteiros: início `4N`, consumo `4`, bônus por humano `N`. Isso preserva exatamente `N/4`, inclusive acumulando frações. Menos de uma rodada inteira disponível encerra o jogo; a fração residual fica registrada. É a convenção já explicitada nas reproduções anteriores.
- A punição retira iniciativa e força abstenção na próxima rodada. Repetir uma punição para a mesma rodada não cria novas rodadas de penalidade. V02 remove penalidades atuais e agendadas, sem repetir ações já realizadas e sem remover restrições próprias da IA ou o bloqueio de saída do controlador.
- A distribuição inicial usa exatamente um detentor por bloco, sem associação fixa à natureza. Por padrão sorteia uma distribuição com um participante contendo dois blocos; é possível fornecer outra distribuição válida por `owners`. `ai_id` também é configurável ou sorteado.
- Liberação, cotas e intervalos usam os valores propostos do catálogo v03. Uma cópia pode ser alterada em `Game(..., catalog=catalog)`; a configuração efetiva acompanha o checkpoint.
- A IA inicial mantém o rumo da missão. Quando o humano eleito continua, perde o direito de saída. Um humano sozinho permanece apenas no fluxo de decisão de rota enquanto houver rodadas; não tenta perguntar a si ou votar.
- Perfis humanos expressam escolhas das políticas, não novas proibições do ambiente. Os callbacks finais e a integração da cabeça continuam separados desta entrega. As políticas de demonstração não tentam identificar a IA, conquistar confiança ou expelir outros participantes.
- A entrega da carga depois do encerramento não é simulada. `cargo_delivered=None` indica ausência de observação de entrega; retorno registra cancelamento. O resultado não rotula um único vencedor nem avalia o destino externo de quem saiu.

## Verificações e reprodução

Na raiz dos materiais do semestre:

```sh
python3 evidencias/aula-05-2026-2/engine-v01/test_engine.py
python3 evidencias/aula-05-2026-2/engine-v01/test_carregar_agentes.py
python3 evidencias/aula-05-2026-2/questoes-v03/test_catalogo_questoes.py
python3 notebooks/06-exemplo-engine-missao-espacial.py
python3 evidencias/aula-05-2026-2/engine-v01/validar_notebook.py
python3 evidencias/aula-05-2026-2/engine-v01/verificar_escala.py
```

Os testes cobrem regras e efeitos, privacidade, turnos, votos, penalidades, bonificação fracionária, eleição, saídas simultâneas, encerramento, comandos inválidos e retomada entre fases, inclusive em um processo novo. A exceção de candidato penalizado único sobrevivente e a remoção de punição futura usam fixtures ambientais específicas; não são apresentadas como caminhos de jogo produzidos pelas políticas do exemplo.

A reprodução de escala executa 100.000 rodadas com cinco agentes, perguntas Q10, 500.000 respostas e 100.000 revelações. Não exercita votação, saída ou modelo aprendido nessa reprodução; esses primeiros efeitos são cobertos em cenários separados. O notebook foi executado em Python local, não no Colab. Nenhum modelo foi treinado, nenhuma massa de treinamento foi gerada e não há inferência Phi-4 nesta entrega.

O gerador `evidencias/aula-05-2026-2/engine-v01/gerar_notebook.py` sincroniza a engine, o carregador e os arquivos de agentes embutidos no notebook.
