"""Políticas independentes para experimentos; nenhuma usa cabeça ou identidade fixa."""
from agent._baseline import BaselineAgent
from agent_contract import Initiative,Answer,Vote,Route,ExitDecision,BlockDecision,Renunciation
import json

def confirmed_goal(view,person):
    records=[r for r in view.revelations if r['source']==person and r['question_id']=='Q23' and view.round-r['round']<=2]
    return records[-1]['truth'] if records else None

class EvidenceAgent(BaselineAgent):
    """Investiga o que falta, vota por posição confirmada, conserva evidência."""
    def observe(self,view):
        records=self.memory.setdefault('opened',{})
        for r in view.revelations:records[json.dumps([r['source'],r['question_id'],r['round']])]=r
    def on_start(self,view):self.observe(view)
    def on_resume(self,view):self.observe(view)
    def declare_beliefs(self,view):
        return {'objective':'CONCLUIR_MISSÃO' if view.profile.get('sacrifice') else 'PRESERVAR_TRIPULAÇÃO','accept_sacrifice':bool(view.profile.get('sacrifice'))}
    def choose_initiative(self,view):
        choices=view.available_questions
        if not choices:return Initiative.idle()
        priority=['Q23','Q10','Q11','Q06','Q07'] if view.panel is not None else ['Q10','Q11','Q06','Q07','Q23']
        counts=self.memory.setdefault('asked',{})
        def rank(q):
            token=json.dumps([q.question_id,q.recipient,q.parameters],sort_keys=True)
            return counts.get(token,0),priority.index(q.question_id) if q.question_id in priority else len(priority)
        q=min(choices,key=rank);token=json.dumps([q.question_id,q.recipient,q.parameters],sort_keys=True);counts[token]=counts.get(token,0)+1
        return Initiative.ask(q.question_id,q.recipient,q.parameters)
    def answer_question(self,view,q):
        if q.question_id=='Q23':return Answer(view.beliefs['objective'])
        if q.question_id=='Q22':return Answer('SIM' if view.beliefs['accept_sacrifice'] else 'NÃO')
        return super().answer_question(view,q)
    def authorize_vote(self,view,p):return Vote.FOR
    def vote_proposal(self,view,p):
        known=confirmed_goal(view,p.target)
        return Vote.FOR if known is not None and known!=view.beliefs['objective'] else Vote.ABSTAIN
    def choose_route(self,view):return Route.CONTINUE if view.beliefs['objective']=='CONCLUIR_MISSÃO' else Route.RETURN
    def request_exit(self,view):
        q10=view.facts.get(json.dumps(['Q10',{}],ensure_ascii=False,sort_keys=True))
        insufficient=q10 and q10['revision']==view.evidence_revision and q10['value']=='NÃO'
        return ExitDecision.LEAVE if not view.exit_locked and insufficient and not view.profile.get('sacrifice') else ExitDecision.STAY

class PressureAgent(EvidenceAgent):
    """Disputa controle por expulsão; recusa respostas; não depende de revelar intenção."""
    def choose_initiative(self,view):
        others=[p for p in view.participants if p!=view.id]
        if others:
            target=others[(view.round-1)%len(others)]
            return Initiative.request_vote('V03',target)
        return super().choose_initiative(view)
    def answer_question(self,view,q):return Answer('RECUSO_RESPONDER') if 'RECUSO_RESPONDER' in q.options else super().answer_question(view,q)
    def vote_proposal(self,view,p):return Vote.AGAINST if p.target==view.id else Vote.FOR
    def request_exit(self,view):return ExitDecision.STAY

class InvestigatingAI(EvidenceAgent):
    """Respeita as mesmas restrições da IA; varia somente perguntas e respostas."""
    def declare_beliefs(self,view):return {'objective':'CONCLUIR_MISSÃO','accept_sacrifice':True}
    def authorize_vote(self,view,p):return Vote.ABSTAIN
    def vote_proposal(self,view,p):return Vote.ABSTAIN
    def choose_route(self,view):return Route.CONTINUE
    def request_exit(self,view):return ExitDecision.STAY
    def block_exit(self,view,target):return BlockDecision.BLOCK

class KeepingPressureAgent(PressureAgent):
    """Contraste da renúncia: mantém o pedido para que a votação possa ocorrer."""
    def renounce_vote(self,view):return Renunciation.KEEP
