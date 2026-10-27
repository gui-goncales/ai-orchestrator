"""In-memory jobs relayed by the local UI to a user-installed Chrome extension."""
import threading
import time
import uuid


class BrowserBridge:
    def __init__(self):
        self.lock = threading.Lock()
        self.jobs = {}

    def request(self, extension_id, action, prompt, cancel, timeout):
        job_id = uuid.uuid4().hex
        job = {'id': job_id, 'extension_id': extension_id, 'action': action,
               'prompt': prompt, 'timeout_ms': min(max(int(timeout * 1000) - 2000, 1000), 180000)}
        entry = {'job': job, 'dispatched': False, 'result': None, 'done': threading.Event()}
        with self.lock:
            self.jobs[job_id] = entry
        try:
            deadline = time.monotonic() + timeout
            while not entry['done'].wait(.1):
                if cancel.is_set() or time.monotonic() >= deadline:
                    return {'status': 'cancelled' if cancel.is_set() else 'interrupted',
                            'result': '', 'usage': {}, 'error': 'Extensão não confirmou o resultado. Mantenha o orquestrador aberto e confira a aba antes de reenviar.'}
            return entry['result']
        finally:
            with self.lock:
                self.jobs.pop(job_id, None)

    def next_job(self):
        with self.lock:
            for entry in self.jobs.values():
                if not entry['dispatched']:
                    entry['dispatched'] = True
                    return entry['job']
        return None

    def complete(self, job_id, result):
        if not isinstance(result, dict) or result.get('status') not in (
                'completed', 'failed', 'authentication_required', 'session_closed', 'interrupted', 'validation_required'):
            raise ValueError('Resultado de navegador inválido')
        if not isinstance(result.get('result', ''), str):
            raise ValueError('Resposta inválida')
        with self.lock:
            entry = self.jobs.get(job_id)
            if not entry or entry['done'].is_set():
                return False
            entry['result'] = result
            entry['done'].set()
        return True


bridge = BrowserBridge()
