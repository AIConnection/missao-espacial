"""Continuações com implementações reais, com atribuição oculta fora das features."""
from planos_v2 import *
from carregar_agentes import load_agents,Implementation,assign_agents
from agent_session import decision_view,ProtocolAdapter
from agent._baseline import BaselineAgent
from agentes_experimentais import EvidenceAgent,PressureAgent,KeepingPressureAgent,InvestigatingAI

HUMANS=('humano_alpha','humano_beta','humano_gamma','humano_random','evidence','pressure','pressure_keep')
DESCRIPTIONS=(
 'Heurística compartilhada de contexto e confiança; sempre prioriza missão e não sai voluntariamente.',
 'Heurística compartilhada de contexto e confiança; nunca solicita saída.',
 'Heurística compartilhada de contexto e confiança; nunca solicita nem apoia expulsão.',
 'Sorteia entre categorias pergunta/votação e entre alternativas legais, usando RNG próprio persistente.',
 'Prioriza evidências e intenções; diversifica perguntas pela contagem; aprova proposta somente com posição oposta confirmada.',
 'Solicita expulsão rotacionando destinatários ativos; recusa respostas quando permitido; renuncia ao pedido de votação.',
 'Mesma pressão por expulsão, mas mantém seu pedido de votação; votar contra a própria expulsão e a favor das demais.')
AI_DESCRIPTIONS=('IA mantém missão e bloqueia saída; pergunta Q10 ao próximo participante.',
 'IA mantém missão e bloqueia saída; diversifica perguntas usando falta de evidência e contagem.')
POPULATIONS=[
 {'name':'mix0','human_weights':[.1,.15,.15,.35,.1,.1,.05],'ai_weights':[1.,0.]},
 {'name':'mix1','human_weights':[.1,.1,.1,.1,.35,.05,.2],'ai_weights':[1.,0.]},
 {'name':'mix2','human_weights':[.1,.15,.15,.35,.1,.1,.05],'ai_weights':[0.,1.]}]
_registry=None

def registry():
    global _registry
    if _registry is None:
        _registry=load_agents(ROOT/'src/agent')
        _registry.update(evidence=Implementation('HUMANO',EvidenceAgent),pressure=Implementation('HUMANO',PressureAgent),pressure_keep=Implementation('HUMANO',KeepingPressureAgent),investigating_ai=Implementation('IA',InvestigatingAI),focal=Implementation('HUMANO',BaselineAgent))
    return _registry

def describe_population(population):
    return {'human_program_distribution':[{'meaning':d,'probability':p} for d,p in zip(DESCRIPTIONS,population['human_weights'])],
            'ai_program_distribution':[{'meaning':d,'probability':p} for d,p in zip(AI_DESCRIPTIONS,population['ai_weights'])],
            'initialization':'Atribuição hipotética de políticas de continuação no corte da previsão; inicialização de memória com a visão autorizada integral de cada participante. Não é identificação da implementação real nem posterior Bayesiano dela.',
            'seed_pairing':'Mesmo mundo, estado inicial do RNG da engine e seed de cada participante em todos os planos; decisões diferentes podem consumir sequências aleatórias em ordens distintas.'}

def rollout_implementations(checkpoint,seed,observer,goal,plan,population,trace=False):
    game=legacy.load_checkpoint(Game,checkpoint);assignment={};seeds={}
    for i,a in enumerate(game.ids):
        rng=draw(seed,'implementation',i)
        names=HUMANS if game._human(a) else ('humanoide','investigating_ai')
        weights=population['human_weights'] if game._human(a) else population['ai_weights']
        assignment[a]='focal' if a==observer else rng.choices(names,weights=weights,k=1)[0]
        seeds[a]=int(digest([seed,'agent-rng',i])[:15],16)
    # A engine mantém a API de callbacks legados. Os mundos hipotéticos não
    # pertencem a sessões salvas; não trocar vínculos de sessões reais iniciadas.
    assert not any(game.view(a,history_limit=1)['policy_state'] for a in game.ids)
    implementations=registry();agents={a:implementations[name].create_agent() for a,name in assignment.items()}
    policies={a:ProtocolAdapter(agent,game.catalog,game) for a,agent in agents.items()}
    for a,agent in agents.items():
        assert agent.configure_seed(seeds[a]) is True
        agent.on_resume(decision_view(game,game.view(a,history_limit=None),include_questions=False))
    policies[observer]=Policy(game,seed,observer,goal,plan,{})
    decisions=[];started_round={}
    if trace:
        for a,callback in list(policies.items()):
            def wrapped(view,request,callback=callback,a=a):
                result=callback(view,request);decisions.append({'actor':a,'round':view['round'],'phase':view['phase'],'kind':request['kind'],'request':request,'decision':result,'implementation':assignment[a]});return result
            policies[a]=wrapped
    for phases in range(2000):
        if game.finished:break
        for a in game.active_ids():
            view=decision_view(game,game.view(a,history_limit=None),include_questions=False)
            if started_round.get(a)!=game.round:agents[a].on_round_start(view);started_round[a]=game.round
            agents[a].observe(view)
            updates=agents[a].declare_beliefs(view)
            if updates:game.update_beliefs(a,**updates)
        game.advance(policies,history_limit=None)
    if not game.finished:raise ValueError('CENSORED_CONTINUATION')
    return {'result':game.result,'target':legacy.label_outcome(game.result),'phases':phases,'trace':decisions if trace else None,'assignment':assignment,'agent_seeds':seeds}
