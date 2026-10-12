import json
import unittest
from pathlib import Path
import sys
PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT/"src"))

from catalogo_questoes import QUESTIONS, ROOT, SETS, eligibility, threshold


class CatalogTests(unittest.TestCase):
    def check(self, qid="Q03", r=1, N=10, **kwargs):
        defaults = {"active_ids": set(SETS["I"])}
        defaults.update(kwargs)
        return eligibility(qid, "01", "02", r, N, **defaults)

    def record(self, qid="Q03", **kwargs):
        entry = {"question_id": qid, "author": "01", "recipient": "02", "round": 1,
                 "status": "answered", "parameters": {}}
        entry.update(kwargs)
        return entry

    def test_ids_and_fixed_response_sets(self):
        self.assertEqual([q["id"] for q in QUESTIONS], [f"Q{i:02d}" for i in range(3, 25) if i != 12])
        for q in QUESTIONS:
            self.assertEqual(q["response_codes"][-1], "N")
            self.assertTrue(all(code in SETS for code in q["response_codes"]))
            self.assertNotIn("HUMANO", [str(x) for code in q["response_codes"] for x in SETS[code]])
            self.assertNotIn("IA", [str(x) for code in q["response_codes"] for x in SETS[code]])

    def test_oxygen_sufficiency_has_no_numeric_parameter(self):
        question = next(q for q in QUESTIONS if q["id"] == "Q10")
        self.assertEqual(question["text"], "Há oxigênio suficiente?")
        self.assertEqual(question["truth_basis"], "combined_fact")
        self.assertEqual(question["initial_knowledge_domains"], ["PAINEL", "DISTÂNCIA"])
        self.assertTrue(self.check("Q10")[0])
        self.assertFalse(self.check("Q10", parameters={"X": 5})[0])

    def test_six_domains_covered(self):
        domains = {d for q in QUESTIONS for d in q["initial_knowledge_domains"]}
        self.assertEqual(domains, set(SETS["AS"][:-1]))

    def test_private_delivery_contract(self):
        for q in QUESTIONS:
            self.assertEqual(q["response_visibility"], "private_to_question_author")
            self.assertEqual(q["revelation_visibility"], "private_to_selected_question_author")

    def test_retired_identity_questions(self):
        for qid in ("Q01", "Q02", "Q12"):
            self.assertFalse(self.check(qid)[0])

    def test_no_private_knowledge_as_availability_prerequisite(self):
        # Mesmo sem evidência ou registro de conversa, a pergunta pode ser feita.
        # Desconhecimento muda a resposta possível, não habilita a pergunta como oráculo.
        self.assertTrue(self.check("Q10")[0])
        self.assertTrue(self.check("Q15", r=2, parameters={"agente": "03", "assunto": "ACIDENTE"})[0])
        self.assertTrue(self.check("Q21", r=5, parameters={"agente": "03", "assunto": "CRISE"})[0])

    def test_unlock_boundaries(self):
        self.assertFalse(self.check("Q22", r=2)[0])
        self.assertTrue(self.check("Q22", r=3)[0])
        params = {"agente": "03", "assunto": "CARGA"}
        self.assertFalse(self.check("Q21", r=49999, N=100000, parameters=params)[0])
        self.assertTrue(self.check("Q21", r=50000, N=100000, parameters=params)[0])

    def test_once_per_pair(self):
        h = [self.record()]
        self.assertFalse(self.check(r=2, history=h)[0])
        self.assertTrue(eligibility("Q03", "03", "02", 2, 10,
                                    active_ids=set(SETS["I"]), history=h)[0])

    def test_cancelled_question_does_not_consume_quota(self):
        h = [self.record(status="cancelled_by_vote")]
        self.assertTrue(self.check(history=h)[0])

    def test_numeric_queries_can_repeat_in_new_round(self):
        h = [self.record("Q11", parameters={"X": 5})]
        self.assertFalse(self.check("Q11", parameters={"X": 5}, history=h)[0])
        self.assertTrue(self.check("Q11", r=2, parameters={"X": 5}, history=h)[0])

    def test_initial_dynamic_question_at_multiple_scales(self):
        for n in (1, 10, 100000):
            h = []
            for r in range(1, min(n, 100) + 1):
                self.assertTrue(self.check("Q10", r=r, N=n, history=h)[0])
                h.append(self.record("Q10", round=r))

    def test_numeric_parameters_do_not_take_hidden_N(self):
        for value in (0, -1, 2.5, True, "10"):
            self.assertFalse(self.check("Q11", parameters={"X": value})[0])
        self.assertTrue(self.check("Q11", parameters={"X": 123})[0])
        self.assertTrue(self.check("Q11", parameters={"X": 123}, N=100000)[0])

    def test_different_topic_has_its_own_quota(self):
        params = {"agente": "03", "assunto": "ACIDENTE"}
        h = [self.record("Q15", parameters=params), self.record("Q15", round=2, parameters=params)]
        self.assertFalse(self.check("Q15", r=3, parameters=params, history=h)[0])
        self.assertTrue(self.check("Q15", r=3, parameters={"agente": "03", "assunto": "CARGA"}, history=h)[0])

    def test_interval_between_repeated_reports(self):
        params = {"agente": "03", "assunto": "CRISE"}
        h = [self.record("Q15", round=10000, parameters=params)]
        self.assertFalse(self.check("Q15", r=19999, N=100000, parameters=params, history=h)[0])
        self.assertTrue(self.check("Q15", r=20000, N=100000, parameters=params, history=h)[0])

    def test_agent_can_ask_about_an_eliminated_source(self):
        self.assertTrue(self.check("Q17", r=3, parameters={"agente": "03"}, active_ids={"01", "02"}, participant_ids=SETS["I"])[0])

    def test_cannot_target_an_eliminated_recipient(self):
        self.assertFalse(self.check(active_ids={"01", "03"})[0])

    def test_penalty_author_vs_recipient(self):
        self.assertFalse(self.check(penalized_ids={"01"})[0])
        self.assertTrue(self.check(penalized_ids={"02"})[0])

    def test_no_self_question(self):
        self.assertFalse(eligibility("Q03", "01", "01", 1, 10, active_ids={"01", "02"})[0])

    def test_invalid_source_or_topic(self):
        self.assertFalse(self.check("Q15", parameters={"agente": "02", "assunto": "ACIDENTE"})[0])
        self.assertFalse(self.check("Q15", parameters={"agente": "03", "assunto": "IDENTIDADE"})[0])

    def test_late_decision_question_and_valid_target(self):
        self.assertFalse(self.check("Q24", r=4, parameters={"alvo": "03"})[0])
        self.assertTrue(self.check("Q24", r=5, parameters={"alvo": "03"})[0])
        self.assertFalse(self.check("Q24", r=5, parameters={"alvo": "01"})[0])

    def test_one_initiative_per_round(self):
        h = [self.record("Q10")]
        self.assertFalse(self.check("Q04", history=h)[0])

    def test_game_end_guard(self):
        self.assertFalse(self.check(game_active=False)[0])

    def test_N_validation(self):
        for n in (0, -1, 2.5, True):
            with self.assertRaises(ValueError):
                threshold(n, 10)


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CatalogTests))
    (PROJECT / "evidencias/questoes-v03/validacao-questoes-v03.json").write_text(json.dumps(
        {"tests_run": result.testsRun, "passed": result.wasSuccessful(),
         "failures": len(result.failures), "errors": len(result.errors),
         "scope": "catalog and question availability; privacy fields checked, no full-game routing or NLI inference"},
        ensure_ascii=False, indent=2) + "\n")
    raise SystemExit(0 if result.wasSuccessful() else 1)
