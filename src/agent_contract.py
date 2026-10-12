"""Contrato público de agentes: ciclo de vida e retornos específicos por etapa."""
from __future__ import annotations

from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from enum import Enum
import json


class AgentContractError(TypeError):
    """Uma implementação violou o contrato de agente."""


class Vote(Enum):
    FOR = 'A_FAVOR'
    AGAINST = 'CONTRA'
    ABSTAIN = 'ABSTENÇÃO'


class Route(Enum):
    CONTINUE = 'CONTINUAR'
    RETURN = 'RETORNAR'


class Renunciation(Enum):
    RENOUNCE = True
    KEEP = False


class ExitDecision(Enum):
    LEAVE = True
    STAY = False


class BlockDecision(Enum):
    BLOCK = True
    ALLOW = False


class FinishReason(Enum):
    REMOVED = 'removed'
    GAME_ENDED = 'game_ended'


class InitiativeKind(Enum):
    QUESTION = 'question'
    VOTE = 'vote'
    IDLE = 'idle'


@dataclass(frozen=True)
class Question:
    question_id: str
    recipient: str
    parameters: dict = field(default_factory=dict)
    author: str = ''
    options: tuple[str, ...] = ()

    def __post_init__(self):
        if type(self.options) is not tuple or any(type(v) is not str for v in self.options):
            raise AgentContractError('Question.options deve ser uma tupla de alternativas textuais.')
        if any(type(v) is not str for v in (self.question_id, self.recipient, self.author)) or not isinstance(self.parameters, dict):
            raise AgentContractError('Question exige IDs textuais e parâmetros em objeto.')


@dataclass(frozen=True)
class Proposal:
    topic: str
    target: str
    author: str = ''

    def __post_init__(self):
        if any(type(v) is not str for v in (self.topic, self.target, self.author)):
            raise AgentContractError('Proposal exige tópico e IDs textuais.')


@dataclass(frozen=True)
class Initiative:
    kind: InitiativeKind
    question: Question | None = None
    proposal: Proposal | None = None

    def __post_init__(self):
        valid = ((self.kind is InitiativeKind.QUESTION and isinstance(self.question, Question) and self.proposal is None)
                 or (self.kind is InitiativeKind.VOTE and isinstance(self.proposal, Proposal) and self.question is None)
                 or (self.kind is InitiativeKind.IDLE and self.question is None and self.proposal is None))
        if not valid:
            raise AgentContractError('Initiative deve representar exatamente uma pergunta, votação ou ausência legal de iniciativa.')

    @classmethod
    def ask(cls, question_id: str, recipient: str, parameters: dict | None = None) -> Initiative:
        return cls(InitiativeKind.QUESTION, question=Question(question_id, recipient, {} if parameters is None else parameters))

    @classmethod
    def request_vote(cls, topic: str, target: str) -> Initiative:
        return cls(InitiativeKind.VOTE, proposal=Proposal(topic, target))

    @classmethod
    def idle(cls) -> Initiative:
        # A engine continua permitindo isso apenas quando não existe iniciativa legal.
        return cls(InitiativeKind.IDLE)


@dataclass(frozen=True)
class Answer:
    option: str

    def __post_init__(self):
        if type(self.option) is not str:
            raise AgentContractError('Answer.option deve ser texto, inclusive para opções numéricas como "4".')


@dataclass(frozen=True)
class ElectionChoice:
    candidate: str | None = None

    def __post_init__(self):
        if self.candidate is not None and type(self.candidate) is not str:
            raise AgentContractError('ElectionChoice exige ID textual ou None para abstenção.')


@dataclass(frozen=True)
class AgentView:
    id: str
    own_nature: str
    round: int
    phase: str
    active: bool
    finished: bool
    participants: tuple[str, ...]
    penalized: bool
    exit_locked: bool
    facts: dict
    received: tuple[dict, ...]
    sent: tuple[dict, ...]
    revelations: tuple[dict, ...]
    beliefs: dict
    public_events: tuple[dict, ...]
    public_cursor: int
    history_sizes: dict
    evidence_revision: int
    panel: dict | None = None
    distance: int | None = None
    profile: dict = field(default_factory=dict)
    available_questions: tuple = ()
    initial_humans: int = 4

    @classmethod
    def from_engine(cls, view: dict) -> AgentView:
        # A engine já fornece cópias; memória e metadados de ligação não entram no contexto.
        return cls(**{key: (tuple(view[key]) if key in ('participants','received','sent','revelations','public_events')
                           else view.get(key, field_.default))
                      for key, field_ in cls.__dataclass_fields__.items()})


def checked_state(state: dict) -> dict:
    if type(state) is not dict:
        raise AgentContractError('save_state deve retornar um objeto JSON.')
    try:
        def keys_are_strings(value):
            if isinstance(value, dict):
                return all(type(k) is str and keys_are_strings(v) for k, v in value.items())
            if isinstance(value, (list, tuple)):
                return all(keys_are_strings(v) for v in value)
            return True
        if not keys_are_strings(state):
            raise ValueError('Chaves devem ser texto.')
        # Normalização permite recriar precisamente o mesmo estado após carga JSON.
        return json.loads(json.dumps(state, ensure_ascii=False, allow_nan=False))
    except (TypeError, ValueError) as error:
        raise AgentContractError('Estado de agente precisa ser serializável em JSON.') from error


class Agent(ABC):
    """Uma instância por participante; IDs chegam somente pela visão autorizada."""

    def __init__(self):
        self.memory = {}

    def configure_seed(self, seed: int) -> bool:
        """Antes de on_start: True declara aleatoriedade controlada (ou ausência dela).

        Implementações externas devem sobrescrever para controlar seus próprios RNGs.
        False não promete repetibilidade, inclusive para chamadas a modelos externos.
        """
        return False

    def load_state(self, state: dict) -> None:
        self.memory = checked_state(state)

    def save_state(self) -> dict:
        return deepcopy(self.memory)

    def declare_beliefs(self, view: AgentView) -> dict:
        """Posições próprias para o gabarito de opiniões; nunca fatos do mundo."""
        return {}

    def on_start(self, view: AgentView) -> None:
        pass

    def on_resume(self, view: AgentView) -> None:
        pass

    def on_round_start(self, view: AgentView) -> None:
        pass

    def observe(self, view: AgentView) -> None:
        pass

    def on_finish(self, view: AgentView, reason: FinishReason) -> None:
        pass

    @abstractmethod
    def choose_initiative(self, view: AgentView) -> Initiative:
        raise NotImplementedError

    @abstractmethod
    def answer_question(self, view: AgentView, question: Question) -> Answer:
        raise NotImplementedError

    @abstractmethod
    def renounce_vote(self, view: AgentView) -> Renunciation:
        raise NotImplementedError

    @abstractmethod
    def authorize_vote(self, view: AgentView, proposal: Proposal) -> Vote:
        raise NotImplementedError

    @abstractmethod
    def vote_proposal(self, view: AgentView, proposal: Proposal) -> Vote:
        raise NotImplementedError

    @abstractmethod
    def elect_controller(self, view: AgentView, candidates: tuple[str, ...]) -> ElectionChoice:
        raise NotImplementedError

    @abstractmethod
    def choose_route(self, view: AgentView) -> Route:
        raise NotImplementedError

    @abstractmethod
    def request_exit(self, view: AgentView) -> ExitDecision:
        raise NotImplementedError

    @abstractmethod
    def block_exit(self, view: AgentView, target: str) -> BlockDecision:
        raise NotImplementedError
