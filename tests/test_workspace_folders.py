import tempfile
import unittest
from pathlib import Path
from backend.core import Store
from backend.workspace_folders import WorkspaceFolders


class WorkspaceFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.store = Store(self.root/'state.sqlite3',self.root)
        self.folders = WorkspaceFolders(self.store)
        for name in ('a','b','c'):(self.root/name).mkdir()

    def bind(self, id, directory, tasks=None):
        return self.folders.bind({'id':id,'name':id,'path':str(self.root/directory),'task_ids':tasks or []})

    def test_each_folder_owns_a_project_and_rebinding_does_not_touch_others(self):
        a,b = self.bind('A','a'),self.bind('B','b')
        self.assertNotEqual(a['project_id'],b['project_id'])
        self.bind('A','c')
        reopened = WorkspaceFolders(Store(self.store.path,self.root))
        result = {item['id']:item for item in reopened.bindings()}
        self.assertEqual(result['A']['path'],str(self.root/'c'))
        self.assertEqual(result['B']['path'],str(self.root/'b'))
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT path FROM projects WHERE id='local'").fetchone()[0],str(self.root))

    def test_completed_conversations_move_to_only_their_folder(self):
        a=self.store.create('Analisar A','local','codex','a')
        b=self.store.create('Analisar B','local','codex','b')
        self.store.update(a,'completed');self.store.update(b,'completed')
        bound=self.bind('A','a',[a])
        self.assertEqual(self.store.task(a)['project_id'],bound['project_id'])
        self.assertEqual(self.store.task(b)['project_id'],'local')

    def test_pending_work_cannot_be_redirected_to_a_different_root(self):
        task=self.store.create('Work','local','codex','pending','work')
        with self.assertRaises(ValueError):self.bind('A','a',[task])
        self.store.update(task,'interrupted')
        self.store.save_execution_state(task,{'messages':[]})
        with self.assertRaises(ValueError):self.bind('A','a',[task])
        self.assertEqual(self.store.task(task)['project_id'],'local')
        self.assertEqual(self.folders.bindings(),[])

    def test_invalid_directory_is_rejected_without_changing_binding(self):
        original=self.bind('A','a')
        for path in ('relative',str(self.root/'missing')):
            with self.assertRaises(ValueError):self.folders.bind({'id':'A','name':'A','path':path})
        self.assertEqual(self.folders.bindings()[0]['path'],original['path'])

    def test_pending_checkpoint_can_be_bound_to_its_existing_directory(self):
        task=self.store.create('Work','local','codex','same-root','work')
        self.store.update(task,'interrupted')
        state=self.store.save_execution_state(task,{'messages':[{'role':'user','content':'keep context'}]})
        result=self.folders.bind({'id':'A','name':'A','path':str(self.root),'task_ids':[task]})
        self.assertEqual(self.store.task(task)['project_id'],result['project_id'])
        self.assertEqual(self.store.load_execution_state(task),state)

    def test_active_task_still_cannot_be_migrated_even_to_same_directory(self):
        task=self.store.create('Work','local','codex','active-root','work')
        with self.assertRaises(ValueError):
            self.folders.bind({'id':'A','name':'A','path':str(self.root),'task_ids':[task]})

    def test_checkpoint_uses_recorded_execution_root_if_shared_project_was_changed(self):
        task=self.store.create('Work','local','codex','recorded-root','work')
        self.store.update(task,'interrupted')
        state=self.store.save_execution_state(task,{'messages':[]})
        with self.store.connect() as db:
            self.store.event(db,task,'workspace_context',{'root':str(self.root/'a')})
            db.execute("UPDATE projects SET path=? WHERE id='local'",(str(self.root/'b'),))
        with self.assertRaises(ValueError):self.bind('A','b',[task])
        result=self.bind('A','a',[task])
        self.assertEqual(result['path'],str(self.root/'a'))
        self.assertEqual(self.store.load_execution_state(task),state)
