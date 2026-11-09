import { isChatProviderReady, canRouteAutomatically } from '../providers';
import React, { useState, useRef, useEffect } from 'react';
import {
  ArrowUp,
  Bot,
  Terminal,
  User,
  Copy,
  Check,
  Download,
  Play,
  Square,
  Sparkles,
  ArrowUpRight,
  Search,
  PanelRightClose,
  PanelRight,
  AlertCircle,
  FileCode,
  ChevronRight,
  RefreshCw, Paperclip, X
} from 'lucide-react';
import { Task, Data, Revision } from '../types';
import { MarkdownRenderer } from './MarkdownRenderer';
import { ExecutionTimeline } from './ExecutionTimeline';

interface ChatViewProps {
  task: Task | undefined;
  data: Data;
  online: boolean;
  onSendMessage: (objective: string, provider: string, workflow: string, model?: string, files?: File[]) => Promise<void>;
  onAction: (path: string, body?: any) => Promise<any>;
  onSelectTask: (taskId: string) => void;
  showInspector: boolean;
  onToggleInspector: () => void;
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
  onNewChat: () => void;
}

const isPreviewableImage = (file: File) => /\.(png|jpe?g|webp|gif)$/i.test(file.name) || file.type.startsWith('image/');

function AttachmentPreview({ file, onOpen }: { file: File; onOpen: (url: string, name: string) => void }) {
 const [url, setUrl] = useState('');
 useEffect(() => {
 if (!isPreviewableImage(file)) return;
 const objectUrl = URL.createObjectURL(file);
 setUrl(objectUrl);
 return () => URL.revokeObjectURL(objectUrl);
 }, [file]);
 if (!url) return <FileCode size={22} aria-hidden="true" />;
 return <button type="button" className="chat-attachment-open" aria-label={`Ampliar imagem ${file.name}`} onClick={() => onOpen(url, file.name)}><img className="chat-attachment-thumbnail" src={url} alt="" /></button>;
}

export function ChatView({
  task,
  data,
  online,
  onSendMessage,
  onAction,
  onSelectTask,
  showInspector,
  onToggleInspector,
  labels,
  ImprovementControlsComponent,
  RevisionPanelComponent,
  onNewChat,
}: ChatViewProps) {
  const draftKey = `orchestrator_chat_draft_${task?.conversation_id || task?.id || 'new'}`;
 const [inputPrompt, setInputPrompt] = useState(() => {
 try { return localStorage.getItem(draftKey) || ''; }
 catch { return ''; }
 });
 useEffect(() => {
 try {
 if (inputPrompt) localStorage.setItem(draftKey, inputPrompt);
 else localStorage.removeItem(draftKey);
 } catch { /* Storage may be disabled in private sessions. */ }
 }, [draftKey, inputPrompt]);
 const [selectedProvider, setSelectedProvider] = useState<string>('auto');
 const [selectedModel, setSelectedModel] = useState('auto');
 const tessModels = data.providers.find(p => p.id === 'tess')?.models || [];
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [files, setFiles] = useState<File[]>([]);
 const [expandedImage, setExpandedImage] = useState<{ url: string; name: string } | null>(null);
 useEffect(() => {
 if (!expandedImage) return;
 const onEscape = (event: KeyboardEvent) => { if (event.key === 'Escape') setExpandedImage(null); };
 document.addEventListener('keydown', onEscape);
 return () => document.removeEventListener('keydown', onEscape);
 }, [expandedImage]);
  const [uploading, setUploading] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const allowed = new Set('png jpg jpeg webp gif pdf docx doc txt md markdown csv xlsx xls json xml svg js jsx ts tsx py html css scss java c cpp h hpp go rs sh sql yaml yml'.split(' '));
  const addFiles = (incoming: File[]) => {
   setSubmitError('');
   const valid = incoming.filter(f => {
   const ext = f.name.split('.').pop()?.toLowerCase() || '';
   if (!allowed.has(ext) || !f.size || f.size > 20 * 1024 * 1024) { setSubmitError('Arquivo não suportado, vazio ou acima de 20 MB: ' + f.name); return false; }
   return true;
   });
   setFiles(previous => {
   const merged = [...previous];
   for (const file of valid) if (!merged.some(f => f.name === file.name && f.size === file.size && f.lastModified === file.lastModified)) merged.push(file);
   if (merged.length > 10 || merged.reduce((n, f) => n + f.size, 0) > 60 * 1024 * 1024) { setSubmitError('Limite de 10 arquivos e 60 MB por mensagem.'); return previous; }
   return merged;
   });
  };
  const [copiedResponse, setCopiedResponse] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
const hasInitiallyScrolled = useRef(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (task) { setSelectedProvider(task.provider); }
    setSelectedModel(task?.spec?.model || 'auto');
  }, [task?.id]);

  const readyProviders = data.providers.filter(isChatProviderReady);
  const hasAutomatic = data.providers.some(canRouteAutomatically);
  const providerReady = selectedProvider === 'auto' ? hasAutomatic : readyProviders.some(p => p.id === selectedProvider);
  useEffect(() => {
    if (!providerReady) setSelectedProvider(hasAutomatic ? 'auto' : readyProviders[0]?.id || '');
  }, [providerReady, hasAutomatic, readyProviders.map(p => p.id).join(',')]);

  // Auto-scroll on new message or task change
  useEffect(() => {
    const end = messagesEndRef.current;
 const container = end?.closest('.chat-thread');
 if (!end || !container) return;
 const nearBottom = container.scrollHeight - container.scrollTop - container.clientHeight < 160;
 if (!hasInitiallyScrolled.current) {
container.scrollTop = container.scrollHeight;
hasInitiallyScrolled.current = true;
} else if (nearBottom) {
container.scrollTop = container.scrollHeight;
}
  }, [task?.id, task?.result, task?.status]);

  // Auto-grow textarea
  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInputPrompt(e.target.value);
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`;
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    const trimmed = inputPrompt.trim();
    if ((!trimmed && !files.length) || isSubmitting || !online || !providerReady || task?.status === 'running' || task?.status === 'queued') return;

    setSubmitError('');
    setIsSubmitting(true);
    try {
      setUploading(true);
 await onSendMessage(trimmed, selectedProvider, 'auto', selectedProvider === 'tess' ? selectedModel : undefined, files);
 setFiles([]);
 try { localStorage.removeItem(draftKey); } catch {}
      setInputPrompt('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    } catch (error) {
      setSubmitError((error as Error).message);
    } finally {
      setIsSubmitting(false);
 setUploading(false);
    }
  };

  const handleCopyFullResult = () => {
    if (task?.result) {
      navigator.clipboard.writeText(task.result);
      setCopiedResponse(true);
      setTimeout(() => setCopiedResponse(false), 2000);
    }
  };

  const providerName = (providerId?: string) => {
    if (!providerId || providerId === 'auto') return 'Orquestrador';
    if (providerId === 'codex') return 'Codex';
    if (providerId === 'rea') return 'REA Local';
    if (['gemini', 'antigravity'].includes(providerId)) return 'Gemini';
    const found = data.providers.find(p => p.id === providerId);
    return found?.name || providerId;
  };

  const visibleResponse = task?.result?.replace(/<(?:tool_call|action)\s+name=[\s\S]*?<\/(?:tool_call|action)>/gi, '').trim() || '';

  const isRunning = task?.status === 'running' || task?.status === 'queued';

  return (
    <div className="chat-container">
      {/* Chat Top Header */}
      <div className="chat-header">
        <div className="chat-header-info">
          {task ? (
            <>
              <h2 className="chat-title" title={task.objective}>
                {task.objective.split(/\n/)[0].replace(/^#+\s*/, '').slice(0, 85)}
              </h2>
              <div className="chat-meta">
                <span className="chat-provider-badge">
                  <Bot size={12} />
                  <span>{providerName(task.provider)}</span>
                </span>
                <span className={`badge ${task.status}`}>
                  <span className="dot" />
                  {labels[task.status] || task.status}
                </span>

              </div>
            </>
          ) : (
            <div>
              <h2 className="chat-title">Nova Conversa</h2>
              <p className="chat-subtitle">Ideias, código e decisões em um só lugar.</p>
            </div>
          )}
        </div>

        <div className="chat-header-actions">
          {task && (
            <button
              type="button"
              className="chat-icon-btn"
              onClick={() => {
                const cp = data.checkpoints.find(c => c.task_id === task.id);
                if (cp) {
                  const blob = new Blob([JSON.stringify(cp.payload, null, 2)], {
                    type: 'application/json',
                  });
                  const a = document.createElement('a');
                  a.href = URL.createObjectURL(blob);
                  a.download = `handoff-${task.id}.json`;
                  a.click();
                  URL.revokeObjectURL(a.href);
                } else {
                  alert('Ainda não há checkpoint para exportar.');
                }
              }}
              title={data.checkpoints.some(c => c.task_id === task.id) ? 'Exportar checkpoint JSON' : 'Checkpoint ainda indisponível para esta conversa'}
              aria-label="Exportar checkpoint JSON"
              disabled={!data.checkpoints.some(c => c.task_id === task.id)}
            >
              <Download size={15} />
            </button>
          )}

          <button
            type="button"
            className="chat-icon-btn"
            onClick={onToggleInspector}
            title={showInspector ? 'Ocultar detalhes' : 'Ver detalhes do contexto'}
            aria-label={showInspector ? 'Ocultar detalhes' : 'Ver detalhes do contexto'}
            disabled={!task}
          >
            {showInspector ? <PanelRightClose size={15} /> : <PanelRight size={15} />}
          </button>
        </div>
      </div>

      {/* Messages Thread */}
      <div className="chat-thread">
        {!task ? (
          <div className="chat-welcome">
            <div className="welcome-icon">
              <Sparkles size={28} />
            </div>
            <h3>O que você deseja construir ou analisar?</h3>
            <p>
              Explore uma ideia, planeje o próximo passo ou transforme seu projeto.
            </p>
            <div className="quick-suggestions">
              <button
                type="button"
                className="suggestion-pill"
                onClick={() =>
                  setInputPrompt('Analise a arquitetura do projeto e sugira otimizações.')
                }
              >
                <Search size={17} /><span>Analisar projeto<small>Entenda a arquitetura e encontre melhorias</small></span><ArrowUpRight size={15} />
              </button>
              <button
                type="button"
                className="suggestion-pill"
                onClick={() =>
                  setInputPrompt('Criar uma funcionalidade com validação de tipagem e testes.')
                }
              >
                <FileCode size={17} /><span>Criar funcionalidade<small>Transforme uma ideia em implementação</small></span><ArrowUpRight size={15} />
              </button>
              <button
                type="button"
                className="suggestion-pill"
                onClick={() =>
                  setInputPrompt('Analise os arquivos do projeto e proponha um plano de implementação.')
                }
              >
                <Sparkles size={17} /><span>Planejar próximos passos<small>Defina uma abordagem antes de começar</small></span><ArrowUpRight size={15} />
              </button>
            </div>
          </div>
        ) : (
          <div className="chat-messages-list">
            {task.conversation_history?.map((message, index) => <React.Fragment key={index}>
              <div className="chat-message-row user-row"><div className="chat-message-content"><div className="chat-bubble-text">{message.objective}</div></div></div>
              <div className="chat-message-row"><div className="chat-message-content"><MarkdownRenderer content={message.result}/></div></div>
            </React.Fragment>)}
            {/* User Message */}
            <div className="chat-message-row user-row">
              <div className="chat-avatar user-avatar" title="Você">
                <User size={15} />
              </div>
              <div className="chat-bubble user-bubble">
                <div className="chat-bubble-author">
                  <span>Você</span>
                  <span className="chat-bubble-time">
                    {new Date(task.created_at).toLocaleTimeString('pt-BR', {
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                  </span>
                </div>
                <div className="chat-bubble-text">{task.objective}</div>
              </div>
            </div>

            {/* Assistant Message */}
            <div className="chat-message-row assistant-row">
              <div
                className={`chat-avatar assistant-avatar ${task.provider || 'auto'}`}
                title={providerName(task.provider)}
              >
                {task.provider === 'codex' ? (
                  <Terminal size={15} />
                ) : (
                  <Bot size={15} />
                )}
              </div>

              <div className="chat-bubble assistant-bubble">
                <div className="chat-bubble-author">
                  <strong>{providerName(task.provider)}</strong>
                  {task.routing?.model && <span className="workflow-badge" title={task.routing.model_reason}>{task.routing.model}</span>}
                  {task.spec?.mode_decision && (<span className="workflow-badge" title={task.spec.mode_decision.decision_reason}>Solicitado: {task.spec.mode_decision.requested_mode} · Selecionado: {task.spec.mode_decision.selected_mode}{task.spec.mode_decision.permission_conflict ? " · Permissão bloqueada" : ""}</span>)}
 {task.workflow && (
                    <span className="workflow-badge">{({direct:'Análise',work:'Work',rea:'Planejamento',deliver:'Artefato',improve:'Melhoria'} as Record<string,string>)[task.workflow] || task.workflow}</span>
                  )}
                  <div className="bubble-actions">
                    {task.result && (
                      <button
                        type="button"
                        className="bubble-action-btn"
                        onClick={handleCopyFullResult}
                        title="Copiar resposta completa"
                      >
                        {copiedResponse ? (
                          <>
                            <Check size={12} className="text-green" />
                            <span>Copiado</span>
                          </>
                        ) : (
                          <>
                            <Copy size={12} />
                            <span>Copiar</span>
                          </>
                        )}
                      </button>
                    )}
                  </div>
                </div>

                {data.events.filter(event => event.task_id === task.id && event.kind === 'model_fallback').map(event => <p key={event.id} role="status" className="chat-p-muted">Modelo alterado de {event.payload.previous_model} para {event.payload.model}: {event.payload.reason}.</p>)}
                {/* Assistant Output Content */}
                <div className="assistant-content" aria-live="polite">
                  {task.status === 'queued' && !task.result ? (
 <div className="ai-thinking-state" role="status">Na fila · aguardando início da execução.</div>
 ) : task.status === 'running' && !task.result ? (
 <div className="ai-thinking-state" role="status">
 <RefreshCw size={14} className="spin text-accent" />
 <span>Execução em andamento · acompanhe as ações registradas abaixo.</span>
 </div>
 ) : visibleResponse ? (
 <>
 <p className="chat-p-muted" role="status">
 {task.status === 'failed' ? 'Execução falhou · saída possivelmente incompleta' : task.status === 'running' || task.status === 'queued' ? 'Saída intermediária · execução em andamento' : task.status === 'completed' ? 'Execução concluída · qualidade sujeita à revisão' : 'Saída registrada'}
 </p>
 {task.status === 'failed' && (
 <div className="chat-error-box" role="alert"><AlertCircle size={15} /><span>{task.error || 'A execução falhou.'}</span></div>
 )}
 <MarkdownRenderer content={visibleResponse} />
 </>
 ) : isRunning ? (
                    <p className="chat-p-muted">Consultando o projeto…</p>
                  ) : task.status === 'failed' ? (
                    <div className="chat-error-box">
                      <AlertCircle size={15} />
                      <span>{task.error || 'A tarefa falhou durante a execução.'}</span>
                    </div>
                  ) : (
                    <p className="chat-p-muted">Aguardando início do processamento...</p>
                  )}
                </div>

                {/* Artifacts Created Banner */}
                {data.artifacts
                  ?.filter(a => a.task_id === task.id)
                  .map(a => (
                    <div className="chat-inline-artifact" key={a.task_id}>
                      <div className="artifact-icon">
                        <FileCode size={18} />
                      </div>
                      <div className="artifact-details">
                        <strong>Resultado e artefatos prontos</strong>
                        <p>
                          {a.manifest.files.length} arquivos gerados · {a.manifest.scope}
                        </p>
                      </div>
                      <div className="artifact-links">
                        <a
                          className="primary-sm"
                          href={a.manifest.preview_url}
                          target="_blank"
                          rel="noreferrer"
                        >
                          <ArrowUpRight size={13} />
                          Abrir resultado
                        </a>
                        <a
                          className="secondary-sm"
                          href={`/api/artifacts/${task.id}/download`}
                        >
                          <Download size={13} />
                          ZIP
                        </a>
                        <button
                          type="button"
                          className="secondary-sm"
                          disabled={!online}
                          onClick={() =>
                            onAction(`tasks/${task.id}/visual-review`)
                          }
                        >
                          <Search size={13} />
                          Análise visual
                        </button>
                      </div>
                    </div>
                  ))}

                {/* Visual Review Sections */}
                {data.visual_reviews
                  ?.filter(r => r.parent_id === task.id || r.task_id === task.id)
                  .slice(0, 1)
                  .map(r => (
                    <div className="chat-visual-review" key={r.task_id}>
                      <div className="visual-header">
                        <h4>Revisão Visual do Agente</h4>
                        <span className="badge">
                          {data.tasks.find(t => t.id === r.task_id)?.status || 'queued'}
                        </span>
                      </div>
                      <div className="visual-grid">
                        {r.capture.images?.map(i => (
                          <a
                            href={`/api/reviews/${r.task_id}/evidence/${i.name}`}
                            target="_blank"
                            rel="noreferrer"
                            key={i.name}
                          >
                            <img
                              src={`/api/reviews/${r.task_id}/evidence/${i.name}`}
                              alt={i.label}
                              loading="lazy"
                            />
                            <span>{i.label}</span>
                          </a>
                        ))}
                      </div>
                      {r.report && (
                        <div className="visual-report">
                          <MarkdownRenderer content={r.report} />
                        </div>
                      )}
                      {data.tasks.find(t => t.id === r.task_id)?.status ===
                        'completed' && (
                        <ImprovementControlsComponent
                          review={r}
                          online={online}
                          onApply={async (ids, feedback) => {
                            await onAction(`tasks/${r.parent_id}/improve`, {
                              review_id: r.task_id,
                              proposal_ids: ids,
                              feedback,
                            });
                          }}
                        />
                      )}
                    </div>
                  ))}

                {/* Revisions Sections */}
                {data.revisions
                  ?.filter(
                    v =>
                      v.parent_id === task.id ||
                      v.task_id === task.id ||
                      v.after_review_id === task.id
                  )
                  .map(v => (
                    <RevisionPanelComponent
                      key={v.task_id}
                      revision={v}
                      data={data}
                      online={online}
                      act={onAction}
                      onOpen={onSelectTask}
                    />
                  ))}

<details className="workspace-execution-details"><summary>Detalhes da execução <span>Eventos, checkpoints e validações</span></summary><ExecutionTimeline task={task} data={data} /></details>
                {/* Action Bar inside Assistant Message */}
                <div className="chat-msg-footer">
                  {task.workflow === 'rea' && task.status === 'completed' && (
                    <button
                      type="button"
                      className="primary-sm"
                      disabled={!online}
                      onClick={() => onAction(`tasks/${task.id}/implement`)}
                    >
                      <Play size={13} />
                      Implementar este plano
                    </button>
                  )}

                  {isRunning ? (
                    <button
                      type="button"
                      className="secondary-sm"
                      disabled={!online}
                      onClick={() => onAction(`tasks/${task.id}/cancel`)}
                    >
                      <Square size={13} />
                      Cancelar execução
                    </button>
                  ) : (
                    task.status !== 'completed' && (
                      <button
                        type="button"
                        className="secondary-sm"
                        disabled={!online}
                        onClick={() => onAction(`tasks/${task.id}/resume`)}
                      >
                        <Play size={13} />
                        Retomar do checkpoint
                      </button>
                    )
                  )}

                  {['completed', 'needs_review'].includes(task.status) &&
                    task.quality !== 'accepted' && (
                      <button
                        type="button"
                        className="secondary-sm"
                        disabled={!online}
                        onClick={() => { if (window.confirm("Aceitar a qualidade registra sua aprovação desta versão. Execução concluída não significa testes aprovados. Você revisou o resultado e deseja aceitar a qualidade?")) void onAction(`tasks/${task.id}/accept`); }}
                      >
                        <Check size={13} />
                        Revisar e aceitar qualidade
                      </button>
                    )}
                </div>
              </div>
            </div>

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Bottom Floating Prompt Dock */}
      <div className="chat-input-dock" onDragOver={e => e.preventDefault()} onDrop={e => { e.preventDefault(); if (!isSubmitting && !isRunning) addFiles(Array.from(e.dataTransfer.files)); }}>
 <input ref={fileInput} type="file" multiple hidden onChange={e => { addFiles(Array.from(e.target.files || [])); e.target.value = ""; }} />
 {uploading && <p role="status">Enviando {files.length} arquivo(s)…</p>}
 <div className="chat-input-wrapper">
 {files.length > 0 && (
 <div className="chat-attachment-list" aria-label="Anexos selecionados">
 {files.map((file, index) => (
 <div className={`chat-attachment-item ${isPreviewableImage(file) ? 'is-image' : 'is-document'}`} key={`${file.name}-${file.size}-${file.lastModified}`}>
 <AttachmentPreview file={file} onOpen={(url, name) => setExpandedImage({ url, name })} />
 {!isPreviewableImage(file) && <span title={file.name}>{file.name}</span>}
 <button type="button" className="chat-attachment-remove" aria-label={`Remover ${file.name}`} disabled={isSubmitting} onClick={() => { setExpandedImage(null); setFiles(old => old.filter((_, i) => i !== index)); }}><X size={14}/></button>
 </div>
 ))}
 </div>
 )}
 <textarea
            ref={textareaRef}
            className="chat-textarea"
            aria-label="Mensagem para o agente"
            placeholder={
              task
                ? 'Continue a conversa…'
                : 'O que você quer fazer neste projeto?'
            }
            value={inputPrompt}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
 onPaste={e => { const images = Array.from(e.clipboardData.files).filter(f => isPreviewableImage(f)); if (images.length) { e.preventDefault(); addFiles(images); } }}
            rows={1}
            disabled={!online || isSubmitting || isRunning}
          />

          <div className="chat-input-controls">
            <div className="chat-controls-left">
 <button type="button" className="icon-btn" title="Anexar arquivos" aria-label="Anexar arquivos" disabled={!online || isSubmitting || isRunning} onClick={() => fileInput.current?.click()}><Paperclip size={17}/></button>
              {selectedProvider === 'tess' && <div className="control-pill-group">
                <select className="control-select" aria-label="Modelo Tess" value={selectedModel}
                  disabled={!online || isRunning || isSubmitting} onChange={e => setSelectedModel(e.target.value)}>
                  <option value="auto">Modelo automático</option>
                  {tessModels.map(model => <option key={model} value={model}>{model}</option>)}
                </select>
              </div>}
              {/* Provider Quick Selector */}
              <div className="control-pill-group">
                <Bot size={13} />
                <select
                  value={selectedProvider}
                  onChange={e => setSelectedProvider(e.target.value)}
                  className="control-select"
                  title="Selecionar agente"
                  aria-label="Agente pronto para usar"
                  disabled={!online || !readyProviders.length || isRunning}
                >
                  {hasAutomatic && <option value="auto">Escolher automaticamente</option>}
                  {!readyProviders.length && <option value="">Nenhum agente pronto</option>}
                  {readyProviders
                    .map(p => (
                      <option key={p.id} value={p.id}>
                        {p.name || p.id}
                      </option>
                    ))}

                </select>
              </div>


            </div>

            <div className="chat-controls-right">
              {isRunning ? (
                <button
                  type="button"
                  className="chat-stop-btn"
                  onClick={() => onAction(`tasks/${task!.id}/cancel`)}
                  title="Interromper execução"
                >
                  <Square size={13} />
                  <span>Parar</span>
                </button>
              ) : (
                <button
                  type="button"
                  className="chat-send-btn"
                  disabled={(!inputPrompt.trim() && !files.length) || isSubmitting || !online || !providerReady}
                  onClick={handleSubmit}
                  title="Enviar mensagem (Enter)"
                >
                  <ArrowUp size={16} /><span>Enviar</span>
                </button>
              )}
            </div>
          </div>
        </div>

        {expandedImage && (
<div
className="chat-image-lightbox"
role="presentation"
onMouseDown={event => {
if (event.target === event.currentTarget) setExpandedImage(null);
}}
>
<div className="chat-image-lightbox-content" role="dialog" aria-modal="true" aria-label={`Visualização de ${expandedImage.name}`}>
<button
type="button"
className="chat-image-lightbox-close"
aria-label="Fechar imagem ampliada"
onClick={() => setExpandedImage(null)}
>
<X size={22} />
</button>
<img src={expandedImage.url} alt={expandedImage.name} />
</div>
</div>
)}
{submitError && <p role="alert" className="chat-submit-error">{submitError}</p>}
        {!readyProviders.length && <p role="status" className="chat-submit-error">Nenhum agente pronto. Conecte e valide um agente na página Agents.</p>}
        <div className="chat-input-hint">
          <span>
            {!online ? 'Offline' : 'Enter para enviar'}
          </span>
          <span className="hint-divider">·</span>
          <span>Shift + Enter para quebrar linha</span>
        </div>
      </div>
    </div>
  );
}
