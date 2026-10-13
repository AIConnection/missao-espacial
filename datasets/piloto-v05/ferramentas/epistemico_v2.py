"""Mesma semântica NLI; avanços derivados do histórico público completo."""
from epistemico import from_view as legacy_from_view,validate

def from_view(view):
    progress=sum(e.get('progress_increment',1) for e in view['public_events'] if e['kind']=='advanced')
    # Encerramento logo após um avanço conserva o número da rodada. A versão
    # antiga deduzia avanços só pela rodada e perdia esse último avanço.
    proxy=view
    if view['phase']=='finished' and progress==view['round']:
        proxy=dict(view,phase='exit')
    ctx=legacy_from_view(proxy)
    ctx['moment']['phase']=view['phase'];ctx['moment']['progress']=progress
    validate(ctx)
    return ctx
