# Treinamento piloto — Missão Espacial

Foram treinadas duas cabeças novas com dados da Missão Espacial. O corpo pré-treinado público do Phi-4 ficou congelado. A cabeça e a normalização treinadas para o Crivo não foram carregadas. O Crivo foi apenas referência de método; o ambiente Python e os arquivos-base locais foram reutilizados.

## Massa e protocolo

- Classificação: 600 exemplos, 200 por classe; 420 treino, 90 calibração, 90 teste. Grupos relacionados ficaram na mesma partição.
- Desfechos: 216 exemplos; 144 treino, 36 calibração, 36 teste. Alvos estimados com 32 continuações por plano da engine; 6.912 continuações apoiam 216 exemplos, não 6.912 exemplos independentes.
- Cada cabeça usa a representação de 5.120 dimensões do prompt completo. Normalização calculada apenas no treino; pesos/bias novos inicializados com zero. Adam, 400 épocas fixas, learning rate 0,01, regularização L2 0,1, semente 171. Temperatura selecionada na calibração. Teste não selecionou época, temperatura, parâmetros ou limiar.
- Nenhum ID real ou módulo de implementação entrou no prompt. Referências pessoais temporárias e mapeamento externo. Nenhum futuro da continuação ou testemunha de supervisão foi fornecido como feature.
- Todos os 816 prompts foram preservados; limite de 16.384 tokens, máximo observado 9.119; sem truncamento.

## Classificação — teste

| Leitura | Acurácia | Macro F1 | NLL |
|---|---:|---:|---:|
| Cabeça crua | 0.922222 | 0.922395 | 0.264398 |
| Cabeça calibrada | 0.922222 | 0.922395 | 0.262645 |
| Phi-4 zero-shot A/B/C | 0.688889 | 0.687400 | 0.703984 |
| Uniforme | 0.333333 | 0.166667 | 1.098612 |

A projeção A/B/C é do vocabulário do Phi-4 pré-treinado. Não é a cabeça NLI treinada para o Crivo. Matriz de confusão e resultados por classe estão em `resultado.json`. O teste tem 90 exemplos e avalia famílias/episódios reservados; não prova cobertura de perguntas inéditas, todas as fronteiras numéricas ou todos os contextos possíveis.

## Desfechos — teste

| Leitura | Brier (menor é melhor) | Perda Bernoulli |
|---|---:|---:|
| Cabeça crua | 0.01823789 | 0.11807210 |
| Cabeça calibrada | 0.01370151 | 0.08122915 |
| Constante ajustada no treino | 0.01322433 | 0.07712374 |

A constante usa a frequência do treino (0.967665), sem consultar o teste. O relatório informa as frequências observadas e os bins. Os 36 exemplos possuem 32 continuações cada, com correlações de família/plano: não são 1.152 contextos independentes.

O limiar demonstrativo foi escolhido na calibração com custos FP=FN=1 e aplicado intacto ao teste. Não é uma regra para decidir retorno, sacrifício ou expulsão. A comparação dos três candidatos é um diagnóstico de uma política de avaliação externa; a cabeça não escolhe o plano nem a ação. A referência de melhor candidato é uma frequência finita amostrada, não um ótimo verdadeiro.

## Execução e portabilidade

A execução local usou MPS detectado automaticamente. CUDA e CPU permanecem suportados pelo pacote portátil, mas não se afirma que o treinamento completo foi executado nesses dispositivos. A aceleração local reconstruiu as mesmas matrizes fp16: 14.145.290.240 valores foram comparados, com igualdade exata. O agrupamento de multiplicações foi medido contra o caminho portátil. Um teste com três exemplos em lote não acelerou esta máquina, portanto não foi aplicado.

Para reduzir recomputação, o executor ordenou os prompts apenas pelos tokens e reaproveitou prefixos exatamente iguais, cortando do cache todas as posições divergentes. Isso é reuso causal de cálculo: os tokens restantes e todo o histórico relevante continuaram representados. Exemplos longos foram processados em blocos com cache completo. Nenhum prompt foi transformado ou encurtado. Os 107 checkpoints calculados anteriormente foram preservados. Fingerprints, hashes, números de tokens e tempo por linha ficam nos manifestos. Diferenças de arredondamento entre plataformas/modos de cálculo continuam possíveis.

O salvamento de uma representação levou mediana de aproximadamente 0,00164 s em 100 repetições; o forward levou cerca de 20 s nos exemplos medidos. Gravação não foi o gargalo. Os checkpoints permitem retomar extração sem repetir as linhas concluídas.

## Uso e limites

As heads retornam classificação ou probabilidades normalizadas de entrega no planeta e retorno com sobrevivência. A implementação mantém os destinatários e decide ações de acordo com seu objetivo. Não há transferência da política do Crivo, rótulos de traição/colaboração ou perfil moral permanente de participantes.

A cabeça probabilística permanece condicionada ao amostrador e aos três programas do v04. Esta massa não prova generalização para qualquer estratégia. Resultado de treinamento não equivale a integração: os agentes da engine continuam com suas implementações existentes. Uma head que não supera seus baselines não deve ser apresentada como pronta para decisões de missão.

O corpo do modelo, os datasets anteriores e o código-fonte do simulador não foram alterados neste treinamento.

## Verificação dos artefatos exportados

As matrizes e representações normalizadas são finitas. O NumPy emitiu avisos de overflow/divisão/invalidez durante multiplicações, mas os resultados foram finitos e coincidiram exatamente com a multiplicação independente no PyTorch CPU. A conferência float64 preservou todas as classificações; a maior diferença de probabilidade NLI foi inferior a 9e-7 e a diferença de Brier dos desfechos foi inferior a 1e-9. Esses avisos não foram ocultados; `validacao-numerica.json` registra a reprodução e a conferência.

`validacao-inferencia.json` registra quatro forwards reais adicionais pelo carregador portátil original: um exemplo de teste de cada classe e um de desfechos. As cabeças foram reabertas com verificação dos hashes; os resultados concordaram com as previsões das representações salvas. Essa conferência local não substitui uma avaliação integral em CUDA, CPU ou Colab.

Os arquivos em `execucao/` documentam a execução local e incluem caminhos desta máquina. O fluxo portátil para os alunos permanece no notebook e em `../pacote/`; os auxiliares locais não são necessários para executar no Colab. Os pesos públicos de 8,2 GB não estão duplicados nesta entrega. `features/` contém os 816 checkpoints reais, suficientes para reproduzir o ajuste das cabeças sem repetir a extração.
