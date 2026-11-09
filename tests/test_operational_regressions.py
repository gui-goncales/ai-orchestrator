"""Regression coverage for read-only schema checks and real isolated HTTP startup."""
import json
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from backend.operational_health import REQUIRED_SCHEMA, ProcessIdentity, inspect_schema


class SchemaRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / "schema.sqlite"

    def create_schema(self, omitted=None, absent=None):
        omitted = omitted or {}
        with sqlite3.connect(self.db) as connection:
            for table, columns in REQUIRED_SCHEMA.items():
                if table == absent:
                    continue
                names = sorted(columns - set(omitted.get(table, ())))
                connection.execute("CREATE TABLE " + table + " (" + ", ".join('"' + name + '" TEXT' for name in names) + ")")

    def test_each_required_column_missing_is_detected(self):
        for table, columns in REQUIRED_SCHEMA.items():
            for column in sorted(columns):
                with self.subTest(table=table, column=column):
                    self.db.unlink(missing_ok=True)
                    self.create_schema({table: {column}})
                    before = self.db.read_bytes()
                    result = inspect_schema(self.db)
                    self.assertFalse(result["compatible"])
                    self.assertIn("Coluna ausente: " + table + "." + column, result["issues"])
                    self.assertEqual(before, self.db.read_bytes())

    def test_missing_table_and_simultaneous_incompatibilities(self):
        self.create_schema({"execution_states": {"version", "state"}}, absent="tool_actions")
        result = inspect_schema(self.db)
        self.assertFalse(result["compatible"])
        self.assertIn("Tabela ausente: tool_actions", result["issues"])
        self.assertIn("Coluna ausente: execution_states.version", result["issues"])
        self.assertIn("Coluna ausente: execution_states.state", result["issues"])

    def test_missing_database_is_not_created(self):
        self.assertFalse(inspect_schema(self.db)["compatible"])
        self.assertFalse(self.db.exists())


class RealServerStartup(unittest.TestCase):
    def test_isolated_server_health_ready_and_late_import(self):
        import urllib.request
        with tempfile.TemporaryDirectory() as folder:
            db = Path(folder) / "test.sqlite"
            sock = socket.socket()
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
            sock.close()
            script = (
                "import sys\n"
                "from backend.server import serve\n"
                "class SimulatedAdapter:\n"
                " def check(self, *args, **kwargs): return {'status':'disconnected'}\n"
                " def execute(self, *args, **kwargs): return {'status':'failed'}\n"
                "serve(port=int(sys.argv[1]), data=sys.argv[2], adapter=SimulatedAdapter())\n"
            )
            proc = subprocess.Popen([sys.executable, "-c", script, str(port), str(db)], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, cwd=str(Path(__file__).resolve().parents[1]))
            try:
                url = "http://127.0.0.1:" + str(port)
                def request(path):
                    req = urllib.request.Request(url + path, headers={"Host": "127.0.0.1:" + str(port)})
                    with urllib.request.urlopen(req, timeout=2) as response:
                        return json.load(response)
                deadline = time.monotonic() + 12
                while True:
                    if proc.poll() is not None:
                        self.fail("Isolated backend exited: " + proc.stderr.read().decode()[-2500:])
                    try:
                        health = request("/api/health")
                        break
                    except (OSError, TimeoutError):
                        if time.monotonic() > deadline:
                            self.fail("Isolated backend did not become ready")
                        time.sleep(.1)
                self.assertTrue(health["identity_verified"], health)
                self.assertFalse(health["restart_required"], health)
                self.assertEqual(health["readiness"]["status"], "ready", health)
                self.assertTrue(health["readiness"]["persistent_resume"])
                request("/api/browser-bridge/next")
                after = request("/api/health")
                self.assertTrue(after["identity_verified"], after)
                self.assertFalse(after["restart_required"], after)
                self.assertEqual(after["readiness"]["status"], "ready", after)
            finally:
                proc.terminate()
                try:
                    proc.communicate(timeout=8)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.communicate()


if __name__ == "__main__":
    unittest.main()
