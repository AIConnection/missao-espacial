# Missão espacial — aulas 05 e 06

Projeto do simulador com uma tripulação configurável: um humanoide IA e qualquer quantidade positiva de humanos. A aula 05 prepara a cabeça de classificação; a aula 06 utiliza o jogo. A engine e os comportamentos em Python estão implementados. Os dados de treinamento e a integração com Phi-4 continuam pendentes.

## Onde encontrar

```text
missao-espacial/
├── setup.json               # Único setup editável de novas partidas
├── src/                     # Engine, contrato, sessão e catálogo em Python
│   └── agent/               # Cinco implementações e suas bases compartilhadas
├── tests/                   # Testes da engine, agentes, recuperação e catálogo
├── notebooks/               # Notebook autossuficiente para levar ao Colab
├── examples/                # Partida e recuperação por checkpoint
├── scripts/                 # Gerar/validar notebook e verificações auxiliares
├── catalogos/               # Questões e alternativas fixas da versão atual
├── docs/                    # Regras, documentação e diagramas Mermaid
│   └── historico/           # Proposta inicial e seus documentos exportados
├── evidencias/              # Resultados de validação e decisões anteriores
├── estado/                  # Checkpoints do jogo
└── entrega.json             # Manifesto atual, caminhos e hashes
```

As [regras atuais](docs/05-06-Cenario_e_Regras_Jogo_Missao_Espacial_2026-2.md) delimitam o jogo. A [documentação da engine](docs/README_Engine_Missao_Espacial.md) descreve contratos, agentes e checkpoints. Os [diagramas](docs/diagramas/) mostram os turnos e decisões. A proposta inicial em `docs/historico/` contém ideias substituídas e não define o comportamento atual.

## Configurar em um único lugar

Edite [setup.json](setup.json). Ali estão `rodadas`, `seed` do motor, diretório dos agentes, checkpoint, os grupos de `tripulantes` e os detentores de `conhecimentos`. Cada grupo define `quantidade`, `papel` (`HUMANO`/`IA`) e `implementacao`. O total de tripulantes é a soma das quantidades; não há limite de cinco participantes ou de cinco módulos disponíveis.

Na configuração padrão, quatro grupos têm quantidade 1. Altere a quantidade do último grupo para:

| Total desejado | Quantidade do último grupo | Humanos iniciais | Maioria se todos os humanos votarem |
|---|---:|---:|---:|
| 5 | 1 | 4 | 3 |
| 10 | 6 | 9 | 5 |
| 15 | 11 | 14 | 8 |
| 50 | 46 | 49 | 25 |

Para 100.000 rodadas iniciais, use `"rodadas": 100000`. As bonificações podem ampliar a duração; retorno e remoções podem encerrar a partida antes. Os IDs são atribuídos pela ordem dos grupos, sem identidade sorteada. Ao mudar quantidades nos primeiros grupos, revise os IDs em `conhecimentos`; o resumo exibido antes da partida mostra o vínculo expandido. Cada bloco protegido mantém exatamente um detentor; um agente pode deter vários blocos.

Pode selecionar 50 implementações diferentes ou reutilizar uma implementação em vários agentes. Cada participante recebe uma instância e memória independentes. O papel deve ser compatível com `NATURE` do módulo. A partida mantém exatamente um humanoide IA. O perfil opcional de cada grupo permite restrições humanas adicionais.

O motor deriva destino em `2 × N`, bônus de `N ÷ humanos iniciais` por humano removido e maioria de **mais da metade dos votos válidos**. IA, penalizados e abstenções não contam como votos válidos. Eleição do controlador usa o maior número de votos. A saída continua exigindo pelo menos dois bloqueadores. O denominador do bônus permanece o número inicial de humanos.

O notebook incorpora este mesmo setup pelo gerador e prepara `setup.json` no runtime. Edite esse arquivo para uma nova partida; retomar um checkpoint preserva a tripulação e as rodadas salvas.

## Executar

A partir desta pasta, com Python 3.10 ou posterior e sem instalar dependências:

```sh
python3 examples/06-exemplo-engine-missao-espacial.py
python3 -m unittest discover -s tests -p 'test_*.py'
python3 scripts/gerar_notebook.py
python3 scripts/validar_notebook.py
python3 scripts/verificar_escala.py
```

O [notebook](notebooks/06-Engine_Missao_Espacial_2026-2.ipynb) contém a engine, o contrato e os agentes. Pode ser enviado ao Colab como arquivo único. Sua preparação cria arquivos locais no runtime; eles são distintos da pasta de fontes `src/` deste projeto. Checkpoints devem ficar em armazenamento persistente para sobreviver à exclusão do runtime.

Para alterar agentes, edite `src/agent/`. O carregador descobre os módulos sem alteração da engine. A seleção de módulos e papéis é feita em setup.json. O exemplo, o notebook e o executor de escala leem esse mesmo setup.

O executor de escala registra a partida configurada em `evidencias/setup/execucao-configurada.json` e salva o checkpoint no caminho do setup. Resultados matemáticos anteriores, com distâncias ilustrativas, permanecem em `evidencias/validacao-oxigenio/` como histórico. A configuração atual é validada pelos testes da engine e do setup.

## Estado da validação

179 de 179 testes passaram, incluindo os 20 testes do setup. As falhas nas respostas de histórico e objetivo do humanoide foram corrigidas, sem enfraquecer os testes. Foram validadas tripulações de 5, 10, 15 e 50, configuração de 10, 20, 50 e 100.000 rodadas, 50 implementações distintas, frações exatas, votação e retomada com 50 participantes.

Também foram executadas 100.000 rodadas completas do núcleo com cinco participantes e ações controladas, gerando 500.000 respostas e 100.000 revelações. Essa execução não mede políticas aprendidas ou 50 agentes por 100.000 rodadas. O notebook foi executado localmente e retomou o mesmo estado da execução contínua. Não houve execução no serviço Colab ou treinamento Phi-4.

O [registro da movimentação](evidencias/organizacao/movimentacao.json) relaciona os caminhos anteriores aos atuais e conserva os hashes dos arquivos antes de atualizar referências. Os materiais das demais aulas permanecem nos diretórios comuns da disciplina.

## Dashboard do jogo

Execute na pasta do projeto:

```sh
python3 src/dashboard.py
```

Abra http://127.0.0.1:8765. A dashboard começa uma nova sessão a partir do `setup.json`, sem sobrescrever o checkpoint existente. Use **Retomar checkpoint** para carregar a partida salva; **Salvar checkpoint** grava explicitamente no caminho do setup. **Nova partida do setup** relê a configuração. Esses controles substituem a sessão exibida em memória; salve antes de trocar uma partida que queira conservar.

Acompanhe rodada, fase, oxigênio exato, progresso, controlador, tripulação, penalidades e histórico paginado de ações. Selecione um agente para ver conhecimentos, acesso ao painel/distância, respostas recebidas/enviadas, verdades reveladas e crenças declaradas. Respostas recebidas ficam separadas das confirmações; fatos dinâmicos antigos aparecem como históricos. Indicadores de confiança e humanos identificados aparecem nas políticas que os mantêm.

Avance por fase ou rodada, ou execute automaticamente e pause entre rodadas. O histórico público permite navegar por toda a partida; as listas privadas mostram os últimos 50 registros e o total. A execução não salva a cada fase: use o botão de checkpoint para persistir o ponto de retomada. Pausar interrompe a sequência após a rodada em andamento.

Esta é a visão administrativa do professor, com naturezas e informações privadas visíveis. Ela não altera o contexto entregue aos agentes. A interface funciona no navegador local, com Python e biblioteca padrão; ainda não foi integrada à interface do Colab. O observador `dashboard.observe(session, participant)` também permite consultar uma sessão existente sem executar decisões.

Foram validados seis testes da dashboard e interações reais no navegador. A engine e os comportamentos dos agentes não foram modificados.

## Experimentos: muitas partidas e comparação de cenários

Edite [experimentos.json](experimentos.json), separado do setup da partida interativa. `partidas_por_cenario` é a quantidade de **partidas completas** por cenário; `rodadas` no setup continua sendo a reserva inicial de oxigênio de **cada partida**. Assim, 100.000 partidas com 10 rodadas é diferente de uma partida com 100.000 rodadas iniciais. O retorno ou as bonificações podem alterar a duração efetiva.

O plano aponta para o `setup_base`, define `seed_base`, `diretorio_resultados` e uma lista de cenários com `nome` e `alteracoes`. Campos de `alteracoes` substituem o campo inteiro do setup: para mudar um grupo, forneça a lista `tripulantes` completa; os demais campos permanecem iguais ao setup base. Pode variar rodadas, quantidade de tripulantes, implementação, perfil e distribuição de conhecimentos. Todas as regras e validações do setup continuam aplicadas. `seed` é definida pelo lote e o checkpoint da partida interativa não é escrito. O primeiro cenário é a referência das comparações.

O exemplo configurado executa 1.000 partidas por cenário e compara o setup base com a mesma configuração acrescentando `never_exit: true` ao humano aleatório. Altere somente um fator por vez quando quiser isolar seu efeito; alterações simultâneas medem o efeito conjunto. Para comparar implementações, troque o módulo no grupo correspondente. Para avaliar uma revisão de código em relação à anterior no mesmo lote, disponibilize as duas implementações com nomes distintos e registre-as nos cenários.

Execute pelo botão **Experimentos → Iniciar lote** na dashboard ou pelo terminal:

```sh
python3 src/experimentos.py
# Outro plano, se necessário:
python3 src/experimentos.py --plan caminho/experimentos.json
```

A dashboard exibe progresso, permite interromper seu próprio lote entre fases e apresenta o relatório mais recente salvo. Um lote externo, iniciado por CLI, é identificado pelo estado gravado em arquivo; a página não afirma controlar esse processo. Os lotes executam separadamente da partida interativa. Ao reiniciar a aplicação, o último relatório pode ser lido novamente; isso não retoma uma execução incompleta. Relatórios anteriores permanecem nos respectivos diretórios, com CSV e JSONL.

Cada lote cria um diretório próprio em `diretorio_resultados`, contendo:

- `relatorio.json`: configurações efetivas, hashes das fontes, resultados agregados e diferenças pareadas.
- `partidas.csv`: cenário, réplica, sementes, rodadas, progresso, fases, tempo e resultado de cada partida.
- `partidas.jsonl`: resultado e contagens detalhadas por questão, resposta, implementação, votação, revelação e remoção.

Partidas incompletas ou com erro não entram como encerramentos naturais nem nos denominadores. Interrupção/erro permanece explícito no relatório. Os arquivos de partidas são gravados após cada conclusão; o agregado é publicado a cada 25 partidas e ao finalizar. Uma queda pode deixar o agregado atrás dos registros já escritos; não há recuperação automática do lote nesta versão.

### O que é medido

- Rodadas efetivamente visitadas (incluindo uma rodada que termina por retorno), avanços e fases executadas.
- Tempo total, preparação de agentes e tempo executando fases, em segundos reais do computador. O total inclui coleta de métricas; não inclui gravação posterior da linha da partida nem publicação do relatório. Não é uma medida de tempo físico dentro do jogo ou um benchmark isolado de carga do sistema.
- Médias, extremos, desvio padrão e intervalo aproximado de 95% da média. Diferenças são calculadas entre pares com a mesma semente inicial; o tempo de execução tem ordem de cenários alternada aleatoriamente por réplica.
- Frequência de cada motivo de encerramento, com intervalo de Wilson de 95%. Os resultados não são convertidos em vitória/derrota: manter a missão garante a entrega da carga, mesmo que os humanos não sobrevivam; retornar cancela a entrega.
- Perguntas escolhidas, efetivamente declaradas e não realizadas, taxas por partida/rodada e respostas por questão/alternativa/implementação/natureza.
- Verdade, mentira, `NÃO_SEI` verdadeiro/falso, recusas de quem sabe/não sabe e declarações sem gabarito. O gabarito de todas as respostas é capturado administrativamente antes de sua entrega, sem revelar conteúdo aos agentes.
- Revelações sorteadas separadas da análise de todas as respostas; iniciativas, votos, penalidades, expulsões, saídas e controle. Perguntas/respostas também são agrupadas por faixas proporcionais de N e rodadas extras.

A taxa de verdade inclui dizer `NÃO_SEI` quando o agente não sabe; ela não mede compreensão do contexto. Recusas e respostas sem gabarito ficam fora dessa taxa. As respostas de uma mesma partida são correlacionadas, portanto a taxa de respostas não recebe um intervalo binomial como se cada resposta fosse uma partida independente. Perguntas por rodada na tabela geral são a média das taxas de cada partida; a taxa por questão agrega seus registros sobre todas as rodadas do cenário.

### Sementes, contratos e escala

Para cada réplica, o motor recebe `seed_base + réplica`, e os RNGs de agentes recebem sementes de um fluxo externo comum aos cenários, antes de `on_start`. A seed não transmite identidade/natureza à implementação. Uma implementação pode sobrescrever `Agent.configure_seed(seed) -> bool`; deve retornar `True` somente se controlar sua aleatoriedade ou for determinística. Os agentes fornecidos declaram isso; o aleatório inicializa seu próprio RNG. Implementações externas sem declaração aparecem no relatório como não controladas. Sementes comuns não obrigam trajetórias iguais após decisões divergirem. Chamadas a modelos externos podem não ser repetíveis.

O comportamento padrão fora dos experimentos é preservado. A semente de `setup.json` continua sendo a semente do motor; os novos argumentos opcionais de `GameSetup.start` permitem controlar RNGs de agentes e reutilizar implementações já carregadas no lote. Não é permitido substituir sementes ao retomar um checkpoint: a sequência salva deve ser preservada. O notebook foi regenerado com o mesmo contrato e validado localmente.

Os agregados numéricos usam estatísticas incrementais com memória constante, e os registros de partidas ficam em disco. Cada partida preserva seus históricos da engine e dos agentes; removê-los alteraria conhecimentos e comportamentos. A memória necessária para **uma partida longa** continua dependendo desses históricos. Este lote validou 2.000 partidas de cinco tripulantes com N=10; não é evidência de 100.000 partidas ou de 50 agentes por 100.000 rodadas.

Validação adicional: 23 testes de experimentos, incluindo pares idênticos, não interferência da coleta, gabarito de respostas não reveladas, recusas, sementes não controladas, cancelamento, falha, recuperação do relatório e tripulação de 50 com N=20. A suíte completa está aprovada; as falhas Q15/Q23 do humanoide foram corrigidas.

## Zerar e comparar experimentos segregados

Na aba **Experimentos**, atribua um nome ao próximo lote. Cada execução mantém seu próprio diretório, configuração efetiva, fontes registradas, relatório e arquivos de partidas. Em **Experimentos salvos**, selecione um lote para visualizar ou exportar seu resultado. Os arquivos não são mesclados automaticamente.

Para comparar execuções, escolha **Experimento A / Cenário A** e **Experimento B / Cenário B**, e clique **Comparar experimentos**. A comparação apresenta duração, tempo real, encerramentos, configuração, fontes com hashes diferentes, perguntas por rodada e distribuição de respostas por questão/implementação. As diferenças históricas são descritivas (B − A); não pressupõem independência entre lotes nem estimam intervalo de confiança entre amostras potencialmente sobrepostas. Os pares/intervalos já calculados dentro de cada lote continuam disponíveis no respectivo relatório.

**Zerar estatísticas** fica bloqueado durante a execução de um lote e enquanto um lote externo tiver estado gravado como `running`. Após o encerramento, zera a série atual e arquiva os resultados anteriores. Não remove os arquivos de resultados, a partida interativa ou seu checkpoint. Os experimentos arquivados continuam acessíveis por seleção explícita e para comparação; não reaparecem automaticamente na série atual ao atualizar/reabrir a página. O registro `.estatisticas-zeradas.json` no diretório de resultados torna a limpeza persistente. Um novo lote inicia uma série nova.

O humanoide agora compartilha com a base de comportamento os mecanismos de memória privada, respostas sinceras e declaração de crenças. Mantém sua implementação própria, perguntas cíclicas Q10, renúncia, abstinência nas votações, continuidade da missão, permanência e bloqueio de saídas. Q15–Q18 usam seu histórico; Q23 declara concluir a missão; nenhuma informação administrativa é entregue ao agente. O notebook foi regenerado e validado localmente. Resultados históricos continuam vinculados às versões de código usadas na coleta; a correção não reescreve suas medições.


## Localização

Raiz atual: `/Users/alexandre/projects/missao-espacial`. O diretório anterior na pasta da disciplina foi movido integralmente. Fontes em `src/`, configurações, documentação, notebook, testes, checkpoints e experimentos permanecem juntos. Para preparação dos materiais das aulas, as orientações institucionais estão em [2026 - 2sem/AGENTS.md](</Users/alexandre/Documents/2026-1 Senac - CAVI Conteudo diciplina/2026 - 2sem/AGENTS.md>).
