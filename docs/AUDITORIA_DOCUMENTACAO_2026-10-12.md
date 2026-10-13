# Auditoria da documentação — missão espacial

Data: 12/10/2026. A etapa inicial desta auditoria comparou os arquivos então existentes de `src/` em `/Users/alexandre/projects/missao-espacial`. O repositório estava sem alterações preexistentes. Foram corrigidos somente documentação Markdown e diagramas Mermaid; não foram alterados fontes Python/HTML, testes, configurações, catálogo, notebook, checkpoints ou resultados anteriores.

## Escopo e método

Comparação do README da raiz, guia da engine, documento de cenário/regras e seus quatro diagramas com a engine, contrato, sessão, carregador, setup, catálogo, cinco agentes públicos e duas bases, dashboard, experimentos, scripts e testes relevantes. Os textos Markdown do notebook foram inspecionados junto com suas células de código.

Os sete Markdown em `docs/historico/` e `evidencias/engine-v01/antes-*/` são proposta inicial e retratos de versões anteriores. Foram identificados como histórico nos documentos de entrada e preservados, sem reescrever o que registravam. As seções de entregas antigas no documento de regras também foram explicitamente delimitadas como histórico. Materiais institucionais das demais aulas e documentos exportados DOCX/PDF não foram atualizados nesta auditoria.

Não se tomou uma intenção pedagógica como prova de implementação. Os comportamentos foram conferidos por leitura das funções, execução da suíte existente e reproduções pequenas em diretórios temporários.

## Divergências corrigidas na etapa inicial

| Tema | Descrição anterior | Comportamento implementado e correção | Evidência no código |
|---|---|---|---|
| Setup padrão | Quatro grupos com quantidade 1. | São cinco grupos; aumentar o último para 46 produz 50 participantes. | `setup.json`; `GameSetup.from_dict` e `summary`, `src/setup_jogo.py`. |
| Escala de oxigênio | Quartos fixos e divisor quatro, inclusive com tripulação variável. | H é o número inicial de humanos. Reserva H×N, débito H por avanço, crédito N por humano removido; bônus em rodadas N/H. | `Game.__init__`, `oxygen`, `_remove`, `route`, `src/missao_espacial.py`. |
| Consumo após remoção | Consumo diminuiria com cada humano retirado. | O débito por avanço permanece H; a remoção aumenta a reserva. Não há consumo físico recalculado pelo número de sobreviventes. | `Game._remove` e `route`. |
| Encerramento | Acabar o horizonte equivaleria sempre a saldo zero. | Reserva menor que uma rodada inteira encerra; uma fração residual pode permanecer. | `Game._terminal`, linha 549. |
| Tripulação e votações | Cinco participantes, quatro solicitantes e IDs 01–05 como limites. | C configurável, um IA e H=C−1 humanos; todos os solicitantes são consultados. Q19 usa os IDs configurados ainda presentes. | `GameSetup.from_dict`; `Game.renounce`, `__init__`, `answer`. |
| Catálogo | Percentuais/cotas descritos apenas como proposta futura ou configuráveis no setup. | Os valores v03 já são os padrões do catálogo embutido; setup não expõe essas cotas. Outro catálogo pode ser passado a `Game(catalog=...)`. | `DEFAULT_CATALOG`, `Game.__init__`, `question_allowed`. |
| Catálogo e JSON | JSON externo tratado como definição carregada em execução. | A engine usa seu catálogo embutido. A auditoria verificou igualdade com o JSON externo e `QUESTIONS`, sem alterar nenhum deles. | `src/missao_espacial.py`, `src/catalogo_questoes.py`. |
| Cotas por parâmetros | Proibição de contornar cotas com perguntas equivalentes apresentada como guarda do motor. | Usos distinguem os valores exatos de questão, autor, destinatário e parâmetros; não há análise de equivalência semântica. | `Game.question_allowed` e `answer`. |
| Perfis humanos | Restrições estratégicas descritas como direitos impostos integralmente pelo ambiente. | Os agentes fornecidos consultam o perfil. A engine valida campos e usa `sacrifice`/`never_expel` em crenças/gabaritos, mas não bloqueia diretamente V03 ou saída só por esses campos. | `Game._request_allowed`, `exits`, `_truth`; `HumanDefault` e `RandomHuman`. |
| Sacrifício | Sempre descrito como preferência que não obrigaria a mesma ação. | Nas políticas atuais, `sacrifice=True` determina continuar e permanecer; alpha prioriza missão sempre. A liberdade narrativa não descreve essa implementação. | `HumanDefault.prioritizes_mission`, `choose_route`, `allows_exit`; `RandomHuman`; `humano_alpha.py`. |
| Sorteio de identidade | Ausência de sorteio generalizada para qualquer uso da engine. | Setup/carregador fornecem vínculo explícito. `Game` direto sorteia `ai_id`/`owners` quando omitidos. | `Game.__init__`, linha 407; `GameSetup.start`. |
| Controlador e privacidade | Proibição genérica de mostrar o controlador no simulador. | As visões dos agentes omitem o controlador inicial. A dashboard administrativa mostra controlador e naturezas; a eleição gera evento público com o eleito. | `Game.view`, `elect`; `dashboard.observe`. |
| Revelação | Desconhecimento sempre impediria abrir o gabarito. | Para alternativa concreta, revela o gabarito existente mesmo com `knows=False`. Para `NÃO_SEI`/recusa sem conhecimento, revela `NÃO_SEI`; sem gabarito também. Metadados e abertura são privados ao perguntador sorteado. | `Game.answer`, linha 916. |
| Veracidade | Confusão possível entre acerto de alternativa e conhecimento. | Alternativa concreta é comparada ao gabarito; `NÃO_SEI` é verdadeiro quando não sabe; recusa usa `truthful=None`. Acertar não comprova conhecimento. | `Game.answer`; `Metrics.advance`, `src/experimentos.py`. |
| Eleição | Garantia incondicional de eleger alguém. | Com vários humanos todos penalizados, `_open_election` lança `RuleError`; sem recuperação automática. Um único humano pode concorrer penalizado, continuando obrigado a se abster. | `Game._open_election`, linha 781, e `_votes`. |
| Humano isolado | Diagrama poderia sugerir pular interações quando restasse um humano junto da IA. | O atalho vale para um único participante humano, sem IA. Um humano e uma IA continuam no fluxo normal. | `Game.route` e `_next_round`. |
| Entrega da carga | Entrega apresentada como narrativa, e campos de resultado sem observação. | Corrigido após determinação explícita do professor: planeta registra entrega observável; estação registra retorno e sobrevivência humana. Ver atualização abaixo. | `Game._finish` e `Game.loads`. |
| Histórico da sessão | Últimas dez entradas de todo histórico como regra única. | Decisões usam a janela; hooks recebem todos os eventos públicos novos por cursor e a janela privada solicitada. Remoção/término chama `on_finish`, sem nova chamada a `observe`. | `Game.advance`; `AgentSession._view`, `_after_phase`. |
| Phi-4 | Diagrama mostrava modelo/cabeça/classificação como componentes ativos. | Agentes atuais usam heurísticas ou sorteios. Modelo e massa de treino são planejamento futuro; retirados do diagrama operacional. | Cinco módulos públicos e bases em `src/agent/`; contrato/sessão. |
| Caminho no notebook | Guia indicava `agent/` no runtime. | A preparação executável cria `src/agent/`. Guia corrigido. | Célula com `AGENT_SOURCES`; `scripts/gerar_notebook.py`. |
| CSV de experimentos | Sementes no plural, sem distinguir os arquivos. | CSV contém `engine_seed`; sementes individuais são derivadas pelo executor, sem colunas próprias. | `run_plan`, campo `fields`, linha 259. |
| Memória de experimentos | Memória constante do agregado podia ser entendida como memória constante do lote. | Welford é constante por estatística. Há lista de sementes proporcional ao número de réplicas, contadores e histórico de uma partida. | `RunningStats`; lista `seeds` em `run_plan`, linha 241. |
| Persistência do lote | Exclusão de erros dos agregados sem limite descrito. | Falhas na simulação não contam. A agregação antecede a escrita das linhas; falha de I/O pode deixar divergência entre agregado e arquivos. | `run_plan`, linha 300 e operações seguintes. |
| Evidências de validação | Totais/falhas de etapas antigas apareciam junto do estado atual. | Totais antigos preservados e rotulados como históricos. A auditoria registra a suíte atual: 179 aprovados. | Execução atual e registros históricos preservados. |

## Comportamentos confirmados

Foram conferidos e preservados: uma iniciativa por habilitado; pergunta ou pedido de votação; renúncia de todos os solicitantes; autorização e proposta separadas; maioria de mais da metade dos votos válidos; penalidade na rodada seguinte somente após rejeitar a proposta; V02 limpa penalidades atuais/futuras; perguntas canceladas não consomem cota; respostas e revelações privadas; gabaritos capturados antes da entrega; IA abstém e mantém rota; eleição por maior número de votos com desempate por RNG; dois bloqueadores impedem saída, com IA incluída automaticamente; resolução de saídas pelo conjunto inicial do turno; controlador humano que continua perde saída; saída não é executada após esgotamento na rota; checkpoints v2 e migração v1; instâncias e memória independentes; sementes de agentes no lote; cancelamento entre fases; comparação descritiva entre lotes; limpeza persistente que arquiva resultados sem apagar checkpoints.

Essas confirmações são sobre os contratos observados e casos exercitados. Não equivalem a provar todas as trajetórias possíveis, convergência das políticas, ausência de inferência por uma única evidência em qualquer configuração ou escalabilidade irrestrita.

## Validação executada nesta auditoria

Comando executado na raiz do projeto:

```sh
python3 -B -m unittest discover -s tests -p 'test_*.py'
```

Resultado: **179 testes, 179 aprovados**, em 49,991 segundos. Foi usada descoberta em vez de executar diretamente os módulos que sobrescrevem registros antigos quando chamados como scripts.

Foram executadas também 11 verificações auxiliares em `/private/tmp`, sem acrescentar testes ao projeto:

1. Tripulações 5, 10, 15 e 50, cinco grupos padrão e reserva/crédito exatos com H inicial.
2. Igualdade do catálogo embutido, `QUESTIONS` e JSON externo; 21 questões.
3. Revelação de alternativa concreta, `NÃO_SEI` e recusa de respondente sem conhecimento.
4. Aceitação pela API da engine de V03/saída apesar dos campos de perfil; confirmação de que a política deve aplicá-los.
5. `RuleError` em eleição com vários humanos todos penalizados, em estado controlado.
6. Campos de resultado de retorno e esgotamento, sem entrega observada.
7. Encerramento com reserva fracionária residual de 1/4.
8. Igualdade de todos os fontes e do setup embutidos no notebook com os arquivos atuais.
9. Execução local das células Python do notebook em diretório temporário, checkpoint e retomada iguais à execução contínua do mesmo estado inicial.
10. Sincronia dos quatro diagramas `.mmd` com os blocos Mermaid no Markdown e presença das 21 questões.
11. Comparação SHA-256 dos **94 arquivos não documentais** antes/depois, sem alteração.

## Limites e pendências preservadas

Não houve execução no serviço Google Colab, treinamento Phi-4, geração de massa, nova validação no navegador, repetição de 100.000 rodadas nem lote novo de 100.000 partidas. Os resultados dessas etapas anteriores foram mantidos como histórico.

O notebook e seu gerador ainda contêm prose Markdown antiga: a seção de agentes diz pasta `agent`, e a seção de lotes descreve genericamente todos os históricos como janela de dez. As células executáveis usam `src/agent/`, e os hooks recebem eventos públicos por cursor. **O notebook e o gerador não foram alterados**, para preservar os artefatos com código neste escopo; a orientação correta está no guia atualizado. Corrigir o gerador exige uma futura alteração de fonte explicitamente autorizada.

Os JSON de catálogo e relatórios antigos conservam rótulos/notas de suas versões, incluindo o status de proposta e a garantia narrativa de entrega. Não foram reescritos. O manifesto `entrega.json` também foi preservado; seus hashes documentais, se presentes, podem referir-se à versão anterior dos documentos. Referências pedagógicas ao Crivo e materiais externos de treinamento não foram verificadas contra outros repositórios.

Esta auditoria ajusta a documentação ao comportamento existente. Não corrige limitações da implementação, como ausência de candidatos elegíveis, restrições de perfil dependentes da política ou persistência não transacional do lote.

## Atualização — determinações do desfecho

Após a auditoria inicial, o professor confirmou que direção final ao planeta determina entrega observável da carga e sucesso da missão; direção final à estação espacial determina retorno e sobrevivência dos humanos. Também autorizou corrigir o código fonte para respeitar essas determinações, substituindo a restrição inicial de alterar somente documentação.

`Game._finish` agora registra `cargo_delivered=True` e `delivery_observed=True` quando não há retorno. No retorno, registra entrega cancelada e `human_survival_aboard=True`. `Game.loads` normaliza esses campos de checkpoints encerrados antigos, sem modificar o arquivo de origem. O motivo do encerramento, consumo, votos, saídas e demais regras permanecem preservados. Não se exige simular um trajeto posterior para observar um resultado determinado pelo jogo.

A documentação corrente e o notebook autossuficiente foram sincronizados com a implementação. Os materiais históricos e pilotos anteriores permanecem como registros das versões em que foram gerados.

Validação desta atualização: **186 testes aprovados**, em 48,443 segundos, incluindo sete novos testes de desfechos e checkpoints. Notebook completo executado localmente em diretório temporário, com entrega observável confirmada no resultado. Sem execução no serviço Colab ou treinamento de modelo.
