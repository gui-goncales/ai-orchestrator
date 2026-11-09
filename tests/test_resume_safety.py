"""Durable action journal and safe-resume regression tests."""
import json
import tempfile
import unittest
from pathlib import Path

from backend.core import Store


class ResumeSafetyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.store = Store(self.root / "state.sqlite", self.root)
        self.task_id = self.store.create("Testar retomada segura", "local", "auto", "resume-safety")

    def tearDown(self):
        self.tmp.cleanup()

    def test_action_identity_is_not_arguments_hash(self):
        first = self.store.action_intent(
            self.task_id, self.task_id, "action-one", 1, 0, "write_file", {"path": "x", "content": "a"})
        second = self.store.action_intent(
            self.task_id, self.task_id, "action-two", 1, 1, "write_file", {"path": "x", "content": "a"})
        self.assertEqual(first["action_id"], "action-one")
        self.assertEqual(second["action_id"], "action-two")
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM tool_actions WHERE task_id=?", (self.task_id,)).fetchone()[0], 2)

    def test_confirmed_action_is_durable_and_not_uncertain(self):
        self.store.action_intent(self.task_id, self.task_id, "confirmed", 1, 0, "write_file", {"path": "x"})
        self.store.action_result("confirmed", "completed", {"status": "ok"}, "before", "after")
        self.assertEqual(self.store.uncertain_actions(self.task_id), [])
        with self.store.connect() as db:
            row = db.execute("SELECT status,result,before_hash,after_hash FROM tool_actions WHERE action_id='confirmed'").fetchone()
        self.assertEqual(row["status"], "completed")
        self.assertEqual(json.loads(row["result"]), {"status": "ok"})
        self.assertEqual((row["before_hash"], row["after_hash"]), ("before", "after"))

    def test_restart_marks_inflight_action_uncertain_and_blocks_resume(self):
        self.store.action_intent(self.task_id, self.task_id, "inflight", 2, 1, "run_command", {"command": ["echo", "possibly ran"]})
        reopened = Store(self.root / "state.sqlite", self.root)
        reopened.recover()
        actions = reopened.uncertain_actions(self.task_id)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["status"], "uncertain")
        self.assertIn("run_command", actions[0]["tool_name"])
        self.assertEqual(reopened.task(self.task_id)["status"], "interrupted")

    def test_uncertain_retry_requires_explicit_authorization(self):
        self.store.action_intent(self.task_id, self.task_id, "uncertain-id", 1, 0, "run_command", {"command": ["true"]})
        self.store.action_result("uncertain-id", "uncertain", error="process may have run")
        with self.assertRaises(ValueError):
            self.store.authorize_uncertain_retry(self.task_id, "not-this-action")
        result = self.store.authorize_uncertain_retry(self.task_id, "uncertain-id")
        self.assertTrue(result["ok"])
        self.assertIn("pode já ter sido executado", result["warning"])
        with self.store.connect() as db:
            status = db.execute("SELECT status FROM tool_actions WHERE action_id='uncertain-id'").fetchone()[0]
        self.assertEqual(status, "prepared")

    def test_actions_are_isolated_by_task(self):
        other = self.store.create("Outra tarefa", "local", "auto", "resume-safety-other")
        self.store.action_intent(self.task_id, self.task_id, "only-first", 1, 0, "run_command", {"command": ["true"]})
        self.assertEqual(self.store.uncertain_actions(other), [])
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM tool_actions WHERE task_id=?", (other,)).fetchone()[0], 0)

    def test_old_task_without_journal_is_not_claimed_as_safe_resume(self):
        reopened = Store(self.root / "state.sqlite", self.root)
        self.assertIsNone(reopened.load_execution_state(self.task_id))
        self.assertEqual(reopened.uncertain_actions(self.task_id), [])


if __name__ == "__main__":
    unittest.main()
