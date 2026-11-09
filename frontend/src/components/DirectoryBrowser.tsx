import { useEffect, useRef, useState } from 'react';
import '../styles/directory-browser.css';
import { ChevronRight, File, Folder, FolderOpen, LoaderCircle, Search, X } from 'lucide-react';

type Entry = { name: string; path: string; type: 'dir' | 'file' };
type Listing = { path: string; parent: string | null; entries: Entry[] };
type Props = {
initialPath: string;
folderName: string;
busy: boolean;
online: boolean;
error: string;
onCancel: () => void;
onSelect: (path: string) => Promise<void>;
onNativePick: () => Promise<string | undefined>;
hasRunningTasks: boolean;
};

export function DirectoryBrowser({ initialPath, folderName, busy, online, error, onCancel, onSelect, onNativePick, hasRunningTasks }: Props) {
const [path, setPath] = useState(initialPath);
const [listing, setListing] = useState<Listing | null>(null);
const [query, setQuery] = useState('');
const [loading, setLoading] = useState(false);
const [browseError, setBrowseError] = useState('');
const searchRef = useRef<HTMLInputElement>(null);
const dialogRef = useRef<HTMLElement>(null);
const requestId = useRef(0);

useEffect(() => {
searchRef.current?.focus();
const onKey = (event: KeyboardEvent) => {
if (event.key === 'Escape' && !busy) { event.preventDefault(); onCancel(); }
if (event.key === 'Tab') {
const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled)') || []);
if (!focusable.length) return;
const first = focusable[0], last = focusable[focusable.length - 1];
if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
}
};
document.addEventListener('keydown', onKey);
return () => document.removeEventListener('keydown', onKey);
}, [busy, onCancel]);

useEffect(() => {
const id = ++requestId.current;
const controller = new AbortController();
setLoading(true);
setBrowseError('');
setListing(null);
fetch('/api/workspace/browse-directory', {
method: 'POST', headers: { 'Content-Type': 'application/json' },
body: JSON.stringify({ path }), signal: controller.signal
}).then(async response => {
const payload = await response.json();
if (!response.ok) throw Error(payload.error || 'Não foi possível acessar esta pasta.');
return payload as Listing;
}).then(result => { if (id === requestId.current) setListing(result); })
.catch(reason => { if (id === requestId.current && !controller.signal.aborted) setBrowseError(String(reason.message || reason)); })
.finally(() => { if (id === requestId.current) setLoading(false); });
return () => controller.abort();
}, [path]);

const navigate = (next: string) => { setPath(next); setQuery(''); };
const crumbs = listing?.path.split('/').filter(Boolean) || [];
const entries = listing?.entries.filter(entry => entry.name.toLocaleLowerCase().includes(query.toLocaleLowerCase())) || [];
const confirm = async () => {
if (!listing || busy) return;
if (hasRunningTasks && !window.confirm('Existem tarefas em andamento. Alterar o diretório pode afetar a execução. Deseja continuar?')) return;
await onSelect(listing.path);
};
return <div className="directory-browser-backdrop" onMouseDown={event => { if (event.target === event.currentTarget && !busy) onCancel(); }}>
<section className="directory-browser" ref={dialogRef} role="dialog" aria-modal="true" aria-labelledby="directory-browser-title" aria-describedby="directory-browser-description">
<header className="directory-browser-header">
<div><span className="directory-browser-eyebrow">WORKSPACE / DIRETÓRIO</span><h2 id="directory-browser-title">Alterar diretório</h2><p id="directory-browser-description">Escolha o diretório vinculado a <strong>{folderName}</strong>.</p></div>
<button type="button" className="directory-browser-icon-button" aria-label="Fechar" onClick={onCancel} disabled={busy}><X size={19}/></button>
</header>
<nav className="directory-browser-crumbs" aria-label="Caminho atual">
<button type="button" onClick={() => navigate('/')} disabled={busy}>Raiz</button>
{crumbs.map((part, index) => <span key={index} className="directory-browser-crumb"><ChevronRight size={14}/><button type="button" disabled={busy} aria-current={index === crumbs.length - 1 ? 'location' : undefined} onClick={() => navigate('/' + crumbs.slice(0, index + 1).join('/'))}>{part}</button></span>)}
</nav>
<div className="directory-browser-toolbar">
<label className="directory-browser-search"><Search size={17}/><input ref={searchRef} value={query} onChange={event => setQuery(event.target.value)} placeholder="Filtrar pastas e arquivos..." aria-label="Filtrar pastas e arquivos"/></label>
<button type="button" className="secondary" disabled={busy || !online} onClick={async () => { const chosen = await onNativePick(); if (chosen) navigate(chosen); }}>Escolher no Mac</button>
</div>
<div className="directory-browser-list" aria-live="polite" aria-busy={loading}>
{loading ? <div className="directory-browser-state"><LoaderCircle className="directory-browser-spin" size={26}/><strong>Carregando diretórios...</strong></div>
: browseError ? <div className="directory-browser-state directory-browser-error" role="alert"><strong>Não foi possível acessar o diretório</strong><p>{browseError}</p><button type="button" className="secondary" onClick={() => navigate(listing?.parent || '/')}>Voltar à raiz</button></div>
: entries.length === 0 ? <div className="directory-browser-state"><FolderOpen size={28}/><strong>{query ? 'Nenhum resultado encontrado' : 'Esta pasta está vazia'}</strong><p>{query ? 'Tente outro termo de busca.' : 'Você ainda pode selecionar este diretório.'}</p></div>
: entries.map(entry => <button type="button" key={entry.path} className={'directory-browser-entry ' + (entry.type === 'dir' ? 'is-folder' : 'is-file')} disabled={busy || entry.type === 'file'} title={entry.path} onClick={() => navigate(entry.path)}>{entry.type === 'dir' ? <Folder size={19}/> : <File size={19}/>}<span>{entry.name}</span>{entry.type === 'dir' && <ChevronRight size={16}/>}</button>)}
</div>
{(error || !online) && <p className="directory-browser-alert" role="alert">{error || 'O backend está desconectado. Reconecte para selecionar um diretório.'}</p>}
<footer className="directory-browser-footer"><div className="directory-browser-selected"><small>Diretório atual</small><strong title={listing?.path}>{listing?.path || 'Aguardando pasta válida'}</strong></div><div className="directory-browser-actions"><button type="button" className="secondary" onClick={onCancel} disabled={busy}>Cancelar</button><button type="button" className="primary" disabled={!online || busy || loading || !listing || !!browseError} onClick={() => void confirm()}>{busy ? 'Salvando...' : 'Selecionar este diretório'}</button></div></footer>
</section>
</div>;
}
