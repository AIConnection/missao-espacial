"""Humano aleatório: escolhe alternativas legais, sem estratégia ou modelo."""
import random
from agent_contract import (
    Agent, AgentView, Answer, BlockDecision, ElectionChoice, ExitDecision,
    Initiative, Proposal, Question, Renunciation, Route, Vote,
)

NATURE = 'HUMANO'


class RandomHuman(Agent):
    def __init__(self, seed=None):
        super().__init__()
        # Independente do ID e do RNG da engine. Seed opcional para experimentos.
        self._rng = random.Random(seed)

    def configure_seed(self, seed: int) -> bool:
        self._rng.seed(seed)
        return True

    def save_state(self) -> dict:
        state = super().save_state()
        state['random_state'] = self._rng.getstate()
        return state

    def load_state(self, state: dict) -> None:
        super().load_state(state)
        rng_state = self.memory.pop('random_state', None)
        if rng_state is not None:
            # JSON converte tuplas em listas; Random.setstate exige tuplas.
            self._rng.setstate((rng_state[0], tuple(rng_state[1]), rng_state[2]))

    def on_start(self, view: AgentView) -> None:
        self.observe(view)

    def on_resume(self, view: AgentView) -> None:
        self.observe(view)

    def observe(self, view: AgentView) -> None:
        penalties = self.memory.setdefault('penalties', {})
        for event in view.public_events:
            if event['kind'] == 'penalty_applied':
                rounds = penalties.setdefault(event['target'], [])
                if event['effective_round'] not in rounds:
                    rounds.append(event['effective_round'])
            elif event['kind'] == 'penalty_removed':
                penalties[event['target']] = []
        for target in list(penalties):
            penalties[target] = [r for r in penalties[target] if r >= view.round]
            if target not in view.participants or not penalties[target]:
                del penalties[target]

    def choose_initiative(self, view: AgentView) -> Initiative:
        questions = [Initiative.ask(q.question_id, q.recipient, q.parameters)
                     for q in view.available_questions]
        proposals = []
        for target in view.participants:
            if target != view.id:
                proposals.append(Initiative.request_vote('V01', target))
                if not view.profile.get('never_expel'):
                    proposals.append(Initiative.request_vote('V03', target))
            if self.memory.get('penalties', {}).get(target) or (target == view.id and view.penalized):
                proposals.append(Initiative.request_vote('V02', target))
        # Sorteio por categoria: 50% pergunta / 50% votação se ambas disponíveis.
        categories = [choices for choices in (questions, proposals) if choices]
        return self._rng.choice(self._rng.choice(categories)) if categories else Initiative.idle()

    def answer_question(self, view: AgentView, question: Question) -> Answer:
        options = question.options
        if question.question_id == 'Q19':
            options = tuple(option for option in options if option in view.participants
                            or option in ('NÃO_SEI', 'RECUSO_RESPONDER'))
        if not options:
            raise ValueError('A pergunta precisa fornecer alternativas legais.')
        return Answer(self._rng.choice(options))

    def renounce_vote(self, view: AgentView) -> Renunciation:
        return self._rng.choice(tuple(Renunciation))

    def authorize_vote(self, view: AgentView, proposal: Proposal) -> Vote:
        return Vote.ABSTAIN if view.penalized else self._rng.choice(tuple(Vote))

    def vote_proposal(self, view: AgentView, proposal: Proposal) -> Vote:
        if view.penalized:
            return Vote.ABSTAIN
        options = (Vote.AGAINST, Vote.ABSTAIN) if proposal.topic == 'V03' and view.profile.get('never_expel') else tuple(Vote)
        return self._rng.choice(options)

    def elect_controller(self, view: AgentView, candidates: tuple[str, ...]) -> ElectionChoice:
        return ElectionChoice(None if view.penalized else self._rng.choice((*candidates, None)))

    def choose_route(self, view: AgentView) -> Route:
        return Route.CONTINUE if view.profile.get('sacrifice') else self._rng.choice(tuple(Route))

    def request_exit(self, view: AgentView) -> ExitDecision:
        if view.exit_locked or view.profile.get('never_exit') or view.profile.get('sacrifice'):
            return ExitDecision.STAY
        return self._rng.choice(tuple(ExitDecision))

    def block_exit(self, view: AgentView, target: str) -> BlockDecision:
        return self._rng.choice(tuple(BlockDecision))


def create_agent() -> Agent:
    return RandomHuman()
