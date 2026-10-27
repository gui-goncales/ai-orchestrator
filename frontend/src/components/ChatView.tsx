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
  Layers,
  ChevronRight,
  RefreshCw
} from 'lucide-react';
import { Task, Data, Revision } from '../types';
import { MarkdownRenderer } from './MarkdownRenderer';

interface ChatViewProps {
  task: Task | undefined;
  data: Data;
  online: boolean;
  onSendMessage: (objective: string, provider: string, workflow: string) => Promise<void>;
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
  const [inputPrompt, setInputPrompt] = useState('');
  const [selectedProvider, setSelectedProvider] = useState<string>('auto');
  const [selectedWorkflow, setSelectedWorkflow] = useState<string>('direct');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState('');
  const [copiedResponse, setCopiedResponse] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (task) { setSelectedProvider(task.provider); setSelectedWorkflow(task.workflow || 'auto'); }
  }, [task?.id]);

  const readyProviders = data.providers.filter(isChatProviderReady);
  const hasAutomatic = data.providers.some(canRouteAutomatically);
  const providerReady = selectedProvider === 'auto' ? hasAutomatic : readyProviders.some(p => p.id === selectedProvider);
  useEffect(() => {
    if (!providerReady) setSelectedProvider(hasAutomatic ? 'auto' : readyProviders[0]?.id || '');
  }, [providerReady, hasAutomatic, readyProviders.map(p => p.id).join(',')]);

  // Auto-scroll on new message or task change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
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
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleSubmit = async () => {
    const trimmed = inputPrompt.trim();
    if (!trimmed || isSubmitting || !online || !providerReady || task?.status === 'running' || task?.status === 'queued') return;

    setSubmitError('');
    setIsSubmitting(true);
    try {
      await onSendMessage(trimmed, selectedProvider, selectedWorkflow);
      setInputPrompt('');
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
      }
    } catch (error) {
      setSubmitError((error as Error).message);
    } finally {
      setIsSubmitting(false);
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
  const toolActivity = data.events.filter(e => e.task_id === task?.id && e.kind === 'tool_call').slice().reverse();

  const isRunning = task?.status === 'running' || task?.status === 'queued';

  return (
    <div className="chat-container">
      {/* Chat Top Header */}
      <div className="chat-header">
        <div className="chat-header-info">
          {task ? (
            <>
              <h2 className="chat-title" title={task.objective}>
                {task.objective}
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
                <span className="mono chat-id">#{task.id.slice(0, 8)}</span>
              </div>
            </>
          ) : (
            <div>
              <h2 className="chat-title">Nova Conversa</h2>
              <p className="chat-subtitle">Pronto para orquestrar agentes e tarefas.</p>
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
              title="Exportar checkpoint JSON"
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
              Converse sobre o projeto ou escolha Work para editar os arquivos da pasta conectada.
            </p>
            <div className="quick-suggestions">
              <button
                type="button"
                className="suggestion-pill"
                onClick={() =>
                  setInputPrompt('Analise a arquitetura do projeto e sugira otimizações.')
                }
              >
                Analisar arquitetura do projeto
              </button>
              <button
                type="button"
                className="suggestion-pill"
                onClick={() =>
                  setInputPrompt('Criar uma funcionalidade com validação de tipagem e testes.')
                }
              >
                Desenvolver nova funcionalidade
              </button>
              <button
                type="button"
                className="suggestion-pill"
                onClick={() =>
                  setInputPrompt('Analise os arquivos do projeto e proponha um plano de implementação.')
                }
              >
                Planejar uma alteração
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

                {/* Assistant Output Content */}
                <div className="assistant-content">
                  {task.status === 'running' && !task.result ? (
                    <div className="ai-thinking-state">
                      <RefreshCw size={14} className="spin text-accent" />
                      <span>Agente processando resposta e gerando saídas…</span>
                    </div>
                  ) : visibleResponse ? (
                    <MarkdownRenderer content={visibleResponse} />
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

                {toolActivity.length > 0 && <details className="chat-tool-activity"><summary>{toolActivity.length} ações no projeto</summary><ul>{toolActivity.map(e => <li key={e.id}><span>{({read_file:'Leitura',list_dir:'Pasta',find_files:'Busca',write_file:'Escrita',edit_file:'Edição',delete_file:'Exclusão'} as Record<string,string>)[e.payload.name] || e.payload.name}</span> <code>{e.payload.args?.path || e.payload.args?.pattern || ''}</code></li>)}</ul></details>}
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
                        onClick={() => onAction(`tasks/${task.id}/accept`)}
                      >
                        <Check size={13} />
                        Aceitar qualidade
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
      <div className="chat-input-dock">
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder={
              task
                ? 'Continue a conversa…'
                : 'O que você quer fazer neste projeto?'
            }
            value={inputPrompt}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={!online || isSubmitting || isRunning}
          />

          <div className="chat-input-controls">
            <div className="chat-controls-left">
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

              {/* Workflow Quick Selector */}
              <div className="control-pill-group">
                <Layers size={13} />
                <select
                  value={selectedWorkflow}
                  onChange={e => setSelectedWorkflow(e.target.value)}
                  className="control-select"
                  title="Tipo de fluxo"
                  aria-label="Modo de trabalho"
                  disabled={isRunning}
                >
                  <option value="auto">Decidir pelo objetivo</option>
                  <option value="work">Work · arquivos e comandos</option><option value="deliver">Criar artefato</option>
                  <option value="direct">Analisar · somente leitura</option>
                  <option value="rea">Planejar</option>
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
                  disabled={!inputPrompt.trim() || isSubmitting || !online || !providerReady}
                  onClick={handleSubmit}
                  title="Enviar mensagem (Enter)"
                >
                  <ArrowUp size={16} />
                </button>
              )}
            </div>
          </div>
        </div>

        {submitError && <p role="alert" className="chat-submit-error">{submitError}</p>}
        {!readyProviders.length && <p role="status" className="chat-submit-error">Nenhum agente pronto. Conecte e valide um agente na página Agents.</p>}
        <div className="chat-input-hint">
          <span>
            {!online ? 'Offline' : selectedWorkflow === 'work' ? 'Permite editar a pasta do projeto' : selectedWorkflow === 'direct' ? 'Leitura da pasta · sem alterações' : 'Enter para enviar'}
          </span>
          <span className="hint-divider">·</span>
          <span>Shift + Enter para quebrar linha</span>
        </div>
      </div>
    </div>
  );
}
