# Datasets e versões

A fonte atual aplica as determinações de encerramento: direção final ao planeta registra entrega observável; direção final à estação espacial registra retorno e sobrevivência humana.

- `piloto-v01` e `piloto-v02` são registros das versões em que foram gerados. Seus hashes, relatórios e notas sobre a fonte referem-se àquelas versões; não representam o comportamento atual de resultados finais. Foram preservados.
- `piloto-v03` usa a fonte corrigida e referências temporárias para distinguir participantes sem expor IDs persistentes. Cobre todas as alternativas de fala das 21 perguntas em configurações de 5 e 10 participantes. Essa cobertura não prova cobertura de todas as inferências sobre conteúdo ou todas as estratégias.
- O experimento de desfechos da v03 usa resultados da engine para estimar frequências sob um amostrador declarado. Não é um modelo treinado nem fornece ainda probabilidades de colaboração ou traição.

Entrada do modelo, supervisão e arquivos de auditoria/roteamento são separados. Nunca fornecer todos os arquivos deste diretório como features. Os pilotos ainda não possuem splits de treinamento/calibração/avaliação.

- `piloto-v04`: massa de previsão condicionada ao contexto e plano, com contrato executável, 216 entradas, 6.912 continuações e partições de treino/calibração/teste. Preserva a classificação de evidências da v03 como tarefa separada. O backend probabilístico ainda precisa ser treinado e integrado; consultar o escopo e as validações em `piloto-v04/README.md` e `piloto-v04/CONTRATO.md`.
