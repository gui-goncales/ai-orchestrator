import React from 'react';
import { Box, Check, X, Shield, Cpu, Activity, Database, CheckCircle2, ChevronDown, ScrollText } from 'lucide-react';
import { Task, Data } from '../types';

interface ChatInspectorProps {
  task: Task;
  data: Data;
  online: boolean;
  onAcceptQuality: () => Promise<void>;
  onClose: () => void;
}

const fmt = (n: number) =>
  new Intl.NumberFormat('pt-BR', {
    notation: n > 9999 ? 'compact' : 'standard',
    maximumFractionDigits: 1,
  }).format(n);

const date = (s: string) =>
  new Date(s).toLocaleString('pt-BR', {
    day: '2-digit',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  });

export function ChatInspector({
  task,
  data,
  online,
  onAcceptQuality,
  onClose,
}: ChatInspectorProps) {
  const providerLabel = data.providers.find(p => p.id === task.provider)?.name || task.provider;

  const hasUsage = task.usage?.input_tokens != null || task.usage?.output_tokens != null;
  const totalTokens = hasUsage ? (task.usage?.input_tokens ?? 0) + (task.usage?.output_tokens ?? 0) : null;

  const stages =
    task.workflow === 'deliver'
      ? ['research', 'evaluate', 'architect', 'implement', 'validate']
      : ['research', 'evaluate', 'architect'];

  const checkpoints = data.checkpoints.filter(c => c.task_id === task.id);
  const logs = data.events
    .filter(e => e.task_id === task.id)
    .slice()
    .sort((a, b) => Date.parse(b.time) - Date.parse(a.time))
    .slice(0, 60);

  return (
    <aside className="panel inspector chat-inspector-panel">
      <div className="inspector-header">
        <div className="flex items-center gap-2">
          <Activity size={15} className="text-accent" />
          <h3>Inspetor de Contexto</h3>
        </div>
        <button
          type="button"
          className="icon-btn-xs"
          onClick={onClose}
          title="Fechar painel"
          aria-label="Fechar painel de inspeção"
        >
          <X size={14} />
        </button>
      </div>

      <div className="inspector-content">
        <div className="inspector-item">
          <span className="inspector-label">
            <Cpu size={12} /> Agente / Modelo
          </span>
          <strong>{providerLabel}</strong>
        </div>

        <div className="inspector-item">
          <span className="inspector-label">
            <Database size={12} /> Decisão do Orquestrador
          </span>
          <p>
            {task.routing?.reason ||
              'Não informado'}
          </p>
        </div>

        <div className="inspector-item">
          <span className="inspector-label">
            <Shield size={12} /> Política & Segurança
          </span>
          <strong>
            {task.workflow === 'work' ? 'Escrita na pasta vinculada' : ['deliver', 'improve'].includes(task.workflow || '')
              ? 'Escrita no workspace isolado'
              : 'Somente leitura'}
          </strong>
        </div>

        <div className="inspector-item">
          <span className="inspector-label">Contexto Otimizado</span>
          <p>
            {task.context_metrics?.prompt_characters ?? '—'} caracteres ·{' '}
            {task.context_metrics?.duplicates_removed ? task.context_metrics.duplicates_removed.length : 'Não informado'} duplicatas
            removidas
          </p>
          <p className="text-xs text-muted">
            {task.context_metrics?.constraints_preserved === true ? 'Objetivo e restrições preservados.' : 'Preservação das restrições: não informada.'}
          </p>
        </div>

        <div className="inspector-item">
          <span className="inspector-label">Tokens Reportados</span>
          <strong className="mono text-lg">{totalTokens === null ? 'Não informado' : fmt(totalTokens)}</strong>
          <small className="text-muted block mt-1">
            Entrada: {task.usage?.input_tokens == null ? '—' : fmt(task.usage.input_tokens)} · Saída:{' '}
            {task.usage?.output_tokens == null ? '—' : fmt(task.usage.output_tokens)}
          </small>
        </div>

        <div className="inspector-item">
          <span className="inspector-label">Validação & Qualidade</span>
          <strong>
            {task.status === 'completed'
              ? ['deliver', 'improve'].includes(task.workflow || '')
                ? 'Execução concluída · confira os testes e artefatos'
                : 'Execução concluída · qualidade não aceita automaticamente'
              : 'Pendente de validação'}
          </strong>
          <div className="inspector-validation-facts">
            <div><span>Execução</span><strong>{task.status === 'completed' ? 'Concluída' : task.status === 'failed' ? 'Falhou' : task.status}</strong></div>
            <div><span>Testes executados</span><strong>Não informado</strong></div>
            <div><span>Validação</span><strong>{task.validation?.status || 'Não informada'}</strong></div>
            <div><span>Aprovação técnica</span><strong>{task.validation?.status === 'approved' ? 'Aprovada' : 'Não comprovada'}</strong></div>
            <div><span>Aceite</span><strong>{task.quality === 'accepted' ? 'Aceita pelo usuário' : 'Pendente'}</strong></div>
          </div>
          {task.quality === 'accepted' ? (
            <div className="quality-badge accepted">
              <CheckCircle2 size={13} />
              <span>Qualidade aceita pelo usuário</span>
            </div>
          ) : (
            ['completed', 'needs_review'].includes(task.status) && (
              <button
                type="button"
                className="secondary-sm mt-2 w-full"
                disabled={!online}
                onClick={() => { if (window.confirm("Aceitar a qualidade registra sua aprovação desta versão. Execução concluída não significa testes aprovados. Você revisou o resultado e deseja aceitar a qualidade?")) void onAcceptQuality(); }}
              >
                <Check size={13} />
                Revisar e aceitar qualidade da versão
              </button>
            )
          )}
        </div>

        {['rea', 'deliver'].includes(task.workflow || '') && (
          <div className="inspector-stages">
            <h4>Etapas de Execução</h4>
            {stages.map(stage => {
              const done = data.task_steps?.some(
                s => s.task_id === task.id && s.stage === stage
              );
              return (
                <div className="stage-row" key={stage}>
                  <span className="mono">{stage.toUpperCase()}</span>
                  <span className={`stage-status ${done ? 'done' : 'pending'}`}>
                    {done ? 'Registrada' : 'Sem registro'}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        {/* Gaveta retrátil: checkpoints persistidos */}
        <details className="inspector-drawer drawer-checkpoints" open={checkpoints.length > 0}>
          <summary>
            <Box size={12} />
            <span>Checkpoints Salvos</span>
            <span className="drawer-count">{checkpoints.length}</span>
            <ChevronDown size={13} className="drawer-chevron" />
          </summary>
          <div className="drawer-body">
            {checkpoints.length === 0 ? (
              <div className="drawer-empty">
                <Box size={18} />
                <p>Nenhum checkpoint registrado.</p>
              </div>
            ) : (
              checkpoints.map(c => (
                <details key={c.id} className="checkpoint-detail">
                  <summary>
                    <Box size={12} />
                    <span>
                      #{c.id} · {date(c.time)}
                    </span>
                  </summary>
                  <pre>{JSON.stringify(c.payload, null, 2)}</pre>
                </details>
              ))
            )}
          </div>
        </details>

        {/* Gaveta retrátil: eventos/logs brutos da tarefa */}
        <details className="inspector-drawer drawer-logs">
          <summary>
            <ScrollText size={12} />
            <span>Logs brutos</span>
            <span className="drawer-count">{logs.length}</span>
            <ChevronDown size={13} className="drawer-chevron" />
          </summary>
          <div className="drawer-body">
            {logs.length === 0 ? (
              <div className="drawer-empty">
                <ScrollText size={18} />
                <p>Nenhum evento registrado para esta tarefa.</p>
              </div>
            ) : (
              logs.map(e => (
                <div className="log-row" key={e.id}>
                  <div className="log-meta">
                    <span className="log-kind mono">{e.kind}</span>
                    <span>{date(e.time)}</span>
                  </div>
                  {e.payload != null && e.payload !== '' && (
                    <pre>{typeof e.payload === 'string' ? e.payload : JSON.stringify(e.payload, null, 2)}</pre>
                  )}
                </div>
              ))
            )}
          </div>
        </details>
      </div>
    </aside>
  );
}
