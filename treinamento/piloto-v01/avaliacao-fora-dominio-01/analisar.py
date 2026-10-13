from pathlib import Path
import json, math, hashlib
B=Path(__file__).parent
report=json.loads((B/'resultado.json').read_text())
supervision=[json.loads(l) for l in (B/'supervisao.jsonl').read_text().splitlines()]
inputs=[json.loads(l) for l in (B/'inputs.jsonl').read_text().splitlines()]
results=[json.loads(l) for l in (B/'previsoes.jsonl').read_text().splitlines()]
for name,h in report['data_sha256'].items():
 assert hashlib.sha256((B/name).read_bytes()).hexdigest()==h
assert all(s['expected']==r['expected'] and s['index']==r['index'] for s,r in zip(supervision,results))
m=report['metrics'];labels=m['labels']
assert len(results)==30 and all(r['index']==i for i,r in enumerate(results))
assert sum(sum(row) for row in m['confusion_matrix_true_rows_predicted_columns'])==30
errors=[r for r in results if not r['correct']]
paired=report['paired_variants']
uniform={'accuracy':1/3,'macro_f1':1/6,'nll':math.log(3),'tie_rule':'argmax chooses suporte; does not randomly sample a class'}
report['uniform_baseline']=uniform
report['errors']=[{'index':r['index'],'case_id':r['case_id'],'family':r['family'],'expected':r['expected'],'predicted':r['output']['classification'],'hypothesis':inputs[r['index']]['hypothesis'],'rationale':supervision[r['index']]['rationale'],'audit_probability_of_predicted_class':r['audit_probabilities'][r['output']['classification']]} for r in errors]
(B/'resultado.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
fmt=lambda x:f'{x:.4f}'.replace('.',',')
lines=['# Inferência fora do domínio — cabeça NLI da Missão Espacial','',
 f'Executamos **30 forwards reais do Phi-4** em **8 famílias de casos**, com 10 alvos de cada classe. A cabeça acertou **{30-len(errors)}/30 ({100*m["accuracy"]:.1f}%)**. Macro F1: **{fmt(m["macro_f1"])}**.',
 '', 'Neste ensaio, os 20 casos de suporte/contradição foram corretos. A cabeça reconheceu apenas 3/10 insuficientes: 4 viraram suporte e 3, contradição. Assim, o principal limite observado foi resolver hipóteses sem evidência suficiente.', '', '## Contrato e método','',
 '- Entrada do modelo: somente `premise` e `hypothesis`, ambas strings. O prefixo NLI original e o chat template foram preservados.',
 '- Saída pública: somente a chave `classification`, com um dos rótulos `suporte`, `insuficiente` ou `contradição`. As probabilidades em `previsoes.jsonl` pertencem somente à auditoria da avaliação.',
 '- Cabeça, normalização e temperatura originais. Nenhum ajuste de pesos ou calibração durante o ensaio. A cabeça de outro domínio não foi carregada.',
 '- Alvos e justificativas foram salvos e tiveram seus hashes calculados antes de carregar o modelo. Não foram fornecidos como entrada.',
 '- Premissas ricas, fonte da informação explícita, instante definido quando relevante, regras numéricas e exclusividade fornecidas. Nenhuma identidade de agente entra nas premissas.',
 f'- Maior entrada: {report["maximum_tokens"]} tokens, sem truncamento, na janela de 16.384. Dispositivo executado: {report["body_identity"]["device"]}.',
 '- Esta avaliação testa a cabeça de três classes. A cabeça de desfechos mantém um contrato específico de missão, contexto e planos, e não foi chamada com desfechos genéricos incompatíveis.',
 '', '## Métricas','', '| Método | Acurácia | Macro F1 | NLL interna |','|---|---:|---:|---:|',
 f'| Cabeça treinada, fora do domínio | {100*m["accuracy"]:.1f}% | {fmt(m["macro_f1"])} | {fmt(m["nll_audit_only"])} |',
 f'| Distribuição uniforme | 33,3% | {fmt(1/6)} | {fmt(math.log(3))} |',
 '', 'Acurácia conta rótulos corretos. Macro F1 dá o mesmo peso às classes. NLL usa a probabilidade interna do alvo e revela erros confiantes, com piso numérico 1e-12. A probabilidade calibrada no domínio de treino não tem calibração demonstrada neste novo domínio. A referência uniforme desempata pelo primeiro rótulo, sem sorteio.',
 '', 'No teste original, a cabeça acertou 83/90 (92,2%). Os dois corpora diferem em composição e tamanho; essa comparação é descritiva, sem atribuir causalmente a diferença apenas ao domínio.',
 '', '## Matriz de confusão','', 'Linhas: alvo. Colunas: previsão.', '', '| Alvo / previsão | suporte | insuficiente | contradição |','|---|---:|---:|---:|']
for label,row in zip(labels,m['confusion_matrix_true_rows_predicted_columns']):lines.append('| '+label+' | '+' | '.join(map(str,row))+' |')
lines+=['','| Classe | Precisão | Revocação | F1 |','|---|---:|---:|---:|']
for p in m['per_class']:lines.append(f'| {p["label"]} | {fmt(p["precision"])} | {fmt(p["recall"])} | {fmt(p["f1"])} |')
lines+=['','## Coesão e famílias','', '| Família | Acertos / casos |','|---|---:|']
for f,v in m['by_family'].items():lines.append(f'| {f} | {v["correct"]}/{v["rows"]} |')
lines+=['',f'As 24 entradas de base tiveram {100*m["base_cases_accuracy"]:.1f}% de acerto. As seis variantes preservam o significado, parafraseiam a hipótese e acrescentam um fato irrelevante. {sum(p["same_classification"] for p in paired)}/6 pares mantiveram a classe; {sum(p["both_correct"] for p in paired)}/6 tiveram ambas as previsões corretas. Consistência sozinha não significa correção. As variantes não são exemplos independentes.',
 '', '## Erros observados','']
if errors:
 for er in report['errors']:
  lines += [f'### {er["case_id"]}: {er["family"]}', '', f'**Hipótese:** {er["hypothesis"]}', '', f'**Esperado:** {er["expected"]}. **Previsto:** {er["predicted"]}. Probabilidade interna da classe prevista: {100*er["audit_probability_of_predicted_class"]:.2f}%.', '', '**Motivo do alvo:** '+er['rationale'], '']
else:lines+=['Nenhum erro nestes casos selecionados. Isso não demonstra desempenho perfeito fora do domínio.','']
lines+=['## Limites e interpretação','',
 'O ensaio verifica saída contratual, inferência real e relações de evidência fora dos assuntos do treino. Ele não certifica generalização para qualquer contexto ou estratégia.',
 '', 'Os casos são uma amostra construída por conveniência, com alvos anotados pelo autor, sem revisão humana independente. Há oito famílias e seis variantes correlacionadas. Mudam assuntos e formulações textuais; o ensaio não isola o efeito de cada mudança. O prefixo constante ainda contém regras específicas da Missão Espacial, porque removê-lo alteraria o contrato usado no treinamento.',
 '', 'Os erros mostram divergência em relação à evidência fornecida. Não identificam, sozinhos, a causa dentro do modelo. Nenhum alvo foi corrigido para acomodar a previsão. Novos ensaios precisam ter casos e critérios definidos antes da execução.',
 '', '## Arquivos e reprodução','',
 '`inputs.jsonl` contém apenas as entradas. `supervisao.jsonl` contém alvos, famílias, variantes e justificativas externas. `CASOS.md` mostra as premissas completas. `protocolo.json` registra a definição anterior ao ensaio e hashes. `previsoes.jsonl` e `resultado.json` guardam saídas e métricas. `features/` contém representações reais para conferir a projeção sem novo forward. `validacao-numerica.json` confere os cálculos da cabeça.',
 '', 'Para repetir, copie `inputs.jsonl`, `supervisao.jsonl` e `protocolo.json` para uma pasta nova. Execute o carregador com o pacote e os pesos públicos correspondentes:',
 '', '```sh','python executar.py --project /caminho/missao-espacial --model-directory /caminho/pesos-phi4 --device auto --data /caminho/pasta-nova','```',
 '', 'O script recusa sobrescrever previsões anteriores. Ele não baixa uma cabeça de outro domínio nem treina pesos. A seleção `auto` admite CPU, CUDA ou MPS conforme o ambiente; esta execução foi somente local em MPS.',
 '', f'Integridade da cabeça antes/depois: `{report["head_sha256"]}`. Tempo total da execução: {report["total_elapsed_seconds"]:.1f} s.', '']
(B/'RELATORIO.md').write_text('\n'.join(lines))
cases=['# Casos de inferência fora do domínio','', 'Rótulos e justificativas definidos antes da inferência. IDs abaixo são índices externos da avaliação, não identidades ou features do modelo. O prefixo original é acrescentado pelo carregador e está em `prefixo-utilizado.txt`.','']
for x,s,r in zip(inputs,supervision,results):
 cases += [f'## {s["case_id"]}: {s["family"]} ({s["variant"]})','', '### Premissa','', '```text',x['premise'],'```','', '### Hipótese','',x['hypothesis'],'',f'**Alvo:** {s["expected"]}. **Justificativa:** {s["rationale"]}','',f'**Previsão real:** {r["output"]["classification"]}.','']
(B/'CASOS.md').write_text('\n'.join(cases))
print(json.dumps({'accuracy':m['accuracy'],'macro_f1':m['macro_f1'],'errors':len(errors),'paired_consistent':sum(p['same_classification'] for p in paired)},ensure_ascii=False))
