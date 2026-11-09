"""Conservative, read-only verification of the running backend identity."""
import ast
import hashlib
import inspect
import sqlite3
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

REQUIRED_SCHEMA = {
"execution_states": {"task_id", "version", "execution_id", "state", "updated_at"},
"tool_actions": {
"action_id", "task_id", "execution_id", "turn_index", "batch_index",
"tool_name", "arguments", "status", "result", "before_hash",
"after_hash", "error", "evidence", "created_at", "updated_at",
},
}
CAPABILITY_MARKER = "persistent_resume_v1"


def backend_fingerprint(root):
    root = Path(root).resolve()
    digest = hashlib.sha256()
    for path in sorted((root / "backend").rglob("*.py")):
        if not path.is_file():
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def inspect_schema(db_path):
    path = Path(db_path)
    if not path.is_file():
        return {"compatible": False, "issues": ["Banco de dados não encontrado."]}
    issues = []
    try:
        uri = path.resolve().as_uri() + "?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=2) as db:
            for table, required in REQUIRED_SCHEMA.items():
                rows = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchall()
                if not rows:
                    issues.append("Tabela ausente: " + table)
                    continue
                columns = {row[1] for row in db.execute("PRAGMA table_info(" + table + ")")}
                for column in sorted(required - columns):
                    issues.append("Coluna ausente: " + table + "." + column)
    except (sqlite3.Error, OSError) as exc:
        issues.append("Não foi possível consultar o schema: " + type(exc).__name__)
    return {"compatible": not issues, "issues": issues}


def _code_signature(code):
    """Compare executable code without filename and line-table metadata."""
    return (
        code.co_code, code.co_names, code.co_varnames, code.co_freevars,
        code.co_cellvars, code.co_argcount, code.co_posonlyargcount,
        code.co_kwonlyargcount,
        tuple(_code_signature(c) if isinstance(c, types.CodeType) else c
        for c in code.co_consts),
    )


def _compiled_functions(source, filename):
    compiled = compile(source, filename, "exec")
    found = {}
    def walk(code, prefix=""):
        for const in code.co_consts:
            if isinstance(const, types.CodeType):
                name = prefix + const.co_name
                if const.co_name not in ("<listcomp>", "<dictcomp>", "<setcomp>", "<genexpr>", "<lambda>"):
                    found[name] = _code_signature(const)
                walk(const, name + ".")
    walk(compiled)
    return found


def _loaded_modules(root):
    backend = (Path(root).resolve() / "backend").resolve()
    result = {}
    for name, module in tuple(sys.modules.items()):
        if not name.startswith("backend.") or module is None:
            continue
        filename = getattr(module, "__file__", None)
        if not filename:
            continue
        try:
            path = Path(filename).resolve()
            if path.parent == backend and path.suffix == ".py":
                result[name] = (module, path)
        except (OSError, TypeError, ValueError):
            continue
    return result


def _verify_module(module, path):
    """Reject unverifiable runtime code instead of trusting the current disk."""
    try:
        source = path.read_bytes()
        tree = ast.parse(source, filename=str(path))
        expected = _compiled_functions(source, str(path))
        actual = {}
        for name, value in vars(module).items():
            if inspect.isfunction(value) and getattr(value, "__module__", None) == module.__name__:
                actual[name] = _code_signature(inspect.unwrap(value).__code__)
            elif inspect.isclass(value) and getattr(value, "__module__", None) == module.__name__:
                for method_name, member in vars(value).items():
                    if isinstance(member, (staticmethod, classmethod)):
                        member = member.__func__
                    if inspect.isfunction(member) and getattr(member, "__module__", None) == module.__name__:
                        actual[name + "." + method_name] = _code_signature(inspect.unwrap(member).__code__)
        for name, signature in actual.items():
            if name not in expected or expected[name] != signature:
                return False
        # Literal module constants catch VERSION=1 -> VERSION=2 even without functions.
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in vars(module):
                        if vars(module)[target.id] != node.value.value:
                            return False
        return True
    except (OSError, SyntaxError, ValueError, TypeError):
        return False


class ProcessIdentity:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.started_at = datetime.now(timezone.utc).isoformat()
        before = backend_fingerprint(self.root)
        self._modules = _loaded_modules(self.root)
        self._verified = all(_verify_module(module, path) for module, path in self._modules.values())
        after = backend_fingerprint(self.root)
        self.loaded_version = before
        self._verified = self._verified and before == after
        self._initial_modules = frozenset(self._modules)

    def diagnose(self, db_path):
        issues = []
        try:
            disk_version = backend_fingerprint(self.root)
            restart_required = disk_version != self.loaded_version
        except OSError:
            disk_version = None
            restart_required = True
            issues.append("Não foi possível verificar os arquivos do backend.")
        current_modules = _loaded_modules(self.root)
        initial_unchanged = all(
            name in current_modules and current_modules[name][0] is module
            and current_modules[name][1] == path
            for name, (module, path) in self._modules.items()
        )
        identity_verified = (
            self._verified and initial_unchanged
            and all(
                path.name == name.rsplit(".", 1)[-1] + ".py"
                and _verify_module(module, path)
                for name, (module, path) in current_modules.items()
            )
        )
        if not identity_verified:
            issues.append("Identidade do código carregado não verificada; reinicie o serviço com segurança.")
        if restart_required:
            issues.append("Arquivos do backend foram alterados; reinicie o serviço com segurança.")
        schema = inspect_schema(db_path)
        issues.extend(schema["issues"])
        ready = not issues
        return {
            "started_at": self.started_at,
            "loaded_version": self.loaded_version,
            "disk_version": disk_version,
            "restart_required": restart_required or not identity_verified,
            "identity_verified": identity_verified,
            "readiness": {
                "status": "ready" if ready else "degraded",
                "persistent_resume": ready,
                "capabilities": [CAPABILITY_MARKER] if ready else [],
                "schema_compatible": schema["compatible"],
                "issues": issues,
            },
        }
