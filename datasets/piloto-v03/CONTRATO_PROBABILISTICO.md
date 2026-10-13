# Saídas probabilísticas — contrato em preparação

## Decisão confirmada

Manter as três classes epistemológicas e acrescentar saídas probabilísticas ao modelo. A implementação recebe classificações/previsões e escolhe a ação conforme objetivo e plano. O modelo não responde uma ação. A engine é a fonte dos efeitos executados, não um oráculo de probabilidades já disponível.

## O que deve ser previsto

Cada previsão precisa especificar evento, pessoa referida temporariamente, objetivo/plano ou ação candidata relevante e horizonte. «Probabilidade de colaboração» sem dizer colaborar com quê, de que maneira e até quando não é alvo reproduzível. «Confiabilidade» não é atributo fixo por ID: dizer a verdade, cumprir compromisso e agir favoravelmente ao objetivo são comportamentos diferentes.

As probabilidades das três classes medem a relação de evidência. Não são probabilidade de sucesso, colaboração ou traição. Novas saídas requerem supervisão e avaliação próprias; não estão implementadas no backend atual de três logits nem treinadas nesta entrega.

## Uso da engine

Gerar continuações com diferentes estados desconhecidos compatíveis com o contexto autorizado e diferentes comportamentos dos participantes. O gerador pode consultar registros completos para rotular efeitos reais, mas não transmitir segredos ou implementações como features. Nenhuma informação posterior ao instante da previsão pode entrar no contexto.

Uma frequência empírica de um evento definido sob continuações amostradas estima uma probabilidade sob aquela distribuição de estados/comportamentos. Não garante o resultado contra qualquer estratégia. Documentar amostragem, horizonte, número de continuações, variação e incerteza. Rollouts repetidos idênticos não são evidência independente.

Não transformar efeito não observado em falso. Se há resultados sem observação do evento, registrar censura/indefinição; não contar como derrota ou traição. Rótulos binários de resultados realizados e estimativas de frequência por muitas continuações são supervisões diferentes e devem ser identificadas como tais.

## Determinações confirmadas pelo usuário

- Direção final PLANETA: carga entregue, entrega observável e sucesso da missão.
- Direção final ESTAÇÃO ESPACIAL: retorno e sobrevivência dos humanos.

Esses são rótulos por determinação do jogo, não aproximações nem substitutos de uma entrega futura. `desfecho.label_outcome` os deriva do desfecho terminal. A engine registra `returned` e `mission_commitment`, usados para resolver as duas direções; resultados ausentes ou incoerentes são rejeitados.

A divergência anterior foi corrigida na engine: `_finish` registra entrega e observação verdadeiras na direção ao planeta; `Game.loads` adequa checkpoints encerrados antigos. Os rótulos derivados seguem os campos da fonte corrigida e preservam o resultado bruto para auditoria. Passaram os 186 testes do simulador e a execução local completa do notebook.

O alvo «retorno e sobrevivência» é o evento conjunto definido pela direção à estação. No registro derivado, `humans_survived=True` no retorno; nos demais casos permanece indefinido, pois a determinação sobre entrega no planeta não declara por si só o destino individual de todos os humanos. Não usar um rótulo ausente como falso.

Não há evento denominado colaboração ou traição na engine. Não confundir uma mentira, recusa ou interesse diferente com traição sem uma definição contextual e observável. Os perfis das implementações não são rótulos de confiança.

## Definições pendentes

1. Critério de colaboração: evento/ação, favorecido e horizonte.
2. Critério de traição: compromisso ou condição observável violada, pessoa afetada e horizonte.
3. Os dois desfechos finais já estão definidos pelas determinações acima. Objetivos compostos exigem explicitar sua avaliação, sem transformar interesses distintos em uma estratégia única.
4. O significado operacional de confiabilidade e a distribuição de comportamentos nas continuações.

Não gerar números para colaboração, traição ou confiabilidade antes de resolver suas definições. A determinação dos desfechos já permite estimar suas frequências. O código fonte foi corrigido conforme a autorização posterior do usuário para cumprir as determinações do desfecho.

## Avaliação dos limiares

Separar partidas/famílias de comportamento de treino, calibração e avaliação. Usar resultados observados para avaliar se probabilidades previstas correspondem a frequências, por evento, horizonte e objetivo. Testar também comportamentos não usados no treino e mudanças de comportamento durante a partida. Uma taxa de classificação alta não comprova calibração das novas saídas.

Limiar é escolha da implementação/política, não verdade do ambiente. Escolher conforme custos de falso positivo e falso negativo e validar a utilidade das decisões. No caso binário simplificado com custos C_FP e C_FN, o limiar de custo esperado é C_FP / (C_FP + C_FN); essa fórmula não cobre custos gerais dependentes de estado, múltiplas ações ou objetivos compostos. Não adotar 0,5 ou outro número universal sem avaliar o custo e a calibração. As probabilidades devem continuar utilizáveis por estratégias com custos distintos.

Nenhum limiar foi escolhido nem validado empiricamente nesta entrega. Não há modelo treinado ou dataset probabilístico finalizado.
