"""Account login stays in a dedicated browser profile; no API tokens or cookie export."""
import json
import os
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from urllib.parse import urlsplit
from backend.integrations import ROOT

PROFILES = ROOT/'data'/'browser-profiles'
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
DEFAULT_TESS = {'id': 'web-tess', 'name': 'Tess', 'login_url': 'https://tess.im/pt-BR/login',
                'chat_url': 'https://tess.im/pt-BR/chat',
                'input_selector': '#chat_input_textarea, #chat-textarea-input',
                'send_selector': 'button.template_send_message_button',
                'response_selector': '.chat-content-assistant-message[data-error-only="false"]',
                'busy_selector': 'button.template_stop_message_button, .chat-assistant-message[data-stream-active], .chat-content.is-streaming, .chat-assistant-message .loading-info.thinking'}


DEFAULT_CHATGPT = {
    'id': 'web-chatgpt', 'name': 'ChatGPT · navegador',
    'transport': 'extension', 'extension_id': '',
    'login_url': 'https://chatgpt.com', 'chat_url': 'https://chatgpt.com',
    'input_selector': '[contenteditable="true"][data-composer-markdown], #prompt-textarea',
    'send_selector': '',
    'response_selector': '[data-markdown-text-style="assistant-message"], [data-message-author-role="assistant"] .markdown',
    'busy_selector': '[data-testid="stop-button"], button[aria-label="Stop generating"], button[aria-label="Stop response"], button[aria-label="Parar geração"], button[aria-label="Parar resposta"]',
}


def validate(config):
    fields = set(DEFAULT_TESS) | {'transport', 'extension_id'}
    if not isinstance(config, dict) or set(config)-fields or any(not isinstance(v, str) for v in config.values()):
        raise ValueError('Configuração de sessão inválida.')
    c = {key: config.get(key, '').strip() for key in fields}
    if not re.fullmatch(r'web-[a-z0-9-]{1,48}', c['id']) or not c['name'] or len(c['name'])>100:
        raise ValueError('ID deve começar com web-; informe um nome de até 100 caracteres.')
    for key in ('login_url', 'chat_url'):
        u = urlsplit(c[key])
        if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment:
            raise ValueError('Use URLs HTTPS sem credenciais, query ou fragmento.')
    if urlsplit(c['login_url']).netloc != urlsplit(c['chat_url']).netloc:
        raise ValueError('Login inicial e conversa devem pertencer ao mesmo site; redirecionamentos de login são feitos pelo navegador.')
    if any(len(v)>1000 or any(ord(ch)<32 for ch in v) for v in c.values()):
        raise ValueError('Campo inválido.')
    if c['id']=='web-chatgpt':
        if urlsplit(c['login_url']).hostname != 'chatgpt.com':
            raise ValueError('A conexão ChatGPT deve usar chatgpt.com.')
        c['transport'] = c['transport'] or 'extension'
        if c['transport'] not in ('extension', 'dedicated'):
            raise ValueError('Transporte ChatGPT inválido.')
        if c['extension_id'] and not re.fullmatch('[a-p]{32}', c['extension_id']):
            raise ValueError('ID da extensão deve conter 32 letras de a até p.')
        for key in ('input_selector', 'response_selector', 'busy_selector'):
            if not c[key]:
                c[key] = DEFAULT_CHATGPT[key]
    if c['id'] != 'web-chatgpt':
        c.pop('transport', None)
        c.pop('extension_id', None)
    if c['id']=='web-tess' and urlsplit(c['login_url']).hostname!='tess.im':
        raise ValueError('A conexão Tess deve usar tess.im.')
    return c


class WebAdapter:
    # Browser conversations retain earlier turns on the provider's page.
    retains_conversation = True
    def __init__(self, config):
        self.config = validate(config)
        self.id = self.config['id']
        self.state = 'authentication_required'
        self.session_ready = False
        self.controls_mapped = False
        self.execution_validated = False
        self.connection_error = None
        self.operation = threading.Lock()

    @property
    def profile(self):
        return PROFILES/self.id[4:]

    def endpoint(self):
        try:
            port = int((self.profile/'DevToolsActivePort').read_text().splitlines()[0])
            if 0<port<65536:
                return 'http://127.0.0.1:'+str(port)
        except (OSError, ValueError, IndexError):
            pass
        return None

    def probe(self):
        return {'id': self.id, 'name': self.config['name'], 'installed': bool(shutil.which('node') and Path(CHROME).is_file()),
                'state': self.state, 'auth': 'Login da conta · sessão no Chrome dedicado',
                'config': self.config, 'session_ready': self.session_ready, 'controls_mapped': self.controls_mapped,
                'execution_validated': self.execution_validated, 'connection_error': self.connection_error, 'automatic_routing': True,
                'capabilities': {'read_only': True, 'write': False, 'streaming': False, 'browser_session': True}}

    def open_login(self):
        if not self.operation.acquire(blocking=False):
            raise ValueError('Sessão ocupada por outra operação.')
        try:
            if self.config.get('transport') == 'extension':
                subprocess.Popen(['open', '-a', 'Google Chrome', self.config['login_url']], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return {'ok': True, 'message': 'No Chrome normal, entre no ChatGPT e use Conectar esta aba na extensão AI Orchestrator. Não use a janela com depuração remota para login Google.'}
            self.profile.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.profile.chmod(0o700)
            if not Path(CHROME).is_file():
                raise ValueError('Google Chrome não encontrado neste macOS.')
            # Chrome reuses this dedicated profile if it is already open.
            subprocess.Popen([CHROME, '--user-data-dir='+str(self.profile), '--remote-debugging-address=127.0.0.1',
                              '--remote-debugging-port=0', '--no-first-run', '--no-default-browser-check', self.config['login_url']],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)
            self.state = 'authentication_required'
            self.session_ready = False
            return {'ok': True, 'message': 'Entre na janela dedicada e abra uma conversa vazia. Depois clique em Verificar sessão.'}
        finally:
            self.operation.release()

    def command(self, action, cancel, prompt='', timeout=30):
        if self.config.get('transport') == 'extension':
            if not self.config.get('extension_id'):
                return {'status': 'authentication_required', 'session_ready': False, 'controls_mapped': False, 'result': '', 'usage': {}, 'error': 'Instale a extensão local, conecte a aba ChatGPT e informe o ID em Ajustar conexão.'}
            from backend.browser_bridge import bridge
            return bridge.request(self.config['extension_id'], action, prompt, cancel, timeout)
        endpoint = self.endpoint()
        if not endpoint:
            return {'status': 'authentication_required', 'result': '', 'usage': {}, 'error': 'Abra o login no navegador dedicado.'}
        node = shutil.which('node')
        if not node:
            raise ValueError('Node não encontrado.')
        # Prompt travels over stdin, never argv, logs, browser storage exports, or a public CDP port.
        from tempfile import TemporaryFile
        with TemporaryFile() as incoming, TemporaryFile() as outgoing:
            incoming.write(json.dumps({'action': action, 'endpoint': endpoint, 'config': self.config, 'prompt': prompt,
                                       'timeout_ms': max(1000, (timeout-2)*1000)}).encode());incoming.seek(0)
            proc = subprocess.Popen([node, str(ROOT/'scripts'/'web-session.cjs')], cwd=ROOT, stdin=incoming,
                                    stdout=outgoing, stderr=subprocess.DEVNULL, start_new_session=True)
            start = time.monotonic()
            while proc.poll() is None:
                if cancel.wait(.1) or time.monotonic()-start>timeout:
                    proc.terminate()
                    try: proc.wait(timeout=3)
                    except subprocess.TimeoutExpired: proc.kill();proc.wait()
                    return {'status': 'cancelled' if cancel.is_set() else 'interrupted', 'result': '', 'usage': {},
                            'error': 'Espera local interrompida; confira a conversa antes de retomar para não duplicar o envio.'}
            outgoing.seek(0)
            try:
                result=json.loads(outgoing.read(8*1024*1024+1))
                if not isinstance(result,dict): raise ValueError()
                return result
            except (ValueError, TypeError):
                return {'status':'failed','result':'','usage':{},'error':'Não foi possível controlar a sessão. Reabra o login.'}

    def check(self):
        if not self.operation.acquire(blocking=False):
            raise ValueError('Sessão ocupada por outra operação.')
        try:
            result = self.command('check', threading.Event())
            for key, value in (result.get('suggested_config') or {}).items():
                if key in ('input_selector', 'response_selector', 'busy_selector') and not self.config.get(key):
                    self.config[key] = value
            self.session_ready = result.get('session_ready', False)
            self.controls_mapped = bool(result.get('controls_mapped')) and all(self.config.get(k) for k in ('input_selector', 'response_selector', 'busy_selector'))
            self.connection_error = result.get('error')
            self.state = ('available' if self.controls_mapped else 'validation_required') if self.session_ready else ('session_closed' if result.get('reason') in ('browser_unavailable', 'conversation_missing') else 'authentication_required')
            return {**result, 'state': self.state, 'execution_validated': self.execution_validated}
        finally:
            self.operation.release()

    def execute(self, prompt, cwd, on_event, cancel, timeout=600):
        if not self.operation.acquire(blocking=False):
            return {'status':'failed','result':'','usage':{},'error':'Sessão ocupada.'}
        try:
            result = self.command('execute', cancel, prompt, timeout)
            self.state = 'available' if result.get('status')=='completed' else result.get('status','failed')
            self.execution_validated = result.get('status')=='completed'
            if result.get('status') == 'session_closed':
                result['status'] = 'authentication_required'
            if result.pop('submitted', False):
                on_event('browser_submission', {'provider': self.id, 'confirmed': True,
                         'warning': 'Envio pela interface; cancelar localmente não cancela a geração remota.'})
            if result.get('status')=='completed':
                on_event('message', {'text': result['result']})
            return {key: result.get(key, default) for key, default in [('status', 'failed'), ('result', ''), ('usage', {}), ('error', None)]}
        finally:
            self.operation.release()
