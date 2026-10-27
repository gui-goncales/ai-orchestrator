"""Isolated UI test backend. Never calls a provider or production database."""
from backend.server import serve

class FixtureAdapter:
    def probe(self):
        return {'id': 'codex', 'state': 'available', 'installed': True, 'auth': 'MOCK — teste isolado'}
    def execute(self, prompt, cwd, emit, cancel):
        emit('message', {'text': 'MOCK_UI_OK — resposta simulada, sem consumo de cota'})
        return {'status': 'completed', 'result': 'MOCK_UI_OK — resposta simulada, sem consumo de cota', 'usage': {}, 'error': None}

serve(8788, '/private/tmp/orchestrator-ui-test.sqlite3', FixtureAdapter())
