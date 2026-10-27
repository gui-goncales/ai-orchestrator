import React, { useState } from 'react';
import {
  Folder,
  FolderOpen,
  FolderPlus,
  ChevronDown,
  ChevronRight,
  MoreVertical,
  Plus,
  Search,
  MessageSquare,
  Trash2,
  Edit2,
  FolderInput,
  Check,
  X
} from 'lucide-react';
import { Task, ChatFolder } from '../types';

interface FolderTreeProps {
  tasks: Task[];
  selectedTaskId: string;
  onSelectTask: (taskId: string) => void;
  onDeleteTask: (taskId: string) => void;
  folders: ChatFolder[];
  onAddFolder: (name: string) => void;
  onRenameFolder: (folderId: string, newName: string) => void;
  onDeleteFolder: (folderId: string) => void;
  taskFolderMap: Record<string, string>; // taskId -> folderId
  onMoveTaskToFolder: (taskId: string, folderId: string | null) => void;
  onNewTaskInFolder?: (folderId: string | null) => void;
  labels: Record<string, string>;
}

export function FolderTree({
  tasks,
  selectedTaskId,
  onSelectTask,
  onDeleteTask,
  folders,
  onAddFolder,
  onRenameFolder,
  onDeleteFolder,
  taskFolderMap,
  onMoveTaskToFolder,
  onNewTaskInFolder,
  labels,
}: FolderTreeProps) {
  const [search, setSearch] = useState('');
  const [collapsedFolders, setCollapsedFolders] = useState<Record<string, boolean>>({});
  const [isCreatingFolder, setIsCreatingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [editingFolderId, setEditingFolderId] = useState<string | null>(null);
  const [editingFolderName, setEditingFolderName] = useState('');
  const [openMenuTaskId, setOpenMenuTaskId] = useState<string | null>(null);

  const toggleFolder = (folderId: string) => {
    setCollapsedFolders(prev => ({ ...prev, [folderId]: !prev[folderId] }));
  };

  const handleCreateSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (newFolderName.trim()) {
      onAddFolder(newFolderName.trim());
      setNewFolderName('');
      setIsCreatingFolder(false);
    }
  };

  const handleRenameSubmit = (folderId: string) => {
    if (editingFolderName.trim()) {
      onRenameFolder(folderId, editingFolderName.trim());
      setEditingFolderId(null);
      setEditingFolderName('');
    }
  };

  // Filter tasks based on search
  const filteredTasks = tasks.filter(t =>
    t.objective.toLowerCase().includes(search.toLowerCase()) ||
    t.id.toLowerCase().includes(search.toLowerCase())
  );

  // Group tasks by folder
  const tasksByFolder: Record<string, Task[]> = {};
  const unassignedTasks: Task[] = [];

  // Initialize folders
  folders.forEach(f => {
    tasksByFolder[f.id] = [];
  });

  filteredTasks.forEach(task => {
    const fId = taskFolderMap[task.id];
    if (fId && tasksByFolder[fId]) {
      tasksByFolder[fId].push(task);
    } else {
      unassignedTasks.push(task);
    }
  });

  return (
    <div className="folder-tree-container">
      {/* Search and Action Bar */}
      <div className="folder-tree-header">
        <div className="folder-tree-search">
          <Search size={14} />
          <input
            type="text"
            placeholder="Buscar conversas..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          {search && (
            <button
              className="icon-btn-xs"
              onClick={() => setSearch('')}
              title="Limpar busca"
            >
              <X size={12} />
            </button>
          )}
        </div>
        <button
          className="folder-add-btn"
          onClick={() => {
            setIsCreatingFolder(true);
            setNewFolderName('');
          }}
          title="Nova Pasta"
        >
          <FolderPlus size={14} />
        </button>
      </div>

      {/* New Folder Inline Form */}
      {isCreatingFolder && (
        <form onSubmit={handleCreateSubmit} className="folder-inline-form">
          <Folder size={14} className="folder-icon-accent" />
          <input
            autoFocus
            type="text"
            placeholder="Nome da pasta..."
            value={newFolderName}
            onChange={e => setNewFolderName(e.target.value)}
          />
          <button type="submit" className="icon-btn-xs" title="Criar">
            <Check size={13} />
          </button>
          <button
            type="button"
            className="icon-btn-xs"
            onClick={() => setIsCreatingFolder(false)}
            title="Cancelar"
          >
            <X size={13} />
          </button>
        </form>
      )}

      {/* Folders List */}
      <div className="folder-tree-list">
        {folders.map(folder => {
          const folderTasks = tasksByFolder[folder.id] || [];
          const isCollapsed = !!collapsedFolders[folder.id];
          const isEditing = editingFolderId === folder.id;

          return (
            <div key={folder.id} className="folder-group">
              <div className="folder-header-row">
                <button
                  type="button"
                  className="folder-toggle-btn"
                  onClick={() => toggleFolder(folder.id)}
                >
                  {isCollapsed ? <ChevronRight size={13} /> : <ChevronDown size={13} />}
                  {isCollapsed ? (
                    <Folder size={14} className="folder-icon" />
                  ) : (
                    <FolderOpen size={14} className="folder-icon open" />
                  )}
                  {isEditing ? (
                    <input
                      autoFocus
                      type="text"
                      className="folder-rename-input"
                      value={editingFolderName}
                      onChange={e => setEditingFolderName(e.target.value)}
                      onKeyDown={e => {
                        if (e.key === 'Enter') handleRenameSubmit(folder.id);
                        if (e.key === 'Escape') setEditingFolderId(null);
                      }}
                      onClick={e => e.stopPropagation()}
                    />
                  ) : (
                    <span className="folder-name" title={folder.name}>
                      {folder.name}
                    </span>
                  )}
                  <span className="folder-count">{folderTasks.length}</span>
                </button>

                <div className="folder-actions">
                  {isEditing ? (
                    <button
                      className="icon-btn-xs"
                      onClick={() => handleRenameSubmit(folder.id)}
                      title="Salvar"
                    >
                      <Check size={12} />
                    </button>
                  ) : (
                    <>
                      {onNewTaskInFolder && (
                        <button
                          className="icon-btn-xs"
                          onClick={() => onNewTaskInFolder(folder.id)}
                          title="Nova conversa nesta pasta"
                        >
                          <Plus size={12} />
                        </button>
                      )}
                      <button
                        className="icon-btn-xs"
                        onClick={() => {
                          setEditingFolderId(folder.id);
                          setEditingFolderName(folder.name);
                        }}
                        title="Renomear pasta"
                      >
                        <Edit2 size={11} />
                      </button>
                      <button
                        className="icon-btn-xs delete"
                        onClick={() => {
                          if (confirm(`Excluir a pasta "${folder.name}"? As conversas serão movidas para Sem Pasta.`)) {
                            onDeleteFolder(folder.id);
                          }
                        }}
                        title="Excluir pasta"
                      >
                        <Trash2 size={11} />
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Tasks within folder */}
              {!isCollapsed && (
                <div className="folder-tasks">
                  {folderTasks.length === 0 ? (
                    <div className="folder-empty">Pasta vazia</div>
                  ) : (
                    folderTasks.map(task => (
                      <TaskTreeItem
                        key={task.id}
                        task={task}
                        isSelected={task.id === selectedTaskId}
                        onSelect={() => onSelectTask(task.id)}
                        folders={folders}
                        currentFolderId={folder.id}
                        onDelete={() => onDeleteTask(task.id)}
                        onMoveFolder={fId => onMoveTaskToFolder(task.id, fId)}
                        isMenuOpen={openMenuTaskId === task.id}
                        onToggleMenu={() =>
                          setOpenMenuTaskId(openMenuTaskId === task.id ? null : task.id)
                        }
                        labels={labels}
                      />
                    ))
                  )}
                </div>
              )}
            </div>
          );
        })}

        {/* Unassigned / Default Section */}
        <div className="folder-group unassigned-group">
          <div className="folder-header-row unassigned-header">
            <span className="unassigned-title">
              <MessageSquare size={13} />
              <span>Sem pasta / Recentes</span>
              <span className="folder-count">{unassignedTasks.length}</span>
            </span>
          </div>

          <div className="folder-tasks">
            {unassignedTasks.length === 0 ? (
              <div className="folder-empty">Nenhuma conversa solta</div>
            ) : (
              unassignedTasks.map(task => (
                <TaskTreeItem
                  key={task.id}
                  task={task}
                  isSelected={task.id === selectedTaskId}
                  onSelect={() => onSelectTask(task.id)}
                  folders={folders}
                  currentFolderId={null}
                  onDelete={() => onDeleteTask(task.id)}
                        onMoveFolder={fId => onMoveTaskToFolder(task.id, fId)}
                  isMenuOpen={openMenuTaskId === task.id}
                  onToggleMenu={() =>
                    setOpenMenuTaskId(openMenuTaskId === task.id ? null : task.id)
                  }
                  labels={labels}
                />
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function TaskTreeItem({
  task,
  isSelected,
  onSelect,
  folders,
  currentFolderId,
  onMoveFolder,
  onDelete,
  isMenuOpen,
  onToggleMenu,
  labels,
}: {
  task: Task;
  isSelected: boolean;
  onSelect: () => void;
  folders: ChatFolder[];
  currentFolderId: string | null;
  onMoveFolder: (folderId: string | null) => void;
  onDelete: () => void;
  isMenuOpen: boolean;
  onToggleMenu: () => void;
  labels: Record<string, string>;
}) {
  const statusColorClass =
    task.status === 'completed'
      ? 'status-green'
      : task.status === 'running'
      ? 'status-purple'
      : task.status === 'failed'
      ? 'status-red'
      : 'status-muted';

  return (
    <div className={`task-tree-item ${isSelected ? 'active' : ''}`}>
      <button
        type="button"
        className="task-tree-btn"
        onClick={onSelect}
        title={task.objective}
      >
        <span className={`task-status-dot ${statusColorClass}`} />
        <span className="task-tree-title">{task.objective}</span>
      </button>

      <button type="button" className="icon-btn-xs" title="Excluir conversa" aria-label="Excluir conversa" onClick={onDelete}><Trash2 size={12}/></button>
      {folders.length > 0 && (
        <div className="task-tree-actions">
          <button
            type="button"
            className="icon-btn-xs"
            onClick={e => {
              e.stopPropagation();
              onToggleMenu();
            }}
            title="Mover de pasta"
          >
            <FolderInput size={12} />
          </button>

          {isMenuOpen && (
            <div
              className="task-folder-dropdown"
              onClick={e => e.stopPropagation()}
            >
              <div className="dropdown-title">Mover para:</div>
              {currentFolderId !== null && (
                <button
                  type="button"
                  className="dropdown-item"
                  onClick={() => {
                    onMoveFolder(null);
                    onToggleMenu();
                  }}
                >
                  <MessageSquare size={12} />
                  <span>Sem pasta</span>
                </button>
              )}
              {folders.map(f => (
                <button
                  key={f.id}
                  type="button"
                  className={`dropdown-item ${currentFolderId === f.id ? 'current' : ''}`}
                  onClick={() => {
                    onMoveFolder(f.id);
                    onToggleMenu();
                  }}
                >
                  <Folder size={12} />
                  <span>{f.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
