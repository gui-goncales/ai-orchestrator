import React from 'react';
import { Box, Check, X, Shield, Cpu, Activity, Database, CheckCircle2 } from 'lucide-react';
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

  const totalTokens = (task.usage?.input_tokens || 0) + (task.usage?.output_tokens || 0);

  const stages =
    task.workflow === 'deliver'
      ? ['research', 'evaluate', 'architect', 'implement', 'validate']
      : ['research', 'evaluate', 'architect'];

  const checkpoints = data.checkpoints.filter(c => c.task_id === task.id);

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
              'Seleção explícita de versão anterior ou ferramenta de artefatos.'}
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
            {(task.context_metrics?.duplicates_removed || []).length} duplicatas
            removidas
          </p>
          <p className="text-xs text-muted">
            Objetivo e restrições preservados.
          </p>
        </div>

        <div className="inspector-item">
          <span className="inspector-label">Tokens Reportados</span>
          <strong className="mono text-lg">{fmt(totalTokens)}</strong>
          <small className="text-muted block mt-1">
            Entrada: {fmt(task.usage?.input_tokens || 0)} · Saída:{' '}
            {fmt(task.usage?.output_tokens || 0)}
          </small>
        </div>

        <div className="inspector-item">
          <span className="inspector-label">Validação & Qualidade</span>
          <strong>
            {task.status === 'completed'
              ? ['deliver', 'improve'].includes(task.workflow || '')
                ? 'Arquivos + sintaxe validados'
                : 'Resposta + exit 0'
              : 'Pendente de validação'}
          </strong>
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
                onClick={onAcceptQuality}
              >
                <Check size={13} />
                Aceitar qualidade da versão
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
                    {done ? 'Confirmada' : 'Pendente'}
                  </span>
                </div>
              );
            })}
          </div>
        )}

        <div className="inspector-checkpoints">
          <h4>Checkpoints Salvos ({checkpoints.length})</h4>
          {checkpoints.length === 0 ? (
            <p className="text-muted text-xs">Nenhum checkpoint registrado.</p>
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
      </div>
    </aside>
  );
}
