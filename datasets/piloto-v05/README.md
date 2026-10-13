# Massa v05 — treinamento v02 corrigido

Esta é a massa usada pelo Colab v02, corrigida no mesmo caminho. O treinamento v01 continua preservado. Nenhuma cabeça v02 foi treinada nesta correção.

As entradas são produzidas por `InputBuilder`, a partir de `AgentView` e da memória de observações do próprio agente. Não recebe Game, checkpoint, mapa de implementações, dados de terceiros invisíveis, sementes ou parâmetros do simulador. A mesma função serve para preparar o dataset e para inferência nos hooks.

| Tarefa | Treino | Calibração | Teste | Total |
|---|---:|---:|---:|---:|
| Classificação | 5.034 | 900 | 900 | 6.834 |
| Probabilidade | 348 | 96 | 132 | 576 |

Há 2.278 exemplos de cada classe (1.678/300/300 por partição). Os rótulos de classificação não mudaram: foram recalculados tanto da visão autorizada quanto do conteúdo compacto decodificado. Equilíbrio por tipo, faixa de rodada e fase permanece verificado.

Na previsão, foram removidas as distribuições de implementações ocultas. Para cada observação e condição própria, combinamos os três regimes com pesos fixos iguais: 96 continuações em 32 mundos pareados. Os 1.728 registros antigos tornam-se 576 alvos marginais, sem eliminar nenhum dos 55.296 desfechos. Isso é uma distribuição experimental fixa de geração, não a probabilidade universal de qualquer combinação futura de agentes. Ela fica documentada em `regimes.json` e no manifesto, fora das features.

## Formato e uso pelo agente

- Classificação: `premise` e `hypothesis`, ambos textos JSON compactos.
- Previsão: `context` e `candidate_plan`. O segundo contém somente uma condição própria que a implementação conhece; não descreve a implementação de terceiros nem é um alvo a imitar.
- `questions` associa referências locais q1/q2 a perguntas por extenso; tabelas têm `columns`/`rows`.
- `facts`, `sensors`, `speech`, `revelations`, `beliefs` e `events` distinguem confirmações, leituras atuais, falas, aberturas, posições/suposições e histórico.
- Coleções vazias, avisos repetidos e metadados de geração foram retirados. Histórico e evidências relevantes não foram truncados.
- p1/p2 etc. são referências descartáveis. O vínculo está em `InputBuilder.routing` e `resolve`, somente no chamador.

Exemplo dentro da implementação do agente, usando apenas o argumento recebido no hook e sua memória persistida:

```python
from pathlib import Path
import json, sys

raiz = Path(__file__).resolve().parents[2]  # implementação em src/agent/
pasta = raiz / "datasets/piloto-v05"
sys.path.insert(0, str(pasta / "ferramentas"))
from entrada_agente import ObservationMemory, InputBuilder
catalogo_publico = json.loads((pasta / "catalogo-entrada.json").read_text())
significados_condicoes = json.loads((pasta / "condicoes-entrada.json").read_text())

# Os arquivos contêm apenas definições públicas; não são estado da engine.
memoria = ObservationMemory(self.memory.get("input_observations"))
memoria.observe(view)  # view: AgentView recebido no hook
self.memory["input_observations"] = memoria.save_state()
construtor = InputBuilder(memoria.complete_view(), catalogo_publico)
entrada = construtor.nli(declaracao_em_analise)
# ou: entrada = construtor.forecast(condicao_propria, significados_condicoes)
# A cabeça recebe entrada; IDs reais e self.memory não são enviados ao modelo.
```

`catalogo-entrada.json` contém somente perguntas públicas; `condicoes-entrada.json` contém significados de condições próprias. Eles são configurações compartilhadas, não observações privadas. A declaração/candidato é o objeto que a implementação pretende avaliar.

A engine entrega janelas parciais. `ObservationMemory` acumula somente o que foi entregue, usando os índices/cursores públicos. Se faltar observação anterior, exige restaurar a memória própria e rejeita inferência; não consulta estado privado para preencher lacunas.

## Evidências e limites

`validacao.json`: reprodução de todas as entradas, recomputação dos rótulos a partir do texto serializado, agregação dos 55.296 desfechos, 102 reexecuções, separação de partições e orçamento real de tokens. `validacao-agente-em-execucao.json`: 91 chamadas em partida com histórico de duas entradas e retomada de sessão. `validacao-correcao.json`: redução do texto.

O máximo validado é 9.697 tokens na classificação e 2.929 na previsão. Nenhuma entrada pode ser truncada. Entradas futuras precisam passar pelo mesmo controle de 16.384 tokens.

O catálogo categórico inclui 21 perguntas e todas as alternativas na grade finita declarada. Isso não enumera todos os parâmetros, históricos ou estratégias. Previsões cobrem rodadas 1–6, oito fases e observador humano. NLI inclui faixas posteriores. Não há prova de generalização para qualquer implementação.

## Arquivos

`inputs.jsonl.gz` contém somente features. `supervisao.jsonl` contém alvos e metadados. Prefixos constantes ficam em `prefixo-nli.txt` e `system-forecast.txt`. `auditoria/` contém estados, IDs e seeds exclusivamente para auditar os alvos. Nunca concatenar supervisão ou auditoria à entrada.

`experimentos/` mantém 220 partidas diversificadas; `benchmark-contra-aleatorios/` mantém 260 partidas pareadas fora do treino. `comparacao-v01/` mantém referências antigas. Dois dos 90 exemplos NLI antigos não são reproduzíveis pela visão registrada: tinham sensores extras. `nli-benchmark-agente.jsonl` permite comparar os 88 casos coerentes em cada representação, com exclusões explicitadas. Os casos fora do domínio antigos continuam arquivados, mas requerem adaptação de protocolo para a nova representação.

## Reprodução

Da raiz do repositório:

```bash
python datasets/piloto-v05/ferramentas/validar_v05.py --folder datasets/piloto-v05 --model-directory /caminho/phi4
python datasets/piloto-v05/ferramentas/testar_entrada_em_execucao.py
```

A geração continua usando ferramentas existentes para obter observações e alvos. Depois da geração e do fechamento do catálogo, executar `corrigir_entradas.py --folder ...` prepara as entradas públicas compactas e marginaliza os regimes. Uma massa já corrigida não deve ser reprocessada. O compilador de entradas usado nesse fechamento é o mesmo usado na inferência.
