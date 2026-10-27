import React, { useState, useEffect } from 'react';
import { Task, Data, ChatFolder, Revision } from '../types';
import { FolderTree } from './FolderTree';
import { ChatView } from './ChatView';
import { ProjectContext } from './ProjectContext';
import { ChatInspector } from './ChatInspector';

interface ChatWorkspaceProps {
  data: Data;
  activeProject: string;
  selectedTaskId: string;
  onSelectTask: (taskId: string) => void;
  online: boolean;
  onSendMessage: (objective: string, provider: string, workflow: string, folderId?: string | null) => Promise<string | void>;
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
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState('');
  const [targetFolderForNewChat, setTargetFolderForNewChat] = useState<string | null>(null);

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

  const handleMoveTaskToFolder = (taskId: string, folderId: string | null) => {
    setTaskFolderMap(prev => {
      const updated = { ...prev };
      if (folderId === null) {
        delete updated[taskId];
      } else {
        updated[taskId] = folderId;
      }
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
    [...projectTasks].reverse().map(t => [t.conversation_id || t.id, t])
  ).values());
  const currentTask = selectedTask && conversations.find(
    t => (t.conversation_id || t.id) === (selectedTask.conversation_id || selectedTask.id)
  );
  const conversationItems = conversations.map(t => ({...t,
    objective: projectTasks.find(root => root.id === t.conversation_id)?.objective || t.objective
  }));

  const handleSendChatMessage = async (
    objective: string,
    provider: string,
    workflow: string
  ) => {
    const inheritedFolder = currentTask ? taskFolderMap[currentTask.id] || taskFolderMap[currentTask.conversation_id || currentTask.id] : null;
    const id = await onSendMessage(objective, provider, workflow, targetFolderForNewChat || inheritedFolder);
    if (id && (targetFolderForNewChat || inheritedFolder)) handleMoveTaskToFolder(id, targetFolderForNewChat || inheritedFolder);
    setTargetFolderForNewChat(null);
  };

  return (
    <div
      className={`chat-workspace-layout ${
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
      {/* Left Column: Folders & Sessions Navigation */}
      <aside className="chat-workspace-sidebar panel">
        <div className="workspace-sidebar-header">
          <div className="sidebar-title-group">
            <button className="workspace-sessions-toggle" aria-expanded={showSessions} onClick={() => setShowSessions(value => !value)}>Conversas <span>{showSessions ? '⌃' : '⌄'}</span></button>
            <span className="count">{conversations.length}</span>
          </div>
        </div>

        {showSessions && <>
        <button type="button" className="secondary workspace-new-chat" onClick={() => handleNewChatInFolder(null)}>+ Nova conversa</button>
        <FolderTree
          tasks={conversationItems}
          selectedTaskId={currentTask?.id || ''}
          onSelectTask={id => {
            onSelectTask(id);
            setTargetFolderForNewChat(null);
          }}
          folders={folders.filter(f => !f.projectId || activeProject === 'all' || f.projectId === activeProject)}
          onDeleteTask={id => {setDeleteTarget(id); setDeleteError('');}}
          onAddFolder={handleAddFolder}
          onRenameFolder={handleRenameFolder}
          onDeleteFolder={handleDeleteFolder}
          taskFolderMap={taskFolderMap}
          onMoveTaskToFolder={handleMoveTaskToFolder}
          onNewTaskInFolder={handleNewChatInFolder}
          labels={labels}
        />
        </>}
      </aside>

      {/* Center Column: Modern AI Chat Interface */}
      <section className="chat-workspace-main panel">
        <ProjectContext data={data} projectId={currentTask?.project_id || (activeProject === 'all' ? data.projects[0]?.id || '' : activeProject)} online={online} request={onAction}/>
        <ChatView
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
            onSelectTask('');
            setTargetFolderForNewChat(null);
          }}
        />
      </section>

      {/* Right Column: Collapsible Context & Validation Inspector */}
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
