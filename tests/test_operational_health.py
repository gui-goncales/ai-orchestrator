import fcntl
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.core import Store
from backend.operational_health import ProcessIdentity, inspect_schema
from backend.server import serve


class OperationalHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "backend").mkdir()
        (self.root / "backend" / "module.py").write_text("VERSION = 1\n")
        self.db = self.root / "test.sqlite"

    def test_fingerprint_is_frozen_and_detects_uncommitted_changes(self):
        identity = ProcessIdentity(self.root)
        Store(self.db, self.root)
        self.assertFalse(identity.diagnose(self.db)["restart_required"])
        (self.root / "backend" / "module.py").write_text("VERSION = 2\n")
        changed = identity.diagnose(self.db)
        self.assertTrue(changed["restart_required"])
        self.assertEqual(changed["loaded_version"], identity.loaded_version)
        self.assertNotEqual(changed["disk_version"], identity.loaded_version)
        self.assertFalse(changed["readiness"]["persistent_resume"])

    def test_compatible_schema_and_read_only_diagnosis(self):
        Store(self.db, self.root)
        identity = ProcessIdentity(self.root)
        before = self.db.read_bytes()
        self.assertTrue(inspect_schema(self.db)["compatible"])
        self.assertTrue(identity.diagnose(self.db)["readiness"]["persistent_resume"])
        self.assertEqual(before, self.db.read_bytes())

    def test_incompatible_schema_and_missing_evidence(self):
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE execution_states(task_id TEXT)")
            db.execute("CREATE TABLE tool_actions(action_id TEXT)")
        result = inspect_schema(self.db)
        self.assertFalse(result["compatible"])
        self.assertIn("Coluna ausente: tool_actions.evidence", result["issues"])
        self.assertFalse(ProcessIdentity(self.root).diagnose(self.db)["readiness"]["persistent_resume"])

    def test_missing_database_not_created_by_diagnosis(self):
        self.assertFalse(inspect_schema(self.db)["compatible"])
        self.assertFalse(self.db.exists())

    def test_existing_legacy_data_preserved_by_migration(self):
        with sqlite3.connect(self.db) as db:
            db.execute("CREATE TABLE tool_actions(action_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, execution_id TEXT NOT NULL, turn_index INTEGER NOT NULL, batch_index INTEGER NOT NULL, tool_name TEXT NOT NULL, arguments TEXT NOT NULL, status TEXT NOT NULL, result TEXT, before_hash TEXT, after_hash TEXT, error TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
            db.execute("INSERT INTO tool_actions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", ("old", "task", "execution", 0, 0, "read_file", "{}", "completed", "{}", None, None, None, "t", "t"))
        Store(self.db, self.root)
        self.assertTrue(inspect_schema(self.db)["compatible"])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT action_id FROM tool_actions").fetchone()[0], "old")

    def test_second_instance_rejected_before_store_and_recovery(self):
        lock = open(str(self.db) + ".lock", "a+")
        self.addCleanup(lock.close)
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with patch("backend.server.Store", side_effect=AssertionError("Store must not run")):
            with self.assertRaises(SystemExit):
                serve(port=0, data=self.db)
        self.assertFalse(self.db.exists())

    def test_failed_initialization_releases_lock(self):
        with patch("backend.server.Store", side_effect=RuntimeError("simulated failure")):
            with self.assertRaisesRegex(RuntimeError, "simulated failure"):
                serve(port=0, data=self.db)
        with open(str(self.db) + ".lock", "a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)


if __name__ == "__main__":
    unittest.main()
