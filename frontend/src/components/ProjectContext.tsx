import React, { useEffect, useState } from 'react';
import { Data } from '../types';

export function ProjectContext({ data, projectId, online, request }: { data: Data; projectId: string; online: boolean; request: (path: string, body?: any) => Promise<any> }) {
  const project = data.projects.find(p => p.id === projectId);
  const [path, setPath] = useState('.');
  const [listing, setListing] = useState<any>(null);
  const [file, setFile] = useState<any>(null);
  const [error, setError] = useState('');
  useEffect(() => { setPath('.'); setFile(null); setListing(null); }, [projectId]);
  useEffect(() => {
    let active = true;
    setListing(null);
    if (project && online) request('projects/context', { project_id: project.id, path }).then(result => {
      if (active) { setListing(result); setError(result?.error || ''); }
    }).catch(e => { if (active) setError(e.message); });
    return () => { active = false; };
  }, [projectId, project?.path, path, online]);
  return <section className="panel project-context">
    <details className="project-context-disclosure"><summary><span className="context-project-name">{project?.name || 'Selecione um projeto'}</span><span className="context-open-label">Arquivos e contexto</span></summary>
      {project && <><p className="mono">{project.path}</p><p>Esta é a pasta usada pelos agentes. O modo Work permite editar seus arquivos.</p>
        <details><summary>Conectar / alterar pasta local</summary><form onSubmit={async e => {
          e.preventDefault(); const form = new FormData(e.currentTarget);
          try { const result = await request('projects', { id: project.id, name: project.name, path: form.get('path') }); if (result) { setPath('.'); setFile(null); setError('Pasta conectada.'); } } catch (e) { setError((e as Error).message); }
        }}><label>Diretório absoluto no dispositivo<input name="path" required defaultValue={project.path} key={project.path}/></label><button className="secondary" disabled={!online}>Conectar pasta</button></form></details>
        <details><summary>Arquivos da pasta</summary><p className="mono">{path}</p><button className="secondary" disabled={path === '.' || !online} onClick={() => { setPath(path.split('/').slice(0, -1).join('/') || '.'); setFile(null); }}>Pasta acima</button>
          <div className="context-file-list">{listing?.items?.map((item: any) => <button key={item.path} className="text-button" disabled={!online} onClick={async () => {
            setFile(null);
            if (item.type === 'dir') setPath(item.path);
            else { const result = await request('projects/context', { project_id: project.id, file: item.path }); setFile(result); }
          }}>{item.type === 'dir' ? '▸' : '·'} {item.name}</button>)}</div>
          {file && <details open><summary>{file.path || 'Arquivo'}</summary><pre>{file.content || file.error}</pre></details>}
        </details>
        <details><summary>Memórias e restrições ({data.memory.filter(m => m.project_id === project.id).length})</summary>{data.memory.filter(m => m.project_id === project.id).map(m => <p key={m.id}>{m.content}</p>)}</details>
      </>}
      {error && <p role="status">{error}</p>}
    </details>
  </section>;
}
