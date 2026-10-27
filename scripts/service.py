"""Manage only AI Orchestrator's per-user macOS LaunchAgent."""
import argparse
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
LABEL='com.local.ai-orchestrator'
PLIST=Path.home()/'Library'/'LaunchAgents'/(LABEL+'.plist')
DOMAIN='gui/'+str(os.getuid())
SERVICE=DOMAIN+'/'+LABEL


def configuration():
    paths=list(dict.fromkeys([str(Path(shutil.which('node') or '/usr/bin/node').parent),
                             str(Path(shutil.which('codex') or '/usr/bin/codex').parent),
                             '/opt/homebrew/bin','/usr/local/bin','/usr/bin','/bin','/usr/sbin','/sbin']))
    return {'Label':LABEL,'ProgramArguments':[sys.executable,str(ROOT/'scripts'/'run-backend.py')],
            'WorkingDirectory':str(ROOT),'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':10,
            'EnvironmentVariables':{'PATH':':'.join(paths),'PYTHONUNBUFFERED':'1','PYTHONPYCACHEPREFIX':str(ROOT/'data'/'pycache')},
            'StandardOutPath':str(ROOT/'data'/'service.log'),'StandardErrorPath':str(ROOT/'data'/'service-error.log')}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['install','status','restart','remove','plan']);args=parser.parse_args()
    if args.action=='plan':
        print(plistlib.dumps(configuration()).decode());return
    if args.action=='install':
        (ROOT/'data').mkdir(exist_ok=True)
        PLIST.parent.mkdir(parents=True,exist_ok=True)
        if PLIST.exists() and plistlib.loads(PLIST.read_bytes()).get('WorkingDirectory')!=str(ROOT):
            raise SystemExit('An existing service points to another workspace; refusing to replace it.')
        PLIST.write_bytes(plistlib.dumps(configuration()))
        subprocess.run(['launchctl','bootout',SERVICE],capture_output=True)
        subprocess.run(['launchctl','bootstrap',DOMAIN,str(PLIST)],check=True)
        print('Installed:',PLIST)
    elif args.action=='status':
        subprocess.run(['launchctl','print',SERVICE],check=True)
    elif args.action=='restart':
        subprocess.run(['launchctl','kickstart','-k',SERVICE],check=True)
    else:
        subprocess.run(['launchctl','bootout',SERVICE],capture_output=True)
        if PLIST.exists():
            if plistlib.loads(PLIST.read_bytes()).get('WorkingDirectory')!=str(ROOT):
                raise SystemExit('Service does not belong to this workspace.')
            PLIST.unlink()
        print('Service removed; SQLite data preserved.')

if __name__=='__main__':main()
