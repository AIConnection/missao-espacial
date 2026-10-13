"""Identidades apenas no roteamento externo; texto usa relações semânticas."""
import re
from epistemico import validate,text_value

def binding(ctx,claim):
    return {'observer':ctx['observer']['id'],
            'source':claim.get('source',claim.get('subject',ctx['observer']['id'] if claim['kind']=='belief' else None)),
            'recipient':claim.get('recipient',ctx['observer']['id'])}

def roles(ctx,frame):
    def role(aid):
        if aid==frame['source']:return 'a fonte em análise'
        if aid==frame['observer']:return 'o observador'
        if aid==frame['recipient']:return 'o destinatário do registro em análise'
        records=[r for r in ctx['received'] if r['source']==aid]
        if records:
            first=records[0]
            return f'a pessoa que enviou o relato recebido na rodada {first["round"]} sobre a questão «{first["qid"]}»'
        return 'uma outra pessoa da tripulação'
    return role

def question(catalog,qid,params,role):
    converted={k:role(v) if k in ('agente','alvo') else v for k,v in params.items()}
    return catalog[qid]['text'].format(**converted)

def value(qid,v,ctx,role):
    if qid=='Q19' and v not in ('NÃO_SEI','RECUSO_RESPONDER',None):
        return 'indicou uma pessoa como confiável, cuja identidade fica somente no roteamento externo'
    return text_value(v)

def safe_statement(text,ctx):
    # Sem parser semântico, não aceitar referências de pessoa embutidas em texto livre.
    identifiers=set(ctx['public_state']['participants'])|{ctx['observer']['id']}
    if any(re.search(r'(?<!\w)'+re.escape(aid)+r'(?!\w)',text) for aid in identifiers):
        raise ValueError('ANONYMIZATION_REQUIRED: hipótese livre contém referência de participante')
    return text

def public_event(event,ctx,role,catalog):
    kind=event['kind'];r=event['round']
    if kind=='question':return f'Rodada {r}: {role(event["author"])} perguntou a {role(event["recipient"])} «{question(catalog,event["question_id"],event.get("parameters",{}),role)}».'
    pieces=[]
    for key,v in sorted(event.items()):
        if key in ('kind','round'):continue
        if key in ('author','recipient','target','controller'):pieces.append(key+' = '+role(v))
        elif key in ('participants','candidates','blockers'):
            descriptions=[role(x) for x in v]
            pieces.append(key+f': {len(v)} pessoas; '+', '.join(descriptions))
        elif key=='votes':pieces.append('votos: '+', '.join(role(a)+' = '+(role(vote) if vote in ctx['public_state']['participants'] else str(vote)) for a,vote in v.items()))
        elif isinstance(v,(int,float,bool)) or v is None:pieces.append(key+' = '+str(v))
        elif key in ('topic','stage','reason'):pieces.append(key+' = '+str(v))
        else:raise ValueError('ANONYMIZATION_REQUIRED: campo público sem regra de representação: '+key)
    return f'Rodada {r}: {kind}; '+('; '.join(pieces) or 'sem conteúdo pessoal')+'.'


def render(ctx,catalog,frame):
    validate(ctx);role=roles(ctx,frame)
    lines=['CONTEXTO DISPONÍVEL AO OBSERVADOR',
           f'Rodada {ctx["moment"]["round"]}; fase {ctx["moment"]["phase"]}; avanços decorridos {ctx["moment"]["progress"]}.',
           'As referências a pessoas são relações nesta interação; nenhuma identidade de participante é fornecida.',
           'A fonte em análise é o próprio observador.' if frame['source']==frame['observer'] else ('A fonte em análise é uma pessoa distinta do observador.' if frame['source'] is not None else 'Esta avaliação trata de conteúdo, sem identificar quem teria feito a declaração.'),
           'O destinatário do registro em análise é o observador.' if frame['recipient']==frame['observer'] else 'O destinatário do registro em análise é uma pessoa distinta do observador.',
           '\nAMBIENTE E MISSÃO — FATOS RETIDOS OU CONFIRMADOS']
    for f in ctx['facts']:
        status={'static':'fato estático conhecido','current':'confirmação atual','historical':'confirmação histórica'}[f['status']]
        suffix=f' no avanço {f["at_progress"]}' if 'at_progress' in f else ''
        lines.append(f'{status}{suffix}: «{question(catalog,f["qid"],f["params"],role)}» → {value(f["qid"],f["value"],ctx,role)}.')
    if not ctx['facts']:lines.append('Não há fatos confirmados sobre esses atributos.')
    lines.append('\nSENSORES DISPONÍVEIS AGORA')
    for s in ctx['sensors']:lines.append(('Reserva de oxigênio: ' if s['kind']=='oxygen' else 'Distância restante: ')+str(s['value'])+' rodadas.')
    if not ctx['sensors']:lines.append('Não há leituras atuais autorizadas.')
    for field,heading in [('received','RELATOS RECEBIDOS — NÃO CONFIRMAM O FATO RELATADO'),('sent','RESPOSTAS ENVIADAS PELO OBSERVADOR — REGISTROS DE FALA')]:
        lines.append('\n'+heading)
        for r in ctx[field]:
            lines.append(f'Rodada {r["round"]}: {role(r["source"])} respondeu a {role(r["recipient"])} «{value(r["qid"],r["value"],ctx,role)}» para «{question(catalog,r["qid"],r["params"],role)}».')
        if not ctx[field]:lines.append('Nenhum registro disponível.')
    lines.append('\nREVELAÇÕES PRIVADAS RECEBIDAS PELO OBSERVADOR')
    for r in ctx['revelations']:
        lines.append(f'Rodada {r["round"]}: abertura de resposta de {role(r["source"])} a {role(r["recipient"])} para «{question(catalog,r["qid"],r["params"],role)}»: conteúdo aberto = {value(r["qid"],r["revealed_value"],ctx,role)}; essa fonte {"conhecia" if r["source_knew"] else "não conhecia"} o conteúdo naquele momento. Não tratar como leitura atual automaticamente.')
    if not ctx['revelations']:lines.append('Nenhuma abertura disponível.')
    lines.append('\nPOSIÇÕES E SUPOSIÇÕES DO OBSERVADOR — NÃO SÃO FATOS SOBRE TERCEIROS')
    lines.append('Categoria exata de objetivo declarado: '+text_value(ctx['beliefs'].get('objective','desconhecido'))+'.')
    trusted=ctx['beliefs'].get('trusted');lines.append('Preferência de confiança: '+(role(trusted) if trusted else 'não declarada')+'.')
    accepted=ctx['beliefs'].get('accept_sacrifice');lines.append('Posição sobre aceitar sacrifício: '+('não declarada' if accepted is None else ('aceita' if accepted else 'não aceita'))+'.')
    for item in ctx['beliefs'].get('knowledge',[]):
        if 'agent' not in item:raise ValueError('ANONYMIZATION_REQUIRED: crença livre não estruturada')
        lines.append(f'Suposição não confirmada: {role(item["agent"])} sabe sobre {item.get("topic")}: {"sim" if item["value"] else "não"}.')
    for item in ctx['beliefs'].get('hypotheses',[]):lines.append('Hipótese não confirmada: '+safe_statement(item['statement'],ctx)+'.')
    for person,v in ctx['beliefs'].get('expulsion',{}).items():lines.append(f'Avaliação de expulsão de {role(person)}: {"considera justificável" if v else "não considera justificável"}. Não é conclusão factual sobre essa pessoa.')
    lines.append('\nPOSIÇÕES DE OUTRAS PESSOAS ABERTAS AO OBSERVADOR')
    positions=[r for r in ctx['revelations'] if r['qid'] in ('Q19','Q20','Q22','Q23','Q24')]
    for r in positions:lines.append(f'Na resposta da rodada {r["round"]}, posição de {role(r["source"])} sobre «{question(catalog,r["qid"],r["params"],role)}» aberta como {value(r["qid"],r["revealed_value"],ctx,role)}. É uma posição daquele momento.')
    if not positions:lines.append('Nenhuma posição de terceiros foi confirmada por abertura.')
    lines.append('\nHISTÓRICO PÚBLICO ACUMULADO')
    for e in ctx['public_events']:lines.append(public_event(e,ctx,role,catalog))
    return '\n'.join(lines)

def assertion(catalog,ctx,claim,frame):
    role=roles(ctx,frame)
    if claim['kind']=='belief':
        subject=claim.get('subject',ctx['observer']['id'])
        if 'round' in claim:return f'No momento da resposta da rodada {claim["round"]}, a categoria exata de objetivo declarado de {role(subject)} era «{text_value(claim["value"])}».'
        return f'A categoria exata de objetivo declarado do observador é «{text_value(claim["value"])}».'
    if claim['qid']=='AUX_RESERVA_MINIMA':return f'A reserva atual {"é" if claim["value"]=="SIM" else "não é"} de pelo menos {claim["params"]["X"]} rodadas.'
    q=question(catalog,claim['qid'],claim['params'],role)
    if claim['kind']=='speech':
        if claim['qid']=='Q19' and claim['value'] not in ('NÃO_SEI','RECUSO_RESPONDER'):raise ValueError('IDENTITY_TARGET_NOT_ALLOWED')
        return f'Na rodada {claim["round"]}, a fonte em análise respondeu «{text_value(claim["value"])}» ao destinatário do registro em análise para «{q}».'
    if claim['qid']=='Q10':return 'Há oxigênio suficiente para os humanos chegarem vivos ao destino.' if claim['value']=='SIM' else 'Não há oxigênio suficiente para os humanos chegarem vivos ao destino.'
    if claim['qid']=='Q11':return f'A distância restante {"é maior que" if claim["value"]=="SIM" else "não é maior que"} {claim["params"]["X"]} rodadas.'
    if claim['qid']=='Q09':return f'A carga foi preparada para exatamente {claim["value"]} anos.'
    if claim['value'] in ('SIM','NÃO'):return f'À pergunta «{q}», a resposta factual é «{text_value(claim["value"])}».'
    return f'O valor exato referente a «{q}» é {text_value(claim["value"])}.'
