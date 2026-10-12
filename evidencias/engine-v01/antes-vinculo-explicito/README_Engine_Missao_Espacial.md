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

## Implementações independentes dos IDs

A pasta `agent/` contém uma biblioteca de implementações, não arquivos associados a participantes:

```text
notebooks/
  missao_espacial.py
  carregar_agentes.py
  agent/
    politica_alpha.py
    politica_beta.py
    politica_gamma.py
    politica_delta.py
    politica_epsilon.py
    _baseline.py
```

Cada módulo define apenas o callback síncrono `decide(view, request)`. Não declara `AGENT_ID`, não conhece antecipadamente seu participante e pode ser associado a qualquer ID. A função recebe o ID próprio e os IDs presentes pela visão do jogo, para poder escolher interlocutores; isso não fixa identidade ou implementação. Os cinco exemplos usam a mesma política simples como ponto de partida e podem ser editados independentemente.

```python
from carregar_agentes import load_agents, assign_agents

implementations = load_agents("agent")  # nome de implementação → callback

game = Game(N=10, seed=17)
policies = assign_agents(game, implementations)  # ID da partida → callback

game.run_round(policies)
game.save("partida.json")

# Retomar: reutiliza as atribuições salvas, sem novo sorteio.
game = Game.load("partida.json")
policies = assign_agents(game, load_agents("agent"))
game.run_round(policies)
```

`load_agents` descobre os módulos públicos `*.py` do diretório. Seus nomes identificam implementações, sem vínculo com os números dos uniformes. Arquivos iniciados por `_` são auxiliares; `__init__.py` não é executado. Imports relativos como `from ._baseline import decide` são suportados por um pacote isolado, sem alterar `sys.path`. Função inválida, pasta vazia ou declaração antiga de `AGENT_ID` gera `AgentLoadError`.

`assign_agents` distribui as implementações na partida nova usando um RNG independente do ambiente. Com cinco implementações, faz uma permutação. Com menos, reutiliza implementações, incluindo a possibilidade de um único módulo servir aos cinco participantes; com mais, seleciona cinco. O vínculo não é condicionado a quem é humano/IA e não consome o estado dos sorteios da engine. Para reproduzir uma experiência, use `seed` de atribuição explícito, separado do seed do ambiente. Sem seed, uma nova partida recebe um novo sorteio; variar seeds permite comparar distribuições diferentes.

A atribuição fica no checkpoint por um campo reservado `__agent_implementation__` na memória JSON de cada participante, usando a interface existente `set_policy_state`. O adaptador retira esse campo da visão passada ao callback: nomes de arquivos e metadados da atribuição não entram na entrada do agente/classificador. O arquivo da engine permanece inalterado.

Se o aplicativo atualizar memória via `set_policy_state`, preserve campos existentes, por exemplo:

```python
memory = game.view(participant_id, history_limit=1)["policy_state"]
game.set_policy_state(participant_id, {**memory, "counter": 7})
```

A recarga conserva o vínculo de uma partida já configurada, mesmo se outro seed for informado. Se um módulo salvo estiver ausente ou a atribuição estiver incompleta, falha sem substituir ou sortear participantes. Checkpoints antigos sem atribuição podem continuar com a interface original da engine; o novo atribuidor não inventa um sorteio para partidas já iniciadas sem esse registro.

Após editar um módulo, reconecte com `policies = assign_agents(game, load_agents("agent"))`. Isso troca o callback carregado daquela implementação, preservando seu vínculo e o estado do jogo. Carregue na inicialização ou reconexão, não a cada rodada. No notebook, a preparação não sobrescreve edições e não acrescenta exemplos a uma biblioteca personalizada que já contenha implementações.

Em outro runtime, restaure também os arquivos personalizados: o checkpoint guarda estado e vínculos, não código, globais de módulos ou pesos de modelos. Para continuar a mesma política, reconecte a mesma versão dos arquivos. Os exemplos antigos com IDs nos nomes e `AGENT_ID` foram preservados no histórico `evidencias/aula-05-2026-2/engine-v01/antes-desacoplar-ids/`; não integram a biblioteca vigente.

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
