"""Optional subprocess bridge to a project-local MLX runtime, offline only."""
import json
import os
from pathlib import Path
import subprocess


class LocalProcessScorer:
    def __init__(self, python_path, model_path, timeout=60):
        # Keep the venv entrypoint: resolving its symlink would select the base
        # interpreter and discard the isolated environment's installed packages.
        self.python_path = str(Path(python_path).expanduser().absolute())
        self.model_path = str(Path(model_path).expanduser().resolve())
        if not Path(self.python_path).is_file() or not Path(self.model_path).is_dir():
            raise ValueError('Runtime e modelo locais devem existir')
        self.timeout = timeout

    def __call__(self, state, questions):
        body = json.dumps({'state': state, 'questions': questions}, ensure_ascii=False)
        if len(body.encode()) > 65536:
            raise ValueError('Entrada do Decision excede 64 KiB')
        env = dict(os.environ, HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
        worker = Path(__file__).with_name('decision_mlx.py')
        try:
            result = subprocess.run([self.python_path, str(worker), self.model_path], input=body, text=True,
                                    capture_output=True, timeout=self.timeout, env=env)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('Inferência local excedeu o prazo') from exc
        if result.returncode:
            # Do not expose prompts or customer data from dependency tracebacks.
            raise RuntimeError('Inferência local falhou; verifique runtime, modelo e limite de contexto')
        if len(result.stdout.encode()) > 262144:
            raise ValueError('Resposta local excede 256 KiB')
        return json.loads(result.stdout)


def configured_scorer():
    mode = os.environ.get('DECISION_MODE', 'off')
    if mode not in ('off', 'shadow', 'on'):
        raise ValueError('DECISION_MODE deve ser off, shadow ou on')
    if mode == 'off':
        return mode, None
    return mode, LocalProcessScorer(os.environ.get('DECISION_PYTHON', ''), os.environ.get('DECISION_MODEL_PATH', ''))
