"""Pinned local CLIs. No cookie or credential parsing; no shell command input."""
import json
import os
import signal
import shlex
import re
import threading
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def binary(name):
    path = ROOT/'node_modules'/'.bin'/name
    return str(path) if path.is_file() else None


def run_local(args, cwd, cancel, timeout=300, env=None):
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        proc = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                stdout=stdout, stderr=stderr, start_new_session=True)
        start = time.monotonic()
        reason = None
        while proc.poll() is None:
            if cancel.wait(.1) or time.monotonic()-start > timeout:
                reason = 'cancelled' if cancel.is_set() else 'interrupted'
                try:
                    os.killpg(proc.pid, signal.SIGTERM)
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                except ProcessLookupError:
                    pass
                break
        stdout.seek(0)
        stderr.seek(0)
        raw = stdout.read(8*1024*1024+1)
        if len(raw) > 8*1024*1024:
            raise ValueError('Saída excedeu 8 MiB. Selecione um alvo menor; resultado não truncado silenciosamente.')
        # stderr intentionally not persisted: external CLI diagnostics may contain auth URLs.
        return proc.returncode, raw.decode('utf-8', errors='replace'), reason


class GeminiAdapter:
    id = 'gemini'
    def __init__(self):
        self.state = 'authentication_required'
    def probe(self):
        return {'id': self.id, 'installed': bool(binary('gemini')), 'state': self.state if binary('gemini') else 'offline',
                'auth': 'Google · execução validada' if self.state == 'available' else 'Login Google / validação necessária',
                'capabilities': {'read_only': True, 'streaming': False, 'automatic_failover': False, 'write': False}}
    @staticmethod
    def parse(raw, code):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return {'status': 'failed', 'result': '', 'usage': {}, 'error': 'Gemini não retornou JSON válido; conclua o login oficial e tente novamente.'}
        if value.get('error'):
            error = value['error']
            return {'status': 'authentication_required' if error.get('type') in ('AuthenticationError','AuthError') or error.get('code') in (401,'unauthorized') else 'failed', 'result': '', 'usage': {}, 'error': 'Gemini: '+str(error.get('type', error.get('code','erro do provedor')))}
        usage = {}
        models = value.get('stats', {}).get('models', {})
        if models:
            for dest, source in [('input_tokens','input'),('output_tokens','candidates'),('cached_input_tokens','cached')]:
                vals = [m.get('tokens', {}).get(source) for m in models.values()]
                if vals and all(isinstance(v, (int,float)) for v in vals):
                    usage[dest] = sum(vals)
        result = value.get('response', '')
        return {'status': 'completed' if code == 0 and result else 'failed', 'result': result, 'usage': usage,
                'error': None if code == 0 and result else 'Gemini encerrou sem resposta completa.'}
    def execute(self, prompt, cwd, on_event, cancel, timeout=600):
        if not binary('gemini'):
            return {'status': 'failed', 'result': '', 'usage': {}, 'error': 'Gemini CLI não instalado; execute npm ci na raiz.'}
        env = dict(os.environ)
        for key in ('GEMINI_API_KEY','GOOGLE_API_KEY','GOOGLE_GENAI_USE_VERTEXAI','GOOGLE_GENAI_USE_GCA'):
            env.pop(key, None)
        code, raw, reason = run_local([binary('gemini'), '--approval-mode', 'plan', '--output-format', 'json', '--prompt', prompt], cwd, cancel, timeout, env)
        if reason:
            return {'status': reason, 'result': '', 'usage': {}, 'error': 'Execução interrompida.'}
        parsed = self.parse(raw, code)
        self.state = 'available' if parsed['status'] == 'completed' else parsed['status']
        if parsed['result']:
            on_event('message', {'text': parsed['result']})
        if parsed['usage']:
            on_event('usage', parsed['usage'])
        return parsed


class ReaAdapter:
    id = 'rea'
    # Only static, non-executing commands are exposed by the application.
    commands = {'javascript': 'analyze-javascript-application', 'macho': 'inspect-macho', 'elf': 'inspect-binary-layout'}
    def probe(self):
        return {'id': self.id, 'installed': bool(binary('rea')), 'state': 'available' if binary('rea') else 'offline',
                'auth': 'Motor local · sem conta', 'capabilities': {'static_analysis': True, 'target_execution': False}}
    @classmethod
    def target(cls, spec, cwd):
        if spec.get('kind') not in cls.commands:
            raise ValueError('Tipo REA não suportado')
        root = Path(cwd).resolve()
        target = Path(spec.get('target', '')).expanduser()
        if not target.is_absolute():
            target = root/target
        target = target.resolve()
        if not target.exists() or not target.is_relative_to(root):
            raise ValueError('Alvo REA deve existir dentro do projeto registrado, inclusive após resolver symlinks.')
        if spec['kind'] == 'javascript' and not (target.is_dir() or target.suffix == '.asar'):
            raise ValueError('Selecione um diretório de aplicativo JavaScript ou ASAR.')
        return target
    def execute(self, spec, cwd, on_event, cancel, timeout=300):
        if not binary('rea'):
            raise ValueError('REA não instalado; execute npm ci na raiz.')
        target = self.target(spec, cwd)
        args = [binary('rea'), self.commands[spec['kind']], str(target), '--format', 'json', '--full-output']
        code, raw, reason = run_local(args, cwd, cancel, timeout)
        if reason:
            return {'status': reason, 'result': '', 'usage': {}, 'error': 'Análise REA interrompida.'}
        # Do not invent evidence IDs or equate CLI exit with successful analysis.
        try:
            evidence = json.loads(raw)
        except json.JSONDecodeError:
            raise ValueError('REA não retornou Evidence JSON válido.')
        failed = code != 0 or evidence.get('ok') is False or evidence.get('isError') or evidence.get('error') or evidence.get('success') is False
        result = json.dumps(evidence, ensure_ascii=False, indent=2)
        on_event('rea_evidence', {'target': str(target), 'kind': spec['kind'], 'evidence': evidence})
        on_event('message', {'text': result})
        return {'status': 'failed' if failed else 'completed', 'result': result, 'usage': {},
                'error': 'REA retornou uma limitação ou erro; consulte Evidence.' if failed else None}


REA_STAGES = (
    ('research', 'RESEARCH: pesquise o objetivo usando fontes disponíveis e arquivos autorizados do projeto (você pode inspecionar arquivos existentes com as ferramentas de leitura do workspace: list_dir, read_file, find_files). Registre fontes e evidências verificáveis; não invente navegação ou resultados. Separe observado, inferido e desconhecido.'),
    ('evaluate', 'EVALUATE: avalie as evidências anteriores. Compare alternativas, riscos, limitações, compatibilidade e esforço. Classifique suporte como comprovado, parcial, pendente ou não suportado. Não invente testes.'),
    ('architect', 'ARCHITECT: proponha arquitetura e plano incremental fundamentados na pesquisa e avaliação. Inclua interfaces, segurança, persistência, testes e critérios de aceitação. Não implemente nem altere arquivos.'),
)

class AntigravityAdapter:
    id = 'antigravity'
    def __init__(self):
        self.state = 'authentication_required'
        self.auth_lock = threading.Lock()
        self.session_ready = False
        self.connection_error = None
        self.execution_validated = False
    @staticmethod
    def path():
        p=ROOT/'tools'/'bin'/'agy'
        return str(p) if p.is_file() else None
    def probe(self):
        return {'id': self.id, 'installed': bool(self.path()), 'state': self.state if self.path() else 'offline',
                'login_command': shlex.quote(self.path()) if self.path() else None,
                'session_ready': self.session_ready, 'execution_validated': self.execution_validated, 'connection_error': self.connection_error,
                'auth': 'Google · Gemini via Antigravity' if self.state == 'available' else 'Login Google / validação necessária',
                'capabilities': {'read_only': True, 'streaming': False, 'write': False, 'automatic_failover': False}}
    def check_auth(self, explicit=False):
        if not self.auth_lock.acquire(blocking=False):
            return self.probe()
        try:
            if not self.path():
                self.state = 'offline'
                self.session_ready = False
                self.connection_error = 'Antigravity não está instalado.'
                return self.probe()
            env = dict(os.environ)
            for key in ('GEMINI_API_KEY','GOOGLE_API_KEY','GOOGLE_GENAI_USE_VERTEXAI','GOOGLE_GENAI_USE_GCA'):
                env.pop(key, None)
            try:
                # Official read-only command. No prompt, generation, credential file, or stderr export.
                value = subprocess.run([self.path(), 'models'], cwd=ROOT, env=env, stdin=subprocess.DEVNULL,
                                       capture_output=True, text=True, timeout=15)
                rows = value.stdout.splitlines()
                catalog = [line for line in rows if re.fullmatch(r'[a-z0-9][a-z0-9._-]+\t[^\t\r\n]+', line)]
                self.session_ready = value.returncode == 0 and bool(catalog)
                failed_execution = self.state in ('failed', 'rate_limited', 'authentication_required', 'interrupted') and self.connection_error is not None
                if explicit:
                    failed_execution = False
                self.state = (self.state if failed_execution else 'available') if self.session_ready else 'validation_required'
                self.connection_error = self.connection_error if self.session_ready and failed_execution else None if self.session_ready else 'A CLI não confirmou acesso aos modelos. Abra o Antigravity e verifique o login.'
            except (OSError, subprocess.TimeoutExpired):
                self.session_ready = False
                self.state = 'validation_required'
                self.connection_error = 'Não foi possível verificar a CLI agora. Tente novamente.'
            return self.probe()
        finally:
            self.auth_lock.release()

    @staticmethod
    def parse(raw, code):
        try:
            value=json.loads(raw)
        except json.JSONDecodeError:
            return {'status':'authentication_required' if code else 'failed','result':'','usage':{},'error':'Sem envelope JSON; conclua o login oficial com tools/bin/agy.'}
        if not isinstance(value,dict):
            return {'status':'failed','result':'','usage':{},'error':'Antigravity retornou envelope inválido.'}
        structured=value.get('structured_output')
        if isinstance(structured,dict) and isinstance(structured.get('report'),str) and structured['report'].strip():
            value['response']=structured['report']
        status=value.get('status')
        state='completed' if code==0 and status=='SUCCESS' and value.get('response') else 'authentication_required' if status=='AUTHENTICATION_REQUIRED' else 'failed'
        usage={k:v for k,v in value.get('usage',{}).items() if k in ('input_tokens','output_tokens','thinking_tokens','total_tokens') and isinstance(v,(int,float))}
        if isinstance(value.get('usage',{}).get('cache_read_tokens'),(int,float)):
            usage['cached_input_tokens']=value['usage']['cache_read_tokens']
        return {'status':state,'result':value.get('response',''),'usage':usage,'error':None if state=='completed' else ('Antigravity encerrou com SUCCESS, mas sem resposta pública. Nenhuma etapa foi confirmada; retome após verificar o diagnóstico.' if status=='SUCCESS' and not value.get('response') else 'Antigravity: '+str(status or 'execução incompleta'))}
    @classmethod
    def parse_stream(cls,raw,code):
        final=None
        public=[]
        types=set()
        for line in raw.splitlines():
            try:
                event=json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event,dict):
                continue
            if event.get('event')=='result' and isinstance(event.get('result'),dict):
                final=event['result']
            elif event.get('event')=='step_update':
                step=event.get('step_update',{})
                types.add(step.get('step_type','unknown'))
                # Never expose reasoning, tool arguments, or internal planning text.
                if step.get('step_type')=='agent_response' and isinstance(step.get('text_delta'),str):
                    public.append(step['text_delta'])
            elif 'status' in event:
                final=event  # Accept legacy single-object fixtures too.
        final=dict(final or {'status':'ERROR'})
        if not final.get('response') and public:
            final['response']=''.join(public)
        diagnostic={'status':final.get('status'),'exit_code':code,
                    'public_response_characters':len(final.get('response') or ''),
                    'public_fragments':len(public),'step_types':sorted(types),
                    'conversation_id':final.get('conversation_id'),
                    'structured_output_present':isinstance(final.get('structured_output'),dict),
                    'response_source':'result' if not public or final.get('response')!=''.join(public) else 'public_agent_response'}
        return cls.parse(json.dumps(final),code),diagnostic

    def execute_report(self,prompt,cwd,on_event,cancel):
        return self.execute(prompt,cwd,on_event,cancel,report=True)

    def execute_improvements(self,prompt,cwd,on_event,cancel,images=None):
        return self.execute(prompt,cwd,on_event,cancel,timeout=1200)

    def execute_visual(self,prompt,cwd,on_event,cancel,images=None):
        return self.execute(prompt,cwd,on_event,cancel,timeout=600)

    def execute_build(self,prompt,cwd,on_event,cancel):
        return self.execute(prompt,cwd,on_event,cancel,timeout=1200)

    def execute(self,prompt,cwd,on_event,cancel,timeout=600,report=False):
        if not self.path():
            raise ValueError('Antigravity CLI não instalado')
        env=dict(os.environ)
        for key in ('GEMINI_API_KEY','GOOGLE_API_KEY','GOOGLE_GENAI_USE_VERTEXAI','GOOGLE_GENAI_USE_GCA'):
            env.pop(key,None)
        args=[self.path(),'--mode','plan','--disable-slash-commands','--output-format','stream-json']
        if report:
            schema={'type':'object','properties':{'report':{'type':'string','minLength':1}},'required':['report'],'additionalProperties':False}
            args+=['--json-schema',json.dumps(schema)]
        args+=['--print',prompt]
        code,raw,reason=run_local(args,cwd,cancel,timeout,env)
        if reason:
            return {'status':reason,'result':'','usage':{},'error':'Execução interrompida.'}
        parsed, diagnostic=self.parse_stream(raw,code)
        on_event('provider_diagnostic',diagnostic)
        self.state='available' if parsed['status']=='completed' else parsed['status']
        self.execution_validated = parsed['status']=='completed'
        self.connection_error = None if self.execution_validated else parsed.get('error') or 'Execução não validada.'
        if parsed['result']:on_event('message',{'text':parsed['result']})
        if parsed['usage']:on_event('usage',parsed['usage'])
        return parsed
