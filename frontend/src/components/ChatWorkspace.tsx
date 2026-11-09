import React, { useState, useEffect } from 'react';
import { Task, Data, ChatFolder, Revision } from '../types';
import { FolderTree } from './FolderTree';
import { ChatView } from './ChatView';
import { ProjectContext } from './ProjectContext';
import { ChatInspector } from './ChatInspector';
import { DirectoryBrowser } from './DirectoryBrowser';
import { Menu, X, PanelLeftClose, PanelLeft, Plus } from 'lucide-react';

interface ChatWorkspaceProps {
  data: Data;
  activeProject: string;
  selectedTaskId: string;
  onSelectTask: (taskId: string) => void;
  online: boolean;
  onSendMessage: (objective: string, provider: string, workflow: string, folderId?: string | null, model?: string, projectId?: string, files?: File[]) => Promise<string | void>;
  onAction: (path: string, body?: any) => Promise<any>;
  labels: Record<string, string>;
  ImprovementControlsComponent: React.ComponentType<{
    review: NonNullable<Data['visual_reviews']>[number];
    online: boolean;
    onApply: (ids: string[], feedback: string) => Promise<void>;
  }>;
  RevisionPanelComponent: React.ComponentType<{
    revision: Revision;
    data: Data;
    online: boolean;
    act: (path: string, body?: any) => Promise<any>;
    onOpen: (id: string) => void;
  }>;
  onOpenTaskModal: () => void;
}

const DEFAULT_FOLDERS: ChatFolder[] = [];

export function ChatWorkspace({
  data,
  activeProject,
  selectedTaskId,
  onSelectTask,
  online,
  onSendMessage,
  onAction,
  labels,
  ImprovementControlsComponent,
  RevisionPanelComponent,
  onOpenTaskModal,
}: ChatWorkspaceProps) {
  // Folders state with persistence in localStorage
  const [folders, setFolders] = useState<ChatFolder[]>(() => {
    try {
      const saved = localStorage.getItem('orchestrator_chat_folders');
      return saved ? JSON.parse(saved) : DEFAULT_FOLDERS;
    } catch {
      return DEFAULT_FOLDERS;
    }
  });

  // Task to Folder mapping
  const [taskFolderMap, setTaskFolderMap] = useState<Record<string, string>>(() => {
    try {
      const saved = localStorage.getItem('orchestrator_task_folders');
      return saved ? JSON.parse(saved) : {};
    } catch {
      return {};
    }
  });

  const [showSessions, setShowSessions] = useState(() => !matchMedia('(max-width: 800px)').matches);
  useEffect(() => {
    const media = matchMedia('(max-width: 800px)');
    const update = () => setShowSessions(!media.matches);
    media.addEventListener('change', update);
    return () => media.removeEventListener('change', update);
  }, []);

  const [showInspector, setShowInspector] = useState(false);
 const [sidebarWidth, setSidebarWidth] = useState(() => { const value = Number(localStorage.getItem('workspace_sidebar_width')); return Number.isFinite(value) && value >= 220 && value <= 520 ? value : 310; });
 const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
 const [mobileNavOpen, setMobileNavOpen] = useState(false);
  useEffect(() => { if (!mobileNavOpen && !showInspector) return; const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape') { setMobileNavOpen(false); setShowInspector(false); } }; document.addEventListener('keydown', onKey); return () => document.removeEventListener('keydown', onKey); }, [mobileNavOpen, showInspector]);
 const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [targetFolderForNewChat, setTargetFolderForNewChat] = useState<string | null>(null);

  type Binding = {id:string;project_id:string;path:string};
  const [bindings,setBindings]=useState<Binding[]>([]);
  const [configuring,setConfiguring]=useState<string|null>(null);
  const [directory,setDirectory]=useState('');
  const [bindingError,setBindingError]=useState('');
  const [bindingBusy,setBindingBusy]=useState(false);
  useEffect(()=>{if(!online)return;let live=true;fetch('/api/workspace/folders').then(r=>{if(!r.ok)throw Error('Não foi possível carregar os diretórios');return r.json()}).then(items=>{if(live)setBindings(items)}).catch(e=>{if(live)setBindingError(String(e))});return()=>{live=false}},[online]);
  const pickDirectory=async()=>{setBindingBusy(true);setBindingError('');try{const result=await onAction('workspace/pick-directory',{});if(!result)throw Error('Não foi possível abrir o seletor de pastas.');if(!result.cancelled)setDirectory(result.path)}catch(error){setBindingError((error as Error).message)}finally{setBindingBusy(false)}};
  const configureFolder=(id:string)=>{setConfiguring(id);setDirectory(bindings.find(b=>b.id===id)?.path||'');setBindingError('')};
  const saveBinding=async(id:string,path:string)=>{
    const folder=folders.find(f=>f.id===id);if(!folder)throw Error('Pasta não encontrada');
    const assigned=new Set(Object.entries(taskFolderMap).filter(([,fid])=>fid===id).map(([tid])=>tid));
    const taskIds=data.tasks.filter(t=>assigned.has(t.id)||assigned.has(t.conversation_id||t.id)).map(t=>t.id);
    const result=await onAction('workspace/folders',{id,name:folder.name,path,task_ids:taskIds});
    if(!result)throw Error('Não foi possível conectar o diretório');
    setBindings(old=>[...old.filter(b=>b.id!==id),result]);return result;
  };

  // Sync folders to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('orchestrator_chat_folders', JSON.stringify(folders));
    } catch {}
  }, [folders]);

  // Sync taskFolderMap to localStorage
  useEffect(() => {
    try {
      localStorage.setItem('orchestrator_task_folders', JSON.stringify(taskFolderMap));
    } catch {}
  }, [taskFolderMap]);

  const handleAddFolder = (name: string) => {
    const newFolder: ChatFolder = {
      id: `folder-${Date.now()}`,
      name,
      createdAt: new Date().toISOString(),
      projectId: activeProject === 'all' ? undefined : activeProject,
    };
    setFolders(prev => [...prev, newFolder]);
    setConfiguring(newFolder.id);setDirectory('');setBindingError('');
  };

  const handleRenameFolder = (folderId: string, newName: string) => {
    setFolders(prev =>
      prev.map(f => (f.id === folderId ? { ...f, name: newName } : f))
    );
  };

  const handleDeleteFolder = (folderId: string) => {
    setFolders(prev => prev.filter(f => f.id !== folderId));
    // Clear mappings for this folder
    setTaskFolderMap(prev => {
      const updated = { ...prev };
      Object.keys(updated).forEach(taskId => {
        if (updated[taskId] === folderId) {
          delete updated[taskId];
        }
      });
      return updated;
    });
  };

  const handleMoveTaskToFolder = async (taskId: string, folderId: string | null) => {
 const task = data.tasks.find(item => item.id === taskId);
 const conversationId = task?.conversation_id || taskId;
 const relatedIds = data.tasks
 .filter(item => (item.conversation_id || item.id) === conversationId)
 .map(item => item.id);
 const binding=bindings.find(b=>b.id===folderId);
 if(binding){
  try { await onAction('workspace/folders',{id:folderId,name:folders.find(f=>f.id===folderId)?.name,path:binding.path,task_ids:relatedIds}); }
  catch(error){setBindingError((error as Error).message);setConfiguring(folderId);setDirectory(binding.path);return;}
 }

 setTaskFolderMap(prev => {
 const updated = { ...prev };
 // Clear legacy turn-level assignments before updating the conversation.
 for (const id of new Set([conversationId, ...relatedIds])) {
 delete updated[id];
 }
 if (folderId !== null) updated[conversationId] = folderId;
 return updated;
 });
 };

 const handleNewChatInFolder = (folderId: string | null) => {
    setTargetFolderForNewChat(folderId);
    onSelectTask(''); // Deselect current task to show empty chat prompt
  };

  // Filter tasks by active project
  const projectTasks = data.tasks.filter(
    t => activeProject === 'all' || t.project_id === activeProject
  );

  const selectedTask = projectTasks.find(t => t.id === selectedTaskId);
  // Keep one sidebar entry per conversation; the latest turn drives the chat.
  const conversations = Array.from(new Map(
    [...projectTasks].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)).map(t => [t.conversation_id || t.id, t])
  ).values()).sort((a, b) => Date.parse(b.created_at) - Date.parse(a.created_at));
  const currentTask = selectedTask && conversations.find(
    t => (t.conversation_id || t.id) === (selectedTask.conversation_id || selectedTask.id)
  );
  const conversationItems = conversations.map(t => ({...t,
    objective: projectTasks.find(root => root.id === t.conversation_id)?.objective || t.objective
  }));

  const handleSendChatMessage = async (
    objective: string,
    provider: string,
    workflow: string,
    model?: string,
 files: File[] = []
 ) => {
    const inheritedFolder = currentTask ? taskFolderMap[currentTask.conversation_id || currentTask.id] || taskFolderMap[currentTask.id] || Object.entries(taskFolderMap).find(([id]) => projectTasks.some(t => t.id === id && (t.conversation_id || t.id) === (currentTask.conversation_id || currentTask.id)))?.[1] || null : null;
    const folderId=targetFolderForNewChat || inheritedFolder;
    const binding=bindings.find(b=>b.id===folderId);
    if(folderId&&!binding)throw Error('Conecte um diretório a esta pasta antes de enviar. Use o ícone de diretório ao lado do nome.');
    const id = await onSendMessage(objective, provider, workflow, folderId, model, binding?.project_id, files);
    if (id && (targetFolderForNewChat || inheritedFolder)) await handleMoveTaskToFolder(currentTask?.conversation_id || currentTask?.id || id, targetFolderForNewChat || inheritedFolder);
    setTargetFolderForNewChat(null);
  };

  const currentFolderId=targetFolderForNewChat || (currentTask && (taskFolderMap[currentTask.conversation_id||currentTask.id] || taskFolderMap[currentTask.id] || Object.entries(taskFolderMap).find(([id])=>projectTasks.some(t=>t.id===id&&(t.conversation_id||t.id)===(currentTask.conversation_id||currentTask.id)))?.[1])) || null;
  const currentFolder=folders.find(f=>f.id===currentFolderId);
  const currentBinding=bindings.find(b=>b.id===currentFolderId);
  return (
    <div
      style={{ '--workspace-sidebar-width': sidebarCollapsed ? '0px' : `${sidebarWidth}px` } as React.CSSProperties}
 className={`chat-workspace-layout ${sidebarCollapsed ? 'sidebar-collapsed ' : ''}${
        showInspector && currentTask ? 'with-inspector' : 'without-inspector'
      }`}
    >
      {deleteTarget && <div className="conversation-delete-backdrop">
        <section role="alertdialog" aria-modal="true" aria-labelledby="delete-conversation-title" className="panel conversation-delete-dialog">
          <h2 id="delete-conversation-title">Excluir conversa?</h2>
          <p>Todo o histórico desta conversa será excluído. Os arquivos do projeto serão preservados.</p>
          {deleteError && <p role="alert">{deleteError}</p>}
          <div className="flex">
            <button type="button" className="secondary" disabled={deleting} onClick={() => setDeleteTarget(null)}>Cancelar</button>
            <button type="button" className="primary" disabled={!online || deleting} onClick={async () => {
              setDeleting(true); setDeleteError('');
              try {
                const result = await onAction(`tasks/${deleteTarget}/delete`);
                if (!result?.ok) {setDeleteError('Não foi possível excluir. Cancele execuções ativas e tente novamente.'); return;}
                if (result.deleted_ids.includes(currentTask?.id)) onSelectTask('');
                setTaskFolderMap(prev => Object.fromEntries(Object.entries(prev).filter(([key]) => !result.deleted_ids.includes(key))));
                setDeleteTarget(null);
              } catch (error) {setDeleteError((error as Error).message);}
              finally {setDeleting(false);}
            }}>{deleting ? 'Excluindo…' : 'Excluir conversa'}</button>
          </div>
        </section>
      </div>}
      <div className="workspace-mobile-toolbar">
 <button type="button" className="secondary" aria-expanded={mobileNavOpen} aria-controls="workspace-conversation-navigation" onClick={() => { setShowSessions(true); setMobileNavOpen(open => !open); }}><Menu size={16} /> Conversas</button>
 <span>AI Workspace</span>
 </div>
 {mobileNavOpen && <button type="button" className="workspace-mobile-backdrop" aria-label="Fechar navegação" onClick={() => setMobileNavOpen(false)} />}
 {/* Left Column: Folders & Sessions Navigation */}
      <aside id="workspace-conversation-navigation" className={`chat-workspace-sidebar panel ${mobileNavOpen ? 'mobile-open' : ''}`}>
        <div className="workspace-sidebar-header">
 <button type="button" className="workspace-mobile-close" aria-label="Fechar navegação" onClick={() => setMobileNavOpen(false)}><X size={18} /></button>
          <div className="sidebar-title-group">
            <button className="workspace-sessions-toggle" aria-expanded={showSessions} onClick={() => setShowSessions(value => !value)}>Conversas <span>{showSessions ? '⌃' : '⌄'}</span></button>
            <span className="count">{conversations.length}</span>
          </div>
        </div>

        {showSessions && <>
        <button type="button" className="secondary workspace-new-chat" onClick={() => { handleNewChatInFolder(null); setMobileNavOpen(false); }}><Plus size={16} /> Nova conversa</button>
        <FolderTree
          tasks={conversationItems}
          selectedTaskId={currentTask?.id || ''}
          onSelectTask={id => {
            onSelectTask(id);
 setMobileNavOpen(false);
            setTargetFolderForNewChat(null);
          }}
          folders={folders.filter(f => !f.projectId || activeProject === 'all' || f.projectId === activeProject)}
          onDeleteTask={id => {setDeleteTarget(id); setDeleteError('');}}
          onAddFolder={handleAddFolder}
          onRenameFolder={handleRenameFolder}
          onDeleteFolder={handleDeleteFolder}
          taskFolderMap={Object.fromEntries(conversationItems.map(t => [t.id, taskFolderMap[t.conversation_id || t.id] || taskFolderMap[t.id] || Object.entries(taskFolderMap).find(([id]) => projectTasks.some(turn => turn.id === id && (turn.conversation_id || turn.id) === (t.conversation_id || t.id)))?.[1]]).filter((entry): entry is [string, string] => typeof entry[1] === 'string'))}
          onMoveTaskToFolder={handleMoveTaskToFolder}
          onNewTaskInFolder={folderId => { handleNewChatInFolder(folderId); setMobileNavOpen(false); }}
          labels={labels}
          onConfigureFolder={configureFolder}
        />
        </>}
      <div className="workspace-resize-handle" role="separator" aria-label="Largura do painel de conversas" aria-orientation="vertical" aria-valuemin={220} aria-valuemax={520} aria-valuenow={sidebarWidth} tabIndex={0}
        onKeyDown={event => { if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') return; event.preventDefault(); const width = Math.max(220, Math.min(520, sidebarWidth + (event.key === 'ArrowRight' ? 10 : -10))); setSidebarWidth(width); localStorage.setItem('workspace_sidebar_width', String(width)); }}
        onPointerDown={event => { event.currentTarget.setPointerCapture(event.pointerId); }}
        onPointerMove={event => { if (!event.currentTarget.hasPointerCapture(event.pointerId)) return; const bounds = event.currentTarget.parentElement!.getBoundingClientRect(); const width = Math.max(220, Math.min(520, event.clientX - bounds.left)); setSidebarWidth(width); }}
        onPointerUp={event => { event.currentTarget.releasePointerCapture(event.pointerId); localStorage.setItem('workspace_sidebar_width', String(sidebarWidth)); }}
      />
 </aside>

      {/* Center Column: Modern AI Chat Interface */}
      <section className="chat-workspace-main panel">
 <button type="button" className="workspace-sidebar-visibility" onClick={() => setSidebarCollapsed(value => !value)} aria-expanded={!sidebarCollapsed} aria-controls="workspace-conversation-navigation" title={sidebarCollapsed ? "Mostrar conversas" : "Recolher conversas"} aria-label={sidebarCollapsed ? "Mostrar painel de conversas" : "Recolher painel de conversas"}>{sidebarCollapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}</button>
        {configuring && <DirectoryBrowser initialPath={directory} folderName={folders.find(f=>f.id===configuring)?.name || 'Workspace'} busy={bindingBusy} online={online} error={bindingError} hasRunningTasks={data.tasks.some(t => (t.status === 'running' || t.status === 'queued') && (taskFolderMap[t.conversation_id || t.id] === configuring || taskFolderMap[t.id] === configuring))} onCancel={() => setConfiguring(null)} onNativePick={async () => { setBindingBusy(true);setBindingError('');try { const result=await onAction('workspace/pick-directory',{});return result && !result.cancelled ? result.path : undefined; } catch (err) {setBindingError((err as Error).message);return undefined;} finally {setBindingBusy(false);} }} onSelect={async path => {setBindingBusy(true);setBindingError('');try {await saveBinding(configuring,path);setDirectory(path);setConfiguring(null);}catch(err){setBindingError((err as Error).message);}finally{setBindingBusy(false);}}} />}
        {!configuring&&currentFolder&&<div className="folder-binding-summary"><span><strong>{currentFolder.name}</strong><small>{currentBinding?.path||'Nenhum diretório conectado'}</small></span><button type="button" className="secondary" onClick={()=>configureFolder(currentFolder.id)}>{currentBinding?'Alterar diretório':'Conectar diretório'}</button></div>}

        {!configuring&&(!currentFolder||currentBinding)&&<ProjectContext data={data} projectId={currentBinding?.project_id || currentTask?.project_id || (activeProject === 'all' ? data.projects[0]?.id || '' : activeProject)} online={online} request={async(path,body)=>currentFolder&&path==='projects'?saveBinding(currentFolder.id,String(body.path)):onAction(path,body)}/>}
        <ChatView
 key={currentTask?.conversation_id || currentTask?.id || 'new'}
          task={currentTask}
          data={data}
          online={online}
          onSendMessage={handleSendChatMessage}
          onAction={onAction}
          onSelectTask={onSelectTask}
          showInspector={showInspector && !!currentTask}
          onToggleInspector={() => setShowInspector(prev => !prev)}
          labels={labels}
          ImprovementControlsComponent={ImprovementControlsComponent}
          RevisionPanelComponent={RevisionPanelComponent}
          onNewChat={() => {
 setMobileNavOpen(false);
            onSelectTask('');
            setTargetFolderForNewChat(null);
          }}
        />
      </section>

      {/* Right Column: Collapsible Context & Validation Inspector */}
 {showInspector && currentTask && <button type="button" className="workspace-inspector-backdrop" aria-label="Fechar painel de inspeção" onClick={() => setShowInspector(false)} />}
      {showInspector && currentTask && (
        <ChatInspector
          task={currentTask}
          data={data}
          online={online}
          onAcceptQuality={() => onAction(`tasks/${currentTask.id}/accept`)}
          onClose={() => setShowInspector(false)}
        />
      )}
    </div>
  );
}
