
import React from 'react';
import { Activity, AlertCircle, CheckCircle2, Clock3, FileCode2 } from 'lucide-react';
import type { Data, Task } from '../types';

type TimelineItem = {
key: string;
time: string;
title: string;
detail: string;
kind: 'call' | 'result' | 'step' | 'checkpoint' | 'error';
payload?: unknown;
};

function stringify(value: unknown): string {
if (value === undefined || value === null) return 'Não informado';
if (typeof value === 'string') return value;
try { return JSON.stringify(value, null, 2); } catch { return String(value); }
}

export function ExecutionTimeline({ task, data }: { task: Task; data: Data }) {
const checkpointTimes = new Set(data.checkpoints.filter(checkpoint => checkpoint.task_id === task.id).map(checkpoint => checkpoint.time));
const items: TimelineItem[] = [
...data.events.filter(event => event.task_id === task.id && !(event.kind === 'checkpoint' && checkpointTimes.has(event.time))).map(event => {
const payload = event.payload || {};
const name = typeof payload.name === 'string' ? payload.name : event.kind;
const path = payload.args?.path || payload.args?.pattern || payload.args?.cwd;
const result = payload.result && typeof payload.result === 'object' ? payload.result : {};
 const failure = /fail|error/i.test(event.kind) || ['error','failed'].includes(payload.status) || ['error','failed'].includes(result.status) || (typeof result.exit_code === 'number' && result.exit_code !== 0) || Boolean(result.error);
return {
key: `event-${event.id}`,
time: event.time,
title: name,
detail: path ? String(path) : event.kind,
kind: (failure ? 'error' : event.kind === 'tool_call' ? 'call' : 'result') as TimelineItem['kind'],
payload
};
}),
...(data.task_steps || []).filter(step => step.task_id === task.id).map((step, index) => ({
key: `step-${index}-${step.time}`,
time: step.time,
title: step.stage,
detail: 'Etapa registrada — resultado disponível nos detalhes',
kind: 'step' as const,
payload: step.output
})),
...data.checkpoints.filter(checkpoint => checkpoint.task_id === task.id).map(checkpoint => ({
key: `checkpoint-${checkpoint.id}`,
time: checkpoint.time,
title: 'Checkpoint salvo',
detail: `Checkpoint #${checkpoint.id}`,
kind: 'checkpoint' as const,
payload: checkpoint.payload
})),
...(data.tool_actions || []).filter(action => action.task_id === task.id).map(action => ({
key: `action-${action.action_id}`,
time: action.updated_at || action.created_at,
title: `Ação ${action.tool_name}: ${action.status}`,
detail: action.status === 'uncertain' || action.status === 'running'
? `Resultado incerto — ID ${action.action_id}`
: `Lote ${action.turn_index}, posição ${action.batch_index}`,
kind: (action.status === 'uncertain' || action.status === 'failed' ? 'error' : 'result') as TimelineItem['kind'],
payload: action
}))
].sort((a, b) => (Date.parse(a.time) || 0) - (Date.parse(b.time) || 0));

return (
<section className="execution-timeline" aria-label="Histórico de execução">
<div className="execution-timeline-heading">
<span><Activity size={15} /> Atividade da execução</span>
<span className="execution-timeline-count">{items.length} registros</span>
</div>
{items.length === 0 ? (
<p className="execution-timeline-empty">Nenhuma operação registrada para esta tarefa.</p>
) : (
<ol className="execution-timeline-list">
{items.map(item => {
const Icon = item.kind === 'error' ? AlertCircle : item.kind === 'checkpoint' ? CheckCircle2 : item.kind === 'call' ? FileCode2 : Clock3;
return (
<li key={item.key} className={`execution-timeline-item is-${item.kind}`}>
<span className="execution-timeline-icon"><Icon size={14} /></span>
<details>
<summary>
<span className="execution-timeline-item-main">
<strong>{item.title}</strong>
<small>{item.detail}</small>
</span>
<time dateTime={item.time} title={item.time}>{item.time ? new Date(item.time).toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '—'}</time>
</summary>
<pre>{stringify(item.payload)}</pre>
</details>
</li>
);
})}
</ol>
)}
{(data.tool_actions || []).filter(action => action.task_id === task.id && action.status === 'uncertain').map(action => (
<p key={action.action_id} className="execution-timeline-error" role="alert">
A ação {action.tool_name} tem resultado incerto. Verifique o efeito no workspace antes de autorizar a repetição.
<button type="button" disabled={task.status === 'running' || task.status === 'queued'} onClick={async () => {
if (!window.confirm('A operação pode já ter sido executada. Você verificou o resultado e deseja autorizar uma nova tentativa?')) return;
try {
const response = await fetch(`/api/tasks/${encodeURIComponent(task.id)}/authorize-retry`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action_id: action.action_id }) });
if (!response.ok) throw new Error(await response.text());
window.location.reload();
} catch (error) { window.alert('Não foi possível autorizar: ' + String(error)); }
}}>Autorizar nova tentativa</button>
</p>
))}
{['interrupted', 'failed'].includes(task.status) && !(data.tool_actions || []).some(action => action.task_id === task.id) && <p className="execution-timeline-note">Tarefa sem journal de ações: execução anterior ou legado sem garantias de retomada granular.</p>}
{task.error && <p className="execution-timeline-error" role="alert"><AlertCircle size={14} /> {task.error}</p>}
<p className="execution-timeline-note">Chamadas registradas não comprovam sucesso. Consulte os resultados e a validação antes de aceitar a qualidade.</p>
</section>
);
}
