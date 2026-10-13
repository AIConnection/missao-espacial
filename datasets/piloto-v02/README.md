# Piloto v02 — classificação contextual sem identidade

A cabeça recebe **contexto autorizado + declaração** e devolve exclusivamente **suporte, insuficiente ou contradição**. A implementação do agente associa a classificação à interação e ao destinatário, e decide como agir conforme seus objetivos e seu plano. O modelo não escolhe perguntas, respostas, votação, saída ou estratégia. O alvo não é aprender uma estratégia, mas avaliar a relação entre evidência e declaração.

## Contrato das classes

| Saída | Código | Nome técnico nos metadados | Significado |
|---|---:|---|---|
| suporte | 0 | entailment | O contexto sustenta a declaração. |
| insuficiente | 1 | neutral | O contexto não sustenta nem contradiz a declaração. |
| contradição | 2 | contradiction | O contexto sustenta conteúdo incompatível com a declaração. |

Suporte não garante verdade absoluta: é sustentação pelo contexto autorizado. Um relato pode sustentar «foi dito X», sem sustentar «X aconteceu». Crenças, objetivos e suposições são apresentados como tais. Uma declaração sobre um objetivo exato não é previsão de ação nem avaliação moral.

Os três rótulos atendem à relação epistemológica para os predicados suportados. Contexto incompleto, referências não representáveis e confirmações incompatíveis são erros de contrato, não uma quarta classe nem casos automaticamente insuficientes. «Devo sair?» exige decisão estratégica e não é alvo desta cabeça. Dividir declarações compostas antes de pedir relações distintas; não interpretar um único rótulo como avaliação de cada componente.

## Separação de identidade e roteamento

`inputs-piloto.jsonl` contém **somente `premise` e `hypothesis`**. Não contém nem mesmo ID de amostra. `labels-piloto.json` é a lista de códigos de supervisão na mesma ordem. O prefixo constante de regras está em `prefixo-modelo.txt` e é acrescentado por `ContextGuard.encode`.

IDs reais, nomes de implementação, natureza própria, perfil e configuração administrativa não são serializados para o modelo. Não há aliases estáveis de participantes. As referências necessárias são relativas à avaliação: «observador», «fonte em análise» e «destinatário do registro em análise». A aplicação resolve essas relações antes da montagem e guarda os endereços separadamente. O modelo não retorna endereço ou identidade.

```text
Aplicação: visão autorizada + declaração tipada + vínculo externo da interação
    → representação sem identidade + declaração
    → cabeça: suporte | insuficiente | contradição
    → aplicação: recupera o vínculo externo e decide a ação segundo seu plano
```

`roteamento.jsonl` associa o índice da linha à referência de auditoria, ao contexto e ao vínculo real. **Nunca enviar esse arquivo ao modelo.** `pares.jsonl`, `contextos.jsonl`, `visoes-auditoria.jsonl`, `trajetorias.jsonl`, controles e relatórios também são materiais de auditoria e podem conter identidades. Um treinador deve consumir exclusivamente entradas anônimas, prefixo e supervisão; não fazer concatenação automática de arquivos do diretório.

Trocar IDs mantendo as mesmas relações e evidências mantém o texto para o modelo. Trocar implementação pode mudar evidências e posições observáveis; o contexto acompanha essas mudanças, sem inferir personalidade pelo endereço. Memórias não passam de uma partida para outra.

## Conhecimento e completude

A coleta usa a visão integral autorizada, com fatos sobre ambiente/missão, sensores acessíveis, todos os relatos recebidos e respostas enviadas, revelações privadas, posições/suposições e histórico público. Não seleciona apenas evidências da pergunta avaliada. Fatos estáticos, atuais e históricos têm estatuto distinto. Relatos não se tornam confirmações por confiança ou repetição.

O corpo textual depende do snapshot e do enquadramento de relações da interação; não depende do rótulo, nem da resposta factual proposta. Ao mudar fonte/destinatário, muda o enquadramento relacional necessário. Informações de identidade são excluídas expressamente por contrato, não como corte para economizar tokens. Campos públicos sem regra de representação e hipóteses livres que contenham IDs conhecidos são rejeitados.

Sem endereços, algumas relações arbitrárias entre terceiros podem ficar ambíguas. Este piloto valida fatos de catálogo, Q10/Q11, reserva auxiliar, registros exatos de fala e objetivos declarados. **Não certifica resolução de qualquer referência em linguagem livre.** Perguntas que exigem prever qual pessoa será nomeada confiável em Q19 não são alvos suportados; o registro mantém apenas que uma pessoa foi indicada. Uma futura ampliação precisa validar que a representação preserva as distinções necessárias antes de admitir o exemplo. A geração bloqueia colisões de entrada anônima com rótulos diferentes.

O adaptador conhece a memória explícita da visão e dos registros deste piloto. Implementações com memória adicional relevante precisam de adaptador semântico próprio; ele não foi integrado. Não há leitura automática de estados internos arbitrários. A proteção textual não é certificação de anonimato estatístico: conteúdos e comportamentos continuam podendo informar sobre a situação. A garantia executada cobre remoção de campos identificadores e invariância à renomeação nos casos suportados.

## Corpus e validação

São 600 pares únicos: 200 por classe; 565 derivados de snapshots de 18 episódios executados e 35 contrastes lógicos hipotéticos explicitamente identificados. As trajetórias de coleta usam planos variados como instrumentos para produzir contextos, nunca como rótulos de ação. Todos os episódios terminaram por esgotamento; esta entrega não acrescenta cobertura executada de chegada, retorno ou eleição.

Os contrastes incluem reserva igual, abaixo e acima da distância; distância 13/14/15 contra «mais de 14»; reserva fracionária; somente uma das medidas; premissas ricas mas irrelevantes; fala versus fato; relatos conflitantes; informações antigas após avanços ou bônus. `AUX_RESERVA_MINIMA` é exercício lógico auxiliar, não Q## da engine. Regras necessárias, inclusive reserva ≥ distância, estão explícitas no prefixo. Exclusividade se aplica a valores exatos dos atributos suportados, não a qualquer pergunta aberta.

Passaram 30 testes semânticos, 12 controles de interesses/natureza/renomeação e as verificações de contexto descritas em `CONTRATO_CONTEXTO.md`. Os controles demonstram propriedades do adaptador e dos rótulos; não demonstram invariância de uma cabeça treinada. Não houve treinamento, execução dos pesos, criação de splits ou integração com os agentes. Antes de treinar, revisar os pares, ampliar linguagem e diversidade, e manter episódios/famílias correlacionadas na mesma partição. Generalização para estratégias diferentes é objetivo de avaliação futura, não resultado comprovado deste piloto.

A fonte do simulador e o piloto v01 não foram alterados. Ferramentas desta entrega são isoladas em `ferramentas/`.

## Reprodução

Executar na raiz do simulador, com diretório de saída novo:

```sh
python3 -B datasets/piloto-v02/ferramentas/gerar_piloto.py --project . --output /private/tmp/missao-v02-reproducao
python3 -B datasets/piloto-v02/ferramentas/testar_piloto.py --folder /private/tmp/missao-v02-reproducao
/Users/alexandre/crivo/.venv/bin/python -B datasets/piloto-v02/ferramentas/contexto.py --project . --folder /private/tmp/missao-v02-reproducao --model-directory /Users/alexandre/crivo/assets/phi4 --runtime-source /Users/alexandre/crivo/crivo_backend.py
```

Os dois primeiros comandos usam biblioteca padrão. A medição usa o tokenizer local existente, sem carregar pesos ou instalar dependências. `EXEMPLOS.md` mostra entradas anônimas completas com classes somente para revisão.
