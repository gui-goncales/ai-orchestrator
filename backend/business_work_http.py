"""HTTP controller for folderless business workspaces."""
import base64
import binascii
from urllib.parse import parse_qs, urlparse

from backend.business_work import BusinessWork


class BusinessWorkHTTP:
 def __init__(self, db_path, supervisor):
  self.work = BusinessWork(db_path)
  self.supervisor = supervisor

 def get(self, path):
  parsed = urlparse(path)
  parts = parsed.path.strip('/').split('/')
  if parts[:2] != ['api', 'business']:
   return None
  if parts == ['api', 'business', 'providers']:
   return self.providers()
  if parts == ['api', 'business', 'contexts']:
   return self.work.contexts()
  if len(parts) == 5 and parts[2] == 'contexts':
   context_id = parts[3]
   if parts[4] == 'sources':
    return self.work.sources(context_id)
   if parts[4] == 'documents':
    return self.work.documents(context_id)
   if parts[4] == 'generations':
    return [self.sync_generation(g) for g in self.work.generations(context_id)]
  if len(parts) == 4 and parts[2] == 'documents':
   return self.work.document(parts[3])
  if len(parts) == 5 and parts[2] == 'documents' and parts[4] == 'export':
   version = parse_qs(parsed.query).get('version_id', [None])[0]
   return ('docx', self.work.export_docx(parts[3], version))
  raise ValueError('Rota BusinessWork desconhecida')

 def post(self, path, body):
  parts = urlparse(path).path.strip('/').split('/')
  if parts[:2] != ['api', 'business']:
   return None
  if parts == ['api', 'business', 'contexts']:
   return self.work.create_context(body.get('name'))
  if len(parts) == 5 and parts[2] == 'contexts':
   context_id = parts[3]
   if parts[4] == 'sources':
    encoded = body.get('data')
    if not isinstance(encoded, str) or len(encoded) > 12000000:
     raise ValueError('Arquivo inválido ou acima do limite')
    try:
     raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
     raise ValueError('Arquivo base64 inválido') from None
    return self.work.add_source(context_id, body.get('name'), raw, body.get('source_id'))
   if parts[4] == 'generate':
    return self.generate(context_id, body)
  if len(parts) == 5 and parts[2] == 'generations' and parts[4] in ('resume', 'cancel'):
   generation = self.work.generation(parts[3])
   if not generation.get('task_id'):
    raise ValueError('Geração sem tarefa vinculada')
   if parts[4] == 'resume':
    self.supervisor.resume(generation['task_id'])
   else:
    self.supervisor.cancel(generation['task_id'])
   return self.sync_generation(generation)
  if len(parts) == 5 and parts[2] == 'documents':
   document_id = parts[3]
   if parts[4] == 'edit':
    return self.work.edit_block(document_id, body.get('expected_version_id'), body.get('block_id'), body.get('text'))
   if parts[4] == 'approve':
    return self.work.approve(document_id, body.get('version_id'))
  raise ValueError('Rota BusinessWork desconhecida')

 def providers(self):
  return [p for p in self.supervisor.providers()
          if p.get('state') in ('available', 'running') and p.get('id') in self.supervisor.adapters
          and (p.get('id') in ('codex', 'antigravity') or p.get('automatic_routing'))
          and p.get('id') not in ('rea', 'gemini')]

 def sync_generation(self, generation):
  if not generation.get('task_id'):
   # Recover a crash between durable task creation and attaching its ID.
   with self.supervisor.store.connect() as db:
    row = db.execute('SELECT task_id FROM commands WHERE key=?', ('business-' + generation['id'],)).fetchone()
   if row:
    self.work.attach_task(generation['id'], row[0])
    generation = self.work.generation(generation['id'])
  if generation.get('task_id') and not generation.get('deliverable_id'):
   task = self.supervisor.store.task(generation['task_id'])
   if task:
    return self.work.finalize_generation(generation['id'], task['status'], task.get('result'), task.get('error'))
  return generation

 def generate(self, context_id, body):
  if not self.providers():
   raise ValueError('Conecte uma IA elegível para seleção automática na página Agents')
  prepared = self.work.prepare_generation(context_id, body.get('kind'), body.get('title'), body.get('source_version_ids'))
  try:
   task_id = self.supervisor.store.create(
    'Gerar documento: ' + prepared['title'], 'local', 'auto',
    'business-' + prepared['id'], 'direct', {'business_generation_id': prepared['id']})
   self.work.attach_task(prepared['id'], task_id)
   return self.work.generation(prepared['id'])
  except Exception:
   self.work.discard_generation(prepared['id'], 'Não foi possível enfileirar a geração')
   raise
