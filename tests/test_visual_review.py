import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.core import Store,Supervisor
from backend.visual_review import fingerprint,review_prompt
from test_core import Fake

class VisionFake(Fake):
    def execute_visual(self,prompt,cwd,emit,cancel,images):
        self.calls.append({'prompt':prompt,'images':images,'cwd':cwd})
        return {'status':'completed','result':'P2: melhorar contraste — evidência desktop.png','usage':{'input_tokens':20,'output_tokens':8},'error':None}

class VisualReviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.output=self.root/'artifacts';self.patch=patch('backend.artifacts.OUTPUT',self.output);self.patch.start()
        self.store=Store(self.root/'db',self.root);self.parent=self.store.create('Criar interface','local','codex','parent')
        self.path=self.output/self.parent;self.path.mkdir(parents=True);(self.path/'index.html').write_text('<button>Jogar</button>')
        with self.store.connect() as db:db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(self.parent,str(self.path),'{}','now'))
        self.store.update(self.parent,'completed')
        self.adapter=VisionFake();self.supervisor=Supervisor(self.store,self.adapter)
        self.supervisor.providers=lambda:[{'id':'codex','installed':True,'state':'available'}]
    def tearDown(self):
        self.patch.stop();self.temp.cleanup()
    def report(self):
        return {'images':[{'name':'desktop.png','label':'Tela desktop','width':1280,'height':800}], 'actions':[], 'page_errors':[], 'failed_requests':[], 'scope':'captura limitada','mobile':{},'renderer':'teste'}
    def test_same_version_reuses_review_and_changed_version_gets_new_review(self):
        first=self.supervisor.request_visual_review(self.parent)
        self.assertEqual(first,self.supervisor.request_visual_review(self.parent))
        (self.path/'index.html').write_text('<button>Novo</button>')
        self.assertNotEqual(first,self.supervisor.request_visual_review(self.parent))
    def test_actual_image_paths_passed_and_parent_files_unchanged(self):
        before=fingerprint(self.path);review=self.supervisor.request_visual_review(self.parent)
        with patch('backend.visual_review.capture',return_value=(self.report(),['/evidence/desktop.png'])):
            self.supervisor.run_once()
        self.assertEqual(self.store.task(review)['status'],'completed')
        self.assertEqual(self.adapter.calls[0]['images'],['/evidence/desktop.png'])
        self.assertIn('Somente leitura',self.adapter.calls[0]['prompt'])
        self.assertEqual(before,fingerprint(self.path))
        row=self.store.snapshot()['visual_reviews'][0];self.assertIn('P2',row['report']);self.assertEqual(row['parent_id'],self.parent)
    def test_stale_artifact_never_sent_for_review(self):
        review=self.supervisor.request_visual_review(self.parent)
        (self.path/'index.html').write_text('versão diferente')
        self.supervisor.run_once()
        self.assertEqual(self.store.task(review)['status'],'failed');self.assertEqual(self.adapter.calls,[])
    def test_capture_failure_never_pretends_agent_saw_images(self):
        review=self.supervisor.request_visual_review(self.parent)
        with patch('backend.visual_review.capture',side_effect=ValueError('Sem capturas')):self.supervisor.run_once()
        self.assertEqual(self.store.task(review)['status'],'failed');self.assertEqual(self.adapter.calls,[])
        self.assertEqual(self.store.snapshot()['visual_reviews'][0]['report'],'')
    def test_review_requires_existing_artifact(self):
        id=self.store.create('Sem artefato','local','codex','missing');self.store.update(id,'completed')
        with self.assertRaises(ValueError):self.supervisor.request_visual_review(id)
    def test_prompt_identifies_evidence_and_limits_without_research_history(self):
        prompt=review_prompt({'objective':'Objetivo integral'},self.report())
        self.assertIn('desktop.png',prompt);self.assertEqual(prompt.count('Objetivo integral'),1)
        self.assertIn('não altere código',prompt);self.assertIn('Não afirme ver movimento',prompt)

class AutomaticVisualQueueTests(unittest.TestCase):
    def test_completed_delivery_automatically_queues_one_visual_review(self):
        from test_artifacts import Builder
        class VisualBuilder(Builder):
            def execute_visual(self,*args):raise AssertionError('The next queued task must run separately')
        with tempfile.TemporaryDirectory() as root,patch('backend.artifacts.OUTPUT',Path(root)/'outputs'):
            store=Store(Path(root)/'db',root);id=store.create('Crie aplicação','local','codex','automatic','deliver')
            with store.connect() as db:
                for stage in ('research','evaluate','architect'):db.execute('INSERT INTO task_steps VALUES(?,?,?,?)',(id,stage,'Confirmado','now'))
            supervisor=Supervisor(store,VisualBuilder());supervisor.run_once()
            snapshot=store.snapshot();reviews=snapshot['visual_reviews']
            self.assertEqual(store.task(id)['status'],'completed');self.assertEqual(len(reviews),1)
            review=store.task(reviews[0]['task_id']);self.assertEqual(review['workflow'],'visual_review');self.assertEqual(review['status'],'queued')
            self.assertEqual(supervisor.request_visual_review(id),review['id'])
