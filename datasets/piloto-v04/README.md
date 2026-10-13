# Piloto v04 — contexto, plano e consequências

Esta massa complementa a classificação de evidências da v03. O novo alvo é avaliar consequências de planos candidatos; a cabeça não aprende a escolher uma estratégia universal. A engine fornece os resultados executados, conforme as determinações do jogo.

São **216 entradas de previsão**, 72 grupos de comparação, 2304 mundos compatíveis e **6912 continuações completas**. Cada plano tem 32 repetições. Os 12 casos de conhecimento/histórico são agrupados em 6 famílias estruturais: variantes correlacionadas permanecem juntas. Partições: 144 treino, 36 calibração e 36 teste.

Em 156 repetições pareadas, os programas tiveram desfechos diferentes. Isso verifica que a intervenção executada pode influenciar o resultado; não demonstra que uma cabeça treinada generaliza.

## Contrato e arquivos

- `CONTRATO.md` e `contrato.json`: entrada/saída, privacidade, planos executáveis, supervisão, partições e avaliação.
- `inputs.jsonl`: somente contexto, objetivo, plano candidato, alvo de previsão e hipóteses do amostrador. Sem ID de linha ou participante real.
- `supervisao.jsonl`: índice externo da linha, contagens, probabilidades empíricas e intervalos. Nunca concatenar à entrada.
- `particoes.jsonl`: índices e grupos destinados a treino/calibração/teste. Nunca usar como features.
- `system-modelo.txt`: regras constantes e contrato da saída probabilística.
- `auditoria/`: raízes/checkpoints, correspondências reais, mundos aceitos, comparações e decisões/crenças das continuações. Contém segredos; não enviar ao modelo.
- `validacao.json`, `contexto-validacao.json`, `manifesto.json` e `SHA256SUMS.json`: verificações, identidades e proveniência.
- `ferramentas/`: gerador, contratos, simulador de planos, testes, validação por replay e avaliador de previsões reais.

## Validação executada

Passaram **24 testes** de planos e contratos. Foram reconstruídas e conferidas as 2304 visões de mundos aceitos e reproduzidas pela engine todas as 6912 continuações registradas, incluindo decisões e mudanças de crenças. Houve 216 verificações de representação sob renomeação de IDs. Nenhuma entrada canônica apareceu em partições diferentes. RNG futuro varia entre repetições e permanece compartilhado entre candidatos da mesma repetição.

O tokenizer local real admitiu todas as 216 entradas sem recortes: máximo 4051 tokens numa janela de 16384. Passaram limite inclusivo, um token acima bloqueado e reabertura da identidade persistida do contrato. Pesos não foram executados.

## Reprodução

Na raiz do simulador, com diretório novo:

```sh
python3 -B datasets/piloto-v04/ferramentas/testar_planos.py
python3 -B datasets/piloto-v04/ferramentas/gerar_planos.py --project . --output /private/tmp/missao-v04-reproducao --trials 32 --families 12
python3 -B datasets/piloto-v04/ferramentas/validar_planos.py --project . --folder /private/tmp/missao-v04-reproducao
/Users/alexandre/crivo/.venv/bin/python -B datasets/piloto-v04/ferramentas/contrato.py --folder /private/tmp/missao-v04-reproducao --model-directory /Users/alexandre/crivo/assets/phi4
```

Os dois logs extensos de auditoria são distribuídos em `.jsonl.gz`, sem perder conteúdo. O validador aceita JSONL ou gzip. `compactar_auditoria.py` gera arquivos compactados determinísticos e verifica igualdade do conteúdo, preservando os originais.

Geração/replay/testes usam biblioteca padrão; medição usa o tokenizer já instalado no ambiente do Crivo. O gerador não altera `src/`, configurações ou pilotos anteriores. `manifesto.json` fica marcado incompleto durante a construção; saídas parciais não são massa aprovada. Não sobrescrever entregas.

Para avaliar uma cabeça treinada, salvar previsões com índice externo e o objeto `probabilities`, para todas as linhas de calibração e teste:

```sh
python3 -B datasets/piloto-v04/ferramentas/avaliar_probabilidades.py --folder datasets/piloto-v04 --predictions /caminho/previsoes.jsonl --output /private/tmp/avaliacao-v04.json --cost-fp 1 --cost-fn 1
```

Os custos são argumentos da avaliação/implementação, não preferências impostas ao modelo. A ferramenta rejeita linhas de treino, duplicatas, linhas ausentes, probabilidades inválidas e grupos incompletos.

## Escopo e limites

O primeiro piloto cobre observador humano ativo na iniciativa, perfil e memória adicional vazios, tripulações de 5/10, raízes nas rodadas 1/3/5 e três programas específicos. O corpus não cobre todas as perguntas como inferência sobre conteúdo, todas as táticas, fases, perfis ou implementações. Dados classificatórios continuam em `../piloto-v03`; sua cobertura de alternativas de fala não significa cobertura total de inferências factuais.

A proposta filtrada de mundos não é um posterior probabilístico completo. As estimativas dependem do amostrador informado. Para ampliar o escopo, adaptar a memória/restrições e o compilador e gerar novos planos/contextos e distribuições de comportamento. Nenhum programa é declarado ótimo.

**Não houve treinamento, integração do backend probabilístico, calibração de modelo ou ajuste empírico de limiares.** Não há relatório de qualidade da cabeça. Há massa e ferramentas verificadas para iniciar esse treinamento no escopo declarado. Fonte do simulador e versões anteriores foram preservadas nesta etapa.
