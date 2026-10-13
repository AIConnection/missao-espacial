# Contrato de contexto para a inferência

**Uma chamada só é admitida quando a cobertura das evidências exigidas está completa e o prompt integral cabe na janela verificada. É proibido truncar silenciosamente, retirar evidência necessária para caber ou converter falha de contexto em `neutral`.** A política continua responsável pela decisão; este contrato protege as avaliações de declarações que alimentam a decisão.

## 1. Janela e identidade verificadas

A configuração local em `/Users/alexandre/crivo/assets/phi4/config.json` declara `max_position_embeddings=16384`; `tokenizer_config.json` declara `model_max_length=16384`; `Phi4Backend.max_length` em `/Users/alexandre/crivo/crivo_backend.py` também declara 16.384. O tokenizer local foi carregado e usado, com arquivos locais somente. Os hashes estão em `contexto-validacao.json`.

A admissão conta o prompt real, com a instrução SYSTEM, o JSON de premissa/declaração, os marcadores do chat template e o prefixo do assistant. Foi verificada igualdade dos IDs de tokens com `_encode` do runtime local, sem carregar ou executar pesos.

```text
tokens(prompt integral) + reserva de saída <= 16.384
```

No runtime de referência a classe é obtida por logits, sem gerar texto: reserva de saída igual a zero. Se uma implementação gerar tokens, a reserva deve ser explícita e positiva, e o contrato/template deve ser novamente validado. Tamanho em caracteres, número de eventos, batch ou quantidade de rodadas não substituem a contagem de tokens.

Modelo, tokenizer e template formam uma identidade persistida. `ContextGuard.from_contract(...)` compara os arquivos com essa identidade. Mudança de configuração ou prompt não pode reaproveitar uma medição anterior silenciosamente. Outro serviço/provedor pode ter um limite menor; o contrato local não o certifica.

## 2. Memória e cobertura

A memória autorizada é acumulada fora do modelo, com origem, conteúdo, rodada e validade. Não é limitada à rodada corrente nem a uma janela fixa de registros recentes. A extração acontece antes de qualquer limitação de tokens.

No subconjunto implementado, a declaração é estruturada e o seletor tem regras explícitas:

| Declaração | Evidências recuperadas |
|---|---|
| Fato estático Q03–Q09, Q13/Q14 | Confirmações da questão e todos os relatos autorizados da mesma questão/parâmetros, independentemente da rodada. |
| Suficiência Q10 | Confirmação atual Q10, confirmação/limites Q11, painel e distância autorizados, relatos Q10. |
| Distância Q11 | Confirmações/limites Q11, distância autorizada e relatos da mesma consulta. |
| Comparação de reserva | Painel autorizado atual; sem painel, o recorte não inventa o saldo. |
| O que um participante disse | Todos os registros autorizados da fonte, pergunta, parâmetros e rodada indicados. |

Limites antigos de distância são atualizados pelo número público de avanços desde a confirmação; a projeção preserva o limite original, os avanços e a origem. Fatos estáticos confirmados continuam válidos. Leituras antigas de oxigênio não são saldos atuais. Relatos continuam alegações sobre o mundo, embora possam provar o que foi dito.

Cada evidência tem referência à visão autorizada. A preparação reconstitui o conjunto exigido para a declaração tipada antes de serializar. O teste do corpus compara esse conjunto com as visões registradas, inclusive quando entradas iguais vieram de posições diferentes dos históricos.

Uma lista de evidências autodeclarada por um chamador não prova cobertura semântica. Na integração futura, usar a preparação validada sobre a memória autorizada; não permitir que a política simplesmente omita elementos e declare o restante como completo. O runtime precisa comparar IDs obrigatórios e IDs incluídos antes da chamada.

## 3. Falhas e comportamento obrigatório

| Condição | Tratamento |
|---|---|
| Evidência obrigatória não incluída | `CONTEXT_INCOMPLETE_EVIDENCE`; não chamar o modelo. |
| Prompt/reserva excede janela | `CONTEXT_OVER_BUDGET`; não chamar, não cortar. |
| Identidade/configuração do backend divergente | `CONTEXT_BACKEND_CHANGED`/`CONTEXT_BACKEND_MISMATCH`; não reutilizar admissão. |
| Tipo de declaração fora do seletor validado | `CONTEXT_UNSUPPORTED_CLAIM`; não prometer cobertura. |

Falha operacional de contexto não é uma classe NLI. A política deve registrar a falha e buscar uma representação fiel menor, uma decomposição semanticamente validada ou um backend com capacidade suficiente. Não pode tratar ausência forçada de evidência como se o agente a desconhecesse. Uma decomposição futura precisa preservar relações entre fatos, tempo e dependências; vários votos independentes da cabeça não substituem automaticamente uma inferência conjunta.

Compressão só será admitida quando houver equivalência verificável para a declaração: por exemplo, remover duplicatas sem perder sua proveniência. Resumo livre por outro modelo não constitui garantia de preservação. A rotina atual não corta nem resume para caber; bloqueia excedentes.

## 4. Evidência executada

Os 600 pares deste piloto foram reconstruídos e admitidos usando o tokenizer real. Controles executados: limite inclusivo; um token acima bloqueado; evidência ausente bloqueada; entrada extensa bloqueada sem truncamento; codificação igual à função do runtime; reabertura do contrato persistido e rejeição de contrato divergente.

| Medida | Tokens |
|---|---:|
| Janela | 16384 |
| Menor prompt | 152 |
| Mediana | 229 |
| Percentil 95 | 466 |
| Maior prompt | 762 |

A entrada extensa de controle foi tokenizada para medir o estouro; não foi enviada ao modelo. Não houve treino nem inferência de pesos. Os resultados estão em `contexto-validacao.json`; a admissão de cada par está em `contexto-admissao.jsonl`.

## 5. Escopo da garantia

O validador garante que **as chamadas admitidas não perdem as evidências exigidas pelo seletor tipado validado por estouro/truncamento**. Não garante que qualquer história arbitrariamente longa caiba, que o seletor reconheça toda relação semântica em texto livre ou que o modelo use corretamente cada evidência. Essas propriedades precisam de testes próprios.

Para ampliar o escopo: cada novo predicado deve ter regra de recuperação, tratamento temporal, casos de prova/contraprova e testes com a evidência relevante longe da rodada corrente. Declarações sobre crenças/conhecimento de terceiros e contexto completo para escolher ações ainda não têm garantia de cobertura neste piloto. O contrato não deve ser apresentado como garantia universal dessas decisões.

A implementação está isolada em `ferramentas/contexto.py`. **Ainda não foi integrada às chamadas dos agentes nem a um treinador**, pois o simulador e o Crivo foram preservados. Uma chamada de inferência futura deve obrigatoriamente passar por essa admissão antes de executar o modelo.

Para reproduzir a medição com o ambiente local já instalado:

```sh
/Users/alexandre/crivo/.venv/bin/python -B datasets/piloto-v01/ferramentas/contexto.py --project . --folder datasets/piloto-v01 --model-directory /Users/alexandre/crivo/assets/phi4 --runtime-source /Users/alexandre/crivo/crivo_backend.py
```

Esse comando atualiza somente os relatórios de contexto do diretório informado. Não altera fontes do simulador/Crivo nem carrega seus pesos. O ambiente Python padrão não tinha `transformers`; foi usado o ambiente existente do Crivo, sem instalar dependências.
