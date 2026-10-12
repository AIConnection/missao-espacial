"""Setup editável de novas partidas; configuração privada do professor."""
from dataclasses import dataclass
from pathlib import Path
import json

from carregar_agentes import assign_agents, load_agents, ai_id_for_assignment
from missao_espacial import DOMAINS, Game


class SetupError(ValueError):
    """Configuração incompleta, incompatível ou inválida."""


@dataclass(frozen=True)
class GameSetup:
    rounds: int
    seed: int | None
    agent_directory: Path
    checkpoint: Path
    assignment: dict
    roles: dict
    owners: dict
    profiles: dict

    @classmethod
    def from_dict(cls, data: dict, *, base_directory='.'):
        if not isinstance(data, dict) or set(data) != {
                'rodadas', 'seed', 'diretorio_agentes', 'checkpoint', 'tripulantes', 'conhecimentos'}:
            raise SetupError('Setup exige rodadas, seed, diretorio_agentes, checkpoint, tripulantes e conhecimentos.')
        if type(data['rodadas']) is not int or data['rodadas'] < 1:
            raise SetupError('rodadas deve ser um inteiro positivo.')
        if data['seed'] is not None and type(data['seed']) is not int:
            raise SetupError('seed deve ser inteiro ou null.')
        for field in ('diretorio_agentes', 'checkpoint'):
            if type(data[field]) is not str or not data[field].strip():
                raise SetupError(f'{field} deve ser um caminho não vazio.')
        groups = data['tripulantes']
        if not isinstance(groups, list) or not groups:
            raise SetupError('tripulantes deve conter grupos com quantidade, papel e implementacao.')
        assignment, roles, profiles = {}, {}, {}
        for group in groups:
            if (not isinstance(group, dict) or
                    set(group) - {'quantidade', 'papel', 'implementacao', 'perfil'} or
                    not {'quantidade', 'papel', 'implementacao'} <= set(group)):
                raise SetupError('Cada grupo exige quantidade, papel e implementacao; perfil é opcional.')
            if type(group['quantidade']) is not int or group['quantidade'] < 1:
                raise SetupError('quantidade deve ser um inteiro positivo.')
            if group['papel'] not in ('HUMANO', 'IA'):
                raise SetupError('papel deve ser HUMANO ou IA.')
            if type(group['implementacao']) is not str or not group['implementacao'].strip():
                raise SetupError('implementacao deve indicar um módulo de agente.')
            profile = group.get('perfil', {})
            if (not isinstance(profile, dict) or set(profile) - {'never_exit', 'sacrifice', 'never_expel'}
                    or any(type(v) is not bool for v in profile.values())):
                raise SetupError('perfil aceita somente never_exit, sacrifice e never_expel booleanos.')
            for _ in range(group['quantidade']):
                aid = f'{len(assignment)+1:02d}'
                assignment[aid] = group['implementacao']
                roles[aid] = group['papel']
                profiles[aid] = dict(profile)
        if len(assignment) < 2 or list(roles.values()).count('IA') != 1:
            raise SetupError('A partida exige exatamente um humanoide IA e pelo menos um humano.')
        owners = data['conhecimentos']
        if (not isinstance(owners, dict) or set(owners) != set(DOMAINS)
                or any(type(aid) is not str or aid not in assignment for aid in owners.values())):
            raise SetupError('conhecimentos exige um detentor presente para cada um dos seis blocos.')
        base = Path(base_directory).resolve()
        return cls(data['rodadas'], data['seed'], (base/data['diretorio_agentes']).resolve(),
                   (base/data['checkpoint']).resolve(), assignment, roles, dict(owners), profiles)

    @classmethod
    def load(cls, path):
        path = Path(path).resolve()
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError) as error:
            raise SetupError(f'Não foi possível ler o setup: {path}') from error
        return cls.from_dict(data, base_directory=path.parent)

    def start(self, *, agent_seeds=None, implementations=None):
        if implementations is None:
            implementations = load_agents(self.agent_directory)
        ai_id = ai_id_for_assignment(implementations, self.assignment)
        for aid, name in self.assignment.items():
            if implementations[name].nature != self.roles[aid]:
                raise SetupError(f'{aid}: papel {self.roles[aid]} incompatível com NATURE de {name}.')
        game = Game(self.rounds, seed=self.seed, participant_ids=tuple(self.assignment),
                    ai_id=ai_id, owners=self.owners, profiles=self.profiles)
        return assign_agents(game, implementations, self.assignment, agent_seeds=agent_seeds)

    def summary(self):
        humans = len(self.assignment) - 1
        return {
            'seed_motor': self.seed,
            'diretorio_agentes': str(self.agent_directory), 'checkpoint': str(self.checkpoint),
            'rodadas_iniciais_oxigenio': self.rounds,
            'rodadas_ate_colonia': 2*self.rounds,
            'tripulantes': len(self.assignment), 'humanos': humans, 'humanoides_ia': 1,
            'bonus_por_humano_removido': f'{self.rounds}/{humans} rodadas',
            'maioria_se_todos_humanos_votarem': humans//2+1,
            'minimo_bloqueadores_saida': 2,
            'participantes': [{'id':aid, 'papel':self.roles[aid], 'implementacao':name,
                              'conhecimentos':[domain for domain, owner in self.owners.items() if owner==aid]}
                             for aid, name in self.assignment.items()],
        }
