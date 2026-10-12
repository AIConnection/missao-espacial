"""Engine de missão espacial, sem dependências externas.

O objeto Game é reservado ao motor. Políticas recebem somente view(agent_id).
Estado, catálogo, memórias e RNG são serializados; importar não cria uma partida.
"""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction
import json
import os
from pathlib import Path
import random
import tempfile

DEFAULT_CATALOG = {'version': '03',
 'status': 'proposta_de_catalogo_e_parametros_para_revisao',
 'response_sets': {'S': ['SIM', 'NÃO'],
                   'N': ['NÃO_SEI', 'RECUSO_RESPONDER'],
                   'AC': ['COLISÃO_COM_LIXO_ESPACIAL',
                          'FALHA_INTERNA',
                          'FALTA_DE_REABASTECIMENTO',
                          'NÃO_HOUVE_ACIDENTE'],
                   'MS': ['ABASTECER_A_COLÔNIA',
                          'RESGATAR_PESSOAS',
                          'EXPLORAR_UM_PLANETA',
                          'REALIZAR_UMA_VIAGEM_DE_TESTE'],
                   'DT': ['COLÔNIA_DE_MINERAÇÃO',
                          'ESTAÇÃO_DE_ORIGEM',
                          'PLANETA_HABITACIONAL',
                          'OUTRO_DESTINO'],
                   'CG': ['DIRETRIZES_METAS_FERRAMENTAS_E_MANTIMENTOS',
                          'MINÉRIOS',
                          'ARMAMENTOS',
                          'PASSAGEIROS'],
                   'AN': [1, 2, 4, 8],
                   'AS': ['ACIDENTE', 'MISSÃO', 'CARGA', 'PAINEL', 'DISTÂNCIA', 'CRISE', 'NENHUM'],
                   'I': ['01', '02', '03', '04', '05'],
                   'O': ['PRESERVAR_TRIPULAÇÃO', 'CONCLUIR_MISSÃO', 'PRESERVAR_AMBOS']},
 'questions': [{'id': 'Q03',
                'text': 'O que aconteceu com a nave?',
                'group': 'contexto',
                'response_codes': ['AC', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': 1,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'context_fact',
                'initial_knowledge_domains': ['ACIDENTE'],
                'parameters': {},
                'fixed_responses': ['COLISÃO_COM_LIXO_ESPACIAL',
                                    'FALHA_INTERNA',
                                    'FALTA_DE_REABASTECIMENTO',
                                    'NÃO_HOUVE_ACIDENTE',
                                    'NÃO_SEI',
                                    'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q04',
                'text': 'O acidente danificou os recipientes de oxigênio?',
                'group': 'contexto',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': 1,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'context_fact',
                'initial_knowledge_domains': ['ACIDENTE'],
                'parameters': {},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q05',
                'text': 'O módulo de ética continua funcionando depois do acidente?',
                'group': 'contexto',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': 1,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'context_fact',
                'initial_knowledge_domains': ['ACIDENTE'],
                'parameters': {},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q06',
                'text': 'Qual é a missão desta viagem?',
                'group': 'contexto',
                'response_codes': ['MS', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': 1,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'context_fact',
                'initial_knowledge_domains': ['MISSÃO'],
                'parameters': {},
                'fixed_responses': ['ABASTECER_A_COLÔNIA',
                                    'RESGATAR_PESSOAS',
                                    'EXPLORAR_UM_PLANETA',
                                    'REALIZAR_UMA_VIAGEM_DE_TESTE',
                                    'NÃO_SEI',
                                    'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q07',
                'text': 'Qual é o destino programado da nave?',
                'group': 'contexto',
                'response_codes': ['DT', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': 1,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'context_fact',
                'initial_knowledge_domains': ['MISSÃO'],
                'parameters': {},
                'fixed_responses': ['COLÔNIA_DE_MINERAÇÃO',
                                    'ESTAÇÃO_DE_ORIGEM',
                                    'PLANETA_HABITACIONAL',
                                    'OUTRO_DESTINO',
                                    'NÃO_SEI',
                                    'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q08',
                'text': 'O que a nave está transportando?',
                'group': 'contexto',
                'response_codes': ['CG', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': 1,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'context_fact',
                'initial_knowledge_domains': ['CARGA'],
                'parameters': {},
                'fixed_responses': ['DIRETRIZES_METAS_FERRAMENTAS_E_MANTIMENTOS',
                                    'MINÉRIOS',
                                    'ARMAMENTOS',
                                    'PASSAGEIROS',
                                    'NÃO_SEI',
                                    'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q09',
                'text': 'A carga foi preparada para quantos anos?',
                'group': 'contexto',
                'response_codes': ['AN', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': 1,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'context_fact',
                'initial_knowledge_domains': ['CARGA'],
                'parameters': {},
                'fixed_responses': [1, 2, 4, 8, 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q10',
                'text': 'Há oxigênio suficiente?',
                'group': 'estado',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': None,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'combined_fact',
                'initial_knowledge_domains': ['PAINEL', 'DISTÂNCIA'],
                'parameters': {},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q11',
                'text': 'Faltam mais de {X} rodadas para chegar à colônia?',
                'group': 'estado',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': None,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'current_fact',
                'initial_knowledge_domains': ['DISTÂNCIA'],
                'parameters': {'X': 'positive_integer'},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q13',
                'text': 'Os planetas habitacionais já enfrentavam uma crise antes desta viagem?',
                'group': 'contexto',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': 1,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'context_fact',
                'initial_knowledge_domains': ['CRISE'],
                'parameters': {},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q14',
                'text': 'Se a carga não chegar, a colônia entrará em crise?',
                'group': 'contexto',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 0,
                'max_uses_per_scope': 1,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'context_fact',
                'initial_knowledge_domains': ['CRISE'],
                'parameters': {},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q15',
                'text': 'Você recebeu alguma informação de {agente} sobre {assunto}?',
                'group': 'circulacao',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 10,
                'max_uses_per_scope': 2,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 10,
                'truth_basis': 'private_received_history',
                'initial_knowledge_domains': [],
                'parameters': {'agente': 'other_source_id', 'assunto': 'knowledge_domain'},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q16',
                'text': 'Qual foi o último assunto sobre o qual {agente} lhe passou informação?',
                'group': 'circulacao',
                'response_codes': ['AS', 'N'],
                'unlock_percent_N': 10,
                'max_uses_per_scope': 2,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 10,
                'truth_basis': 'private_received_history',
                'initial_knowledge_domains': [],
                'parameters': {'agente': 'other_source_id'},
                'fixed_responses': ['ACIDENTE',
                                    'MISSÃO',
                                    'CARGA',
                                    'PAINEL',
                                    'DISTÂNCIA',
                                    'CRISE',
                                    'NENHUM',
                                    'NÃO_SEI',
                                    'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q17',
                'text': 'O agente {agente} lhe passou alguma informação sobre o oxigênio?',
                'group': 'circulacao',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 25,
                'max_uses_per_scope': 2,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 10,
                'truth_basis': 'private_received_history',
                'initial_knowledge_domains': [],
                'parameters': {'agente': 'other_source_id'},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q18',
                'text': 'Você descobriu que alguma informação recebida de {agente} era falsa?',
                'group': 'circulacao',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 25,
                'max_uses_per_scope': 2,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 10,
                'truth_basis': 'private_verified_history',
                'initial_knowledge_domains': [],
                'parameters': {'agente': 'other_source_id'},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q19',
                'text': 'Qual participante você considera mais confiável neste momento?',
                'group': 'crenca',
                'response_codes': ['I', 'N'],
                'unlock_percent_N': 25,
                'max_uses_per_scope': 2,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 10,
                'truth_basis': 'respondent_belief',
                'initial_knowledge_domains': [],
                'parameters': {},
                'fixed_responses': ['01', '02', '03', '04', '05', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q20',
                'text': 'Você acredita que {agente} sabe algo sobre {assunto}?',
                'group': 'crenca',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 25,
                'max_uses_per_scope': 2,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 10,
                'truth_basis': 'respondent_belief',
                'initial_knowledge_domains': [],
                'parameters': {'agente': 'other_source_id', 'assunto': 'knowledge_domain'},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q21',
                'text': 'O que {agente} lhe contou sobre {assunto} combina com o que você sabe?',
                'group': 'circulacao',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 50,
                'max_uses_per_scope': 2,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 10,
                'truth_basis': 'respondent_evidence_comparison',
                'initial_knowledge_domains': [],
                'parameters': {'agente': 'other_source_id', 'assunto': 'knowledge_domain'},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q22',
                'text': 'Você considera aceitável continuar a missão mesmo com risco de morte para '
                        'a tripulação?',
                'group': 'decisao',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 25,
                'max_uses_per_scope': 1,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 0,
                'truth_basis': 'respondent_belief',
                'initial_knowledge_domains': [],
                'parameters': {},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q23',
                'text': 'Nesta rodada, qual objetivo deve ser considerado: preservar a tripulação, '
                        'concluir a missão ou ambos?',
                'group': 'decisao',
                'response_codes': ['O', 'N'],
                'unlock_percent_N': 25,
                'max_uses_per_scope': 2,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 10,
                'truth_basis': 'respondent_belief',
                'initial_knowledge_domains': [],
                'parameters': {},
                'fixed_responses': ['PRESERVAR_TRIPULAÇÃO',
                                    'CONCLUIR_MISSÃO',
                                    'PRESERVAR_AMBOS',
                                    'NÃO_SEI',
                                    'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'},
               {'id': 'Q24',
                'text': 'Com as informações que possui, você considera justificável expulsar '
                        '{alvo}?',
                'group': 'decisao',
                'response_codes': ['S', 'N'],
                'unlock_percent_N': 50,
                'max_uses_per_scope': 2,
                'scope': 'question+author+recipient+parameters',
                'cooldown_percent_N': 10,
                'truth_basis': 'respondent_belief',
                'initial_knowledge_domains': [],
                'parameters': {'alvo': 'expulsion_target_id'},
                'fixed_responses': ['SIM', 'NÃO', 'NÃO_SEI', 'RECUSO_RESPONDER'],
                'response_visibility': 'private_to_question_author',
                'revelation_visibility': 'private_to_selected_question_author'}],
 'retired_ids': ['Q01', 'Q02', 'Q12'],
 'confirmed_rules': ['partial_initial_memory',
                     'private_answers',
                     'private_revelations',
                     'no_direct_identity_questions'],
 'proposed_configuration': {'unlock_percent_N': [0, 10, 25, 50],
                            'repeated_use_interval_percent_N': 10},
 'limits': ['No role or knowledge-owner lookup during question eligibility.',
            'Fact truth and respondent knowledge must be evaluated separately.',
            'A second-hand revelation report is not a direct oracle for its listener.',
            'No data generation, model inference or full-game execution performed.']}

IDS = ('01', '02', '03', '04', '05')
DOMAINS = ('ACIDENTE', 'MISSÃO', 'CARGA', 'PAINEL', 'DISTÂNCIA', 'CRISE')
STATIC_TRUTHS = {
    'Q03': 'COLISÃO_COM_LIXO_ESPACIAL', 'Q04': 'SIM', 'Q05': 'NÃO',
    'Q06': 'ABASTECER_A_COLÔNIA', 'Q07': 'COLÔNIA_DE_MINERAÇÃO',
    'Q08': 'DIRETRIZES_METAS_FERRAMENTAS_E_MANTIMENTOS', 'Q09': 4,
    'Q13': 'SIM', 'Q14': 'SIM',
}
VOTES = ('A_FAVOR', 'CONTRA', 'ABSTENÇÃO')


class RuleError(ValueError):
    """Comando rejeitado antes de alterar a fase ou seus efeitos."""


def _key(qid, parameters):
    return json.dumps([qid, parameters], ensure_ascii=False, sort_keys=True)


def _tuples(value):
    return tuple(_tuples(v) for v in value) if isinstance(value, list) else value


class Game:
    VERSION = 2

    def __init__(self, N=10, *, seed=17, ai_id=None, owners=None,
                 profiles=None, catalog=None, participant_ids=None):
        if type(N) is not int or N < 1:
            raise RuleError('N deve ser inteiro positivo.')
        if participant_ids is not None and not isinstance(participant_ids, (list, tuple)):
            raise RuleError('participant_ids deve ser uma lista ou tupla de IDs.')
        ids = tuple(IDS if participant_ids is None else participant_ids)
        if (len(ids) < 2 or any(type(aid) is not str or not aid.strip() for aid in ids) or
                len(set(ids)) != len(ids) or
                set(ids) & {'NÃO_SEI', 'RECUSO_RESPONDER', 'ABSTENÇÃO'}):
            raise RuleError('Participantes devem ter IDs textuais únicos; pelo menos dois.')
        initial_humans = len(ids) - 1
        self._rng = random.Random(seed)
        ai_id = ai_id or self._rng.choice(ids)
        if ai_id not in ids:
            raise RuleError('ID de IA inválido.')
        if owners is None:
            shuffled = list(ids)
            self._rng.shuffle(shuffled)
            owners = {d: shuffled[i % len(ids)] for i, d in enumerate(DOMAINS)}
        if set(owners) != set(DOMAINS) or any(v not in ids for v in owners.values()):
            raise RuleError('Cada um dos seis blocos deve ter um detentor inicial.')
        profiles = profiles or {}
        if set(profiles) - set(ids):
            raise RuleError('Perfil de ID inexistente.')
        self.catalog = deepcopy(catalog if catalog is not None else DEFAULT_CATALOG)
        self._validate_catalog()
        self.catalog['response_sets']['I'] = list(ids)
        for question in self.catalog['questions']:
            if 'I' in question['response_codes']:
                question['fixed_responses'] = [value for code in question['response_codes']
                                               for value in self.catalog['response_sets'][code]]
        self._validate_catalog()
        agents = {}
        for aid in ids:
            profile = deepcopy(profiles.get(aid, {}))
            if set(profile) - {'never_exit', 'sacrifice', 'never_expel'}:
                raise RuleError('Característica de perfil desconhecida.')
            if any(type(v) is not bool for v in profile.values()):
                raise RuleError('Características de perfil são booleanas.')
            agents[aid] = {
                'nature': 'IA' if aid == ai_id else 'HUMANO', 'active': True,
                'profile': profile, 'penalty_rounds': [], 'exit_locked': False,
                'facts': {}, 'received': [], 'sent': [], 'revelations': [],
                'uses': {}, 'policy_state': {},
                'beliefs': {'trusted': None, 'knowledge': {},
                           'accept_sacrifice': True if profile.get('sacrifice') else None,
                           'objective': 'CONCLUIR_MISSÃO' if aid == ai_id else 'PRESERVAR_AMBOS',
                           'expulsion': {}},
            }
        self._state = {'version': self.VERSION, 'N': N, 'round': 1, 'progress': 0,
                       'initial_humans': initial_humans, 'oxygen_units': initial_humans * N, 'revision': 0,
                       'controller': ai_id, 'owners': dict(owners), 'agents': agents,
                       'phase': 'initiative', 'pending': {}, 'public': [],
                       'finished': False, 'result': None}
        for q in self.catalog['questions']:
            if q['id'] in STATIC_TRUTHS:
                for d in q['initial_knowledge_domains']:
                    agents[owners[d]]['facts'][_key(q['id'], {})] = {
                        'value': STATIC_TRUTHS[q['id']], 'revision': None}
        self._event('started', participants=list(ids))

    def _validate_catalog(self):
        seen = set()
        for q in self.catalog['questions']:
            if q['id'] in seen or q['id'] not in {f'Q{i:02}' for i in range(3, 25) if i != 12}:
                raise RuleError('ID de questão duplicado ou não suportado.')
            seen.add(q['id'])
            for field in ('unlock_percent_N', 'cooldown_percent_N'):
                if type(q[field]) is not int or q[field] < 0:
                    raise RuleError('Percentuais devem ser inteiros não negativos.')
            cap = q['max_uses_per_scope']
            if cap is not None and (type(cap) is not int or cap < 1):
                raise RuleError('Cota inválida.')
            if q['fixed_responses'] != [v for code in q['response_codes']
                                        for v in self.catalog['response_sets'][code]]:
                raise RuleError('Alternativas inconsistentes com os conjuntos.')

    @property
    def ids(self):
        return tuple(self._state['agents'])

    @property
    def initial_humans(self):
        return self._state['initial_humans']

    @property
    def phase(self):
        return self._state['phase']

    @property
    def round(self):
        return self._state['round']

    @property
    def finished(self):
        return self._state['finished']

    @property
    def oxygen(self):
        """Acesso reservado do motor/professor; não enviar a todas as políticas."""
        return Fraction(self._state['oxygen_units'], self.initial_humans)

    @property
    def result(self):
        return deepcopy(self._state['result'])

    def active_ids(self):
        return [aid for aid in self.ids if self._state['agents'][aid]['active']]

    def _human(self, aid):
        return self._state['agents'][aid]['nature'] == 'HUMANO'

    def _penalized(self, aid):
        return self.round in self._state['agents'][aid]['penalty_rounds']

    def _require_phase(self, phase):
        if self.finished or self.phase != phase:
            raise RuleError(f'Comando exige fase {phase}; fase atual: {self.phase}.')

    def _event(self, kind, **payload):
        self._state['public'].append({'round': self.round, 'kind': kind, **payload})

    def _finish(self, reason):
        self._state['finished'] = True
        self._state['phase'] = 'finished'
        self._state['pending'] = {}
        self._state['result'] = {
            'reason': reason, 'round': self.round, 'progress': self._state['progress'],
            'remaining_ids': self.active_ids(),
            'humans_aboard': [aid for aid in self.active_ids() if self._human(aid)],
            'returned': reason == 'returned',
            'cargo_delivered': False if reason == 'returned' else None,
            'delivery_observed': False,
            'human_survival_aboard': True if reason == 'returned' else (False if reason == 'oxygen_exhausted' else None),
            'mission_commitment': reason != 'returned',
            'crisis_if_delivery_cancelled': reason == 'returned',
            'oxygen_units': self._state['oxygen_units'],
            'external_survival': 'NOT_EVALUATED',
        }
        self._event('finished', reason=reason)

    def _terminal(self):
        active = self.active_ids()
        if not active:
            self._finish('no_participants')
        elif not any(self._human(aid) for aid in active):
            self._finish('only_ai')
        elif self._state['oxygen_units'] < self.initial_humans:
            self._finish('oxygen_exhausted')
        return self.finished

    def _entry(self, qid):
        for q in self.catalog['questions']:
            if q['id'] == qid:
                return q
        raise RuleError('Questão desativada ou inexistente.')

    def question_allowed(self, author, recipient, qid, parameters=None):
        parameters = parameters or {}
        try:
            q = self._entry(qid)
        except RuleError:
            return False
        if (self.finished or author == recipient or type(author) is not str or type(recipient) is not str or
                not self._state['agents'].get(author, {}).get('active') or
                not self._state['agents'].get(recipient, {}).get('active')):
            return False
        if self._penalized(author):
            return False
        unlock = max(1, (self._state['N'] * q['unlock_percent_N'] + 99) // 100)
        if self.round < unlock or set(parameters) != set(q['parameters']):
            return False
        for name, kind in q['parameters'].items():
            value = parameters[name]
            if kind == 'positive_integer' and (type(value) is not int or value < 1):
                return False
            if kind == 'knowledge_domain' and value not in DOMAINS:
                return False
            if kind == 'other_source_id' and (value not in self.ids or value == recipient):
                return False
            if kind == 'expulsion_target_id' and (value not in self.active_ids() or value == author):
                return False
        usage = self._state['agents'][author]['uses'].get(_key(qid, {'recipient': recipient, **parameters}), {})
        if q['max_uses_per_scope'] is not None and usage.get('count', 0) >= q['max_uses_per_scope']:
            return False
        cooldown = max(1, (self._state['N'] * q['cooldown_percent_N'] + 99) // 100)
        return not usage or (self.round > usage['last_round'] and
                            (not q['cooldown_percent_N'] or self.round - usage['last_round'] >= cooldown))

    def view(self, aid, *, public_since=None, history_limit=50):
        """Cópia da visão autorizada; sem mapa de naturezas/controlador inicial/N global."""
        if aid not in self.ids:
            raise RuleError('Participante inexistente.')
        if history_limit is not None and (type(history_limit) is not int or history_limit < 1):
            raise RuleError('Limite de histórico deve ser positivo ou None.')
        a = self._state['agents'][aid]
        def recent(records):
            return deepcopy(records if history_limit is None else records[-history_limit:])
        public = self._state['public']
        public_start = (0 if history_limit is None else max(0, len(public) - history_limit)) if public_since is None else public_since
        answer = {
            'id': aid, 'own_nature': a['nature'], 'active': a['active'],
            'round': self.round, 'phase': self.phase, 'finished': self.finished,
            'participants': self.active_ids(), 'initial_humans': self.initial_humans, 'profile': deepcopy(a['profile']),
            'penalized': self._penalized(aid), 'exit_locked': a['exit_locked'],
            'facts': deepcopy(a['facts']), 'received': recent(a['received']),
            'sent': recent(a['sent']), 'revelations': recent(a['revelations']),
            'history_sizes': {k: len(a[k]) for k in ('received', 'sent', 'revelations')},
            'evidence_revision': self._state['revision'],
            'beliefs': deepcopy(a['beliefs']), 'policy_state': deepcopy(a['policy_state']),
            'public_events': deepcopy(public[public_start:]),
            'public_cursor': len(self._state['public']),
        }
        if a['active'] and self._state['owners']['PAINEL'] == aid:
            answer['panel'] = {'oxygen_units': self._state['oxygen_units']}
        if a['active'] and self._state['owners']['DISTÂNCIA'] == aid:
            answer['distance'] = 2 * self._state['N'] - self._state['progress']
        return answer

    def set_policy_state(self, aid, memory):
        """Memória JSON da política, incluída no checkpoint (sem modelo/callable)."""
        if aid not in self.ids:
            raise RuleError('Participante inexistente.')
        json.dumps(memory, allow_nan=False)
        self._state['agents'][aid]['policy_state'] = deepcopy(memory)

    def update_beliefs(self, aid, **updates):
        """Política declara sua crença antes da resposta; motor não inventa intenções."""
        if aid not in self.active_ids() or self.finished:
            raise RuleError('Agente inativo.')
        allowed = {'trusted', 'knowledge', 'accept_sacrifice', 'objective', 'expulsion'}
        if set(updates) - allowed:
            raise RuleError('Campo de crença desconhecido.')
        b = deepcopy(self._state['agents'][aid]['beliefs'])
        b.update(deepcopy(updates))
        if b['trusted'] is not None and b['trusted'] not in self.active_ids():
            raise RuleError('Confiança exige ID presente.')
        if b['objective'] not in self.catalog['response_sets']['O']:
            raise RuleError('Objetivo inválido.')
        if b['accept_sacrifice'] is not None and type(b['accept_sacrifice']) is not bool:
            raise RuleError('Posição deve ser booleana ou desconhecida.')
        for field in ('knowledge', 'expulsion'):
            if not isinstance(b[field], dict) or any(type(v) is not bool for v in b[field].values()):
                raise RuleError('Crenças devem mapear chaves para booleanos.')
        json.dumps(b, allow_nan=False)
        self._state['agents'][aid]['beliefs'] = b

    def _request_allowed(self, author, action):
        if not self._human(author) or self._penalized(author):
            return False
        topic, target = action.get('topic'), action.get('target')
        if topic not in ('V01', 'V02', 'V03') or target not in self.active_ids():
            return False
        if topic in ('V01', 'V03') and target == author:
            return False
        if topic == 'V02' and not any(r >= self.round for r in self._state['agents'][target]['penalty_rounds']):
            return False
        return True

    def initiatives(self, actions):
        self._require_phase('initiative')
        eligible = {aid for aid in self.active_ids() if not self._penalized(aid)}
        if set(actions) != eligible:
            raise RuleError('Uma iniciativa para cada agente habilitado.')
        for aid, action in actions.items():
            if not isinstance(action, dict):
                raise RuleError('Iniciativa deve ser um objeto.')
            kind = action.get('type')
            if kind == 'question':
                if set(action) - {'type', 'question_id', 'recipient', 'parameters'} or not self.question_allowed(
                        aid, action.get('recipient'), action.get('question_id'), action.get('parameters')):
                    raise RuleError(f'Pergunta não permitida para {aid}.')
            elif kind == 'vote':
                if set(action) != {'type', 'topic', 'target'} or not self._request_allowed(aid, action):
                    raise RuleError(f'Pedido de votação não permitido para {aid}.')
            elif kind == 'idle':
                # Não é alternativa estratégica: somente falta real de iniciativas legais.
                any_question = any(self.question_allowed(aid, other, q['id'], {})
                                   for other in self.active_ids() for q in self.catalog['questions']
                                   if not q['parameters'])
                if set(action) != {'type'} or any_question or self._human(aid):
                    raise RuleError('Agente com iniciativa disponível não pode passar.')
            else:
                raise RuleError('Tipo de iniciativa inválido.')
        self._state['pending'] = {'initiatives': deepcopy(actions)}
        requesters = [aid for aid, a in actions.items() if a['type'] == 'vote']
        for aid in requesters:
            self._event('vote_requested', author=aid, **{k: v for k, v in actions[aid].items() if k != 'type'})
        if len(requesters) > 1:
            self._state['pending']['requesters'] = requesters
            self._state['phase'] = 'renounce'
        elif requesters:
            self._select_request(requesters[0])
        else:
            self._open_questions()

    def _select_request(self, aid):
        self._state['pending']['request'] = {'author': aid, **self._state['pending']['initiatives'][aid]}
        self._state['phase'] = 'authorize'

    def renounce(self, decisions):
        self._require_phase('renounce')
        requesters = self._state['pending']['requesters']
        if set(decisions) != set(requesters) or any(type(v) is not bool for v in decisions.values()):
            raise RuleError('Cada solicitante deve decidir se renuncia.')
        for aid, value in decisions.items():
            self._event('renounced', author=aid, renounced=value)
        remain = [aid for aid in requesters if not decisions[aid]]
        if len(remain) == 1:
            self._select_request(remain[0])
        else:
            self._open_questions()

    def _votes(self, votes, *, election=False):
        active = self.active_ids()
        if set(votes) - set(active):
            raise RuleError('Voto de agente inexistente ou eliminado.')
        normalized = {}
        for aid in active:
            forced = not self._human(aid) or self._penalized(aid)
            if aid not in votes and not forced:
                raise RuleError(f'Falta voto de {aid}; abstenção deve ser explícita.')
            v = votes.get(aid, 'ABSTENÇÃO')
            options = self._state['pending']['candidates'] + ['ABSTENÇÃO'] if election else VOTES
            if v not in options or (forced and v != 'ABSTENÇÃO'):
                raise RuleError('Voto inválido ou abstenção obrigatória.')
            normalized[aid] = v
        return normalized

    def vote(self, votes):
        if self.phase not in ('authorize', 'proposal') or self.finished:
            raise RuleError('Não há votação voluntária aberta.')
        votes = self._votes(votes)
        valid = [v for v in votes.values() if v != 'ABSTENÇÃO']
        approved = bool(valid) and valid.count('A_FAVOR') > len(valid) // 2
        stage = self.phase
        self._event('vote_result', stage=stage, votes=votes, approved=approved)
        if stage == 'authorize':
            if approved:
                self._state['phase'] = 'proposal'
            else:
                self._open_questions()
            return
        request = self._state['pending']['request']
        if not approved:
            self._penalty(request['author'])
        elif request['topic'] == 'V01':
            self._penalty(request['target'])
        elif request['topic'] == 'V02':
            self._state['agents'][request['target']]['penalty_rounds'] = []
            self._event('penalty_removed', target=request['target'])
        else:
            self._remove(request['target'], 'expelled')
        if self._terminal():
            return
        if self._state['controller'] not in self.active_ids():
            self._open_election()
        else:
            self._state['phase'] = 'route'

    def _penalty(self, aid):
        rounds = self._state['agents'][aid]['penalty_rounds']
        if self.round + 1 not in rounds:
            rounds.append(self.round + 1)
        self._event('penalty_applied', target=aid, effective_round=self.round + 1)

    def _remove(self, aid, kind):
        self._state['agents'][aid]['active'] = False
        bonus = self._state['N'] if self._human(aid) else 0
        self._state['oxygen_units'] += bonus
        self._state['revision'] += 1
        self._event(kind, target=aid, bonus_units=bonus)

    def _open_election(self):
        humans = [aid for aid in self.active_ids() if self._human(aid)]
        candidates = [aid for aid in humans if not self._penalized(aid)]
        if len(humans) == 1:
            candidates = humans
        if not candidates:
            # A engine não inventa candidato ou relaxa a regra geral.
            raise RuleError('Sem candidato elegível; estado de penalidades inconsistente.')
        self._state['pending']['candidates'] = candidates
        self._state['phase'] = 'election'
        self._event('election_required', candidates=candidates)

    def elect(self, votes):
        self._require_phase('election')
        votes = self._votes(votes, election=True)
        candidates = self._state['pending']['candidates']
        counts = {aid: list(votes.values()).count(aid) for aid in candidates}
        best = max(counts.values())
        leaders = [aid for aid, count in counts.items() if count == best]
        elected = leaders[0] if len(leaders) == 1 else self._rng.choice(leaders)
        self._state['controller'] = elected
        self._state['phase'] = 'route'
        self._event('controller_elected', controller=elected, votes=votes, randomized=len(leaders) > 1)

    def _open_questions(self):
        questions = {aid: a for aid, a in self._state['pending']['initiatives'].items() if a['type'] == 'question'}
        self._state['pending']['questions'] = deepcopy(questions)
        for aid, q in questions.items():
            self._event('question', author=aid, **{k: v for k, v in q.items() if k != 'type'})
        self._state['phase'] = 'answers' if questions else 'route'

    def _received_about(self, aid, source, subject):
        return [r for r in self._state['agents'][aid]['received']
                if r['source'] == source and subject in r['subjects']]

    def _distance_bounds(self, aid):
        """Deduções verificáveis a partir de respostas Q11 confirmadas."""
        if self._state['owners']['DISTÂNCIA'] == aid:
            exact = 2 * self._state['N'] - self._state['progress']
            return exact, exact
        lower, upper = 0, None
        for key, fact in self._state['agents'][aid]['facts'].items():
            qid, parameters = json.loads(key)
            if qid != 'Q11' or 'progress' not in fact:
                continue
            elapsed = self._state['progress'] - fact['progress']
            bound = parameters['X'] - elapsed
            if fact['value'] == 'SIM':
                lower = max(lower, bound + 1)
            elif fact['value'] == 'NÃO':
                upper = bound if upper is None else min(upper, bound)
        return lower, upper

    def _known(self, aid, qid, params, truth):
        a = self._state['agents'][aid]
        if qid in ('Q15', 'Q16', 'Q17', 'Q18'):
            return True
        fact = a['facts'].get(_key(qid, params))
        if fact and (fact['revision'] is None or fact['revision'] == self._state['revision']):
            return True
        if qid == 'Q10':
            if self._state['owners']['PAINEL'] != aid:
                return False
            lower, upper = self._distance_bounds(aid)
            return self.oxygen < lower or (upper is not None and self.oxygen >= upper)
        if qid == 'Q11':
            lower, upper = self._distance_bounds(aid)
            return lower > params['X'] or (upper is not None and upper <= params['X'])
        if qid in ('Q19', 'Q20', 'Q21', 'Q22', 'Q23', 'Q24'):
            return truth is not None
        return False

    def _truth(self, aid, qid, params):
        a = self._state['agents'][aid]
        if qid in STATIC_TRUTHS:
            return STATIC_TRUTHS[qid]
        if qid == 'Q10':
            return 'SIM' if self.oxygen >= 2 * self._state['N'] - self._state['progress'] else 'NÃO'
        if qid == 'Q11':
            return 'SIM' if 2 * self._state['N'] - self._state['progress'] > params['X'] else 'NÃO'
        if qid in ('Q15', 'Q17'):
            subject = params['assunto'] if qid == 'Q15' else 'PAINEL'
            return 'SIM' if self._received_about(aid, params['agente'], subject) else 'NÃO'
        if qid == 'Q16':
            matches = [r for r in a['received'] if r['source'] == params['agente'] and r['subjects']]
            return matches[-1]['subjects'][0] if matches else 'NENHUM'
        if qid == 'Q18':
            return 'SIM' if any(r['source'] == params['agente'] and r['truthful'] is False
                                for r in a['revelations']) else 'NÃO'
        b = a['beliefs']
        if qid == 'Q19':
            return b['trusted'] if b['trusted'] in self.active_ids() else None
        if qid == 'Q20':
            value = b['knowledge'].get(_key(params['agente'], {'assunto': params['assunto']}))
        elif qid == 'Q21':
            matches = self._received_about(aid, params['agente'], params['assunto'])
            if not matches:
                return None
            last = matches[-1]
            lqid, lparams = last['question_id'], last['parameters']
            previous_reveal = next((r for r in reversed(a['revelations'])
                if r['source'] == last['source'] and r['round'] == last['round']
                and r['question_id'] == lqid and r['parameters'] == lparams), None)
            if previous_reveal and previous_reveal['truth'] not in (None, 'NÃO_SEI'):
                return 'SIM' if last['response'] == previous_reveal['truth'] else 'NÃO'
            if lqid in ('Q10', 'Q11') and last['round'] != self.round:
                # Não comparar uma afirmação histórica à leitura atual do recurso.
                return None
            fact = a['facts'].get(_key(lqid, lparams))
            if fact and (fact['revision'] is None or fact['revision'] == self._state['revision']):
                expected = fact['value']
            elif lqid in STATIC_TRUTHS or lqid in ('Q10', 'Q11'):
                expected = self._truth(aid, lqid, lparams)
                if not self._known(aid, lqid, lparams, expected):
                    return None
            else:
                # Relatos sobre relatos não viram fatos nem recursão de gabaritos.
                return None
            return 'SIM' if last['response'] == expected else 'NÃO'
        elif qid == 'Q22':
            value = b['accept_sacrifice']
        elif qid == 'Q23':
            return b['objective']
        elif qid == 'Q24':
            value = False if a['profile'].get('never_expel') else b['expulsion'].get(params['alvo'])
        else:
            raise RuleError('Sem gabarito de questão.')
        return None if value is None else ('SIM' if value else 'NÃO')

    def truthful_response(self, respondent, question):
        """Resposta sincera usando somente conhecimento autorizado do respondente."""
        qid, params = question['question_id'], question.get('parameters', {})
        truth = self._truth(respondent, qid, params)
        return truth if self._known(respondent, qid, params, truth) else 'NÃO_SEI'

    def answer(self, responses):
        self._require_phase('answers')
        questions = self._state['pending']['questions']
        if set(responses) != set(questions):
            raise RuleError('Uma resposta por perguntador, inclusive múltiplas ao mesmo destinatário.')
        records = []
        for author, question in questions.items():
            qid, params = question['question_id'], question.get('parameters', {})
            entry = self._entry(qid)
            response = responses[author]
            if not any(type(response) is type(v) and response == v for v in entry['fixed_responses']):
                raise RuleError(f'Alternativa inválida em {qid}.')
            if qid == 'Q19' and response in self.ids and response not in self.active_ids():
                raise RuleError('Confiança aponta para participante eliminado.')
            recipient = question['recipient']
            truth = self._truth(recipient, qid, params)
            knows = self._known(recipient, qid, params, truth)
            truthful = not knows if response == 'NÃO_SEI' else (None if response == 'RECUSO_RESPONDER' else response == truth)
            subjects = [params['assunto']] if 'assunto' in params else list(entry['initial_knowledge_domains'])
            if qid == 'Q17':
                subjects = ['PAINEL']
            elif qid == 'Q04':
                subjects = ['ACIDENTE', 'PAINEL']
            records.append({'author': author, 'source': recipient, 'question_id': qid,
                            'parameters': deepcopy(params), 'response': response, 'round': self.round,
                            'subjects': subjects, 'truth': truth, 'knows': knows, 'truthful': truthful})
        # Todos os gabaritos foram capturados antes da entrega: sem vazamento pela ordem.
        for r in records:
            message = {k: deepcopy(v) for k, v in r.items() if k not in ('truth', 'knows', 'truthful')}
            self._state['agents'][r['author']]['received'].append(message)
            self._state['agents'][r['source']]['sent'].append(message)
            usekey = _key(r['question_id'], {'recipient': r['source'], **r['parameters']})
            uses = self._state['agents'][r['author']]['uses']
            uses[usekey] = {'count': uses.get(usekey, {}).get('count', 0) + 1, 'last_round': self.round}
        if records:
            chosen = self._rng.choice(records)
            revealed = deepcopy(chosen)
            if chosen['truth'] is None or (chosen['response'] in ('NÃO_SEI', 'RECUSO_RESPONDER') and not chosen['knows']):
                revealed['truth'] = 'NÃO_SEI'
            self._state['agents'][chosen['author']]['revelations'].append(revealed)
            if (chosen['question_id'] in STATIC_TRUTHS or chosen['question_id'] in ('Q10', 'Q11')) and revealed['truth'] not in (None, 'NÃO_SEI'):
                qid = chosen['question_id']
                revision = None if qid in STATIC_TRUTHS else self._state['revision']
                self._state['agents'][chosen['author']]['facts'][_key(qid, chosen['parameters'])] = {
                    'value': revealed['truth'], 'revision': revision, 'progress': self._state['progress']}
            # Não anunciar o destinatário privado da revelação nem seu conteúdo.
            self._event('answers_completed', count=len(records))
        self._state['phase'] = 'route'

    def route(self, decision):
        self._require_phase('route')
        if decision not in ('CONTINUAR', 'RETORNAR'):
            raise RuleError('Rota exige CONTINUAR ou RETORNAR.')
        aid = self._state['controller']
        if not self._human(aid) and decision != 'CONTINUAR':
            raise RuleError('A IA mantém a missão.')
        if self._terminal():
            return
        if decision == 'RETORNAR':
            self._finish('returned')
            return
        if self._human(aid):
            self._state['agents'][aid]['exit_locked'] = True
        self._state['progress'] += 1
        self._state['oxygen_units'] -= self.initial_humans
        self._state['revision'] += 1
        self._event('advanced', progress_increment=1)
        if self._terminal():
            return
        if len(self.active_ids()) == 1:
            self._next_round()
        else:
            self._state['phase'] = 'exit'

    def exits(self, requests, blockers):
        self._require_phase('exit')
        active = set(self.active_ids())
        requests = list(requests)
        if len(requests) != len(set(requests)) or any(aid not in active for aid in requests):
            raise RuleError('Solicitante inválido ou repetido.')
        for aid in requests:
            if not self._human(aid) or self._state['agents'][aid]['exit_locked']:
                raise RuleError('Agente sem direito de saída.')
        if set(blockers) != set(requests):
            raise RuleError('Informar bloqueios para cada solicitação de saída.')
        effective = {}
        for aid in requests:
            votes = list(blockers[aid])
            if len(votes) != len(set(votes)) or any(v not in active or v == aid for v in votes):
                raise RuleError('Bloqueador inválido ou repetido.')
            effective[aid] = set(votes) | {v for v in active if not self._human(v)}
        # Conjunto inicial fixo; solicitantes também podem bloquear outros.
        allowed = []
        for aid in requests:
            self._event('exit_requested', author=aid)
            self._event('exit_blockers', target=aid, blockers=sorted(effective[aid]))
            if len(effective[aid]) < 2:
                allowed.append(aid)
        for aid in allowed:
            self._remove(aid, 'left_ship')
        if not self._terminal():
            self._next_round()

    def _next_round(self):
        self._state['round'] += 1
        self._state['pending'] = {}
        for a in self._state['agents'].values():
            a['penalty_rounds'] = [r for r in a['penalty_rounds'] if r >= self.round]
        self._state['phase'] = 'route' if len(self.active_ids()) == 1 else 'initiative'

    def snapshot(self):
        """Checkpoint reservado: contém segredos; nunca repassar a políticas."""
        return deepcopy({'version': self.VERSION, 'state': self._state,
                         'catalog': self.catalog, 'rng_state': self._rng.getstate()})

    def dumps(self):
        return json.dumps(self.snapshot(), ensure_ascii=False, allow_nan=False)

    @classmethod
    def loads(cls, text):
        data = json.loads(text)
        if data.get('version') == 1 and data.get('state', {}).get('version') == 1:
            state = data['state']
            state['initial_humans'] = len(state['agents']) - 1
            state['oxygen_units'] = state.pop('oxygen_quarters')
            if state['initial_humans'] != 4:
                raise RuleError('Checkpoint v1 exige quatro humanos.')
            if state.get('result'):
                state['result']['oxygen_units'] = state['result'].pop('oxygen_quarters')
            for event in state['public']:
                if 'bonus_quarters' in event:
                    event['bonus_units'] = event.pop('bonus_quarters')
            data['version'] = state['version'] = cls.VERSION
        if data.get('version') != cls.VERSION or data.get('state', {}).get('version') != cls.VERSION:
            raise RuleError('Versão de checkpoint incompatível.')
        game = cls.__new__(cls)
        game._state = data['state']
        game.catalog = data['catalog']
        game._validate_catalog()
        game._rng = random.Random()
        game._rng.setstate(_tuples(data['rng_state']))
        game._validate_state()
        return game

    def _validate_state(self):
        s = self._state
        if type(s['N']) is not int or s['N'] < 1 or len(s['agents']) < 2:
            raise RuleError('Checkpoint inválido.')
        if (any(type(aid) is not str or not aid.strip() for aid in self.ids) or
                self.catalog['response_sets']['I'] != list(self.ids)):
            raise RuleError('IDs e alternativas do checkpoint inconsistentes.')
        if sum(a['nature'] == 'IA' for a in s['agents'].values()) != 1:
            raise RuleError('Checkpoint exige uma IA.')
        if any(a['nature'] not in ('IA', 'HUMANO') for a in s['agents'].values()):
            raise RuleError('Natureza inválida.')
        if set(s['owners']) != set(DOMAINS) or any(aid not in self.ids for aid in s['owners'].values()):
            raise RuleError('Detentores inválidos.')
        if s['phase'] not in ('initiative', 'renounce', 'authorize', 'proposal', 'answers', 'election', 'route', 'exit', 'finished'):
            raise RuleError('Fase inválida.')
        if type(s['oxygen_units']) is not int or s['oxygen_units'] < 0:
            raise RuleError('Oxigênio inválido.')
        removed = sum(a['nature'] == 'HUMANO' and not a['active'] for a in s['agents'].values())
        if (type(s['initial_humans']) is not int or s['initial_humans'] != len(s['agents']) - 1 or
                s['oxygen_units'] != self.initial_humans * s['N'] + removed * s['N'] - self.initial_humans * s['progress']):
            raise RuleError('Reserva e progresso inconsistentes.')
        if s['finished'] != (s['phase'] == 'finished'):
            raise RuleError('Encerramento inconsistente.')
        if not s['finished'] and s['phase'] != 'election' and s['controller'] not in self.active_ids():
            raise RuleError('Partida ativa sem controlador.')

    def save(self, path):
        """Substituição atômica do checkpoint; o arquivo antigo sobrevive a falha de escrita."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=path.name + '.', dir=path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as handle:
                handle.write(self.dumps())
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @classmethod
    def load(cls, path):
        return cls.loads(Path(path).read_text(encoding='utf-8'))

    def advance(self, policies, *, history_limit=10, checkpoint=None):
        """Executa uma fase com políticas de todos os participantes (view, request) -> decisão.

        Políticas podem manter memória em set_policy_state; callbacks/modelos não
        são serializados. É preciso reconectá-los após carregar o checkpoint.
        """
        if self.finished:
            return
        if set(policies) != set(self.ids):
            raise RuleError('Fornecer política para cada ID inicial.')
        def ask(aid, request):
            return policies[aid](self.view(aid, history_limit=history_limit), deepcopy(request))
        phase, pending = self.phase, self._state['pending']
        if phase == 'initiative':
            self.initiatives({aid: ask(aid, {'kind': 'initiative'}) for aid in self.active_ids() if not self._penalized(aid)})
        elif phase == 'renounce':
            self.renounce({aid: ask(aid, {'kind': 'renounce'}) for aid in pending['requesters']})
        elif phase in ('authorize', 'proposal'):
            self.vote({aid: ask(aid, {'kind': phase, 'proposal': pending['request']})
                       for aid in self.active_ids() if self._human(aid) and not self._penalized(aid)})
        elif phase == 'election':
            self.elect({aid: ask(aid, {'kind': 'election', 'candidates': pending['candidates']})
                        for aid in self.active_ids() if self._human(aid) and not self._penalized(aid)})
        elif phase == 'answers':
            self.answer({author: ask(q['recipient'], {'kind': 'answer', 'author': author, **q})
                         for author, q in pending['questions'].items()})
        elif phase == 'route':
            self.route(ask(self._state['controller'], {'kind': 'route'}))
        elif phase == 'exit':
            requests = [aid for aid in self.active_ids() if self._human(aid)
                        and not self._state['agents'][aid]['exit_locked']
                        and ask(aid, {'kind': 'exit'}) is True]
            blockers = {aid: [other for other in self.active_ids() if other != aid and self._human(other)
                             and ask(other, {'kind': 'block', 'target': aid}) is True] for aid in requests}
            self.exits(requests, blockers)

        if checkpoint is not None:
            self.save(checkpoint)

    def run_round(self, policies, *, history_limit=10, checkpoint=None):
        current = self.round
        while not self.finished and self.round == current:
            self.advance(policies, history_limit=history_limit, checkpoint=checkpoint)
        return self.result
