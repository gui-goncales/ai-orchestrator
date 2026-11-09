export type HealthResponse = {
app?: string;
status?: string;
started_at?: string;
loaded_version?: string;
restart_required?: boolean;
readiness?: {
status?: string;
persistent_resume?: boolean;
schema_compatible?: boolean;
issues?: string[];
};
};

export function healthNotice(health: HealthResponse | null): string | null {
if (!health || !health.readiness || typeof health.restart_required !== 'boolean') {
return 'Diagnóstico de versão e retomada indisponível neste backend.';
}
if (health.restart_required) {
return 'Reinicialização necessária: o código em disco difere do backend em execução. Finalize as tarefas e reinicie manualmente com segurança.';
}
if (!health.readiness.schema_compatible) {
return 'Persistência de retomada indisponível: ' +
(health.readiness.issues?.join('; ') || 'schema do banco incompatível.');
}
if (!health.readiness.persistent_resume) {
return 'Backend degradado: ' +
(health.readiness.issues?.join('; ') || 'retomada persistente não confirmada.');
}
return null;
}
