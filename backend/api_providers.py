"""HTTP model adapters; credentials are resolved only from the backend environment."""
import json
import os
import re
import time
from urllib import request, error, parse


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # Never forward credentials to a redirect destination.


def validate(config):
    allowed = {'id', 'name', 'protocol', 'base_url', 'model', 'key_env', 'workspace_id', 'agent_id'}
    if not isinstance(config, dict) or set(config) - allowed:
        raise ValueError('Configuração inválida; use somente referência à variável de ambiente da chave.')
    c = {k: str(v).strip() for k, v in config.items()}
    if not re.fullmatch(r'(api-[a-z0-9-]{1,48}|tess)', c.get('id', '')):
        raise ValueError('ID deve começar com api- ou ser tess.')
    if c.get('protocol') not in ('tess', 'openai') or not c.get('name') or len(c['name']) > 100:
        raise ValueError('Nome ou protocolo inválido.')
    if any(len(v) > 1000 or any(ord(ch) < 32 for ch in v) for v in c.values()):
        raise ValueError('Campos inválidos.')
    url = parse.urlsplit(c.get('base_url', ''))
    if not url.hostname or url.username or url.password or url.query or url.fragment or (url.scheme != 'https' and not (url.scheme == 'http' and url.hostname in ('localhost', '127.0.0.1', '::1'))):
        raise ValueError('Use HTTPS ou HTTP em loopback, sem credenciais, query ou fragmento.')
    c['base_url'] = c['base_url'].rstrip('/')
    if c.get('key_env') and not re.fullmatch(r'[A-Z][A-Z0-9_]{0,99}', c['key_env']):
        raise ValueError('Informe o nome da variável de ambiente, nunca a chave.')
    if c['protocol'] == 'tess':
        if c['base_url'] != 'https://api.tess.im' or not c.get('key_env') or not all(re.fullmatch(r'[1-9][0-9]*', c.get(k, '')) for k in ('workspace_id', 'agent_id')):
            raise ValueError('Tess exige https://api.tess.im, variável de chave, workspace e agente numéricos.')
    elif not c.get('model'):
        raise ValueError('Informe o identificador do modelo.')
    return c


DEFAULT_TESS_API = {
    'id': 'tess',
    'name': 'Tess',
    'protocol': 'tess',
    'base_url': 'https://api.tess.im',
    'key_env': 'TESS_API_KEY',
    'workspace_id': '1518139',
    'agent_id': '3176'
}


class ApiAdapter:
    def __init__(self, config):
        self.config = validate(config)
        self.id = self.config['id']
        self.state = 'validation_required'

    def probe(self):
        c = self.config
        ready = not c.get('key_env') or bool(os.environ.get(c['key_env']))
        state = self.state if ready else 'authentication_required'
        auth = ('API Tess AI · Token ativo' if ready else 'Defina ' + c['key_env'] + ' no ambiente') if c.get('protocol') == 'tess' else ('API · chave no ambiente do backend' if ready else 'Defina ' + c['key_env'] + ' no backend')
        return {'id': self.id, 'name': c['name'], 'installed': True,
                'state': state,
                'auth': auth,
                'config': c, 'capabilities': {'read_only': False, 'write': True, 'streaming': False, 'api': True},
                'automatic_routing': True}

    def check(self):
        ready = not self.config.get('key_env') or bool(os.environ.get(self.config['key_env']))
        if not ready:
            self.state = 'authentication_required'
            return {'state': self.state, 'error': f"Defina {self.config.get('key_env', 'chave')} no ambiente."}
        try:
            if self.config['protocol'] == 'tess':
                self.http('/agents/' + self.config['agent_id'], None, time.monotonic() + 10)
            self.state = 'available'
            return {'state': 'available', 'ok': True}
        except error.HTTPError as exc:
            self.state = 'authentication_required' if exc.code in (401, 403) else 'failed'
            return {'state': self.state, 'error': f'API retornou HTTP {exc.code}.'}
        except Exception as exc:
            self.state = 'failed'
            return {'state': self.state, 'error': str(exc)}

    def http(self, path, payload, deadline):
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json', 'User-Agent': 'ai-orchestrator/1.0'}
        c = self.config
        if c.get('key_env'):
            key = os.environ.get(c['key_env'])
            if not key:
                raise PermissionError()
            headers['Authorization'] = 'Bearer '+key
        if c['protocol'] == 'tess':
            headers['x-workspace-id'] = c['workspace_id']
        req = request.Request(c['base_url']+path, headers=headers,
                              data=json.dumps(payload).encode() if payload is not None else None)
        with request.build_opener(NoRedirect()).open(req, timeout=max(.1, min(15, deadline-time.monotonic()))) as response:
            raw = response.read(8*1024*1024+1)
        if len(raw) > 8*1024*1024:
            raise ValueError()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        return value

    def chat_turn(self, messages, cancel, deadline):
        if cancel.is_set() or time.monotonic() >= deadline:
            raise TimeoutError('Operação cancelada ou tempo limite atingido.')
        c = self.config
        payload = {'messages': messages}
        if c.get('model'):
            payload['model'] = c['model']
        if c['protocol'] == 'tess':
            payload.update({'tools': 'no-tools', 'waitExecution': False})
            data = self.http('/agents/' + c['agent_id'] + '/execute', payload, deadline)
            responses = data.get('responses')
            if not isinstance(responses, list) or len(responses) != 1 or not isinstance(responses[0], dict):
                raise ValueError('Resposta do Tess em formato inesperado')
            item = responses[0]
            while item.get('status') in ('starting', 'running', 'pending', 'processing', 'queued'):
                response_id = str(item.get('id', ''))
                if not re.fullmatch(r'[0-9]+', response_id):
                    raise ValueError('ID de resposta Tess inválido')
                if cancel.wait(1) or time.monotonic() >= deadline:
                    raise TimeoutError('Operação cancelada ou tempo limite atingido.')
                item = self.http('/agent-responses/' + response_id, None, deadline)
            if item.get('status') != 'succeeded':
                raise ValueError('Execução do agente Tess não teve sucesso.')
            output = item.get('output', '')
            if not isinstance(output, str) or not output.strip():
                raise ValueError('Resposta vazia do modelo')
            self.state = 'available'
            return output, {}
        else:
            payload['stream'] = False
            data = self.http('/chat/completions', payload, deadline)
            choice = data['choices'][0]
            if choice.get('finish_reason') not in ('stop', 'tool_calls', None):
                raise ValueError('Modelo não concluiu a resposta normalmente.')
            result = choice['message']['content'] or ''
            raw_usage = data.get('usage') or {}
            usage = {}
            for source, dest in [('prompt_tokens', 'input_tokens'), ('completion_tokens', 'output_tokens')]:
                val = raw_usage.get(source)
                if type(val) in (int, float) and val >= 0:
                    usage[dest] = val
            if not isinstance(result, str) or not result.strip():
                raise ValueError('Resposta vazia do modelo')
            self.state = 'available'
            return result, usage

    def execute(self, prompt, cwd, on_event, cancel, timeout=600):
        deadline = time.monotonic()+timeout
        def stopped():
            return cancel.is_set() or time.monotonic() >= deadline
        status, result, usage, message = 'failed', '', {}, 'Resposta inválida ou falha de conexão com a API.'
        try:
            if stopped():
                return self.interrupted(cancel)
            result, usage = self.chat_turn([{'role': 'user', 'content': prompt}], cancel, deadline)
            if stopped():
                return self.interrupted(cancel)
            if not isinstance(result, str) or not result.strip():
                raise ValueError()
            status, message = 'completed', None
        except PermissionError:
            status, message = 'authentication_required', 'Chave ausente no ambiente do backend.'
        except error.HTTPError as exc:
            status = 'authentication_required' if exc.code in (401, 403) else 'rate_limited' if exc.code == 429 else 'failed'
            message = 'API retornou HTTP '+str(exc.code)+'. Verifique configuração, acesso e cota.'
        except (error.URLError, TimeoutError, OSError, ValueError, KeyError, IndexError, TypeError):
            pass  # Provider bodies and exception strings can contain secrets; never persist them.
        if stopped():
            return self.interrupted(cancel)
        self.state = 'available' if status == 'completed' else status
        if status == 'completed':
            on_event('message', {'text': result})
            if usage:
                on_event('usage', usage)
        return {'status': status, 'result': result if status == 'completed' else '', 'usage': usage, 'error': message}

    def execute_improvements(self, prompt, cwd, on_event, cancel, images=None):
        from backend.agent_engine import run_universal_agent
        return run_universal_agent(self, prompt, cwd, on_event, cancel, timeout=1200)

    def execute_visual(self, prompt, cwd, on_event, cancel, images=None):
        return self.execute(prompt, cwd, on_event, cancel, timeout=600)

    def execute_build(self, prompt, cwd, on_event, cancel):
        from backend.agent_engine import run_universal_agent
        return run_universal_agent(self, prompt, cwd, on_event, cancel, timeout=1200)

    @staticmethod
    def interrupted(cancel):
        return {'status': 'cancelled' if cancel.is_set() else 'interrupted', 'result': '', 'usage': {},
                'error': 'Espera local interrompida; a execução remota pode continuar.'}
