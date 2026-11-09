import unittest

from backend.decision import Decision


class ModeDecisionRegressionTests(unittest.TestCase):
    def test_classification_matrix(self):
        cases = [
            ("Analise a arquitetura", "analyze"),
            ("Revise os arquivos", "analyze"),
            ("Quanto é 2+2?", "analyze"),
            ("Planeje a migração", "plan"),
            ("Crie um roadmap", "plan"),
            ("Implemente o módulo", "work"),
            ("Corrija os bugs", "work"),
            ("Refatore o serviço", "work"),
            ("Desenvolva dashboard", "work"),
            ("Execute testes", "work"),
            ("Aplique a correção", "work"),
            ("Analise e depois implemente", "work"),
            ("Crie plano e depois implemente", "work"),
            ("Crie um PDF de relatório", "artifact"),
            ("Gere uma planilha", "artifact"),
            ("Crie um jogo de arena", "artifact"),
        ]
        for objective, expected in cases:
            with self.subTest(objective=objective):
                self.assertEqual(
                    Decision.classify_mode(objective)["selected_mode"],
                    expected,
                )

    def test_manual_override(self):
        for mode in ("analyze", "plan", "work", "artifact"):
            with self.subTest(mode=mode):
                decision = Decision.classify_mode("Implemente o módulo", mode)
                self.assertEqual(decision["selected_mode"], mode)
                self.assertEqual(decision["requested_mode"], mode)

    def test_missing_capabilities_block(self):
        decision = Decision.classify_mode(
            "Implemente o módulo",
            authorization={"read_files": True},
        )
        self.assertTrue(decision["permission_conflict"])
        self.assertEqual(
            decision["missing_capabilities"],
            ["run_commands", "write_files"],
        )
        self.assertEqual(decision["permitted_operations"], ["read"])

    def test_read_only_permission(self):
        decision = Decision.classify_mode(
            "Analise os arquivos",
            authorization={"read_files": True},
        )
        self.assertFalse(decision["permission_conflict"])
        self.assertEqual(decision["permitted_operations"], ["read"])

    def test_invalid_mode(self):
        with self.assertRaises(ValueError):
            Decision.classify_mode("Teste", "unknown")

    def test_mixed_request_requires_work(self):
        decision = Decision.classify_mode(
            "Inspecione o código, implemente melhorias e execute testes"
        )
        self.assertEqual(decision["selected_mode"], "work")
        self.assertEqual(decision["classification_method"], "deterministic")
        self.assertEqual(decision["permitted_operations"], ["read"])
        self.assertTrue(decision["permission_conflict"])

    def test_read_only_context_does_not_grant_mutation(self):
        decision = Decision.classify_mode(
            "Inspecione e corrija os problemas",
            authorization={
                "read_files": True,
                "write_files": False,
                "run_commands": False,
            },
        )
        self.assertEqual(decision["selected_mode"], "work")
        self.assertTrue(decision["permission_conflict"])
        self.assertNotIn("write", decision["permitted_operations"])
        self.assertNotIn("execute", decision["permitted_operations"])


if __name__ == "__main__":
    unittest.main()
