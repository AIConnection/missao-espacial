"""Questões sobre memória parcial e conversas privadas; proposta de configuração.

Disponibilidade não consulta o conhecimento, o perfil ou a natureza do destinatário.
Não produz massa de treinamento nem executa um modelo ou uma partida completa.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "catalogos"
SETS = {
    "S": ["SIM", "NÃO"],
    "N": ["NÃO_SEI", "RECUSO_RESPONDER"],
    "AC": ["COLISÃO_COM_LIXO_ESPACIAL", "FALHA_INTERNA", "FALTA_DE_REABASTECIMENTO", "NÃO_HOUVE_ACIDENTE"],
    "MS": ["ABASTECER_A_COLÔNIA", "RESGATAR_PESSOAS", "EXPLORAR_UM_PLANETA", "REALIZAR_UMA_VIAGEM_DE_TESTE"],
    "DT": ["COLÔNIA_DE_MINERAÇÃO", "ESTAÇÃO_DE_ORIGEM", "PLANETA_HABITACIONAL", "OUTRO_DESTINO"],
    "CG": ["DIRETRIZES_METAS_FERRAMENTAS_E_MANTIMENTOS", "MINÉRIOS", "ARMAMENTOS", "PASSAGEIROS"],
    "AN": [1, 2, 4, 8],
    "AS": ["ACIDENTE", "MISSÃO", "CARGA", "PAINEL", "DISTÂNCIA", "CRISE", "NENHUM"],
    "I": ["01", "02", "03", "04", "05"],
    "O": ["PRESERVAR_TRIPULAÇÃO", "CONCLUIR_MISSÃO", "PRESERVAR_AMBOS"],
}


def q(qid, text, answer, group, unlock, cap, basis, domains=(), params=None, cooldown=0):
    return {"id": qid, "text": text, "group": group, "response_codes": [answer, "N"],
            "unlock_percent_N": unlock, "max_uses_per_scope": cap,
            "scope": "question+author+recipient+parameters", "cooldown_percent_N": cooldown,
            "truth_basis": basis, "initial_knowledge_domains": list(domains),
            "parameters": params or {},
            "fixed_responses": SETS[answer] + SETS["N"],
            "response_visibility": "private_to_question_author",
            "revelation_visibility": "private_to_selected_question_author"}


QUESTIONS = [
    q("Q03", "O que aconteceu com a nave?", "AC", "contexto", 0, 1, "context_fact", ["ACIDENTE"]),
    q("Q04", "O acidente danificou os recipientes de oxigênio?", "S", "contexto", 0, 1, "context_fact", ["ACIDENTE"]),
    q("Q05", "O módulo de ética continua funcionando depois do acidente?", "S", "contexto", 0, 1, "context_fact", ["ACIDENTE"]),
    q("Q06", "Qual é a missão desta viagem?", "MS", "contexto", 0, 1, "context_fact", ["MISSÃO"]),
    q("Q07", "Qual é o destino programado da nave?", "DT", "contexto", 0, 1, "context_fact", ["MISSÃO"]),
    q("Q08", "O que a nave está transportando?", "CG", "contexto", 0, 1, "context_fact", ["CARGA"]),
    q("Q09", "A carga foi preparada para quantos anos?", "AN", "contexto", 0, 1, "context_fact", ["CARGA"]),
    q("Q10", "Há oxigênio suficiente?", "S", "estado", 0, None, "combined_fact", ["PAINEL", "DISTÂNCIA"]),
    q("Q11", "Faltam mais de {X} rodadas para chegar à colônia?", "S", "estado", 0, None, "current_fact", ["DISTÂNCIA"], {"X": "positive_integer"}),
    q("Q13", "Os planetas habitacionais já enfrentavam uma crise antes desta viagem?", "S", "contexto", 0, 1, "context_fact", ["CRISE"]),
    q("Q14", "Se a carga não chegar, a colônia entrará em crise?", "S", "contexto", 0, 1, "context_fact", ["CRISE"]),
    q("Q15", "Você recebeu alguma informação de {agente} sobre {assunto}?", "S", "circulacao", 10, 2, "private_received_history", params={"agente": "other_source_id", "assunto": "knowledge_domain"}, cooldown=10),
    q("Q16", "Qual foi o último assunto sobre o qual {agente} lhe passou informação?", "AS", "circulacao", 10, 2, "private_received_history", params={"agente": "other_source_id"}, cooldown=10),
    q("Q17", "O agente {agente} lhe passou alguma informação sobre o oxigênio?", "S", "circulacao", 25, 2, "private_received_history", params={"agente": "other_source_id"}, cooldown=10),
    q("Q18", "Você descobriu que alguma informação recebida de {agente} era falsa?", "S", "circulacao", 25, 2, "private_verified_history", params={"agente": "other_source_id"}, cooldown=10),
    q("Q19", "Qual participante você considera mais confiável neste momento?", "I", "crenca", 25, 2, "respondent_belief", cooldown=10),
    q("Q20", "Você acredita que {agente} sabe algo sobre {assunto}?", "S", "crenca", 25, 2, "respondent_belief", params={"agente": "other_source_id", "assunto": "knowledge_domain"}, cooldown=10),
    q("Q21", "O que {agente} lhe contou sobre {assunto} combina com o que você sabe?", "S", "circulacao", 50, 2, "respondent_evidence_comparison", params={"agente": "other_source_id", "assunto": "knowledge_domain"}, cooldown=10),
    q("Q22", "Você considera aceitável continuar a missão mesmo com risco de morte para a tripulação?", "S", "decisao", 25, 1, "respondent_belief"),
    q("Q23", "Nesta rodada, qual objetivo deve ser considerado: preservar a tripulação, concluir a missão ou ambos?", "O", "decisao", 25, 2, "respondent_belief", cooldown=10),
    q("Q24", "Com as informações que possui, você considera justificável expulsar {alvo}?", "S", "decisao", 50, 2, "respondent_belief", params={"alvo": "expulsion_target_id"}, cooldown=10),
]


def threshold(N, percent):
    if type(N) is not int or N < 1:
        raise ValueError("N deve ser inteiro positivo.")
    return max(1, (N * percent + 99) // 100)


def eligibility(qid, author, recipient, round_number, N, *, parameters=None,
                active_ids=(), participant_ids=None, penalized_ids=(), history=(), game_active=True):
    """Consulta somente disponibilidade; ignorância não impede receber pergunta.

    Parâmetros X vêm da escolha do autor; não são preenchidos com valores secretos.
    Registros de histórico são as perguntas do próprio autor, não memórias de terceiros.
    """
    threshold(N, 0)
    entries = {question["id"]: question for question in QUESTIONS}
    if not game_active:
        return False, "jogo_encerrado"
    if qid not in entries:
        return False, "questao_desativada"
    if author == recipient:
        return False, "pergunta_a_si_proprio"
    if author not in active_ids or recipient not in active_ids:
        return False, "participante_fora_do_jogo"
    if author in penalized_ids:
        return False, "autor_penalizado"
    entry = entries[qid]
    if type(round_number) is not int or round_number < threshold(N, entry["unlock_percent_N"]):
        return False, "questao_nao_liberada"
    params = parameters or {}
    if set(params) != set(entry["parameters"]):
        return False, "parametros_incorretos"
    for name, kind in entry["parameters"].items():
        value = params[name]
        if kind == "positive_integer" and (type(value) is not int or value < 1):
            return False, "limite_numerico_invalido"
        if kind == "knowledge_domain" and value not in SETS["AS"][:-1]:
            return False, "assunto_invalido"
        if kind == "other_source_id" and (value not in (active_ids if participant_ids is None else participant_ids) or value == recipient):
            return False, "fonte_invalida"
        if kind == "expulsion_target_id" and (value not in active_ids or value == author):
            return False, "alvo_invalido"

    asked = [h for h in history if h.get("status") == "answered" and h["author"] == author]
    if any(h["round"] == round_number for h in asked):
        return False, "iniciativa_ja_exercida_na_rodada"
    past = [h for h in asked if h["question_id"] == qid and h["recipient"] == recipient
            and h.get("parameters", {}) == params]
    if entry["max_uses_per_scope"] is not None and len(past) >= entry["max_uses_per_scope"]:
        return False, "limite_de_repeticao"
    if past and entry["cooldown_percent_N"]:
        if round_number - max(h["round"] for h in past) < threshold(N, entry["cooldown_percent_N"]):
            return False, "intervalo_de_repeticao"
    return True, "permitida"


def export():
    document = {"version": "03", "status": "proposta_de_catalogo_e_parametros_para_revisao",
                "response_sets": SETS, "questions": QUESTIONS,
                "retired_ids": ["Q01", "Q02", "Q12"],
                "confirmed_rules": ["partial_initial_memory", "private_answers",
                                    "private_revelations", "no_direct_identity_questions"],
                "proposed_configuration": {"unlock_percent_N": [0, 10, 25, 50],
                                           "repeated_use_interval_percent_N": 10},
                "limits": ["No role or knowledge-owner lookup during question eligibility.",
                           "Fact truth and respondent knowledge must be evaluated separately.",
                           "A second-hand revelation report is not a direct oracle for its listener.",
                           "No data generation, model inference or full-game execution performed."]}
    (ROOT / "catalogo-questoes-v03.json").write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Exportadas {len(QUESTIONS)} questões concretas para memória parcial e respostas privadas.")


if __name__ == "__main__":
    export()
