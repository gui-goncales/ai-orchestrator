const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/operationalHealth.ts'), 'utf8');
const compiled = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS } }).outputText;
const moduleShim = { exports: {} };
new Function('module', 'exports', compiled)(moduleShim, moduleShim.exports);
const { healthNotice } = moduleShim.exports;

test('legacy response does not imply readiness', () => {
assert.match(healthNotice({ app: 'ai-orchestrator', status: 'online' }), /indisponível/);
});
test('restart required shows actionable warning', () => {
assert.match(healthNotice({ restart_required: true, readiness: { schema_compatible: true } }), /Reinicialização necessária/);
});
test('schema incompatibility explains cause', () => {
assert.match(healthNotice({ restart_required: false, readiness: { schema_compatible: false, issues: ['Coluna ausente: tool_actions.evidence'] } }), /tool_actions.evidence/);
});
test('persistent resume unavailable reports degradation', () => {
assert.match(healthNotice({ restart_required: false, readiness: { schema_compatible: true, persistent_resume: false } }), /degradado/);
});
test('ready and compatible response has no warning', () => {
assert.equal(healthNotice({ restart_required: false, readiness: { schema_compatible: true, persistent_resume: true } }), null);
});
test('missing response or failed query does not imply readiness', () => {
assert.match(healthNotice(null), /indisponível/);
});
