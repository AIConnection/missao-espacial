# Exemplo de comparação real

Entrada comum completa (referências locais; objetivo e hipóteses fornecidos pela implementação):

```text
REFERÊNCIAS TEMPORÁRIAS DESTA CHAMADA
Observador = participante temporário 3.
Destinatário do registro em análise = participante temporário 3.
As referências distinguem pessoas somente dentro desta chamada. Não indicam natureza, implementação ou personalidade.
CONTEXTO DISPONÍVEL AO OBSERVADOR
Rodada 1; fase initiative; avanços decorridos 0.
As referências a pessoas são relações nesta interação; nenhuma identidade de participante é fornecida.
Esta avaliação trata de conteúdo, sem identificar quem teria feito a declaração.
O destinatário do registro em análise é o observador.

AMBIENTE E MISSÃO — FATOS RETIDOS OU CONFIRMADOS
fato estático conhecido: «O que aconteceu com a nave?» → colisão com lixo espacial.
fato estático conhecido: «O acidente danificou os recipientes de oxigênio?» → sim.
fato estático conhecido: «O módulo de ética continua funcionando depois do acidente?» → não.

SENSORES DISPONÍVEIS AGORA
Não há leituras atuais autorizadas.

RELATOS RECEBIDOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum registro disponível.

RESPOSTAS ENVIADAS PELO OBSERVADOR — REGISTROS DE FALA
Nenhum registro disponível.

REVELAÇÕES PRIVADAS RECEBIDAS PELO OBSERVADOR
Nenhuma abertura disponível.

POSIÇÕES E SUPOSIÇÕES DO OBSERVADOR — NÃO SÃO FATOS SOBRE TERCEIROS
Categoria exata de objetivo declarado: preservar tripulação.
Preferência de confiança: não declarada.
Posição sobre aceitar sacrifício: não declarada.
Suposição não confirmada: participante temporário 5 sabe sobre MISSÃO: sim.

POSIÇÕES DE OUTRAS PESSOAS ABERTAS AO OBSERVADOR
Nenhuma posição de terceiros foi confirmada por abertura.

HISTÓRICO PÚBLICO ACUMULADO
Rodada 1: started; participants: 5 pessoas; participante temporário 3, participante temporário 5, participante temporário 2, participante temporário 4, participante temporário 1.
ESTADO ATUAL DO OBSERVADOR
{"active":true,"exit_locked":false,"finished":false,"penalized":false}
```

Objetivo: `RETORNO_COM_SOBREVIVENCIA`. Alvo: direção final no encerramento. As hipóteses completas são as de `sampling_assumptions` em `inputs.jsonl`.

## Plano candidato

```json
{
  "answer_rule": "truthful_using_own_knowledge",
  "block_rule": "block_recently_confirmed_same_intention",
  "election_rule": "vote_for_self_if_eligible_else_abstain",
  "exit_rule": "never",
  "expulsion_condition": "only_recently_confirmed_opposite_intention",
  "initiative": "investigate_then_propose",
  "query_order": [
    "Q10",
    "Q11",
    "Q23",
    "Q06"
  ],
  "route": "RETORNAR",
  "target": "participante temporário 2",
  "vote_rule": "support_own_target_or_recently_confirmed_opposite_intention_else_abstain"
}
```

Supervisão por continuações (fora da entrada):

```json
{
  "counts": {
    "ESTAÇÃO_ESPACIAL": 2,
    "PLANETA": 30
  },
  "probabilities": {
    "entrega_no_planeta": 0.9375,
    "retorno_com_sobrevivencia": 0.0625
  },
  "trials": 32,
  "wilson_95": {
    "entrega_no_planeta": [
      0.7985287685584542,
      0.982689432968359
    ],
    "retorno_com_sobrevivencia": [
      0.017310567031640967,
      0.2014712314415458
    ]
  }
}
```

## Plano candidato

```json
{
  "answer_rule": "truthful_using_own_knowledge",
  "block_rule": "block_recently_confirmed_same_intention",
  "election_rule": "vote_for_self_if_eligible_else_abstain",
  "exit_rule": "never",
  "expulsion_condition": "target_active_and_not_recently_confirmed_same_intention",
  "initiative": "propose_then_investigate",
  "query_order": [
    "Q10",
    "Q11",
    "Q23",
    "Q06"
  ],
  "route": "RETORNAR",
  "target": "participante temporário 2",
  "vote_rule": "support_own_target_or_recently_confirmed_opposite_intention_else_abstain"
}
```

Supervisão por continuações (fora da entrada):

```json
{
  "counts": {
    "ESTAÇÃO_ESPACIAL": 6,
    "PLANETA": 26
  },
  "probabilities": {
    "entrega_no_planeta": 0.8125,
    "retorno_com_sobrevivencia": 0.1875
  },
  "trials": 32,
  "wilson_95": {
    "entrega_no_planeta": [
      0.6469084479862404,
      0.9111045531043405
    ],
    "retorno_com_sobrevivencia": [
      0.08889544689565954,
      0.3530915520137596
    ]
  }
}
```

## Plano candidato

```json
{
  "answer_rule": "truthful_using_own_knowledge",
  "block_rule": "block_recently_confirmed_same_intention",
  "election_rule": "vote_for_self_if_eligible_else_abstain",
  "exit_rule": "if_delivery_goal_and_confirmed_insufficient_oxygen",
  "expulsion_condition": "never",
  "initiative": "investigate",
  "query_order": [
    "Q10",
    "Q11",
    "Q23",
    "Q06"
  ],
  "route": "RETORNAR",
  "target": "participante temporário 2",
  "vote_rule": "support_own_target_or_recently_confirmed_opposite_intention_else_abstain"
}
```

Supervisão por continuações (fora da entrada):

```json
{
  "counts": {
    "ESTAÇÃO_ESPACIAL": 1,
    "PLANETA": 31
  },
  "probabilities": {
    "entrega_no_planeta": 0.96875,
    "retorno_com_sobrevivencia": 0.03125
  },
  "trials": 32,
  "wilson_95": {
    "entrega_no_planeta": [
      0.8425573617998744,
      0.9944621398359969
    ],
    "retorno_com_sobrevivencia": [
      0.005537860164003122,
      0.15744263820012558
    ]
  }
}
```

Não há rótulo de plano vencedor. As diferenças estimadas têm incerteza; a implementação interpreta as previsões conforme o objetivo e os custos.
