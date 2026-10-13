# Contrato de treinamento e inferência — plano e desfecho v1

Este contrato é implementado e validado **no escopo declarado abaixo**. `contrato.json` registra as regras; `ferramentas/contrato.py`, `planos.py` e `validar_planos.py` executam as verificações. Não equivale a afirmar que a cabeça já foi treinada ou conectada.

## Duas tarefas

1. Evidência: contexto + declaração → **suporte, insuficiente ou contradição**. A massa da v03 permanece separada; não acrescentar um alvo de «probabilidade de uma resposta estar correta» nem de confirmação por revelação.
2. Consequências: contexto autorizado + objetivo + plano candidato + hipóteses de amostragem → **probabilidades dos dois desfechos finais**. A cabeça não escolhe uma ação nem um plano. A implementação fornece objetivos/intenções, constrói candidatos e interpreta as previsões segundo seus interesses.

```json
{"entrega_no_planeta": 0.625, "retorno_com_sobrevivencia": 0.375}
```

Exemplo apenas de formato. Os valores devem ser finitos, entre zero e um, e somar um. Identidade, destinatário real, recomendação ou ação não pertencem à saída. Esses desfechos são exclusivos por direção final. Uma probabilidade alta não se transforma automaticamente em suporte factual.

## Determinações e fonte

PLANETA determina carga entregue e entrega observável. ESTAÇÃO ESPACIAL determina retorno e sobrevivência dos humanos. `desfecho.label_outcome` verifica os campos da engine corrigida. Resultado não observado, incoerente ou continuação censurada bloqueia a geração; não é derrota, zero de probabilidade ou insuficiente.

O alvo de sobrevivência é o desfecho determinado de retorno. Não rotular sobrevivência individual de alguém que saiu da nave quando a fonte a deixa sem avaliação.

## Conhecimento e referência pessoal

A entrada deriva exclusivamente de `Game.view(observer, history_limit=None)` e do catálogo público. Usa fatos, sensores autorizados, relatos recebidos, respostas enviadas, revelações privadas, posições/suposições e todo o histórico público. Acrescenta os próprios estados ativo, encerrado, penalizado e saída bloqueada, necessários às ações. Não filtrar o contexto por pergunta ou pelo rótulo.

`from_view` confere tamanhos de históricos e cursor público. `ForecastEncoder.prepare(expected_view=...)` compara com uma visão independente e confiável; passar a própria representação novamente não certifica completude. IDs reais são convertidos em referências temporárias consistentes, inclusive nos registros históricos de participantes removidos. O mapa/nonce é externo e compartilhado apenas no lote de comparação, sem identidade persistente entre contextos.

Os identificadores, natureza própria e perfil nominal não são features. Esta versão é condicionada a observador humano ativo, com perfil vazio, memória própria adicional vazia e fase de iniciativa. Campo adicional, perfil ou memória sem adaptação semântica provoca erro explícito. É preciso compilar preferências/restrições nas condições do plano e adaptar conhecimentos adicionais antes de ampliar esse escopo; não descartá-los silenciosamente.

## Plano executável

A intenção de rota é explícita no plano e coerente com o objetivo declarado. O programa cobre iniciativa, resposta, votos, eleição, rota, saída e bloqueio. A execução sempre verifica legalidade pela engine. Não basta escrever uma descrição do plano e executar uma política diferente.

O piloto inclui três programas parametrizados por um alvo temporário:

- Investigar; propor expulsão somente quando houver posição oposta confirmada recentemente.
- Propor expulsão do alvo indicado enquanto não houver posição igual confirmada; investigar quando não puder propor.
- Investigar/informar pelas respostas; para o objetivo de entrega, aceitar saída voluntária se a insuficiência for confirmada e a saída estiver habilitada.

Em todos, respostas são sinceras conforme o conhecimento autorizado; perguntas priorizam o alvo e evitam repetir o mesmo assunto recebido nos últimos três turnos quando houver opção legal. Votos apoiam o alvo indicado ou posição oposta confirmada; eleição prefere o próprio observador se elegível; bloqueio considera posição igual confirmada. Posições consideradas recentes têm idade máxima de duas rodadas. Estas são definições dos programas, não recomendações universais nem promessas de táticas ótimas.

PRESERVAR_AMBOS permanece uma categoria de objetivo, não prova de uma intenção de rota. Relato de objetivo não vira confirmação. Abertura informa o objetivo naquele instante, sem garantir que continuará igual. O programa pode rever suas iniciativas quando o alvo sair ou surgirem posições novas, mantendo o objetivo fornecido. A biblioteca e o compilador rejeitam programas fora dos três formatos v1.

## Probabilidade e continuações pareadas

Para cada contexto/objetivo, os candidatos usam o mesmo mundo aceito, estado de RNG futuro da engine e sorteios de comportamento **dentro da repetição**. Entre repetições, reamostrar estados desconhecidos, respostas privadas de terceiros, destinatários ocultos das revelações passadas e aleatoriedade futura. A visão completa do observador deve permanecer exatamente igual após reconstruir o histórico.

Fixar somente os acontecimentos públicos e as respostas enviadas/recebidas que o observador conhece. Não fixar um histórico secreto dos terceiros para rotular uma entrada que não o contém. O amostrador não pondera estados pela verossimilhança das mensagens conhecidas: é uma distribuição proposta, filtrada por compatibilidade, explicitamente informada na entrada, não um posterior Bayesiano demonstrado nem probabilidade universal contra qualquer estratégia.

Preferências dos demais variam entre priorizar retorno, priorizar entrega e reconsiderar o objetivo quando Q10 puder ser respondida com evidência pela engine. Há ruído nas respostas e votos. Os nomes de implementações e as preferências individuais amostradas ficam apenas na auditoria. As regras comuns de recursos, votação, sacrifício e desfecho estão no prefixo constante do modelo.

Cada candidato recebe contagens de resultados, frequências e intervalos de Wilson de 95%. Os intervalos expressam incerteza das frequências com 32 repetições; os valores não são probabilidades exatas fornecidas diretamente pela engine. Não há rótulo de melhor plano ou estratégia para a cabeça aprender.

## Orçamento e montagem

A chamada deve usar `ForecastEncoder.prepare`, que devolve entrada e relatório/roteamento separadamente. `encode` serializa apenas a entrada validada, com SYSTEM e chat template real. Admissão exige que prompt integral + reserva caiba na janela; excesso bloqueia sem recorte. `from_contract` confere tokenizer/configuração e prefixo persistidos.

A reserva zero assume saídas por logits da futura cabeça. Gerar JSON como texto ou trocar modelo/template exige recontar e reservar saída. O backend atual de três classes **não implementa esta tarefa probabilística**; precisa de treinamento e integração próprios. A contagem de tokens não executa pesos nem certifica desempenho.

## Avaliação e limiares

Manter as variantes de cada situação, todos os tempos/objetivos, os três planos e suas continuações na mesma partição estrutural. A calibração escolhe pontos de operação por custos; o teste reutiliza a escolha sem novo ajuste. Não escolher limiares a partir dos desfechos de teste.

`avaliar_probabilidades.py` requer previsões reais para todas as linhas de calibração/teste. Mede Brier/log loss por resultado Bernoulli, frequências por faixas de previsão, custos de falso positivo/negativo e diagnóstico de comparação de planos para cada objetivo. Os pontos incluem os regimes constantes sempre/nunca prever entrega. O diagnóstico de escolha por maior probabilidade é uma política de avaliação, não saída ou regra aprendida da cabeça. Seu melhor candidato de referência é estimado por amostras finitas, não ótimo conhecido.

As contagens em faixas são descritivas: planos e contextos da mesma família têm dependências. Não tratar todas as trajetórias como observações independentes para calcular intervalos globais. Sem previsões do modelo, não produzir indicadores de qualidade nem alegar limiares validados. Os testes unitários do avaliador usam fixtures artificiais apenas para testar a ferramenta.
