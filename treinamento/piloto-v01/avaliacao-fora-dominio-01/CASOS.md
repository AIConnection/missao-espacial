# Casos de inferência fora do domínio

Rótulos e justificativas definidos antes da inferência. IDs abaixo são índices externos da avaliação, não identidades ou features do modelo. O prefixo original é acrescentado pelo carregador e está em `prefixo-utilizado.txt`.

## ood-00: fronteira (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Conferência de um lote de peças, às 15h.

FATOS CONFIRMADOS
O lote atual tem exatamente 14 peças. Todas são embaladas em papel. O peso total é 2 kg.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Mais de 14 significa quantidade > 14. Pelo menos 14 significa quantidade ≥ 14.
```

### Hipótese

O lote atual tem mais de 14 peças.

**Alvo:** contradição. **Justificativa:** 14 não é maior que 14.

**Previsão real:** contradição.

## ood-01: suposicao (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Bancada de ventilação, às 14h.

FATOS CONFIRMADOS
O painel luminoso está aceso. O ventilador está desligado. O estado do filtro não foi medido.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Existe a suposição «o filtro está limpo», formulada sem inspeção.

REGRAS EXPLÍCITAS
Ligado e desligado são estados exclusivos do mesmo ventilador no mesmo instante.
```

### Hipótese

O filtro está limpo às 14h.

**Alvo:** insuficiente. **Justificativa:** Apenas uma suposição informa esse estado, sem confirmação.

**Previsão real:** contradição.

## ood-02: regra-explicita (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Avaliação de um arquivo em um procedimento administrativo, às 13h.

FATOS CONFIRMADOS
O acesso do arquivo está ativo. Seu campo de verificação tem exatamente o valor OK. O arquivo tem duas páginas. Não há registro de assinatura.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
O procedimento aceita o arquivo se, e somente se, o acesso está ativo e o campo de verificação é OK. Em qualquer outro caso, rejeita. Aceitar e rejeitar são resultados exclusivos da execução descrita.
```

### Hipótese

Esse arquivo possui assinatura.

**Alvo:** insuficiente. **Justificativa:** Estado da assinatura não foi registrado e não é condição da regra.

**Previsão real:** contradição.

## ood-03: tempo (paráfrase e evidência irrelevante)

### Premissa

```text
CONTEXTO DISPONÍVEL
Registro de temperatura de uma sala de arquivo. O instante atual é 10h.

FATOS CONFIRMADOS
Uma leitura confirmada às 9h registrou 11 °C. Uma leitura confirmada às 10h registrou 15 °C. A sala contém 18 caixas.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Cada leitura informa a temperatura da sala apenas no instante registrado. Não há regra que garanta temperatura constante.

DADO ADICIONAL CONFIRMADO, IRRELEVANTE PARA A HIPÓTESE
O caderno de anotações tem capa verde.
```

### Hipótese

Às 10h, a leitura confirmada indica uma temperatura de 11 °C.

**Alvo:** contradição. **Justificativa:** 11 °C pertence às 9h e conflita com os 15 °C confirmados às 10h.

**Previsão real:** contradição.

## ood-04: fronteira (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Conferência de um lote de peças, às 15h.

FATOS CONFIRMADOS
O lote atual tem exatamente 14 peças. Todas são embaladas em papel. O peso total é 2 kg.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Mais de 14 significa quantidade > 14. Pelo menos 14 significa quantidade ≥ 14.
```

### Hipótese

O lote que chegará amanhã terá pelo menos 14 peças.

**Alvo:** insuficiente. **Justificativa:** A evidência descreve somente o lote atual, sem quantidade do lote futuro.

**Previsão real:** suporte.

## ood-05: estoque (paráfrase e evidência irrelevante)

### Premissa

```text
CONTEXTO DISPONÍVEL
Estoque de papelaria, às 10h. Todas as declarações de estoque se referem a esse instante.

FATOS CONFIRMADOS
O estoque contém exatamente 14 envelopes. Os envelopes estão lacrados. O pedido atual existe, mas sua quantidade não foi informada.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Um pedido de envelopes pode ser atendido integralmente se, e somente se, a quantidade pedida for menor ou igual ao estoque disponível.

DADO ADICIONAL CONFIRMADO, IRRELEVANTE PARA A HIPÓTESE
O caderno de anotações tem capa verde.
```

### Hipótese

Às 10h, os envelopes disponíveis bastam para um pedido de exatamente 14 unidades.

**Alvo:** suporte. **Justificativa:** 14 ≤ 14, conforme a regra explícita.

**Previsão real:** suporte.

## ood-06: relatos-conflitantes (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Conferência da cor de uma caixa, às 16h.

FATOS CONFIRMADOS
Dois relatos abaixo foram registrados integralmente às 16h. A caixa tem formato cúbico confirmado.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Primeiro relato: «A caixa é azul às 16h». Segundo relato: «A caixa é vermelha às 16h». Não há observação confirmada da cor da caixa.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
A palavra todos nesta hipótese se refere exatamente aos dois relatos apresentados.
```

### Hipótese

Os dois relatos registrados divergem sobre a cor da caixa às 16h.

**Alvo:** suporte. **Justificativa:** Um relata azul e o outro vermelho no mesmo instante.

**Previsão real:** suporte.

## ood-07: suposicao (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Bancada de ventilação, às 14h.

FATOS CONFIRMADOS
O painel luminoso está aceso. O ventilador está desligado. O estado do filtro não foi medido.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Existe a suposição «o filtro está limpo», formulada sem inspeção.

REGRAS EXPLÍCITAS
Ligado e desligado são estados exclusivos do mesmo ventilador no mesmo instante.
```

### Hipótese

O ventilador está ligado às 14h.

**Alvo:** contradição. **Justificativa:** Desligado confirmado é incompatível com ligado no mesmo instante.

**Previsão real:** contradição.

## ood-08: relato (paráfrase e evidência irrelevante)

### Premissa

```text
CONTEXTO DISPONÍVEL
Análise de uma mensagem sobre um alarme, às 9h.

FATOS CONFIRMADOS
A mensagem abaixo foi registrada integralmente às 9h. A porta da sala está confirmadamente fechada.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Há um único relato registrado: «O alarme está acionado às 9h». Não há medição confirmada do estado do alarme.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Nenhuma regra adicional.

DADO ADICIONAL CONFIRMADO, IRRELEVANTE PARA A HIPÓTESE
O caderno de anotações tem capa verde.
```

### Hipótese

No instante das 9h, o estado real do alarme é acionado.

**Alvo:** insuficiente. **Justificativa:** O registro comprova o relato; não confirma seu conteúdo como fato.

**Previsão real:** suporte.

## ood-09: fronteira (paráfrase e evidência irrelevante)

### Premissa

```text
CONTEXTO DISPONÍVEL
Conferência de um lote de peças, às 15h.

FATOS CONFIRMADOS
O lote atual tem exatamente 14 peças. Todas são embaladas em papel. O peso total é 2 kg.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Mais de 14 significa quantidade > 14. Pelo menos 14 significa quantidade ≥ 14.

DADO ADICIONAL CONFIRMADO, IRRELEVANTE PARA A HIPÓTESE
O caderno de anotações tem capa verde.
```

### Hipótese

A quantidade do lote atual ultrapassa 14 peças.

**Alvo:** contradição. **Justificativa:** 14 não é maior que 14.

**Previsão real:** contradição.

## ood-10: tempo (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Registro de temperatura de uma sala de arquivo. O instante atual é 10h.

FATOS CONFIRMADOS
Uma leitura confirmada às 9h registrou 11 °C. Uma leitura confirmada às 10h registrou 15 °C. A sala contém 18 caixas.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Cada leitura informa a temperatura da sala apenas no instante registrado. Não há regra que garanta temperatura constante.
```

### Hipótese

A temperatura da sala às 11h será 15 °C.

**Alvo:** insuficiente. **Justificativa:** Não há observação nem lei de persistência para as 11h.

**Previsão real:** insuficiente.

## ood-11: relato (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Análise de uma mensagem sobre um alarme, às 9h.

FATOS CONFIRMADOS
A mensagem abaixo foi registrada integralmente às 9h. A porta da sala está confirmadamente fechada.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Há um único relato registrado: «O alarme está acionado às 9h». Não há medição confirmada do estado do alarme.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Nenhuma regra adicional.
```

### Hipótese

O relato registrado afirma que o alarme está acionado às 9h.

**Alvo:** suporte. **Justificativa:** A hipótese descreve o conteúdo registrado, não o estado real do alarme.

**Previsão real:** suporte.

## ood-12: regra-explicita (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Avaliação de um arquivo em um procedimento administrativo, às 13h.

FATOS CONFIRMADOS
O acesso do arquivo está ativo. Seu campo de verificação tem exatamente o valor OK. O arquivo tem duas páginas. Não há registro de assinatura.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
O procedimento aceita o arquivo se, e somente se, o acesso está ativo e o campo de verificação é OK. Em qualquer outro caso, rejeita. Aceitar e rejeitar são resultados exclusivos da execução descrita.
```

### Hipótese

O procedimento descrito aceita esse arquivo.

**Alvo:** suporte. **Justificativa:** As duas condições necessárias e suficientes estão confirmadas.

**Previsão real:** suporte.

## ood-13: relato (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Análise de uma mensagem sobre um alarme, às 9h.

FATOS CONFIRMADOS
A mensagem abaixo foi registrada integralmente às 9h. A porta da sala está confirmadamente fechada.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Há um único relato registrado: «O alarme está acionado às 9h». Não há medição confirmada do estado do alarme.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Nenhuma regra adicional.
```

### Hipótese

O alarme está realmente acionado às 9h.

**Alvo:** insuficiente. **Justificativa:** O registro comprova o relato; não confirma seu conteúdo como fato.

**Previsão real:** contradição.

## ood-14: categorias-abertas (paráfrase e evidência irrelevante)

### Premissa

```text
CONTEXTO DISPONÍVEL
Ficha de composição de uma amostra, às 8h.

FATOS CONFIRMADOS
A presença de cobre na amostra foi confirmada. A amostra é sólida. Não há análise sobre a presença de ferro.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
A amostra pode conter vários metais simultaneamente. A presença de cobre não exclui outros metais.

DADO ADICIONAL CONFIRMADO, IRRELEVANTE PARA A HIPÓTESE
O caderno de anotações tem capa verde.
```

### Hipótese

É confirmado que há cobre na amostra.

**Alvo:** suporte. **Justificativa:** Presença confirmada explicitamente.

**Previsão real:** suporte.

## ood-15: estoque (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Estoque de papelaria, às 10h. Todas as declarações de estoque se referem a esse instante.

FATOS CONFIRMADOS
O estoque contém exatamente 14 envelopes. Os envelopes estão lacrados. O pedido atual existe, mas sua quantidade não foi informada.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Um pedido de envelopes pode ser atendido integralmente se, e somente se, a quantidade pedida for menor ou igual ao estoque disponível.
```

### Hipótese

Um pedido de 14 envelopes pode ser atendido integralmente às 10h.

**Alvo:** suporte. **Justificativa:** 14 ≤ 14, conforme a regra explícita.

**Previsão real:** suporte.

## ood-16: estoque (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Estoque de papelaria, às 10h. Todas as declarações de estoque se referem a esse instante.

FATOS CONFIRMADOS
O estoque contém exatamente 14 envelopes. Os envelopes estão lacrados. O pedido atual existe, mas sua quantidade não foi informada.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Um pedido de envelopes pode ser atendido integralmente se, e somente se, a quantidade pedida for menor ou igual ao estoque disponível.
```

### Hipótese

O pedido atual pode ser atendido integralmente às 10h.

**Alvo:** insuficiente. **Justificativa:** A quantidade do pedido atual é desconhecida; estoque e regra não a determinam.

**Previsão real:** insuficiente.

## ood-17: tempo (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Registro de temperatura de uma sala de arquivo. O instante atual é 10h.

FATOS CONFIRMADOS
Uma leitura confirmada às 9h registrou 11 °C. Uma leitura confirmada às 10h registrou 15 °C. A sala contém 18 caixas.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Cada leitura informa a temperatura da sala apenas no instante registrado. Não há regra que garanta temperatura constante.
```

### Hipótese

A temperatura confirmada da sala às 10h é 11 °C.

**Alvo:** contradição. **Justificativa:** 11 °C pertence às 9h e conflita com os 15 °C confirmados às 10h.

**Previsão real:** contradição.

## ood-18: estoque (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Estoque de papelaria, às 10h. Todas as declarações de estoque se referem a esse instante.

FATOS CONFIRMADOS
O estoque contém exatamente 14 envelopes. Os envelopes estão lacrados. O pedido atual existe, mas sua quantidade não foi informada.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Um pedido de envelopes pode ser atendido integralmente se, e somente se, a quantidade pedida for menor ou igual ao estoque disponível.
```

### Hipótese

Um pedido de 15 envelopes pode ser atendido integralmente às 10h.

**Alvo:** contradição. **Justificativa:** 15 > 14, logo a regra impede atendimento integral.

**Previsão real:** contradição.

## ood-19: categorias-abertas (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Ficha de composição de uma amostra, às 8h.

FATOS CONFIRMADOS
A presença de cobre na amostra foi confirmada. A amostra é sólida. Não há análise sobre a presença de ferro.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
A amostra pode conter vários metais simultaneamente. A presença de cobre não exclui outros metais.
```

### Hipótese

A amostra contém ferro.

**Alvo:** insuficiente. **Justificativa:** Ferro não foi analisado e pode coexistir com cobre.

**Previsão real:** insuficiente.

## ood-20: suposicao (paráfrase e evidência irrelevante)

### Premissa

```text
CONTEXTO DISPONÍVEL
Bancada de ventilação, às 14h.

FATOS CONFIRMADOS
O painel luminoso está aceso. O ventilador está desligado. O estado do filtro não foi medido.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Existe a suposição «o filtro está limpo», formulada sem inspeção.

REGRAS EXPLÍCITAS
Ligado e desligado são estados exclusivos do mesmo ventilador no mesmo instante.

DADO ADICIONAL CONFIRMADO, IRRELEVANTE PARA A HIPÓTESE
O caderno de anotações tem capa verde.
```

### Hipótese

Na bancada às 14h, o filtro encontra-se limpo.

**Alvo:** insuficiente. **Justificativa:** Apenas uma suposição informa esse estado, sem confirmação.

**Previsão real:** suporte.

## ood-21: relatos-conflitantes (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Conferência da cor de uma caixa, às 16h.

FATOS CONFIRMADOS
Dois relatos abaixo foram registrados integralmente às 16h. A caixa tem formato cúbico confirmado.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Primeiro relato: «A caixa é azul às 16h». Segundo relato: «A caixa é vermelha às 16h». Não há observação confirmada da cor da caixa.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
A palavra todos nesta hipótese se refere exatamente aos dois relatos apresentados.
```

### Hipótese

Todos os relatos registrados dizem que a caixa é azul às 16h.

**Alvo:** contradição. **Justificativa:** O segundo relato diz vermelha, refutando todos.

**Previsão real:** contradição.

## ood-22: fronteira (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Conferência de um lote de peças, às 15h.

FATOS CONFIRMADOS
O lote atual tem exatamente 14 peças. Todas são embaladas em papel. O peso total é 2 kg.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Mais de 14 significa quantidade > 14. Pelo menos 14 significa quantidade ≥ 14.
```

### Hipótese

O lote atual tem pelo menos 14 peças.

**Alvo:** suporte. **Justificativa:** 14 ≥ 14.

**Previsão real:** suporte.

## ood-23: suposicao (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Bancada de ventilação, às 14h.

FATOS CONFIRMADOS
O painel luminoso está aceso. O ventilador está desligado. O estado do filtro não foi medido.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Existe a suposição «o filtro está limpo», formulada sem inspeção.

REGRAS EXPLÍCITAS
Ligado e desligado são estados exclusivos do mesmo ventilador no mesmo instante.
```

### Hipótese

O painel luminoso está aceso às 14h.

**Alvo:** suporte. **Justificativa:** Fato confirmado do instante descrito.

**Previsão real:** suporte.

## ood-24: relato (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Análise de uma mensagem sobre um alarme, às 9h.

FATOS CONFIRMADOS
A mensagem abaixo foi registrada integralmente às 9h. A porta da sala está confirmadamente fechada.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Há um único relato registrado: «O alarme está acionado às 9h». Não há medição confirmada do estado do alarme.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Nenhuma regra adicional.
```

### Hipótese

O único relato registrado afirma que o alarme está desativado às 9h.

**Alvo:** contradição. **Justificativa:** O conteúdo integral do único relato é acionado, e não desativado.

**Previsão real:** contradição.

## ood-25: regra-explicita (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Avaliação de um arquivo em um procedimento administrativo, às 13h.

FATOS CONFIRMADOS
O acesso do arquivo está ativo. Seu campo de verificação tem exatamente o valor OK. O arquivo tem duas páginas. Não há registro de assinatura.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
O procedimento aceita o arquivo se, e somente se, o acesso está ativo e o campo de verificação é OK. Em qualquer outro caso, rejeita. Aceitar e rejeitar são resultados exclusivos da execução descrita.
```

### Hipótese

O procedimento descrito rejeita esse arquivo.

**Alvo:** contradição. **Justificativa:** As condições determinam aceitar, incompatível com rejeitar.

**Previsão real:** contradição.

## ood-26: categorias-abertas (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Ficha de composição de uma amostra, às 8h.

FATOS CONFIRMADOS
A presença de cobre na amostra foi confirmada. A amostra é sólida. Não há análise sobre a presença de ferro.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
A amostra pode conter vários metais simultaneamente. A presença de cobre não exclui outros metais.
```

### Hipótese

A amostra contém cobre.

**Alvo:** suporte. **Justificativa:** Presença confirmada explicitamente.

**Previsão real:** suporte.

## ood-27: tempo (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Registro de temperatura de uma sala de arquivo. O instante atual é 10h.

FATOS CONFIRMADOS
Uma leitura confirmada às 9h registrou 11 °C. Uma leitura confirmada às 10h registrou 15 °C. A sala contém 18 caixas.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
Cada leitura informa a temperatura da sala apenas no instante registrado. Não há regra que garanta temperatura constante.
```

### Hipótese

A temperatura confirmada da sala às 10h é 15 °C.

**Alvo:** suporte. **Justificativa:** A leitura das 10h informa exatamente 15 °C.

**Previsão real:** suporte.

## ood-28: relatos-conflitantes (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Conferência da cor de uma caixa, às 16h.

FATOS CONFIRMADOS
Dois relatos abaixo foram registrados integralmente às 16h. A caixa tem formato cúbico confirmado.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Primeiro relato: «A caixa é azul às 16h». Segundo relato: «A caixa é vermelha às 16h». Não há observação confirmada da cor da caixa.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
A palavra todos nesta hipótese se refere exatamente aos dois relatos apresentados.
```

### Hipótese

A caixa é azul às 16h.

**Alvo:** insuficiente. **Justificativa:** Relatos conflitantes não resolvem a cor real, que não foi observada.

**Previsão real:** suporte.

## ood-29: categorias-abertas (base)

### Premissa

```text
CONTEXTO DISPONÍVEL
Ficha de composição de uma amostra, às 8h.

FATOS CONFIRMADOS
A presença de cobre na amostra foi confirmada. A amostra é sólida. Não há análise sobre a presença de ferro.

RELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO
Nenhum relato adicional.

SUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES
Nenhuma suposição adicional.

REGRAS EXPLÍCITAS
A amostra pode conter vários metais simultaneamente. A presença de cobre não exclui outros metais.
```

### Hipótese

A amostra não contém cobre.

**Alvo:** contradição. **Justificativa:** Negação de um fato confirmado.

**Previsão real:** contradição.
