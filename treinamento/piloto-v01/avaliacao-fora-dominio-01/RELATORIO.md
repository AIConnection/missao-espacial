# Inferência fora do domínio — cabeça NLI da Missão Espacial

Executamos **30 forwards reais do Phi-4** em **8 famílias de casos**, com 10 alvos de cada classe. A cabeça acertou **23/30 (76.7%)**. Macro F1: **0,7215**.

Neste ensaio, os 20 casos de suporte/contradição foram corretos. A cabeça reconheceu apenas 3/10 insuficientes: 4 viraram suporte e 3, contradição. Assim, o principal limite observado foi resolver hipóteses sem evidência suficiente.

## Contrato e método

- Entrada do modelo: somente `premise` e `hypothesis`, ambas strings. O prefixo NLI original e o chat template foram preservados.
- Saída pública: somente a chave `classification`, com um dos rótulos `suporte`, `insuficiente` ou `contradição`. As probabilidades em `previsoes.jsonl` pertencem somente à auditoria da avaliação.
- Cabeça, normalização e temperatura originais. Nenhum ajuste de pesos ou calibração durante o ensaio. A cabeça de outro domínio não foi carregada.
- Alvos e justificativas foram salvos e tiveram seus hashes calculados antes de carregar o modelo. Não foram fornecidos como entrada.
- Premissas ricas, fonte da informação explícita, instante definido quando relevante, regras numéricas e exclusividade fornecidas. Nenhuma identidade de agente entra nas premissas.
- Maior entrada: 800 tokens, sem truncamento, na janela de 16.384. Dispositivo executado: mps.
- Esta avaliação testa a cabeça de três classes. A cabeça de desfechos mantém um contrato específico de missão, contexto e planos, e não foi chamada com desfechos genéricos incompatíveis.

## Métricas

| Método | Acurácia | Macro F1 | NLL interna |
|---|---:|---:|---:|
| Cabeça treinada, fora do domínio | 76.7% | 0,7215 | 0,6737 |
| Distribuição uniforme | 33,3% | 0,1667 | 1,0986 |

Acurácia conta rótulos corretos. Macro F1 dá o mesmo peso às classes. NLL usa a probabilidade interna do alvo e revela erros confiantes, com piso numérico 1e-12. A probabilidade calibrada no domínio de treino não tem calibração demonstrada neste novo domínio. A referência uniforme desempata pelo primeiro rótulo, sem sorteio.

No teste original, a cabeça acertou 83/90 (92,2%). Os dois corpora diferem em composição e tamanho; essa comparação é descritiva, sem atribuir causalmente a diferença apenas ao domínio.

## Matriz de confusão

Linhas: alvo. Colunas: previsão.

| Alvo / previsão | suporte | insuficiente | contradição |
|---|---:|---:|---:|
| suporte | 10 | 0 | 0 |
| insuficiente | 4 | 3 | 3 |
| contradição | 0 | 0 | 10 |

| Classe | Precisão | Revocação | F1 |
|---|---:|---:|---:|
| suporte | 0,7143 | 1,0000 | 0,8333 |
| insuficiente | 1,0000 | 0,3000 | 0,4615 |
| contradição | 0,7692 | 1,0000 | 0,8696 |

## Coesão e famílias

| Família | Acertos / casos |
|---|---:|
| categorias-abertas | 4/4 |
| estoque | 4/4 |
| fronteira | 3/4 |
| regra-explicita | 2/3 |
| relato | 2/4 |
| relatos-conflitantes | 2/3 |
| suposicao | 2/4 |
| tempo | 4/4 |

As 24 entradas de base tiveram 79.2% de acerto. As seis variantes preservam o significado, parafraseiam a hipótese e acrescentam um fato irrelevante. 4/6 pares mantiveram a classe; 4/6 tiveram ambas as previsões corretas. Consistência sozinha não significa correção. As variantes não são exemplos independentes.

## Erros observados

### ood-01: suposicao

**Hipótese:** O filtro está limpo às 14h.

**Esperado:** insuficiente. **Previsto:** contradição. Probabilidade interna da classe prevista: 46.43%.

**Motivo do alvo:** Apenas uma suposição informa esse estado, sem confirmação.

### ood-02: regra-explicita

**Hipótese:** Esse arquivo possui assinatura.

**Esperado:** insuficiente. **Previsto:** contradição. Probabilidade interna da classe prevista: 91.70%.

**Motivo do alvo:** Estado da assinatura não foi registrado e não é condição da regra.

### ood-04: fronteira

**Hipótese:** O lote que chegará amanhã terá pelo menos 14 peças.

**Esperado:** insuficiente. **Previsto:** suporte. Probabilidade interna da classe prevista: 57.53%.

**Motivo do alvo:** A evidência descreve somente o lote atual, sem quantidade do lote futuro.

### ood-08: relato

**Hipótese:** No instante das 9h, o estado real do alarme é acionado.

**Esperado:** insuficiente. **Previsto:** suporte. Probabilidade interna da classe prevista: 98.84%.

**Motivo do alvo:** O registro comprova o relato; não confirma seu conteúdo como fato.

### ood-13: relato

**Hipótese:** O alarme está realmente acionado às 9h.

**Esperado:** insuficiente. **Previsto:** contradição. Probabilidade interna da classe prevista: 67.03%.

**Motivo do alvo:** O registro comprova o relato; não confirma seu conteúdo como fato.

### ood-20: suposicao

**Hipótese:** Na bancada às 14h, o filtro encontra-se limpo.

**Esperado:** insuficiente. **Previsto:** suporte. Probabilidade interna da classe prevista: 63.94%.

**Motivo do alvo:** Apenas uma suposição informa esse estado, sem confirmação.

### ood-28: relatos-conflitantes

**Hipótese:** A caixa é azul às 16h.

**Esperado:** insuficiente. **Previsto:** suporte. Probabilidade interna da classe prevista: 76.45%.

**Motivo do alvo:** Relatos conflitantes não resolvem a cor real, que não foi observada.

## Limites e interpretação

O ensaio verifica saída contratual, inferência real e relações de evidência fora dos assuntos do treino. Ele não certifica generalização para qualquer contexto ou estratégia.

Os casos são uma amostra construída por conveniência, com alvos anotados pelo autor, sem revisão humana independente. Há oito famílias e seis variantes correlacionadas. Mudam assuntos e formulações textuais; o ensaio não isola o efeito de cada mudança. O prefixo constante ainda contém regras específicas da Missão Espacial, porque removê-lo alteraria o contrato usado no treinamento.

Os erros mostram divergência em relação à evidência fornecida. Não identificam, sozinhos, a causa dentro do modelo. Nenhum alvo foi corrigido para acomodar a previsão. Novos ensaios precisam ter casos e critérios definidos antes da execução.

## Arquivos e reprodução

`inputs.jsonl` contém apenas as entradas. `supervisao.jsonl` contém alvos, famílias, variantes e justificativas externas. `CASOS.md` mostra as premissas completas. `protocolo.json` registra a definição anterior ao ensaio e hashes. `previsoes.jsonl` e `resultado.json` guardam saídas e métricas. `features/` contém representações reais para conferir a projeção sem novo forward. `validacao-numerica.json` confere os cálculos da cabeça.

Para repetir, copie `inputs.jsonl`, `supervisao.jsonl` e `protocolo.json` para uma pasta nova. Execute o carregador com o pacote e os pesos públicos correspondentes:

```sh
python executar.py --project /caminho/missao-espacial --model-directory /caminho/pesos-phi4 --device auto --data /caminho/pasta-nova
```

O script recusa sobrescrever previsões anteriores. Ele não baixa uma cabeça de outro domínio nem treina pesos. A seleção `auto` admite CPU, CUDA ou MPS conforme o ambiente; esta execução foi somente local em MPS.

Integridade da cabeça antes/depois: `b6d5497851e3d74091f317b60fbf42b510eac32883c9da467fe7475333f4fa1e`. Tempo total da execução: 566.9 s.
