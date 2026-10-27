import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.core import Store,Supervisor
from backend.artifacts import inventory,validate,workspace
from test_core import Fake

class Builder(Fake):
    def execute_build(self,prompt,cwd,emit,cancel):
        self.calls.append(prompt)
        Path(cwd,'index.html').write_text('<html><script type="module" src="./main.js"></script></html>')
        Path(cwd,'main.js').write_text('document.title="Artifact";')
        return {'status':'completed','result':'Arquivos implementados','usage':{'input_tokens':1},'error':None}

class ArtifactTests(unittest.TestCase):
    def test_resume_plan_creates_real_files_without_research_calls(self):
        with tempfile.TemporaryDirectory() as root,patch('backend.artifacts.OUTPUT',Path(root)/'outputs'):
            store=Store(Path(root)/'db',root);id=store.create('Crie um jogo','local','codex','key','rea')
            with store.connect() as db:
                for stage in ('research','evaluate','architect'):db.execute('INSERT INTO task_steps VALUES(?,?,?,?)',(id,stage,'Plano confirmado','now'))
            store.update(id,'completed');builder=Builder();supervisor=Supervisor(store,builder)
            supervisor.implement(id);supervisor.providers=lambda:[{'id':'codex','installed':True,'state':'available'}]
            supervisor.run_once();self.assertEqual(store.task(id)['status'],'completed')
            self.assertEqual(len(builder.calls),1)
            self.assertTrue((Path(root)/'outputs'/id/'index.html').is_file())
            self.assertEqual({s['stage'] for s in store.snapshot()['task_steps']},{'research','evaluate','architect','implement','validate'})
            self.assertEqual(len(store.snapshot()['artifacts']),1)
    def test_report_without_files_cannot_count_as_implementation(self):
        class ReportOnly(Builder):
            def execute_build(self,*args):return {'status':'completed','result':'Apenas texto','usage':{},'error':None}
        with tempfile.TemporaryDirectory() as root,patch('backend.artifacts.OUTPUT',Path(root)/'outputs'):
            store=Store(Path(root)/'db',root);id=store.create('Crie um jogo','local','codex','key','deliver')
            task=store.task(id);s=Supervisor(store,ReportOnly())
            result=s.run_delivery(task,lambda *a:None,__import__('threading').Event())
            self.assertEqual(result['status'],'failed');self.assertIn('não criou',result['error'])
    def test_invalid_ids_and_symlinks_rejected(self):
        with tempfile.TemporaryDirectory() as root,patch('backend.artifacts.OUTPUT',Path(root)/'outputs'):
            with self.assertRaises(ValueError):workspace('../escape')
            p=workspace('abcdef123456');(p/'escape').symlink_to('/private/tmp')
            with self.assertRaises(ValueError):inventory(p)
    def test_invalid_javascript_is_not_approved(self):
        with tempfile.TemporaryDirectory() as root:
            p=Path(root);(p/'index.html').write_text('<html></html>');(p/'main.js').write_text('let = ???')
            self.assertFalse(validate(p)['passed'])
    def test_automatic_intent_only_builds_creation_requests(self):
        with tempfile.TemporaryDirectory() as root:
            store=Store(Path(root)/'db',root)
            a=store.create('Crie um jogo de arena','local','auto','a','auto')
            b=store.create('Quanto é 2+2?','local','auto','b','auto')
            self.assertEqual(store.task(a)['workflow'],'deliver');self.assertEqual(store.task(b)['workflow'],'direct')
