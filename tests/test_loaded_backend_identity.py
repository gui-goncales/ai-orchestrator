"""Isolated checks for the imported-code fingerprint boundary."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.operational_health import ProcessIdentity


class LoadedIdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "backend").mkdir()
        self.db = self.root / "absent.db"
        self.names = []

    def module(self, suffix, source):
        name = "backend._identity_test_" + suffix
        path = self.root / "backend" / ("_identity_test_" + suffix + ".py")
        path.write_text(source)
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.names.append(name)
        self.addCleanup(lambda n=name: sys.modules.pop(n, None))
        spec.loader.exec_module(module)
        return path

    def test_stable_loaded_module_verified(self):
        self.module("stable", "def answer():\n return 42\n")
        identity = ProcessIdentity(self.root)
        self.assertTrue(identity.diagnose(self.db)["identity_verified"])

    def test_edit_after_import_before_identity_is_rejected(self):
        path = self.module("before", "def answer():\n return 42\n")
        path.write_text("def answer():\n return 43\n")
        identity = ProcessIdentity(self.root)
        health = identity.diagnose(self.db)
        self.assertFalse(health["identity_verified"])
        self.assertTrue(health["restart_required"])
        self.assertFalse(health["readiness"]["persistent_resume"])

    def test_edit_after_identity_is_rejected(self):
        path = self.module("after", "def answer():\n return 42\n")
        identity = ProcessIdentity(self.root)
        path.write_text("def answer():\n return 43\n")
        self.assertTrue(identity.diagnose(self.db)["restart_required"])

    def test_matching_late_import_is_accepted(self):
        identity = ProcessIdentity(self.root)
        self.module("late", "def answer():\n return 42\n")
        self.assertTrue(identity.diagnose(self.db)["identity_verified"])

    def test_divergent_late_import_is_rejected(self):
        identity = ProcessIdentity(self.root)
        path = self.module("divergent_late", "def answer():\n return 42\n")
        path.write_text("def answer():\n return 43\n")
        health = identity.diagnose(self.db)
        self.assertFalse(health["identity_verified"])
        self.assertTrue(health["restart_required"])

    def test_unverifiable_late_import_is_rejected(self):
        identity = ProcessIdentity(self.root)
        path = self.module("unverifiable_late", "def answer():\n return 42\n")
        path.unlink()
        health = identity.diagnose(self.db)
        self.assertFalse(health["identity_verified"])
        self.assertTrue(health["restart_required"])

    def test_change_during_initialization_is_rejected(self):
        self.module("during", "def answer():\n return 42\n")
        from backend import operational_health
        original = operational_health.backend_fingerprint
        count = [0]
        def changing(root):
            count[0] += 1
            if count[0] == 2:
                (self.root / "backend" / "_identity_test_during.py").write_text("def answer():\n return 43\n")
            return original(root)
        with patch.object(operational_health, "backend_fingerprint", side_effect=changing):
            identity = ProcessIdentity(self.root)
        self.assertFalse(identity.diagnose(self.db)["identity_verified"])

    def test_unreadable_source_fails_closed(self):
        path = self.module("missing", "def answer():\n return 42\n")
        identity = ProcessIdentity(self.root)
        path.unlink()
        health = identity.diagnose(self.db)
        self.assertFalse(health["identity_verified"])
        self.assertTrue(health["restart_required"])


if __name__ == "__main__":
    unittest.main()
