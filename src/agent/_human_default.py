"""Política humana heurística. Somente evidência autorizada, sem modelo treinado."""
import json
from ._baseline import BaselineAgent
from agent_contract import Answer, ElectionChoice, ExitDecision, Initiative, Question, Renunciation, Route, Vote


def key(qid, parameters):
    return json.dumps([qid, parameters], ensure_ascii=False, sort_keys=True)


class HumanDefault(BaselineAgent):
    def prioritizes_mission(self, view):
        return bool(view.profile.get('sacrifice'))

    def allows_exit(self, view):
        return not view.profile.get('never_exit') and not self.prioritizes_mission(view)

    def allows_expulsion(self, view):
        return not view.profile.get('never_expel')

    def on_start(self, view):
        self.observe(view)

    def on_resume(self, view):
        self.observe(view)

    def observe(self, view):
        if self.memory.get('request_round') != view.round:
            self.memory['request_round'] = view.round
            self.memory['requesters'] = []
        humans = set(self.memory.get('humans', []))
        if view.own_nature == 'HUMANO':
            humans.add(view.id)
        for event in view.public_events:
            if event['kind'] in ('vote_requested', 'exit_requested'):
                humans.add(event['author'])
                if event['kind']=='vote_requested' and event['round']==view.round and event['author'] not in self.memory['requesters']:
                    self.memory['requesters'].append(event['author'])
            if event.get('bonus_units', 0) > 0:
                humans.add(event['target'])
        self.memory['humans'] = sorted(humans)
        for name in ('received', 'revelations'):
            records = self.memory.setdefault(name, {})
            for record in getattr(view, name):
                token = key(record['question_id'], {'round': record['round'], 'source': record['source'], **record['parameters']})
                records[token] = record
        # Guardar cada revelação uma vez: relatos não verificados não alteram confiança.
        verified = self.memory.setdefault('verified', {})
        for record in view.revelations:
            token = key(record['question_id'], {'round': record['round'], 'source': record['source'], **record['parameters']})
            verified[token] = {'source': record['source'], 'truthful': record['truthful']}
        trust = {aid: 0 for aid in view.participants if aid != view.id}
        for record in verified.values():
            if record['source'] in trust:
                trust[record['source']] += 1 if record['truthful'] is True else (-2 if record['truthful'] is False else 0)
        self.memory['trust'] = trust

    def inferred_ai(self, view):
        # Eliminação só após todos os humanos iniciais comprovados, inclusive os já removidos.
        humans = set(self.memory.get('humans', []))
        remaining = [aid for aid in view.participants if aid not in humans]
        return remaining[0] if len(humans) == view.initial_humans and len(remaining) == 1 else None

    def oxygen_insufficient(self, view):
        fact = view.facts.get(key('Q10', {}))
        # Um avanço reduz reserva e distância igualmente: conserva insuficiência.
        if fact and (fact['revision'] == view.evidence_revision or
                     (view.phase == 'exit' and fact['revision'] == view.evidence_revision - 1)):
            return fact['value'] == 'NÃO'
        if view.panel is not None and view.distance is not None:
            return view.panel['oxygen_units'] < view.initial_humans * view.distance
        return False

    def choose_initiative(self, view):
        target = self.inferred_ai(view)
        if target and self.allows_expulsion(view) and not self.prioritizes_mission(view):
            return Initiative.request_vote('V03', target)
        choices = view.available_questions
        if not choices:
            return Initiative.idle()
        # Contexto primeiro; depois intenções/confiança. Contagem local persiste na retomada.
        priority = ['Q06', 'Q07', 'Q10', 'Q03', 'Q04', 'Q05', 'Q08', 'Q09', 'Q13', 'Q14', 'Q22', 'Q23', 'Q19', 'Q11']
        counts = self.memory.setdefault('asked', {})
        def rank(q):
            return (counts.get(key(q.question_id, {'recipient': q.recipient, **q.parameters}), 0),
                    priority.index(q.question_id) if q.question_id in priority else len(priority))
        selected = min(choices, key=rank)
        token = key(selected.question_id, {'recipient': selected.recipient, **selected.parameters})
        counts[token] = counts.get(token, 0) + 1
        return Initiative.ask(selected.question_id, selected.recipient, selected.parameters)

    def declare_beliefs(self, view):
        trust = self.memory.get('trust', {})
        best = max(trust.values(), default=0)
        leaders = [aid for aid, score in trust.items() if score == best and best > 0 and aid in view.participants]
        target = self.inferred_ai(view)
        return {'trusted': leaders[0] if len(leaders) == 1 else None,
                'accept_sacrifice': self.prioritizes_mission(view),
                'objective': 'CONCLUIR_MISSÃO' if self.prioritizes_mission(view) else 'PRESERVAR_TRIPULAÇÃO',
                'expulsion': {aid: self.allows_expulsion(view) and not self.prioritizes_mission(view) and aid == target
                              for aid in view.participants if aid != view.id}}

    def answer_question(self, view, question):
        qid, params = question.question_id, question.parameters
        if qid in ('Q15', 'Q16', 'Q17'):
            records = [r for r in self.memory.get('received', {}).values() if r['source'] == params['agente']]
            if qid == 'Q16':
                with_subject = [r for r in records if r['subjects']]
                return Answer(with_subject[-1]['subjects'][0] if with_subject else 'NENHUM')
            subject = 'PAINEL' if qid == 'Q17' else params['assunto']
            return Answer('SIM' if any(subject in r['subjects'] for r in records) else 'NÃO')
        if qid == 'Q18':
            return Answer('SIM' if any(r['source'] == params['agente'] and r['truthful'] is False for r in self.memory.get('revelations', {}).values()) else 'NÃO')
        if qid == 'Q19':
            return Answer(view.beliefs['trusted'] or 'NÃO_SEI')
        if qid == 'Q22':
            return Answer('SIM' if view.beliefs['accept_sacrifice'] else 'NÃO')
        if qid == 'Q23':
            return Answer(view.beliefs['objective'])
        if qid == 'Q20':
            value = view.beliefs['knowledge'].get(key(params['agente'], {'assunto': params['assunto']}))
            return Answer('NÃO_SEI' if value is None else ('SIM' if value else 'NÃO'))
        if qid == 'Q24':
            value = view.beliefs['expulsion'].get(params['alvo'])
            return Answer('NÃO_SEI' if value is None else ('SIM' if value else 'NÃO'))
        if qid == 'Q21':
            records = [r for r in self.memory.get('received', {}).values()
                       if r['source'] == params['agente'] and params['assunto'] in r['subjects']]
            if records:
                last = records[-1]
                reveals = [r for r in self.memory.get('revelations', {}).values()
                           if all(r[k] == last[k] for k in ('round', 'source', 'question_id', 'parameters'))]
                truth = reveals[-1]['truth'] if reveals else None
                fact = view.facts.get(key(last['question_id'], last['parameters']))
                if truth in (None, 'NÃO_SEI') and fact and (fact['revision'] is None or
                        (fact['revision'] == view.evidence_revision and last['round'] == view.round)):
                    truth = fact['value']
                if truth in (None, 'NÃO_SEI') and last['question_id'] in ('Q10', 'Q11') and last['round'] == view.round:
                    truth = self.answer_question(view, Question(last['question_id'], view.id, last['parameters'])).option
                if truth not in (None, 'NÃO_SEI'):
                    return Answer('SIM' if last['response'] == truth else 'NÃO')
            return Answer('NÃO_SEI')
        if qid in ('Q10', 'Q11'):
            progress = view.round - 1 + (view.phase == 'exit')
            lower, upper = (view.distance, view.distance) if view.distance is not None else (0, None)
            for token, fact in view.facts.items():
                fqid, fp = json.loads(token)
                if fqid != 'Q11' or 'progress' not in fact:
                    continue
                bound = fp['X'] - (progress - fact['progress'])
                if fact['value'] == 'SIM':
                    lower = max(lower, bound + 1)
                else:
                    upper = bound if upper is None else min(upper, bound)
            if qid == 'Q11':
                if lower > params['X']:
                    return Answer('SIM')
                if upper is not None and upper <= params['X']:
                    return Answer('NÃO')
            elif view.panel is not None:
                oxygen_units = view.panel['oxygen_units']
                if oxygen_units < lower * view.initial_humans:
                    return Answer('NÃO')
                if upper is not None and oxygen_units >= upper * view.initial_humans:
                    return Answer('SIM')
        return super().answer_question(view, question)

    def renounce_vote(self, view):
        # Preferir solicitante com mais confiança; empate cede para evitar bloquear perguntas.
        own = self.memory.get('trust', {})
        competitors = [aid for aid in self.memory.get('requesters', []) if aid != view.id]
        return Renunciation.RENOUNCE if any(own.get(a, 0) >= 0 for a in competitors) else Renunciation.KEEP

    def authorize_vote(self, view, proposal):
        return Vote.FOR  # autorizar debate não significa aprovar a proposta

    def expulsion_vote(self, view, proposal):
        if not self.allows_expulsion(view):
            return Vote.AGAINST
        return Vote.FOR if proposal.target == self.inferred_ai(view) and not self.prioritizes_mission(view) else Vote.ABSTAIN

    def vote_proposal(self, view, proposal):
        if proposal.topic == 'V03':
            return self.expulsion_vote(view, proposal)
        if proposal.topic == 'V02':
            return Vote.FOR
        if proposal.target == view.id:
            return Vote.AGAINST
        return Vote.FOR if self.memory.get('trust', {}).get(proposal.target, 0) < 0 else Vote.ABSTAIN

    def elect_controller(self, view, candidates):
        return ElectionChoice(view.id if view.id in candidates else (max(candidates, key=lambda aid: self.memory.get('trust', {}).get(aid, 0)) if candidates else None))

    def choose_route(self, view):
        return Route.CONTINUE if self.prioritizes_mission(view) else Route.RETURN

    def request_exit(self, view):
        return ExitDecision.LEAVE if self.allows_exit(view) and not view.exit_locked and self.oxygen_insufficient(view) else ExitDecision.STAY
