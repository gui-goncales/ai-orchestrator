"""Start a detached backend supervisor from an authorized terminal/application."""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
try:
    with urllib.request.urlopen('http://127.0.0.1:8787/api/health',timeout=3) as response:
        if json.load(response).get('app')=='ai-orchestrator':
            print('Backend already online.');raise SystemExit(0)
except (OSError,ValueError):pass
(ROOT/'data').mkdir(exist_ok=True)
pidfile=ROOT/'data'/'watchdog.pid'
if pidfile.exists():
    try:
        os.kill(int(pidfile.read_text()),0)
        raise SystemExit('Supervisor already exists; inspect data/service-error.log.')
    except (ProcessLookupError,ValueError):pidfile.unlink(missing_ok=True)
env=dict(os.environ);env['PYTHONUNBUFFERED']='1';env['PYTHONPYCACHEPREFIX']=str(ROOT/'data'/'pycache')
with open(ROOT/'data'/'supervisor.log','a') as log:
    child=subprocess.Popen([sys.executable,str(ROOT/'scripts'/'watchdog.py')],cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True,close_fds=True)
print('Supervisor started:',child.pid)
