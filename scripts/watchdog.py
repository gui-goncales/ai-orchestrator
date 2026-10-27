"""User-started local backend supervisor; no system privacy settings changed."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
PID=ROOT/'data'/'watchdog.pid'
child=None
stopping=False

def stop(*args):
    global stopping
    stopping=True
    if child is not None and child.poll() is None:child.terminate()

signal.signal(signal.SIGTERM,stop)
signal.signal(signal.SIGINT,stop)
PID.write_text(str(os.getpid()))
try:
    with open(ROOT/'data'/'service.log','a',buffering=1) as out,open(ROOT/'data'/'service-error.log','a',buffering=1) as err:
        while not stopping:
            child=subprocess.Popen([sys.executable,str(ROOT/'scripts'/'run-backend.py')],cwd=ROOT,stdout=out,stderr=err)
            while child.poll() is None:
                time.sleep(.5)
                if stopping:
                    child.terminate()
                    try:child.wait(timeout=8)
                    except subprocess.TimeoutExpired:child.kill()
            if not stopping:
                out.write('Supervisor: backend exited '+str(child.returncode)+'; restarting in 3s\n')
                time.sleep(3)
finally:
    PID.unlink(missing_ok=True)
