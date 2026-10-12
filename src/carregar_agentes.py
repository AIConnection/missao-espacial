"""Descoberta de módulos de agentes externos à engine, usando biblioteca padrão."""
from __future__ import annotations

import importlib.machinery
import importlib.util
import inspect
from dataclasses import dataclass
from typing import Callable
from pathlib import Path
import sys
from types import ModuleType
import uuid

from agent_contract import Agent
from agent_session import AgentSession, BINDING_KEY


@dataclass(frozen=True)
class Implementation:
    nature: str
    create_agent: Callable[[], Agent]


class AgentLoadError(ValueError):
    """Diretório ou contrato de módulo inválido."""


def load_agents(directory='agent'):
    """Carrega implementações *.py por nome de módulo, sem atribuir participantes.

    Arquivos iniciados por '_' são auxiliares e não representam agentes.
    Imports relativos (from ._common import ...) usam um pacote isolado por
    carregamento. Novos carregamentos releem os módulos de agentes e não
    dependem do nome de diretórios ou de alterar sys.path.
    """
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise AgentLoadError(f'Diretório de agentes inexistente: {directory}')
    files = sorted(p for p in directory.glob('*.py') if not p.name.startswith('_'))
    package_name = '_mission_agents_' + uuid.uuid4().hex
    package = ModuleType(package_name)
    package.__path__ = [str(directory)]
    package.__package__ = package_name
    package.__spec__ = importlib.machinery.ModuleSpec(package_name, loader=None, is_package=True)
    sys.modules[package_name] = package
    implementations = {}
    if not files:
        del sys.modules[package_name]
        raise AgentLoadError('Nenhuma implementação Python encontrada.')
    try:
        for path in files:
            module_name = f'{package_name}.{path.stem}'
            spec = importlib.util.spec_from_file_location(module_name, path)
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            try:
                # Ler fonte evita reutilizar bytecode antigo após edição rápida no notebook.
                exec(compile(path.read_bytes(), str(path), 'exec'), module.__dict__)
            except Exception as error:
                raise AgentLoadError(f'Falha ao importar agente: {path.name}') from error
            if hasattr(module, 'AGENT_ID'):
                raise AgentLoadError(f'{path.name}: remova AGENT_ID; IDs pertencem à partida, não à implementação.')
            nature = getattr(module, 'NATURE', None)
            if nature not in ('HUMANO', 'IA'):
                raise AgentLoadError(f'{path.name}: declarar NATURE como HUMANO ou IA.')
            factory = getattr(module, 'create_agent', None)
            if not callable(factory) or inspect.iscoroutinefunction(factory):
                raise AgentLoadError(f'{path.name}: definir create_agent() para retornar uma instância de Agent.')
            try:
                inspect.signature(factory).bind()
            except (TypeError, ValueError) as error:
                raise AgentLoadError(f'{path.name}: create_agent deve poder ser chamada sem argumentos.') from error
            implementations[path.stem] = Implementation(nature, factory)
    except BaseException:
        for name in list(sys.modules):
            if name == package_name or name.startswith(package_name + '.'):
                del sys.modules[name]
        raise
    return implementations


def _validate_assignment(implementations, assignment, participant_ids=None):
    if not isinstance(implementations, dict) or not implementations or any(
            type(name) is not str or not isinstance(impl, Implementation)
            or impl.nature not in ('HUMANO', 'IA') or not callable(impl.create_agent)
            for name, impl in implementations.items()):
        raise AgentLoadError('Registro de implementações inválido.')
    if (not isinstance(assignment, dict) or len(assignment) < 2 or
            any(type(aid) is not str or not aid for aid in assignment) or
            (participant_ids is not None and set(assignment) != set(participant_ids))):
        raise AgentLoadError('Definir explicitamente uma implementação para cada participante da partida.')
    if any(type(name) is not str or name not in implementations for name in assignment.values()):
        raise AgentLoadError('Implementação da atribuição não está disponível no diretório de agentes.')
    ai_ids = [aid for aid, name in assignment.items() if implementations[name].nature == 'IA']
    if len(ai_ids) != 1:
        raise AgentLoadError('A atribuição deve conter um humanoide IA e pelo menos um humano.')
    return ai_ids[0]


def ai_id_for_assignment(implementations, assignment):
    """ID externo do humanoide definido pela configuração, sem sorteio."""
    return _validate_assignment(implementations, assignment)


def assign_agents(game, implementations, assignment=None, *, agent_seeds=None):
    """Conecta o vínculo explícito e confere a natureza definida pelos módulos.

    Partidas novas exigem atribuição externa. Retomadas usam o vínculo salvo.
    Não sorteia IDs, natureza nem implementação; não altera a engine.
    """
    memories = {aid: game.view(aid, history_limit=1)['policy_state'] for aid in game.ids}
    if any(not isinstance(memory, dict) for memory in memories.values()):
        raise AgentLoadError('A atribuição requer memória JSON de política em formato de objeto.')
    existing = {aid: memory[BINDING_KEY] for aid, memory in memories.items() if BINDING_KEY in memory}
    if existing:
        if set(existing) != set(game.ids):
            raise AgentLoadError('Atribuição salva incompleta; não substituir o vínculo da partida.')
        if assignment is not None and assignment != existing:
            raise AgentLoadError('Atribuição diferente do checkpoint; não trocar participantes durante a retomada.')
        selected = existing
    else:
        if assignment is None:
            raise AgentLoadError('Partida sem atribuição salva; fornecer configuração explícita, sem sorteio.')
        if game.round != 1 or game.phase != 'initiative':
            raise AgentLoadError('Partida já iniciada sem atribuição salva; não substituir seus vínculos.')
        selected = assignment
    _validate_assignment(implementations, selected, game.ids)
    for aid, name in selected.items():
        if implementations[name].nature != game.view(aid, history_limit=1)['own_nature']:
            raise AgentLoadError(f'Natureza incompatível no participante {aid}; configurar o humanoide antes de iniciar Game.')
    # O construtor valida as instâncias e hooks antes de persistir o vínculo.
    return AgentSession(game, implementations, selected, resumed=bool(existing), agent_seeds=agent_seeds)
