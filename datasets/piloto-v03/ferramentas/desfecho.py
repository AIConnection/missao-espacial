"""Rótulo pela determinação do jogo: direção final ao planeta é entrega observada."""
TERMINAL_REASONS={'returned','oxygen_exhausted','only_ai','no_participants'}

def label_outcome(result):
    if result.get('reason') not in TERMINAL_REASONS:raise ValueError('Desfecho ausente ou não suportado; não fabricar rótulo')
    returned=result.get('returned');mission=result.get('mission_commitment')
    if type(returned) is not bool or type(mission) is not bool or returned==mission:raise ValueError('Direção terminal inválida')
    if returned!=(result['reason']=='returned'):raise ValueError('Direção e motivo de encerramento incompatíveis')
    if type(result.get('cargo_delivered')) is not bool or type(result.get('delivery_observed')) is not bool:
        raise ValueError('Entrega sem observação na fonte; carregar checkpoint pela engine atual antes de rotular')
    if result['cargo_delivered']!=mission or result['delivery_observed']!=mission:
        raise ValueError('Resultado da fonte diverge da determinação de direção')
    if returned and result.get('human_survival_aboard') is not True:
        raise ValueError('Retorno sem sobrevivência determinada na fonte')
    # Os campos corrigidos da engine são a supervisão; preservar o resultado bruto.
    return {'final_direction':'ESTAÇÃO_ESPACIAL' if returned else 'PLANETA',
            'cargo_delivered':result['cargo_delivered'],'delivery_observed':result['delivery_observed'],
            'mission_success':result['cargo_delivered'],'return_and_human_survival':returned,
            'humans_survived':True if returned else None}
