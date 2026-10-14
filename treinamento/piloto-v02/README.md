# Aula 05 — Colab v02 corrigido

Abra [o Colab](https://colab.research.google.com/github/AIConnection/missao-espacial/blob/main/notebooks/05-Treinamento_Cabecas_v02.ipynb) e execute em ordem. A seção 2 baixa o pacote corrigido da main.

A massa contém 7.410 entradas: 6.834 de classificação e 576 probabilísticas. Entradas vêm apenas de AgentView e memória observada, pela mesma função InputBuilder usada nos agentes. A condição candidata é própria; distribuições de implementações de terceiros e parâmetros de geração não entram no modelo. O pacote não contém auditoria privada.

As previsões combinam os três regimes de geração, com pesos iguais, em 96 continuações de 32 mundos pareados. A distribuição de geração é documentada fora das features e limita a interpretação das probabilidades. Nenhuma das 55.296 continuações foi descartada.

Amostras, distribuições, carregamento do Phi-4, extração, treino, calibração, avaliação e exportação ficam nas células. Checkpoints de vetores são gravados em blocos de 32 entradas. O pacote mudou: os vetores anteriores não são compatíveis; é necessário extrair novamente. O cache rejeita outra identidade de dados.

A comparação NLI usa os 90 casos antigos reproduzíveis, com todos os sensores autorizados. A exclusão anterior de dois casos foi um erro de auditoria: os sensores estavam armazenados separadamente. A célula de comparação baixa o benchmark corrigido diretamente do GitHub; o arquivo histórico de 88 casos no pacote ZIP não é mais utilizado. O ZIP de treinamento permanece idêntico para preservar os caches já extraídos; a v01 permanece intacta. O benchmark fora do domínio antigo continua arquivado e requer adaptação de formato para a cabeça nova.

Validação local: massa completa conferida; tokenizer Phi-4 real; cabeças lineares treinadas em 54 vetores sintéticos por seis épocas para verificar o fluxo; retomada de cache, calibração, comparação e exportação exercitadas. Além disso, a preparação de entradas foi executada em 91 hooks durante uma partida real, com 88 entradas probabilísticas próprias, histórico curto e retomada. Não foi executado treinamento completo nem sessão do Colab nesta correção.
