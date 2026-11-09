"""Independent directory bindings for workspace conversation folders."""
import hashlib
import json
from pathlib import Path


class WorkspaceFolders:
    def __init__(self, store):
        self.store = store
        with store.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS workspace_folders(id TEXT PRIMARY KEY, name TEXT NOT NULL, project_id TEXT UNIQUE NOT NULL)')

    def bindings(self):
        with self.store.connect() as db:
            return [dict(row) for row in db.execute('SELECT f.id,f.name,f.project_id,p.path FROM workspace_folders f JOIN projects p ON p.id=f.project_id')]

    def bind(self, body):
        folder_id, name, path = body.get('id'), body.get('name'), body.get('path')
        ids = body.get('task_ids', [])
        if not isinstance(folder_id, str) or not folder_id or len(folder_id) > 150:
            raise ValueError('Pasta inválida')
        if not isinstance(name, str) or not name.strip() or len(name) > 100:
            raise ValueError('Nome inválido')
        if not isinstance(path, str) or not Path(path).expanduser().is_absolute():
            raise ValueError('Informe um diretório absoluto no dispositivo')
        directory = Path(path).expanduser().resolve()
        if not directory.is_dir():
            raise ValueError('Diretório não encontrado')
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise ValueError('Conversas inválidas')
        project_id = 'folder-' + hashlib.sha256(folder_id.encode()).hexdigest()[:20]
        with self.store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current = db.execute('SELECT path FROM projects WHERE id=?', (project_id,)).fetchone()
            changing = not current or current['path'] != str(directory)
            affected = set(ids) | {r[0] for r in db.execute('SELECT id FROM tasks WHERE project_id=?', (project_id,))}
            for task_id in affected:
                task = db.execute('SELECT status,project_id FROM tasks WHERE id=?', (task_id,)).fetchone()
                if not task:
                    raise ValueError('Conversa não encontrada')
                migrating = task['project_id'] != project_id
                original = db.execute('SELECT path FROM projects WHERE id=?', (task['project_id'],)).fetchone()
                checkpoint = db.execute('SELECT 1 FROM execution_states WHERE task_id=?', (task_id,)).fetchone()
                original_root = original['path'] if original else None
                if checkpoint:
                    event = db.execute("SELECT payload FROM events WHERE task_id=? AND kind='workspace_context' ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
                    if event:
                        recorded = json.loads(event['payload']).get('root')
                        if isinstance(recorded, str) and recorded:
                            original_root = recorded
                root_changed = not original_root or Path(original_root).resolve() != directory
                if ((changing or migrating) and task['status'] in ('running', 'queued')) or (
                    root_changed and task['status'] != 'completed' and
                    checkpoint):
                    raise ValueError('Finalize as execuções desta pasta antes de alterar o diretório; checkpoints pendentes devem manter a raiz original.')
            db.execute('INSERT INTO projects(id,name,path) VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,path=excluded.path', (project_id, name.strip(), str(directory)))
            db.execute('INSERT INTO workspace_folders VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name', (folder_id, name.strip(), project_id))
            for task_id in ids:
                db.execute('UPDATE tasks SET project_id=? WHERE id=?', (project_id, task_id))
            self.store.event(db, None, 'workspace_folder_bound', {'folder_id':folder_id,'project_id':project_id})
        return {'id':folder_id,'name':name.strip(),'project_id':project_id,'path':str(directory)}
