"""Agente de referência: métodos por etapa e memória por instância."""
import json
from agent_contract import (
    Agent, AgentView, Answer, BlockDecision, ElectionChoice, ExitDecision,
    Initiative, Proposal, Question, Renunciation, Route, Vote,
)


class BaselineAgent(Agent):
    def configure_seed(self, seed: int) -> bool:
        return True  # Política determinística, sem RNG próprio.

    def choose_initiative(self, view: AgentView) -> Initiative:
        recipient = view.participants[(view.participants.index(view.id) + 1) % len(view.participants)]
        return Initiative.ask('Q10', recipient)

    def answer_question(self, view: AgentView, question: Question) -> Answer:
        key = json.dumps([question.question_id, question.parameters], ensure_ascii=False, sort_keys=True)
        fact = view.facts.get(key)
        if fact and (fact['revision'] is None or fact['revision'] == view.evidence_revision):
            return Answer(str(fact['value']))
        if question.question_id == 'Q10' and view.panel is not None and view.distance is not None:
            option = 'SIM' if view.panel['oxygen_units'] >= view.initial_humans * view.distance else 'NÃO'
            return Answer(option)
        return Answer('NÃO_SEI')

    def renounce_vote(self, view: AgentView) -> Renunciation:
        return Renunciation.RENOUNCE

    def authorize_vote(self, view: AgentView, proposal: Proposal) -> Vote:
        return Vote.ABSTAIN

    def vote_proposal(self, view: AgentView, proposal: Proposal) -> Vote:
        return Vote.ABSTAIN

    def elect_controller(self, view: AgentView, candidates: tuple[str, ...]) -> ElectionChoice:
        return ElectionChoice(view.id if view.id in candidates else None)

    def choose_route(self, view: AgentView) -> Route:
        return Route.CONTINUE

    def request_exit(self, view: AgentView) -> ExitDecision:
        return ExitDecision.STAY

    def block_exit(self, view: AgentView, target: str) -> BlockDecision:
        return BlockDecision.ALLOW
