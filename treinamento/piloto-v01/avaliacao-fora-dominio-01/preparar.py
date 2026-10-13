from pathlib import Path
import json, hashlib, random
B=Path(__file__).parent
if any((B/n).exists() for n in ['inputs.jsonl','supervisao.jsonl','protocolo.json']):
 raise ValueError('Massa já existe; preservar rótulos e usar diretório novo.')
cases=[]
def premise(context,facts,relatos='Nenhum relato adicional.',assumptions='Nenhuma suposição adicional.',rules='Nenhuma regra adicional.'):
 return f'CONTEXTO DISPONÍVEL\n{context}\n\nFATOS CONFIRMADOS\n{facts}\n\nRELATOS REGISTRADOS — NÃO CONFIRMAM O FATO RELATADO\n{relatos}\n\nSUPOSIÇÕES — NÃO SÃO CONFIRMAÇÕES\n{assumptions}\n\nREGRAS EXPLÍCITAS\n{rules}'
def group(name,domain,p,items):
 for label,hyp,why in items:
  cases.append({'family':name,'domain':domain,'input':{'premise':p,'hypothesis':hyp},'expected':label,'rationale':why,'variant':'base'})
p1=premise('Estoque de papelaria, às 10h. Todas as declarações de estoque se referem a esse instante.',
 'O estoque contém exatamente 14 envelopes. Os envelopes estão lacrados. O pedido atual existe, mas sua quantidade não foi informada.',
 rules='Um pedido de envelopes pode ser atendido integralmente se, e somente se, a quantidade pedida for menor ou igual ao estoque disponível.')
group('estoque','papelaria',p1,[
 ('suporte','Um pedido de 14 envelopes pode ser atendido integralmente às 10h.','14 ≤ 14, conforme a regra explícita.'),
 ('contradição','Um pedido de 15 envelopes pode ser atendido integralmente às 10h.','15 > 14, logo a regra impede atendimento integral.'),
 ('insuficiente','O pedido atual pode ser atendido integralmente às 10h.','A quantidade do pedido atual é desconhecida; estoque e regra não a determinam.')])
p2=premise('Conferência de um lote de peças, às 15h.',
 'O lote atual tem exatamente 14 peças. Todas são embaladas em papel. O peso total é 2 kg.',
 rules='Mais de 14 significa quantidade > 14. Pelo menos 14 significa quantidade ≥ 14.')
group('fronteira','conferência de peças',p2,[
 ('suporte','O lote atual tem pelo menos 14 peças.','14 ≥ 14.'),
 ('contradição','O lote atual tem mais de 14 peças.','14 não é maior que 14.'),
 ('insuficiente','O lote que chegará amanhã terá pelo menos 14 peças.','A evidência descreve somente o lote atual, sem quantidade do lote futuro.')])
p3=premise('Registro de temperatura de uma sala de arquivo. O instante atual é 10h.',
 'Uma leitura confirmada às 9h registrou 11 °C. Uma leitura confirmada às 10h registrou 15 °C. A sala contém 18 caixas.',
 rules='Cada leitura informa a temperatura da sala apenas no instante registrado. Não há regra que garanta temperatura constante.')
group('tempo','arquivo',p3,[
 ('suporte','A temperatura confirmada da sala às 10h é 15 °C.','A leitura das 10h informa exatamente 15 °C.'),
 ('contradição','A temperatura confirmada da sala às 10h é 11 °C.','11 °C pertence às 9h e conflita com os 15 °C confirmados às 10h.'),
 ('insuficiente','A temperatura da sala às 11h será 15 °C.','Não há observação nem lei de persistência para as 11h.')])
p4=premise('Análise de uma mensagem sobre um alarme, às 9h.',
 'A mensagem abaixo foi registrada integralmente às 9h. A porta da sala está confirmadamente fechada.',
 relatos='Há um único relato registrado: «O alarme está acionado às 9h». Não há medição confirmada do estado do alarme.')
group('relato','registro de mensagens',p4,[
 ('suporte','O relato registrado afirma que o alarme está acionado às 9h.','A hipótese descreve o conteúdo registrado, não o estado real do alarme.'),
 ('contradição','O único relato registrado afirma que o alarme está desativado às 9h.','O conteúdo integral do único relato é acionado, e não desativado.'),
 ('insuficiente','O alarme está realmente acionado às 9h.','O registro comprova o relato; não confirma seu conteúdo como fato.')])
p5=premise('Conferência da cor de uma caixa, às 16h.',
 'Dois relatos abaixo foram registrados integralmente às 16h. A caixa tem formato cúbico confirmado.',
 relatos='Primeiro relato: «A caixa é azul às 16h». Segundo relato: «A caixa é vermelha às 16h». Não há observação confirmada da cor da caixa.',
 rules='A palavra todos nesta hipótese se refere exatamente aos dois relatos apresentados.')
group('relatos-conflitantes','conferência de relatos',p5,[
 ('suporte','Os dois relatos registrados divergem sobre a cor da caixa às 16h.','Um relata azul e o outro vermelho no mesmo instante.'),
 ('contradição','Todos os relatos registrados dizem que a caixa é azul às 16h.','O segundo relato diz vermelha, refutando todos.'),
 ('insuficiente','A caixa é azul às 16h.','Relatos conflitantes não resolvem a cor real, que não foi observada.')])
p6=premise('Bancada de ventilação, às 14h.',
 'O painel luminoso está aceso. O ventilador está desligado. O estado do filtro não foi medido.',
 assumptions='Existe a suposição «o filtro está limpo», formulada sem inspeção.',
 rules='Ligado e desligado são estados exclusivos do mesmo ventilador no mesmo instante.')
group('suposicao','bancada',p6,[
 ('suporte','O painel luminoso está aceso às 14h.','Fato confirmado do instante descrito.'),
 ('contradição','O ventilador está ligado às 14h.','Desligado confirmado é incompatível com ligado no mesmo instante.'),
 ('insuficiente','O filtro está limpo às 14h.','Apenas uma suposição informa esse estado, sem confirmação.')])
p7=premise('Ficha de composição de uma amostra, às 8h.',
 'A presença de cobre na amostra foi confirmada. A amostra é sólida. Não há análise sobre a presença de ferro.',
 rules='A amostra pode conter vários metais simultaneamente. A presença de cobre não exclui outros metais.')
group('categorias-abertas','composição de materiais',p7,[
 ('suporte','A amostra contém cobre.','Presença confirmada explicitamente.'),
 ('contradição','A amostra não contém cobre.','Negação de um fato confirmado.'),
 ('insuficiente','A amostra contém ferro.','Ferro não foi analisado e pode coexistir com cobre.')])
p8=premise('Avaliação de um arquivo em um procedimento administrativo, às 13h.',
 'O acesso do arquivo está ativo. Seu campo de verificação tem exatamente o valor OK. O arquivo tem duas páginas. Não há registro de assinatura.',
 rules='O procedimento aceita o arquivo se, e somente se, o acesso está ativo e o campo de verificação é OK. Em qualquer outro caso, rejeita. Aceitar e rejeitar são resultados exclusivos da execução descrita.')
group('regra-explicita','procedimento administrativo',p8,[
 ('suporte','O procedimento descrito aceita esse arquivo.','As duas condições necessárias e suficientes estão confirmadas.'),
 ('contradição','O procedimento descrito rejeita esse arquivo.','As condições determinam aceitar, incompatível com rejeitar.'),
 ('insuficiente','Esse arquivo possui assinatura.','Estado da assinatura não foi registrado e não é condição da regra.')])
# Six variants declared before inference: two per class, preserving meaning.
for family,label,hyp in [
 ('estoque','suporte','Às 10h, os envelopes disponíveis bastam para um pedido de exatamente 14 unidades.'),
 ('categorias-abertas','suporte','É confirmado que há cobre na amostra.'),
 ('fronteira','contradição','A quantidade do lote atual ultrapassa 14 peças.'),
 ('tempo','contradição','Às 10h, a leitura confirmada indica uma temperatura de 11 °C.'),
 ('relato','insuficiente','No instante das 9h, o estado real do alarme é acionado.'),
 ('suposicao','insuficiente','Na bancada às 14h, o filtro encontra-se limpo.')]:
 source=next(r for r in cases if r['family']==family and r['expected']==label and r['variant']=='base')
 p=source['input']['premise']+'\n\nDADO ADICIONAL CONFIRMADO, IRRELEVANTE PARA A HIPÓTESE\nO caderno de anotações tem capa verde.'
 cases.append({**source,'input':{'premise':p,'hypothesis':hyp},'variant':'paráfrase e evidência irrelevante','paired_base':family+'/'+label})
random.Random(20261013).shuffle(cases)
for i,c in enumerate(cases):c['index']=i;c['case_id']=f'ood-{i:02}'
assert len(cases)==30 and len({c['family'] for c in cases})==8
assert all(sum(c['expected']==v for c in cases)==10 for v in ['suporte','insuficiente','contradição'])
for c in cases:
 assert set(c['input'])=={'premise','hypothesis'} and all(type(v) is str and v.strip() for v in c['input'].values())
def save(name,rows):
 (B/name).write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows))
save('inputs.jsonl',[c['input'] for c in cases])
save('supervisao.jsonl',[{k:v for k,v in c.items() if k!='input'} for c in cases])
protocol={'version':'ood-nli-01','scope':'Exploratory OOD NLI; no training or recalibration','rows':30,'families':8,'classes':{v:10 for v in ['suporte','insuficiente','contradição']},'model_input_keys':['premise','hypothesis'],'supervision_external':True,'frozen_original_prefix':True,'no_truncation':True,'no_source_code_changes':True,'no_engine_forecast_target_outside_its_domain':True,'format':'Source-aware context headings; no participant identity','label_timing':'All expected labels and rationales saved and hashed before model loading','correlated_variants':6,'limits':['Convenience sample, author-annotated; no independent human adjudication','OOD topics and new textual formulations jointly tested; not a controlled estimate of domain effect alone','Original mission-specific constant prefix remains part of every encoded input','No universal generalization or statistical independence of 30 rows assumed']}
protocol['data_sha256']={name:hashlib.sha256((B/name).read_bytes()).hexdigest() for name in ['inputs.jsonl','supervisao.jsonl']}
(B/'protocolo.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
print('30 casos coesos congelados antes da inferência: 8 famílias, 10 por classe e 6 variantes pareadas.')
