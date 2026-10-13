# Contrato de entrada — Colab v02

Fonte exclusiva do contexto: `AgentView` recebido pelo agente e histórico anteriormente recebido, preservado em sua memória. A declaração ou condição própria é o objeto escolhido pela implementação para avaliação. O compilador não recebe Game, checkpoint, owners, N oculto, implementações, perfil de terceiros ou RNG.

## Classificação

`premise` = JSON do contexto; `hypothesis` = JSON da declaração. Saída: 0 suporte, 1 insuficiente, 2 contradição. Hipótese `kind=fact` avalia fato; `speech` avalia fala registrada; `position` avalia posição declarada. Nenhuma ausência é tomada como falsidade.

Contexto: observer, moment, state e coleções não vazias de facts/sensors/speech/revelations/beliefs/events. Tabelas usam columns/rows; questions define perguntas locais por extenso. Fatos retêm status e avanço temporal; leituras são atuais; falas não confirmam conteúdo; aberturas não fixam comportamento futuro. Não retirar evidências em função do rótulo. A regra física reserva ≥ distância e regras de validade permanecem no prefixo constante.

## Probabilidade

Entrada: somente context e candidate_plan. O candidato contém alvo temporário e regras semânticas próprias conhecidas pela implementação, sem código de implementação ou atribuição de terceiros. Saída: entrega_no_planeta e retorno_com_sobrevivencia, complementares. Não retorna ação ou plano.

PLANETA determina entrega observável; ESTAÇÃO_ESPACIAL determina retorno e sobrevivência dos humanos a bordo. Sobrevivência de pessoas que saíram não é observada.

Alvo marginal sobre distribuição fixa de geração: três regimes em pesos iguais, com 96 desfechos em 32 mundos. A engine gera o alvo usando estados completos, mas esses estados não entram como feature. Os mundos, não as 96 continuações, são unidades para a incerteza; bootstrap por mundo preserva o pareamento. Regimes, priors, seeds, método de rejeição e inicialização de políticas são auditoria/configuração do gerador. Não se pede que o agente forneça isso.

As regras chamadas opposed significam categoria declarada diferente, e não prova de conflito lógico entre interesses. A representação por extenso explicita essa diferença.

## Identidades e memória

p1/p2 distinguem pessoas dentro de uma chamada; não são IDs persistentes. O chamador conserva routing/resolve, sem enviá-los ao modelo. Campos de natureza, perfil e memória de implementação não são serializados. H inicial é enviado porque faz parte de AgentView e da regra física, sem atribuir natureza a uma pessoa.

ObservationMemory aceita apenas AgentView, junta as janelas por índices e pode ser salva em self.memory. Falta de histórico impede inferência: restaurar apenas memória própria. Nunca reconstruir lacunas a partir de checkpoint privado ou suposta verdade do mundo.

## Janela e partições

Até 16.384 tokens incluindo prefixo, chat template e entrada, sem truncamento. A cabeça devolve logits e não exige reserva para geração de texto. Testar entradas futuras com tokenizer e rejeitar excesso. As medidas executadas estão em validacao.json.

Nenhuma entrada normalizada ou grupo cruza treino/calibração/teste. Classes permanecem equilibradas por partição, tipo, faixa temporal e fase. Frequências de evento não são forçadas a 50/50. A massa não garante cobertura de todos os históricos e estratégias; previsão após rodada 6 e observador IA não foram cobertos.
