import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from backend.core import Store,Supervisor
from backend.artifacts import validate,inventory
from backend.visual_review import fingerprint
from backend.revisions import suggestions,published
from test_core import Fake

REPORT='| Prioridade | Captura | Evidência | Proposta | Critério |\n| P2 | desktop.png | Texto pequeno | Aumentar contraste | Texto legível |'

class ImproveFake(Fake):
    def execute_improvements(self,prompt,cwd,emit,cancel,images):
        self.calls.append({'cwd':cwd,'images':images,'prompt':prompt})
        Path(cwd,'style.css').write_text('body { color: #fff; background: #111; }')
        return {'status':'completed','result':'Contraste alterado','usage':{'input_tokens':4},'error':None}
    def execute_visual(self,prompt,cwd,emit,cancel,images):
        self.vision_call={'prompt':prompt,'images':images}
        return {'status':'completed','result':REPORT,'usage':{'input_tokens':2},'error':None}

class RevisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.patches=[patch('backend.artifacts.OUTPUT',self.root/'artifacts'),patch('backend.visual_review.EVIDENCE',self.root/'evidence')]
        for p in self.patches:p.start()
        self.store=Store(self.root/'db',self.root);self.parent=self.store.create('Objetivo','local','codex','parent')
        self.path=self.root/'artifacts'/self.parent;self.path.mkdir(parents=True)
        (self.path/'index.html').write_text('<script type="module" src="main.js"></script>');(self.path/'main.js').write_text('document.title="ok";');(self.path/'style.css').write_text('body { color:#444; }')
        manifest=validate(self.path)
        with self.store.connect() as db:db.execute('INSERT INTO artifacts VALUES(?,?,?,?)',(self.parent,str(self.path),json.dumps(manifest),'now'))
        self.store.update(self.parent,'completed');self.base_hash=fingerprint(self.path)
        self.review=self.store.create('Revisão','local','codex','review','visual_review',{'parent_id':self.parent,'artifact_digest':self.base_hash})
        self.store.update(self.review,'completed')
        folder=self.root/'evidence'/self.review;folder.mkdir(parents=True);image=folder/'desktop.png';image.write_bytes(b'UNIT_TEST_IMAGE')
        capture={'images':[{'name':'desktop.png','sha256':hashlib.sha256(image.read_bytes()).hexdigest()}],'page_errors':[],'failed_requests':[]}
        with self.store.connect() as db:db.execute('INSERT INTO visual_reviews VALUES(?,?,?,?,?)',(self.review,self.parent,json.dumps(capture),REPORT,'now'))
        self.supervisor=Supervisor(self.store,ImproveFake());self.supervisor.providers=lambda:[{'id':'codex','installed':True,'state':'available'}]
        self.ids=[suggestions(REPORT)[0]['id']]
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.tmp.cleanup()
    def request(self,feedback=''):
        return self.supervisor.request_improvements(self.parent,self.review,self.ids,feedback)
    def ready(self):
        id=self.request();self.supervisor.run_once()
        row=self.store.snapshot()['revisions'][0];rid=row['after_review_id']
        with patch('backend.visual_review.capture',return_value=({'images':[{'name':'desktop.png'}],'page_errors':[],'failed_requests':[]},['/after/desktop.png'])):
            self.supervisor.run_once()
        self.assertEqual(self.store.snapshot()['revisions'][0]['status'],'ready')
        return id
    def test_proposal_extraction_and_unknown_proposals_rejected(self):
        self.assertEqual(suggestions(REPORT)[0]['priority'],'P2')
        with self.assertRaises(ValueError):self.supervisor.request_improvements(self.parent,self.review,['invalid'])
        with self.assertRaises(ValueError):self.supervisor.request_improvements(self.parent,self.review,[])
    def test_idempotent_same_selection(self):
        self.assertEqual(self.request(),self.request())
    def test_candidate_does_not_change_original_and_diff_is_saved(self):
        id=self.request();self.supervisor.run_once()
        self.assertEqual(fingerprint(self.path),self.base_hash)
        candidate=self.root/'artifacts'/id
        self.assertNotEqual(fingerprint(candidate),self.base_hash)
        row=self.store.snapshot()['revisions'][0];self.assertIn('style.css',row['changes']['modified'])
        self.assertEqual(row['status'],'reviewing');self.assertEqual(published(self.store,self.parent),self.path)
        self.assertEqual(self.supervisor.adapter.calls[0]['images'],[str(self.root/'evidence'/self.review/'desktop.png')])
    def test_publish_and_restore_only_change_pointer(self):
        id=self.ready();self.supervisor.publish_revision(id)
        self.assertEqual(published(self.store,self.parent).name,id)
        self.assertTrue(self.path.is_dir())
        self.supervisor.publish_revision(id,restore=True)
        self.assertEqual(published(self.store,self.parent),self.path)
        self.assertTrue((self.root/'artifacts'/id).is_dir())
        self.assertEqual(fingerprint(self.path),self.base_hash)
    def test_publication_blocked_until_review_ready(self):
        id=self.request();self.supervisor.run_once()
        with self.assertRaises(ValueError):self.supervisor.publish_revision(id)
    def test_stale_review_rejected(self):
        (self.path/'main.js').write_text('document.title="changed";')
        with self.assertRaises(ValueError):self.request()
    def test_candidate_modified_after_validation_not_published(self):
        id=self.ready();(self.root/'artifacts'/id/'style.css').write_text('changed')
        with self.assertRaises(ValueError):self.supervisor.publish_revision(id)
    def test_failed_agent_preserves_original(self):
        self.supervisor.adapter.execute_improvements=lambda *a:{'status':'failed','result':'','usage':{},'error':'simulated failure'}
        id=self.request();self.supervisor.run_once()
        self.assertEqual(self.store.task(id)['status'],'failed');self.assertEqual(fingerprint(self.path),self.base_hash)
        self.assertEqual(published(self.store,self.parent),self.path)
    def test_protected_planning_edit_blocks_validation(self):
        original=self.supervisor.adapter.execute_improvements
        def bad(prompt,cwd,*args):
            result=original(prompt,cwd,*args);Path(cwd,'planning').mkdir();Path(cwd,'planning/goal.md').write_text('changed');return result
        self.supervisor.adapter.execute_improvements=bad
        id=self.request();self.supervisor.run_once()
        self.assertEqual(self.store.task(id)['status'],'needs_review')
        self.assertEqual(self.store.snapshot()['revisions'][0]['status'],'validation_failed')
        self.assertEqual(published(self.store,self.parent),self.path)
    def test_after_publication_visual_review_targets_active_candidate(self):
        id=self.ready();self.supervisor.publish_revision(id)
        review=self.supervisor.request_visual_review(self.parent)
        self.assertEqual(json.loads(self.store.task(review)['spec'])['artifact_slug'],id)

    def test_after_review_receives_before_and_after_with_selected_criteria(self):
        self.ready();call=self.supervisor.adapter.vision_call
        self.assertEqual(call['images'][0],'/after/desktop.png')
        self.assertEqual(call['images'][-1],str(self.root/'evidence'/self.review/'desktop.png'))
        self.assertIn('COMPARAÇÃO OBRIGATÓRIA',call['prompt']);self.assertIn('Aumentar contraste',call['prompt'])
    def test_acceptance_records_checkpoint_with_active_artifact(self):
        id=self.ready();self.supervisor.publish_revision(id)
        checkpoints=[c for c in self.store.snapshot()['checkpoints'] if c['task_id']==self.parent]
        self.assertEqual(Path(checkpoints[0]['payload']['artifact']['path']).name,id)

    def test_restored_candidate_can_be_reaccepted_without_losing_either_version(self):
        id=self.ready();self.supervisor.publish_revision(id);self.supervisor.publish_revision(id,restore=True)
        self.supervisor.publish_revision(id)
        self.assertEqual(published(self.store,self.parent).name,id)
        self.assertTrue(self.path.is_dir())
