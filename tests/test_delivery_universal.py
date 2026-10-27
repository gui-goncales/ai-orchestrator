"""Integration tests for universal delivery and improvement workflows with any model."""
import json
import tempfile
import threading
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from backend.core import Store, Supervisor
from backend.api_providers import ApiAdapter


class UniversalDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.store = Store(str(self.root / 'test.sqlite3'), str(self.root))
        self.supervisor = Supervisor(self.store)

    def tearDown(self):
        self.tmp.cleanup()

    def test_api_adapter_universal_delivery_builds_real_artifact(self):
        # Configure Tess as an ApiAdapter
        config = {
            'id': 'tess',
            'name': 'Tess API Model',
            'protocol': 'openai',
            'base_url': 'http://127.0.0.1:11434/v1',
            'model': 'gpt-4o',
            'key_env': 'TESS_API_KEY'
        }
        adapter = ApiAdapter(config)
        adapter.state = "available"
        self.supervisor.adapters['tess'] = adapter

        # Create deliver task with tess provider
        task_id = self.store.create(
            objective='Criar jogo de navegação 3D em HTML5 e JS',
            project='local',
            provider='tess',
            key='task-universal-deliver',
            workflow='deliver'
        )

        # Simulate REA research, evaluate, architect already confirmed in task_steps
        with self.store.connect() as db:
            db.execute("INSERT INTO task_steps VALUES(?, 'research', 'Pesquisa confirmada', '2026-10-27T00:00:00Z')", (task_id,))
            db.execute("INSERT INTO task_steps VALUES(?, 'evaluate', 'Avaliação confirmada', '2026-10-27T00:01:00Z')", (task_id,))
            db.execute("INSERT INTO task_steps VALUES(?, 'architect', 'Arquitetura confirmada', '2026-10-27T00:02:00Z')", (task_id,))

        turn_count = 0
        def fake_chat_turn(messages, cancel, deadline):
            nonlocal turn_count
            turn_count += 1
            if turn_count == 1:
                # Agent creates index.html and main.js using workspace tools
                return (
                    'Vou criar o arquivo index.html agora.\n'
                    '<tool_call name="write_file">\n'
                    '<path>index.html</path>\n'
                    '<content><!DOCTYPE html><html><head><title>Game</title></head><body><div id="game"></div><script type="module" src="main.js"></script></body></html></content>\n'
                    '</tool_call>\n'
                    '<tool_call name="write_file">\n'
                    '<path>main.js</path>\n'
                    '<content>console.log("Game initialized");\nwindow.__gameTest = { getState: () => ({ score: 0 }) };\n</content>\n'
                    '</tool_call>',
                    {'prompt_tokens': 200, 'completion_tokens': 100}
                )
            elif turn_count == 2:
                # Agent calls finish
                return (
                    '<tool_call name="finish">\n'
                    '<summary>MVP implementado com index.html e main.js funcionais.</summary>\n'
                    '</tool_call>',
                    {'prompt_tokens': 250, 'completion_tokens': 30}
                )
            return ('Pronto', {})

        with patch.object(adapter, 'chat_turn', side_effect=fake_chat_turn):
            executed = self.supervisor.run_once()
            self.assertTrue(executed)

        task = self.store.task(task_id)
        self.assertEqual(task['status'], 'completed')
        self.assertIn('Artefato:', task['result'])

        # Verify real files on disk
        from backend.artifacts import OUTPUT
        artifact_dir = OUTPUT / task_id
        self.assertTrue((artifact_dir / 'index.html').is_file())
        self.assertTrue((artifact_dir / 'main.js').is_file())
        self.assertIn('window.__gameTest', (artifact_dir / 'main.js').read_text())

        # Verify SQLite steps recorded
        with self.store.connect() as db:
            steps = {r[0] for r in db.execute("SELECT stage FROM task_steps WHERE task_id=?", (task_id,))}
            self.assertIn('implement', steps)
            self.assertIn('validate', steps)

    def test_api_adapter_universal_improvements_edits_candidate_artifact(self):
        config = {
            'id': 'tess',
            'name': 'Tess API Model',
            'protocol': 'openai',
            'base_url': 'http://127.0.0.1:11434/v1',
            'model': 'gpt-4o',
            'key_env': 'TESS_API_KEY'
        }
        adapter = ApiAdapter(config)
        adapter.state = "available"
        self.supervisor.adapters['tess'] = adapter

        # Prepare base artifact
        from backend.artifacts import workspace, prepare, validate
        from backend.visual_review import fingerprint
        base_id = 'a1b2c3d4e5f6'
        base_dir = workspace(base_id)
        prepare({'id': base_id, 'objective': 'Base game'}, [])
        (base_dir / 'index.html').write_text('<!DOCTYPE html><html><body><h1>Game</h1><script src="main.js"></script></body></html>')
        (base_dir / 'main.js').write_text('let speed = 5;\nconsole.log(speed);\n')
        manifest = validate(base_dir)

        with self.store.connect() as db:
            db.execute("INSERT OR REPLACE INTO artifacts VALUES(?, ?, ?, '2026-10-27T00:00:00Z')",
                       (base_id, str(base_dir), json.dumps(manifest)))

        base_hash = fingerprint(base_dir)
        review_id = 'r1r2r3r4r5r6'
        with self.store.connect() as db:
            db.execute("INSERT OR REPLACE INTO tasks VALUES(?, 'local', 'Review', 'codex', 'completed', 'report', '{}', NULL, '2026-10-27T00:00:00Z', '2026-10-27T00:00:00Z', 'visual_review', ?, '', '{}', '{}', '{}', 'unreviewed')",
                       (review_id, json.dumps({'parent_id': base_id, 'artifact_digest': base_hash})))
            report = {'images': [], 'page_errors': []}
            db.execute("INSERT OR REPLACE INTO visual_reviews VALUES(?, ?, ?, 'P1 | desktop.png | low speed | Aumentar velocidade | speed > 10', '2026-10-27T00:00:00Z')",
                       (review_id, base_id, json.dumps(report)))

        # Request improvements
        improve_task_id = self.store.create(
            objective='Melhorar velocidade',
            project='local',
            provider='tess',
            key='improve-task-key',
            workflow='improve',
            spec={
                'parent_id': base_id,
                'review_id': review_id,
                'base_path': str(base_dir),
                'base_hash': base_hash,
                'proposals': [{'id': 'prop1', 'proposal': 'Aumentar velocidade'}],
                'feedback': 'Aumente speed para 10'
            }
        )

        with self.store.connect() as db:
            db.execute("INSERT INTO revisions(task_id, parent_id, source_review_id, base_path, base_hash, status, created_at) VALUES(?, ?, ?, ?, ?, 'queued', '2026-10-27T00:00:00Z')",
                       (improve_task_id, base_id, review_id, str(base_dir), base_hash))

        def fake_improve_turn(messages, cancel, deadline):
            return (
                'Aplicando melhoria via edit_file:\n'
                '<tool_call name="edit_file">\n'
                '<path>main.js</path>\n'
                '<target>let speed = 5;</target>\n'
                '<replacement>let speed = 10;</replacement>\n'
                '</tool_call>\n'
                '<tool_call name="finish">\n'
                '<summary>Velocidade ajustada para 10.</summary>\n'
                '</tool_call>',
                {'prompt_tokens': 100, 'completion_tokens': 50}
            )

        with patch.object(adapter, 'chat_turn', side_effect=fake_improve_turn):
            executed = self.supervisor.run_once()
            self.assertTrue(executed)

        task = self.store.task(improve_task_id)
        self.assertEqual(task['status'], 'completed')

        from backend.artifacts import OUTPUT
        candidate_dir = OUTPUT / improve_task_id
        self.assertTrue((candidate_dir / 'main.js').is_file())
        self.assertIn('let speed = 10;', (candidate_dir / 'main.js').read_text())
        # Base version should remain untouched
        self.assertIn('let speed = 5;', (base_dir / 'main.js').read_text())


if __name__ == '__main__':
    unittest.main()
