# Treinamento piloto portátil — Missão Espacial

Abra `notebooks/05-Treinamento_Piloto_Missao_Espacial.ipynb` no Colab (upload do notebook) ou em Jupyter local. O notebook incorpora os dados e os scripts: não requer clonagem do projeto, caminhos do computador do professor ou upload separado de datasets.

## Inferência fora do domínio no Colab

[Abra o notebook atualizado da main no Colab](https://colab.research.google.com/github/AIConnection/missao-espacial/blob/main/notebooks/05-Treinamento_Piloto_Missao_Espacial.ipynb).

O modo padrão `MODO_EXECUCAO="inferencia-github"` pula o treinamento e usa as duas cabeças publicadas em `execucao-local-01/heads/`, com verificação de hashes. A seção 9 começa pelo contrato dos inputs, exemplos completos de estoque e relatos e a preparação do prompt. Permite inspecionar um caso com o gabarito oculto e mostra o prefixo, a instrução original e o prompt serializado com sua quantidade de tokens. Em seguida executa 30 pares NLI fora do domínio do jogo, com 10 exemplos por classe, mostra os casos completos, calcula acurácia, macro F1, precisão, recall e matriz de confusão e exporta os resultados. Apenas premissa e hipótese entram no modelo. A cabeça de desfechos não é avaliada fora do contrato da missão.

Todos os downloads usam um único commit resolvido a partir da `main`. O Phi-4 base permanece na revisão fixa registrada no pacote; não precisa repetir as 816 extrações para usar as cabeças. Para percorrer o treinamento original, selecione `MODO_EXECUCAO="treinamento"`. Uma cópia antiga no Drive não é atualizada automaticamente: abra o link acima ou importe novamente o notebook atualizado.

Há 600 exemplos NLI balanceados (200 por classe) e todos os 216 exemplos de desfechos do v04. O notebook extrai features do Phi-4 congelado, treina duas cabeças separadas, calibra em partições reservadas, avalia no teste e exporta as heads com contrato, normalização, previsões e relatório.

A seleção é automática entre CUDA, MPS/Metal e CPU. Não há exigência de uma GPU específica. Os pesos de aproximadamente 8,2 GB são baixados de uma revisão fixa e verificados. CPU exige memória suficiente e pode ser lenta. Prefill em blocos mantém todo o contexto em cache; a janela de 16.384 tokens não é truncada.

Para terminal/local, use a pasta `pacote/` ou descompacte `pacote-treinamento.zip` e siga seu README. `pacote/requirements.txt` tem as dependências. O notebook preserva o PyTorch compatível instalado pelo ambiente, evitando substituição automática da instalação CUDA do Colab.

No Colab, ajuste a pasta de trabalho para armazenamento persistente se quiser retomar entre sessões. Cada feature tem checkpoint e verificação de integridade. O treino recusa cache parcial. As cabeças exportadas têm um script de inferência independente; não modificam o simulador ou o runtime do Crivo.

## Validação realizada nesta entrega

- **20 testes passaram**: operações e quantização CPU, seleção de dispositivo, captura do último token, prefill com contexto completo, splits reais sem cruzamento de grupos, normalização de treino, treino sintético das duas heads, calibração, métricas, cache e exportação/reabertura de uma cabeça sintética.
- As **8 células de código** foram executadas em modo leve, incluindo extração do pacote incorporado, testes e exportação. Esse modo não baixa/executa os pesos Phi-4 nem fabrica métricas de qualidade.
- As 816 entradas foram comparadas com os datasets originais. As 600 sequências NLI têm codificação idêntica ao contrato v03; as 216 entradas de desfechos são idênticas ao v04. Máximo: 9.119 tokens, abaixo de 16.384, sem recorte.
- Os relatórios de validação estão nesta pasta. O notebook mantém outputs vazios para começar uma execução nova.

## Execução local integral concluída

As duas cabeças foram treinadas com todas as 816 representações reais do Phi-4 congelado em MPS. Os pesos, checkpoints, previsões, protocolo e verificações estão em [execucao-local-01/RELATORIO.md](execucao-local-01/RELATORIO.md).

No teste reservado, a classificação acertou 83 de 90 exemplos (92,2%), contra 68,9% do Phi-4 zero-shot A/B/C. A cabeça de desfechos não superou a constante ajustada no treino: Brier 0,01370 contra 0,01322. O teste de desfechos teve 98,7% das continuações terminando no planeta; esse desequilíbrio limita o piloto.

As cabeças foram reabertas e verificadas com forwards reais adicionais pelo carregador portátil. Os avisos numéricos observados foram conferidos com PyTorch e float64; detalhes e limitações estão no relatório. O treinamento integral não foi executado em CUDA, CPU ou em uma sessão real do Colab. Portabilidade de código não equivale a benchmark realizado em todos os hardwares.

O escopo continua piloto: subamostra NLI e três programas candidatos do v04. Uma execução bem-sucedida não prova generalização para qualquer estratégia. As classes epistemológicas não são probabilidades de sucesso; a cabeça de desfechos não escolhe ações. Avalie baselines, matriz de confusão, Brier, perda e calibração no relatório real antes de considerar integração.

Fontes do simulador, pilotos anteriores, pesos e runtime do Crivo foram preservados.
