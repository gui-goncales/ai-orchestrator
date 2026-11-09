"""User-driven native directory selection on the backend's device."""
from pathlib import Path
import subprocess
import sys
import threading

_picker_lock = threading.Lock()


def choose_directory():
    if sys.platform != 'darwin':
        raise ValueError('O seletor nativo está disponível no aplicativo local para macOS.')
    if not _picker_lock.acquire(blocking=False):
        raise ValueError('Há um seletor de pastas aberto. Conclua ou cancele a seleção.')
    try:
        # Fixed script: no paths or user-controlled strings are evaluated as code.
        result = subprocess.run([
            '/usr/bin/osascript', '-e',
            'activate\nPOSIX path of (choose folder with prompt "Escolha a pasta para o AI Orchestrator")'
        ], capture_output=True, text=True, timeout=120)
        if result.returncode:
            if '-128' in result.stderr:
                return {'cancelled': True}
            raise ValueError('Não foi possível abrir o seletor de pastas. Confira as permissões do aplicativo no macOS.')
        directory = Path(result.stdout.strip()).resolve()
        if not result.stdout.strip() or not directory.is_dir():
            raise ValueError('A pasta selecionada não está disponível.')
        return {'cancelled': False, 'path': str(directory)}
    except subprocess.TimeoutExpired:
        raise ValueError('A seleção de pasta expirou. Clique em Escolher pasta para tentar novamente.') from None
    finally:
        _picker_lock.release()
