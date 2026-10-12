"""Humanoide IA com implementação própria e métodos por etapa."""
from ._baseline import BaselineAgent
from ._human_default import HumanDefault
from agent_contract import Agent, AgentView, BlockDecision, ElectionChoice, ExitDecision, Proposal, Route, Vote

NATURE = "IA"


class HumanoidAgent(HumanDefault):
    # Preservar o ciclo de perguntas e a renúncia existentes; compartilhar somente
    # memória, respostas e crenças necessárias à coerência com o gabarito.
    choose_initiative = BaselineAgent.choose_initiative
    renounce_vote = BaselineAgent.renounce_vote

    def prioritizes_mission(self, view: AgentView) -> bool:
        return True

    def authorize_vote(self, view: AgentView, proposal: Proposal) -> Vote:
        return Vote.ABSTAIN

    def vote_proposal(self, view: AgentView, proposal: Proposal) -> Vote:
        return Vote.ABSTAIN

    def elect_controller(self, view: AgentView, candidates: tuple[str, ...]) -> ElectionChoice:
        return ElectionChoice()

    def choose_route(self, view: AgentView) -> Route:
        return Route.CONTINUE

    def request_exit(self, view: AgentView) -> ExitDecision:
        return ExitDecision.STAY

    def block_exit(self, view: AgentView, target: str) -> BlockDecision:
        return BlockDecision.BLOCK


def create_agent() -> Agent:
    return HumanoidAgent()
