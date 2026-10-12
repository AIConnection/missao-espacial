"""Adaptador do protocolo da engine e execução do ciclo de vida dos agentes."""
from __future__ import annotations

import inspect

from agent_contract import (
    Agent, AgentContractError, AgentView, Answer, BlockDecision, ElectionChoice,
    ExitDecision, FinishReason, Initiative, InitiativeKind, Proposal, Question,
    Renunciation, Route, Vote, checked_state,
)

BINDING_KEY = '__agent_implementation__'
CLOSED_KEY = '__agent_closed__'
ROUND_KEY = '__agent_round_started__'
PUBLIC_KEY = '__agent_public_cursor__'
RESERVED_KEYS = {BINDING_KEY, CLOSED_KEY, ROUND_KEY, PUBLIC_KEY}


def decision_view(game, raw, *, include_questions=True):
    # Disponibilidade depende só das regras, autor e uso; nunca do saber do destinatário.
    choices = []
    recipients = raw['participants'] if include_questions and raw['phase']=='initiative' and not raw['finished'] and not raw['penalized'] else ()
    for recipient in recipients:
        for entry in game.catalog['questions']:
            if not entry['parameters']:
                params = {}
            elif entry['id'] == 'Q11':
                params = {'X': max(1, raw['round'] * 2)}
            else:
                continue
            if game.question_allowed(raw['id'], recipient, entry['id'], params):
                choices.append(Question(entry['id'], recipient, params))
    return AgentView.from_engine({**raw, 'available_questions': tuple(choices)})


def _returns(method, result, expected):
    if not isinstance(result, expected):
        raise AgentContractError(f'{method} deve retornar {expected.__name__}; recebeu {type(result).__name__}.')
    return result


def _void(method, result):
    if result is not None:
        raise AgentContractError(f'{method} deve retornar None.')


class ProtocolAdapter:
    """Único componente que conhece request.kind e os valores brutos da engine."""

    def __init__(self, agent: Agent, catalog: dict, game=None):
        if not isinstance(agent, Agent):
            raise AgentContractError('create_agent deve retornar uma instância de Agent.')
        arities = {'configure_seed':1, 'load_state':1, 'save_state':0, 'declare_beliefs':1, 'on_start':1, 'on_resume':1,
                   'on_round_start':1, 'observe':1, 'on_finish':2, 'choose_initiative':1,
                   'answer_question':2, 'renounce_vote':1, 'authorize_vote':2,
                   'vote_proposal':2, 'elect_controller':2, 'choose_route':1,
                   'request_exit':1, 'block_exit':2}
        for name, arity in arities.items():
            method = getattr(agent, name)
            if inspect.iscoroutinefunction(method) or inspect.isasyncgenfunction(method):
                raise AgentContractError(f'{name} deve ser síncrono.')
            try:
                inspect.signature(method).bind(*([None] * arity))
            except (TypeError, ValueError) as error:
                raise AgentContractError(f'Assinatura incompatível em {name}.') from error
        self.agent = agent
        self.game = game
        self._responses = {q['id']: q['fixed_responses'] for q in catalog['questions']}
        self._handlers = {
            'initiative': self._initiative, 'answer': self._answer,
            'renounce': self._renounce, 'authorize': self._authorize,
            'proposal': self._proposal, 'election': self._election,
            'route': self._route, 'exit': self._exit, 'block': self._block,
        }

    def __call__(self, raw_view: dict, request: dict):
        try:
            handler = self._handlers[request['kind']]
        except KeyError as error:
            raise AgentContractError('Etapa desconhecida no adaptador.') from error
        view = decision_view(self.game, raw_view, include_questions=request['kind']=='initiative') if self.game is not None else AgentView.from_engine(raw_view)
        return handler(view, request)

    @staticmethod
    def _proposal_record(request):
        p = request['proposal']
        return Proposal(p['topic'], p['target'], p['author'])

    def _initiative(self, view, request):
        action = _returns('choose_initiative', self.agent.choose_initiative(view), Initiative)
        if action.kind is InitiativeKind.QUESTION:
            q = action.question
            if q.author and q.author != view.id:
                raise AgentContractError('O autor da iniciativa deve ser o próprio participante.')
            return {'type':'question', 'question_id':q.question_id, 'recipient':q.recipient, 'parameters':q.parameters}
        if action.kind is InitiativeKind.VOTE:
            p = action.proposal
            if p.author and p.author != view.id:
                raise AgentContractError('O proponente deve ser o próprio participante.')
            return {'type':'vote', 'topic':p.topic, 'target':p.target}
        return {'type':'idle'}

    def _answer(self, view, request):
        q = Question(request['question_id'], request['recipient'], request.get('parameters', {}), request['author'],
                     tuple(str(v) for v in self._responses.get(request['question_id'], ())))
        answer = _returns('answer_question', self.agent.answer_question(view, q), Answer)
        matches = [option for option in self._responses.get(q.question_id, ()) if str(option) == answer.option]
        if len(matches) != 1:
            raise AgentContractError(f'Alternativa {answer.option!r} inválida ou ambígua em {q.question_id}.')
        return matches[0]

    def _renounce(self, view, request):
        return _returns('renounce_vote', self.agent.renounce_vote(view), Renunciation).value

    def _authorize(self, view, request):
        return _returns('authorize_vote', self.agent.authorize_vote(view, self._proposal_record(request)), Vote).value

    def _proposal(self, view, request):
        return _returns('vote_proposal', self.agent.vote_proposal(view, self._proposal_record(request)), Vote).value

    def _election(self, view, request):
        choice = _returns('elect_controller', self.agent.elect_controller(view, tuple(request['candidates'])), ElectionChoice)
        return choice.candidate if choice.candidate is not None else 'ABSTENÇÃO'

    def _route(self, view, request):
        return _returns('choose_route', self.agent.choose_route(view), Route).value

    def _exit(self, view, request):
        return _returns('request_exit', self.agent.request_exit(view), ExitDecision).value

    def _block(self, view, request):
        return _returns('block_exit', self.agent.block_exit(view, request['target']), BlockDecision).value


class AgentSession:
    """Executa fases, observa seus efeitos e salva memória junto com o jogo.

    A interface legada de callbacks da engine permanece disponível. Sessões de
    agentes usam advance/run_round daqui para executar também os hooks.
    """

    def __init__(self, game, implementations, assignment, *, resumed, agent_seeds=None):
        if agent_seeds is not None and (not isinstance(agent_seeds,dict) or resumed or set(agent_seeds) != set(assignment)
                or any(type(seed) is not int for seed in agent_seeds.values())):
            raise AgentContractError('Sementes exigem partida nova e inteiro para cada agente.')
        self.seed_control = {}
        self.game = game
        self.assignment = dict(assignment)
        self._agents = {}
        self._closed = set()
        self._round_started = {}
        self._public_cursor = {}
        for aid, name in self.assignment.items():
            try:
                agent = implementations[name].create_agent()
            except Exception as error:
                raise AgentContractError(f'Falha em create_agent de {name}.') from error
            if not isinstance(agent, Agent):
                raise AgentContractError(f'create_agent de {name} deve retornar Agent.')
            if any(agent is other for other in self._agents.values()):
                raise AgentContractError('create_agent deve criar uma instância independente por participante.')
            self._agents[aid] = agent
        self._policies = {aid:ProtocolAdapter(agent, game.catalog, game) for aid, agent in self._agents.items()}
        if agent_seeds is not None:
            for aid, agent in self._agents.items():
                controlled = agent.configure_seed(agent_seeds[aid])
                if type(controlled) is not bool:
                    raise AgentContractError('configure_seed deve retornar bool.')
                self.seed_control[aid] = controlled
        for aid, agent in self._agents.items():
            raw = game.view(aid, history_limit=1)
            memory = raw['policy_state']
            closed = memory.get(CLOSED_KEY, False)
            started = memory.get(ROUND_KEY, game.round if resumed else 0)
            if type(closed) is not bool or type(started) is not int or started < 0 or started > game.round:
                raise AgentContractError('Metadados de ciclo de vida inválidos no checkpoint.')
            if closed and raw['active'] and not game.finished:
                raise AgentContractError('Marcador de encerramento incompatível com participante ativo.')
            if not raw['active'] and CLOSED_KEY not in memory:
                closed = True  # migração: não reabrir agentes já removidos em checkpoints antigos
            cursor = memory.get(PUBLIC_KEY, max(0, raw['public_cursor']-10) if resumed else 0)
            if type(cursor) is not int or not 0 <= cursor <= raw['public_cursor']:
                raise AgentContractError('Cursor público inválido no checkpoint.')
            self._public_cursor[aid] = cursor
            self._round_started[aid] = started
            if closed:
                self._closed.add(aid)
            state = {k:v for k,v in memory.items() if k not in RESERVED_KEYS}
            _void('load_state', agent.load_state(checked_state(state)))
        for aid, agent in self._agents.items():
            if aid in self._closed:
                continue
            view = self._view(aid)
            if resumed:
                _void('on_resume', agent.on_resume(view))
            else:
                _void('on_start', agent.on_start(view))
            self._start_round(aid, view)
            self._public_cursor[aid] = view.public_cursor
        if game.finished:
            self._after_phase()
        else:
            self._persist()

    def agent(self, participant_id: str) -> Agent:
        """Acesso do aplicativo/professor à instância; não é contexto para outros agentes."""
        return self._agents[participant_id]

    def _view(self, aid, history_limit=10):
        return decision_view(self.game, self.game.view(aid, history_limit=history_limit,
                             public_since=self._public_cursor[aid]), include_questions=False)

    def _start_round(self, aid, view):
        if not view.finished and view.active and self._round_started[aid] != view.round:
            _void('on_round_start', self._agents[aid].on_round_start(view))
            self._round_started[aid] = view.round

    def _persist(self):
        states = {}
        for aid, agent in self._agents.items():
            state = checked_state(agent.save_state())
            if RESERVED_KEYS & set(state):
                raise AgentContractError('save_state não deve incluir metadados reservados da sessão.')
            states[aid] = {**state, BINDING_KEY:self.assignment[aid],
                           CLOSED_KEY:aid in self._closed, ROUND_KEY:self._round_started[aid],
                           PUBLIC_KEY:self._public_cursor[aid]}
        for aid, state in states.items():
            self.game.set_policy_state(aid, state)
            if aid not in self._closed and not self.game.finished:
                updates = self._agents[aid].declare_beliefs(self._view(aid))
                if type(updates) is not dict:
                    raise AgentContractError('declare_beliefs deve retornar dict.')
                if updates:
                    self.game.update_beliefs(aid, **updates)

    def _after_phase(self, history_limit=10):
        for aid, agent in self._agents.items():
            if aid in self._closed:
                continue
            view = self._view(aid, history_limit)
            if not view.active or view.finished:
                reason = FinishReason.REMOVED if not view.active else FinishReason.GAME_ENDED
                _void('on_finish', agent.on_finish(view, reason))
                self._closed.add(aid)
            else:
                self._start_round(aid, view)
                _void('observe', agent.observe(view))
            self._public_cursor[aid] = view.public_cursor
        self._persist()

    def advance(self, *, checkpoint=None, history_limit=10) -> None:
        if not self.game.finished:
            self.game.advance(self._policies, history_limit=history_limit)
            self._after_phase(history_limit)
        if checkpoint is not None:
            self.save(checkpoint)

    def run_round(self, *, checkpoint=None, history_limit=10) -> None:
        current = self.game.round
        while not self.game.finished and self.game.round == current:
            self.advance(checkpoint=checkpoint, history_limit=history_limit)

    def save(self, path) -> None:
        self._persist()
        self.game.save(path)
