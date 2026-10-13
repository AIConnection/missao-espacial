# Dataset da missão espacial — piloto v01

Este piloto inicia a geração supervisionada para uma cabeça que avalia declarações diante de evidências. **Não ensina estratégia, escolha de ação, interesse, vitória, sinceridade deliberada nem identidade humano/IA.** Os planos pertencem somente aos coletores de situações. As implementações existentes do simulador não foram alteradas.

## Contrato da tarefa

A entrada do modelo é exclusivamente um par textual:

```json
{"id":"identificador","premise":"evidências autorizadas","hypothesis":"declaração a avaliar"}
```

O identificador é chave de alinhamento, não texto do prompt nem feature. Não passar o JSON inteiro ao modelo: utilizar somente `premise` e `hypothesis`. Rótulos ficam em arquivo separado; registros administrativos e justificativas nunca entram na entrada.

| ID | Rótulo de máquina | Significado |
|---|---|---|
| 0 | `entailment` | Suporte: a evidência sustenta a declaração. |
| 1 | `neutral` | Informação insuficiente: não há suporte nem contradição demonstráveis neste recorte. |
| 2 | `contradiction` | A evidência sustenta uma alternativa incompatível ou a negação da declaração. |

A ordem coincide com `labels` do contrato local `/Users/alexandre/crivo-training/original/experiments/phi4-semantics/protocol.json`. O nome `neutral` representa insuficiência informacional, não indiferença estratégica. Esses arquivos ainda não foram conectados a um extrator ou treinador; não se presume compatibilidade automática dos demais campos com scripts históricos.

**A verdade global não determina o rótulo.** Uma declaração verdadeira ou falsa no mundo pode receber `neutral` quando o investigador não possui a evidência. Um relato recebido sustenta o que foi dito, mas não confirma o fato relatado. Uma recusa não prova desconhecimento, falsidade ou natureza IA. Objetivo declarado não é prova de ação futura. Acertar uma alternativa não comprova compreensão.

A avaliação refere-se ao recorte de evidências fornecido, não a toda a memória possível do personagem. Este piloto recupera fatos confirmados, sensores e conversas relevantes à declaração a partir do histórico autorizado completo. Não usa uma janela fixa de cinco registros nem restringe a busca à rodada atual. Para declarações de fala, recupera a fonte, pergunta, parâmetros e rodada indicados; para fatos, recupera confirmações e relatos da mesma pergunta; Q10 inclui limites Q11 e sensores para dedução. Uma confirmação antiga de Q11 é atualizada pelo número de avanços desde a confirmação, preservando a origem e o limite original. Uma leitura antiga de oxigênio não é usada como saldo presente. O alvo não é responder com base em conhecimento geral memorizado sobre a narrativa da missão.

Na inferência futura, a política guarda a memória acumulada e prepara o recorte relevante antes de chamar a cabeça. A cabeça não mantém memória entre chamadas. O agente não precisa reenviar todo o histórico bruto, mas deve recuperar evidência de rodadas antigas quando pertinente. Este coletor usa `Game.view(history_limit=None)` para fazer essa recuperação; ainda não existe integração da cabeça às implementações de agentes. A janela padrão de dez registros da sessão não pode substituir a memória acumulada. Uma futura redução por orçamento de tokens deve explicitar o truncamento; `neutral` descreve o recorte e não prova que o personagem inteiro desconhece o assunto.

## Geração e planos de coleta

Foram executadas 18 partidas controladas pela API existente `Game`, em três configurações: C=5/N=10, C=5/N=20 e C=10/N=10. Cada configuração tem três distribuições de planos e duas sementes. A IA e os detentores variam; em metade dos casos painel e distância têm o mesmo detentor, na outra metade são separados. O sorteio não é o setup interativo do simulador: é parametrização externa da coleta.

| Plano de coleta | Perguntar | Responder | Deliberar, rota e saída |
|---|---|---|---|
| Sobrevivência | Investigar risco e destino sem consultar conhecimento secreto de outros. | Compartilhar o que sabe; declarar desconhecimento quando não sabe. | Tentar restringir uma fonte cuja falsidade confirmou; buscar troca de controle somente com IA inferida e risco confirmado; retornar quando controla com risco; solicitar saída com direito e risco confirmado. |
| Missão | Investigar missão, crises e posições. | Compartilhar contexto; quando sabe que falta oxigênio, pode dizer que há suficiente para desencorajar abandono, sujeito à revelação. | Continuar e bloquear saídas para reter tripulação; não solicitar expulsão como atalho para cumprir missão. |
| Reserva informacional | Reconstruir contexto antes de compromisso. | Compartilhar fatos conhecidos, mas recusar opiniões pessoais. | Deliberar com evidência; restringir fonte comprovadamente falsa; retornar se controla com risco confirmado; não solicitar saída neste piloto. |

Esses são **coletores experimentais mínimos**, não versões novas de alpha/beta/gamma/random/humanoide e não estratégias ótimas. A IA mantém as restrições da engine e o plano de missão. O plano de cada humano é independente do ID. Cada ação executada registra plano, destinatário/alvo quando aplicável e justificativa em `trajetorias.jsonl`. Uma mesma falsidade antiga não gera tentativas repetidas de punição sem nova evidência.

`truthful_response` é usado pelo coletor para respostas sinceras segundo o conhecimento autorizado do próprio respondente. A função de rotulação recebe somente a declaração e a projeção da visão do investigador: não recebe `Game`, natureza alheia, owners, N, plano ou verdade global.

O piloto cobre fatos do contexto/estado perguntados nas trajetórias, registros de fala e comparações de reserva. As perguntas de opinião/histórico presentes são usadas como registros de **o que foi dito**, sem converter a posição de um agente em verdade factual. A cobertura do catálogo completo, especialmente inferência sobre conhecimento e posições de terceiros, não está concluída.

## Arquivos

- `inputs-piloto.jsonl`: os 600 pares textuais, sem rótulos ou estratégia.
- `labels-piloto.json`: mapa ID → classe, na ordem acima.
- `pares.jsonl`: pares, classes, declaração estruturada, evidências, testemunhas de suporte/contradição e proveniência; reservado à geração/revisão.
- `visoes-auditoria.jsonl`: visões privadas que permitem verificar a origem das evidências; reservado ao professor.
- `trajetorias.jsonl`: ações executadas e planos de coleta, resultado e configuração administrativa; reservado ao professor.
- `contrastes.jsonl`: referências a exemplos com a mesma declaração nas três classes; derivadas deste piloto, sem independência de avaliação.
- `controles-invariancia.jsonl`: pares idênticos associados a diferentes metadados de objetivo/natureza; contrato para testar que metadados não sejam usados como features. Não são exemplos adicionais de treino.
- `EXEMPLOS.md`: amostra legível dos pares, rótulos e justificativas.
- `manifesto.json`, `validacao.json` e `SHA256SUMS.json`: geração, resultados dos controles e hashes.
- `CONTRATO_CONTEXTO.md`, `contexto-validacao.json` e `contexto-admissao.jsonl`: cobertura tipada, orçamento real do tokenizer e admissão de cada par, sem executar modelo.
- `ferramentas/`: gerador e testes isolados do código fonte do simulador.

## Validação realizada

São 600 pares textuais únicos, 200 por classe, selecionados dos candidatos por rotação entre fenômenos e ordem de hash determinística. Não houve preenchimento de cotas por duplicação. Unicidade textual não implica independência semântica: há correlação entre episódios, instantes e famílias de declarações.

Passaram 16 testes semânticos com casos esperados explícitos: fato confirmado, alternativa incompatível, verdade global sem evidência, falsidade global sem evidência, fala versus fato, recusa, privacidade de fonte/rodada, insuficiência com somente um sensor, combinação de sensores, frações e limiar inclusivo, propagação de limites Q11, validade temporal e exclusão de estratégia/natureza da projeção. Os controles históricos recuperam uma conversa antiga além da janela recente, preservam um fato estático aprendido antes e atualizam um limite antigo de distância para o presente.

Também foram conferidos alinhamento entre arquivos de entrada/rótulos, deduplicação, igualdade de rótulos para entradas idênticas, origem de cada evidência nas visões registradas e hashes das fontes. Essa validação automatizada não é aprovação humana dos 600 exemplos nem avaliação de uma cabeça.

## Limites observados e critérios para a próxima geração

Todas as 18 trajetórias terminaram por esgotamento de oxigênio. Há perguntas, respostas, autorização/proposta, rota e bloqueios. Não se afirma cobertura executada de eleição, retorno, expulsão ou saída efetivada. Nenhum modelo foi executado, nenhum peso foi treinado e nenhuma capacidade de generalização foi medida.

Os textos usam moldes controlados e alternativas do catálogo. Balanceamento de classes não elimina atalhos: fatos estáticos verdadeiros são constantes deste cenário; por exemplo, a suficiência para chegar vivo é sempre negativa enquanto há humanos. Não inventar um estado incompatível com a engine para apresentar uma trajetória alternativa como real. Na próxima etapa, contrastes lógicos hipotéticos devem ser identificados separadamente, se forem incluídos.

Antes de converter o piloto em treino, revisar os rótulos e a linguagem; ampliar negações, paráfrases, cronologia, confirmações de opiniões e relatos de terceiros; produzir declarações de conteúdo menos dependentes do formato pergunta/alternativa; medir atalhos usando somente a declaração ou sem premissa. O gerador atual rotula um subconjunto explicitamente definido, não toda inferência possível em português.

**Não foram criadas partições de treino/seleção/teste.** A separação futura deve preceder o treino e agrupar origens correlacionadas: mesma trajetória, mesmo fato derivado, paráfrases e contrastes do mesmo caso. Excluir pares normalizados compartilhados entre partições. Reservar configurações, combinações de conhecimento e formas linguísticas para avaliação; não basta trocar seed ou ID. Havendo componentes correlacionados grandes, regenerar famílias antes de dividir, sem forçar uma proporção que provoque vazamento.

Na avaliação da cabeça, medir matriz de confusão e resultados por fenômeno, redução de evidência, contraposição fato/fala, controles sem premissa e invariância a interesses/natureza externos. Estes últimos são controles da avaliação, não uma tentativa de generalizar estratégias.

## Reproduzir

Na raiz de `/Users/alexandre/projects/missao-espacial`, depois de salvar esta entrega:

```sh
python3 -B datasets/piloto-v01/ferramentas/gerar_piloto.py --project . --output /private/tmp/missao-piloto-reproducao
python3 -B datasets/piloto-v01/ferramentas/testar_piloto.py --project . --folder /private/tmp/missao-piloto-reproducao
```

O diretório de saída precisa ser novo; o gerador recusa sobrescrever uma entrega. Usa Python e biblioteca padrão, sem instalações, serviços ou inferência. Os arquivos de documentação e controles de metadados são complementos desta entrega; o gerador reproduz corpus, visões, trajetórias e manifesto, e os testes reproduzem validação e contrastes.

Próxima etapa: revisão do piloto e ampliação dos fenômenos e contextos, seguida de separação por famílias. Treinar antes dessas verificações não demonstraria a propriedade que queremos: avaliação da declaração pela evidência, independente do plano do agente.
