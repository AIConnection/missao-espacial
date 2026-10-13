# Piloto v03 — alternativas do catálogo e referências temporárias

Esta é uma base auxiliar para classificação de evidências. **Ainda não é o dataset de treinamento das novas saídas probabilísticas.** O contrato probabilístico está em `CONTRATO_PROBABILISTICO.md`, com definições pendentes explicitadas. Esta base foi preparada após corrigir as determinações dos desfechos na engine, com autorização explícita do professor. Os pilotos anteriores permanecem intactos como registros de suas versões.

## Cobertura executada

São 2249 pares únicos: 750 suporte, 749 insuficiente e 750 contradição. A quantidade resulta da cobertura e dos exemplos anteriores, não de cotas de 200 por classe.

O catálogo executável tem 21 perguntas ativas. Foram cobertas todas as alternativas de resposta nas configurações de 5 e 10 participantes: 103 + 108 = 211 combinações de configuração, pergunta e resposta, cada uma nas três classes. São 549 combinações concretas incluindo parâmetros, executadas em partidas legais até a resposta de interesse, sem modificar estado privado ou fonte.

**100% aqui significa alternativas do catálogo como declarações sobre fala registrada.** Não significa 100% de inferências sobre o conteúdo, todos os valores de parâmetros, histórias, estratégias ou resultados. O relatório mantém cobertura do conteúdo como não medida. O exemplo «respondeu SIM» pode ter suporte mesmo quando «há oxigênio suficiente» é insuficiente ou contradito. Não usar o primeiro rótulo no lugar do segundo.

Inclui não sei, recusa, todas as alternativas categóricas e todos os participantes elegíveis de Q19 nas duas configurações. Q11 tem qualquer inteiro positivo, e tripulações têm quantidade e IDs configuráveis: enumeração total de instâncias não é finita. Foram usados X = 1, 15, 16, 17 e 1.000.000, todos os seis assuntos e relações de parâmetro com observador ou terceiro. As fronteiras 13/14/15 e reserva parcial/fracionária da v02 permanecem na base.

Os novos episódios são sondagens legais até a rodada 5, não trajetórias completas nem amostras de sucesso da missão. A execução aceita cada resposta pelo contrato da engine. Suporte compara com o registro recebido; contradição propõe outra resposta para a mesma transação; insuficiente usa uma visão autorizada de outro observador, que não recebeu aquela resposta. Nunca remover evidências de uma visão para fabricar insuficiente.

## Distinguir pessoas sem revelar identidade

Cada chamada tem referências temporárias distintas, por exemplo «participante temporário 1». Uma referência aponta para a mesma pessoa em todos os registros daquela chamada, inclusive históricos de pessoas removidas. O vínculo real e o nonce ficam somente na aplicação. A correspondência é reassociada aleatoriamente em novas chamadas; não há alias persistente que identifique pessoa, módulo, natureza ou personalidade.

O contexto relaciona as referências de observador, fonte e destinatário. Isso permite analisar falas, crenças e comportamentos por pessoa sem misturar terceiros. O modelo não escolhe o mapeamento e não recebe IDs reais. Coincidências de referência entre chamadas não autorizam continuidade de identidade.

`ReferenceFrame` cria o vínculo; `ContextGuard.prepare` usa um vínculo novo por padrão. O gerador usa nonces externos reproduzíveis para permitir auditoria. O nonce e o mapa nunca entram em `encode(pair)`. Uma referência desconhecida ou uma tabela não bijetiva/incompleta bloqueia a representação. O chamador não deve reutilizar os vínculos de geração como identidade estável na produção.

IDs, nomes de implementação, natureza própria e perfil não são features. Objetivos e comportamentos observáveis podem aparecer como conhecimento, sem serem usados como endereço. A proteção remove identificadores explícitos; não promete impedir toda associação estatística por comportamento.

## Arquivos de entrada versus auditoria

- Entrada: `inputs-piloto.jsonl`, somente `premise` e `hypothesis`, acrescidos do prefixo por `ContextGuard.encode`.
- Supervisão: `labels-piloto.json`, códigos 0 = suporte, 1 = insuficiente, 2 = contradição, alinhados pela posição da linha.
- Roteamento externo: `roteamento.jsonl`, com índice, vínculo real e referências temporárias; não fornecer ao modelo.
- Auditoria: `pares.jsonl`, `contextos.jsonl`, `visoes-auditoria.jsonl`, `execucoes-cobertura.jsonl` e `matriz-cobertura.jsonl`; podem conter IDs, proveniência e configurações, não são features.
- `cobertura-validacao.json`: matriz por pergunta/alternativa e escopo da medição.
- `contexto-validacao.json`: contrato de tokenizer, janela e verificações executadas.

As novas previsões de risco não são obtidas renomeando as três classes. A base não contém rótulos de colaboração, traição, sucesso ou confiabilidade futura.

## Validação e reprodução

Passaram 30 testes semânticos, 8 testes do mecanismo de referências e 2249 comparações de entrada sob renomeação consistente de IDs e mudança de natureza/perfil administrativo. Essas verificações demonstram propriedades do adaptador, não desempenho de uma cabeça treinada.

Todos os 2249 prompts couberam na janela de 16384 tokens; máximo 9119, sem cortes. Tokenizer/template reais conferidos contra o runtime local; pesos não executados. Incompletude, inconsistência e excesso de orçamento são falhas de contrato, não rótulos insuficientes.

Na raiz do simulador, usar diretório novo:

```sh
python3 -B datasets/piloto-v03/ferramentas/gerar_cobertura.py --project . --base datasets/piloto-v02 --output /private/tmp/missao-v03-reproducao
python3 -B datasets/piloto-v03/ferramentas/verificar_cobertura.py --project . --folder /private/tmp/missao-v03-reproducao
python3 -B datasets/piloto-v03/ferramentas/testar_referencias.py
/Users/alexandre/crivo/.venv/bin/python -B datasets/piloto-v03/ferramentas/contexto.py --project . --folder /private/tmp/missao-v03-reproducao --model-directory /Users/alexandre/crivo/assets/phi4 --runtime-source /Users/alexandre/crivo/crivo_backend.py
```

`gerar_piloto.py` e `testar_piloto.py` são auxiliares herdados para coleta e testes da v02; os pontos de entrada desta versão são `gerar_cobertura.py` e `verificar_cobertura.py`.

O experimento em `experimento-direcao/` executa continuações completas e estima frequências dos dois desfechos determinados pelo jogo. Sua distribuição de comportamentos está registrada no resumo; as probabilidades são condicionadas a esse amostrador, não previsões de um modelo nem probabilidades universais para qualquer estratégia. Não fornece rótulos de colaboração ou traição.

Não houve treinamento, integração com agentes ou criação de splits. Episódios, sondagens correlacionadas, permutações de referências e exemplos derivados precisam ficar juntos na mesma partição. Antes de treinar saídas probabilísticas, resolver os eventos e a cobertura de conteúdos e decisões; a cobertura de alternativas de fala não substitui essas etapas.
