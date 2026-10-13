# Aula 05 — treinamento v02 no Colab

1. Abra [o notebook no Colab](https://colab.research.google.com/github/AIConnection/missao-espacial/blob/main/notebooks/05-Treinamento_Cabecas_v02.ipynb).
2. Execute as células em ordem. A seção 2 baixa `dados-colab-v02.zip` da main do GitHub.
3. A seção 5 baixa o corpo Phi-4; a seção 6 extrai vetores com os pesos congelados; a seção 7 treina as duas cabeças.
4. As seções seguintes calibram, avaliam, demonstram inferência, comparam classificação com a v01 e exportam resultados.

O pacote tem aproximadamente 3 MB e contém a massa v05 completa (8.562 entradas), instruções constantes, protocolo, hashes e referências NLI anteriores. Não inclui a auditoria privada nem os pesos do corpo; estes são obtidos do Hugging Face na revisão fixada do modelo. O notebook e o pacote são publicados juntos no GitHub.

As entradas e alvos dos cinco primeiros e cinco últimos exemplos aparecem separadamente. As distribuições e partições são mostradas antes da extração. Carregador, preparação de textos, treino, calibração, avaliação e exportação estão nas células; não há scripts de treino ocultos, Base64 ou modos de execução.

O trabalho desta execução fica em `/content/treinamento-aula05-v02`. Para persistir após perder a sessão, mude `WORK_DIR` para uma pasta persistente já montada antes de extrair. Checkpoints são gravados a cada 32 entradas. Ao final, baixe o ZIP de resultados com dados, vetores, cabeças e relatórios. O notebook anterior e a massa v05 original não foram modificados.

Validação local: leitura e integridade da massa inteira; treino real das camadas lineares em 54 exemplos com vetores sintéticos e seis épocas; retomada do cache; normalização, calibração, inferência, comparação e exportação; tokenização real das 8.562 entradas com o tokenizer Phi-4. Máximos: 14.223 tokens na classificação e 6.397 na previsão, dentro de 16.384, sem truncamento. Os vetores sintéticos serviram somente para verificar o pipeline, sem produzir métricas de qualidade do Phi-4.

Não foi executada uma sessão do Colab, extração completa do Phi-4 ou treinamento completo v02. O protocolo no notebook usa a massa completa e 400 épocas, mantendo arquitetura e hiperparâmetros do piloto anterior. A cabeça probabilística antiga não é comparada diretamente no contrato novo.
