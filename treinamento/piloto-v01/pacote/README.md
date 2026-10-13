# Pacote do treinamento piloto — Missão Espacial

Este pacote contém entradas, supervisão separada, protocolo, pesos identificados por versão/hash e ferramentas para treinar duas cabeças sobre o mesmo Phi-4 congelado. Não contém os pesos de 8,2 GB: eles são baixados uma vez do repositório público, na revisão fixa registrada em `modelo.json`. Um diretório local com os mesmos arquivos também pode ser usado.

O runtime é PyTorch. Seleção automática: CUDA → MPS/Metal → CPU. Não depende de bitsandbytes, MLX, FlashAttention obrigatório ou de um kernel Metal próprio. É possível selecionar CPU explicitamente. A janela permanece em 16.384 tokens e nenhuma entrada é cortada para caber. O modelo continua grande: CPU é uma alternativa funcional que precisa de memória suficiente e pode demorar bastante; uma máquina com pouca memória pode não comportar o Phi-4.

Na CPU, o prefill padrão processa blocos de 256 tokens e conserva **todas** as chaves/valores anteriores no cache causal. Isso reduz os buffers de atenção, sem descartar o histórico. Em aceleradores, o padrão é processar o prompt inteiro. `--prefill-chunk 256` permite o mesmo prefill em blocos em qualquer dispositivo; `0` significa prompt inteiro. `--tile-rows` limita buffers de desquantização, não a janela de contexto. Trocar dispositivo, ambiente ou configuração da extração exige outro diretório de trabalho: as features podem apresentar diferenças numéricas entre execuções distintas.

## Dados e separação

- Classificação: 600 pares, 200 por classe. Treino 420 (140/classe), calibração 90 (30/classe), teste 90 (30/classe). É uma subamostra do v03, não sua cobertura integral.
- Desfechos: todos os 216 exemplos do v04. Treino 144, calibração 36, teste 36. Cada alvo é uma frequência estimada com 32 continuações, sob o amostrador documentado no v04; não uma probabilidade universal.
- NLI: componentes conectados por episódio, contexto, premissa com referências normalizadas e família de casos hipotéticos permanecem na mesma partição. Casos numéricos de uma mesma família hipotética também ficam juntos. Seleção dos grupos antecede a subamostragem balanceada. Perguntas/tipos de conteúdo podem reaparecer entre partições: não é avaliação de perguntas inéditas.
- Desfechos: todas as variantes/instantes/objetivos/planos da família estrutural original permanecem juntos, conforme o v04.

`dados/inputs.jsonl.gz` tem apenas as entradas autorizadas. `dados/supervisao.jsonl` contém classes/frequências, partição, índice e grupos; é usado para supervisão e avaliação, **nunca concatenado ao prompt**. IDs reais de participantes, roteamento e testemunhas de auditoria não são features. As referências pessoais presentes no contexto são temporárias.

## Treinamento

Uma extração do último estado oculto do Phi-4 (5.120 dimensões) é compartilhada por duas heads independentes. O corpo está congelado. A cabeça NLI produz os três logits; a cabeça de desfechos aprende um logit Bernoulli para entrega, com retorno = 1 − entrega. Não geram texto nem escolhem ações.

Normalização calculada só no treino. Hiperparâmetros definidos antes da execução: Adam, 400 épocas fixas, learning rate 0,01, L2 0,1, semente 171, batch completo na CPU. A calibração escolhe temperatura na grade fixa usando apenas a perda de calibração. O teste não escolhe época, hiperparâmetro, temperatura ou limiar.

Avaliação NLI: matriz de confusão, acurácia, macro F1, perda e resultados por classe; comparação com uniforme e projeção zero-shot A/B/C do Phi-4. Essa projeção não é a cabeça treinada do Crivo.

Avaliação de desfechos: Brier, perda Bernoulli, bins de calibração, comparação com a frequência média **do treino** e diagnóstico de comparação dos três planos. O limiar é ajustado na calibração e reutilizado no teste, com custos unitários meramente demonstrativos. Esses custos não determinam os interesses dos agentes e o limiar não é uma política tática universal. Mostrar separadamente saída crua e calibrada evita esconder o efeito da calibração.

## Rodar localmente

Python 3.10 ou superior, Jupyter para abrir o notebook ou estes comandos a partir da pasta deste pacote:

```sh
python -m pip install -r requirements.txt
python ferramentas/testar.py
python ferramentas/treinar.py extract --package . --work ../execucao --device auto
python ferramentas/treinar.py train --package . --work ../execucao
```

Para reutilizar pesos compatíveis: acrescentar `--model-directory CAMINHO`. Não trocar o modelo por outro menor mantendo este contrato e estas cabeças.

A extração salva uma linha por checkpoint, verifica hashes antes de retomar e recusa treinamento de um cache parcial. Salve o diretório de trabalho em armazenamento persistente para retomar entre sessões. No Colab, isso requer uma pasta do Drive montada ou exportação do diretório: o disco temporário da sessão pode desaparecer. O cache de pesos do Hugging Face também pode ser colocado em armazenamento persistente via `HF_HOME`.

Saídas após execução real: `heads/nli.npz`, `heads/forecast.npz`, `heads/artefato.json`, previsões das partições reservadas e `resultado.json`. São artefatos experimentais; os scripts não modificam o simulador nem o Crivo. `inferir.py` verifica as cabeças, o código, os hashes do pacote, a revisão do modelo e o contrato de feature.

```sh
python ferramentas/inferir.py --package . --heads ../execucao/heads --task nli --input par.json
python ferramentas/inferir.py --package . --heads ../execucao/heads --task forecast --input contexto-e-plano.json
```

NLI retorna apenas a classificação. A previsão retorna as duas probabilidades normalizadas. A implementação do agente mantém o mapeamento de destinatários e decide o que fazer.

## Limites da entrega

O notebook está preparado para executar o treinamento; não inclui cabeças já treinadas nem resultados de qualidade inventados. Os testes com Phi-3 minúsculo e features sintéticas validam o fluxo e a matemática, não o desempenho do Phi-4. O treinamento completo e a extração dos 816 exemplos precisam ser executados pelo aluno/usuário. Os caminhos CUDA/MPS precisam ser validados no hardware escolhido; seleção automática não equivale a teste realizado nesses dispositivos.

Três programas candidatos do v04 e esta subamostra NLI não demonstram generalização para qualquer estratégia. A nova cabeça de desfechos também não está integrada ao backend do simulador. O relatório real deve orientar o próximo experimento; uma head que não supera os baselines não deve ser apresentada como pronta para uso.

Referências do runtime: [PyTorch — dispositivos e backends](https://docs.pytorch.org/docs/stable/backends.html), [pesos quantizados upstream](https://huggingface.co/mlx-community/phi-4-4bit/tree/fc0f8f23d369dc29b55cad1d65cb5bf0dcbee910). A conversão dos pesos affine de 4 bits segue o formato implementado no runtime local auditado, registrado no protocolo; a execução aqui usa apenas PyTorch.
