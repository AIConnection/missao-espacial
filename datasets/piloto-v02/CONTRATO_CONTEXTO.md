# Contrato de contexto e saída — v02

A saída admitida é um único código: 0 = suporte, 1 = insuficiente, 2 = contradição. Não contém ação, identidade, destinatário ou recomendação estratégica. O vínculo e a escolha de ação pertencem à aplicação.

`from_view` exige históricos privados integrais e histórico público com tamanho correspondente ao cursor da engine. `prepare_snapshot` reconstrói a memória esperada e compara a estrutura integral, antes da representação sem identidade. Retirar informação de outro assunto produz `CONTEXT_INCOMPLETE_CONTEXT`. `prepare` sem `expected_context` não pode, isoladamente, certificar que um chamador forneceu toda a memória existente.

O vínculo de observador/fonte/destinatário é aplicado pela montagem local para produzir referências relacionais. `prepare` retorna `pair` e relatório separadamente; `routing_only` fica no relatório, jamais em `encode(pair)`. Contextos estruturados e relatórios com identidades pertencem exclusivamente à aplicação/auditoria. O modelo recebe prefixo, premissa e hipótese.

Fatos confirmados incompatíveis: `CONTEXT_INCONSISTENT`. Campo pessoal ou referência não representável: `CONTEXT_ANONYMIZATION_REQUIRED`. Divergência entre relatos distintos pode permanecer no contexto: um relato não confirma o fato. A geração verifica que entradas anônimas iguais não recebam classes diferentes. Isso não prova preservação semântica de toda linguagem livre.

O orçamento usa tokenizer e template locais reais, SYSTEM, prefixo, premissa, hipótese, JSON e marcadores. A montagem foi comparada com `_encode` do runtime de referência. Modelo, tokenizer, runtime e prefixo são vinculados por hashes verificados ao reabrir o contrato.

```text
tokens(prompt completo) + reserva de saída ≤ janela
```

O backend de referência produz classificação por logits, sem gerar texto; reserva atual zero. Outro backend exige contrato próprio. Ao ultrapassar a janela, retornar `CONTEXT_OVER_BUDGET` antes da chamada. Não cortar silenciosamente, resumir livremente ou converter erro operacional em insuficiente. Não há garantia de que um histórico arbitrariamente longo caiba; há bloqueio quando não couber.

## Evidência executada

| Medida | Tokens |
|---|---:|
| Janela | 16384 |
| Mínimo | 1163 |
| Mediana | 5665 |
| Percentil 95 | 10872 |
| Máximo | 12252 |

Os 600 pares foram admitidos; 0 bloqueados por orçamento. Passaram 30 testes semânticos e os controles operacionais registrados em `contexto-validacao.json`: limite inclusivo, um token acima, falta de evidência, retirada de histórico, entrada extensa, montagem do runtime e reabertura do contrato. A entrada extensa foi tokenizada e bloqueada; nenhum peso foi executado.

Candidatos excluídos antes da seleção: {"IDENTITY_TARGET_NOT_ALLOWED": 32, "Fatos confirmados incompatíveis": 1, "Q10 contradiz sensores ou continuidade histórica": 1}. Não são exemplos rotulados insuficientes.

## Limites

Garantias executadas para os predicados tipados e cenários deste piloto. Memória própria adicional exige adaptação semântica; referências ambíguas entre terceiros exigem contrato de representação antes de ampliar suporte. Não há garantia de anonimato estatístico nem de generalização de modelo treinado. Janela suficiente não demonstra uso correto da evidência pelo modelo. Nenhuma integração foi feita na fonte do simulador.
