import React, { useEffect, useRef, useState } from 'react';
import { Folder, FileText, ChevronDown, ChevronRight, ArrowLeft, X, Brain, FolderOpen } from 'lucide-react';
import { Data } from '../types';

type Listing = { items?: { name: string; path: string; type: string }[]; error?: string };
type Preview = { path?: string; content?: string; error?: string };

export function ProjectContext({ data, projectId, online, request }: { data: Data; projectId: string; online: boolean; request: (path: string, body?: any) => Promise<any> }) {
  const project = data.projects.find(p => p.id === projectId);
  const [path, setPath] = useState('.');
  const [listing, setListing] = useState<Listing | null>(null);
  const [file, setFile] = useState<Preview | null>(null);
  const [error, setError] = useState('');
  const [loadingFile, setLoadingFile] = useState(false);
  const [section, setSection] = useState<'files' | 'memory'>('files');
  const previewSequence = useRef(0);
  const disclosureRef = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const dismiss = (event: PointerEvent) => { if (disclosureRef.current && !disclosureRef.current.contains(event.target as Node)) disclosureRef.current.open = false; };
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape' && disclosureRef.current?.open) { disclosureRef.current.open = false; disclosureRef.current.querySelector('summary')?.focus(); } };
    document.addEventListener('pointerdown', dismiss); document.addEventListener('keydown', escape);
    return () => { document.removeEventListener('pointerdown', dismiss); document.removeEventListener('keydown', escape); };
  }, []);
  const memories = data.memory.filter(m => m.project_id === projectId);
  useEffect(() => { setPath('.'); setFile(null); setListing(null); setError(''); setLoadingFile(false); previewSequence.current++; }, [projectId]);
  useEffect(() => {
    let active = true;
    setListing(null); setError(''); setFile(null); setLoadingFile(false); previewSequence.current++;
    if (project && online) request('projects/context', { project_id: project.id, path }).then(result => {
      if (active) { setListing(result); setError(result?.error || ''); }
    }).catch(e => { if (active) { setError(e.message); setListing({}); } });
    return () => { active = false; previewSequence.current++; };
  }, [projectId, project?.path, path, online]);
  const openFile = async (itemPath: string) => {
    const sequence = ++previewSequence.current;
    setLoadingFile(true); setError(''); setFile(null);
    try { const result = await request('projects/context', { project_id: projectId, file: itemPath }); if (sequence === previewSequence.current) setFile(result); }
    catch (e) { if (sequence === previewSequence.current) setError((e as Error).message); }
    finally { if (sequence === previewSequence.current) setLoadingFile(false); }
  };
  return <section className="panel project-context">
    <details ref={disclosureRef} className="project-context-disclosure">
      <summary aria-label={`Arquivos e contexto · ${project?.name || 'Nenhum projeto'}`}>
        <span className="context-project-mark"><Folder size={15} /></span>
        <span className="context-project-name">{project?.name || 'Nenhum projeto selecionado'}</span>
        <span className="context-open-label">Arquivos e contexto</span><ChevronDown className="context-chevron" size={14} />
      </summary>
      <div className="context-browser">
        <div className="context-browser-heading"><div><strong>Contexto do projeto</strong><span title={project?.path}>{project?.path || 'Selecione um projeto na navegação para explorar seus arquivos.'}</span></div><span className="context-scope">Somente leitura</span></div>
        {project && <>
          <div className="context-switcher" role="group" aria-label="Seção do contexto">
            <button type="button" aria-pressed={section === 'files'} onClick={() => setSection('files')}><FolderOpen size={14} />Arquivos</button>
            <button type="button" aria-pressed={section === 'memory'} onClick={() => setSection('memory')}><Brain size={14} />Memórias<span>{memories.length}</span></button>
          </div>
          {section === 'files' ? <>
            <div className="context-breadcrumb"><button type="button" title="Voltar à pasta anterior" aria-label="Voltar à pasta anterior" disabled={path === '.' || !online} onClick={() => setPath(path.split('/').slice(0, -1).join('/') || '.')}><ArrowLeft size={15} /></button><span title={path}>{path === '.' ? project.name : path}</span></div>
            {!online ? <p className="context-empty">Conecte-se para explorar os arquivos do projeto.</p> : !listing ? <p className="context-empty" role="status">Carregando arquivos…</p> : !error && !listing.items?.length ? <p className="context-empty">Esta pasta está vazia.</p> : null}
            <div className="context-file-list" aria-label="Arquivos do projeto">{listing?.items?.map(item => <button key={item.path} type="button" disabled={!online} className={file?.path === item.path ? 'is-selected' : ''} onClick={() => item.type === 'dir' ? setPath(item.path) : void openFile(item.path)}>
              {item.type === 'dir' ? <Folder size={15} /> : <FileText size={15} />}<span>{item.name}</span>{item.type === 'dir' && <ChevronRight size={13} />}
            </button>)}</div>
            {loadingFile && <p className="context-empty" role="status">Abrindo arquivo…</p>}
            {file && <div className="context-preview"><div><FileText size={14} /><strong>{file.path || 'Prévia do arquivo'}</strong><button type="button" title="Fechar prévia" aria-label="Fechar prévia" onClick={() => setFile(null)}><X size={14} /></button></div>{file.error ? <p role="alert">{file.error}</p> : <pre tabIndex={0}>{file.content || 'Arquivo vazio.'}</pre>}</div>}
          </> : <div className="context-memories">{memories.length ? memories.map(m => <article key={m.id}><Brain size={15} /><p>{m.content}</p></article>) : <p className="context-empty">Nenhuma memória salva para este projeto.</p>}</div>}
        </>}
        {error && <p className="context-error" role="alert">{error}</p>}
      </div>
    </details>
  </section>;
}
