"""Read-only local directory navigation for the workspace selector."""
from pathlib import Path


def browse_directory(path):
    if not isinstance(path, str) or len(path) > 4096 or "\x00" in path:
        raise ValueError("Caminho inválido.")
    directory = Path(path or str(Path.home())).expanduser().resolve()
    if not directory.is_dir():
        raise ValueError("O caminho informado não é um diretório válido.")
    try:
        entries = []
        for entry in directory.iterdir():
            try:
                is_dir = entry.is_dir()
                if not is_dir and not entry.is_file():
                    continue
                entries.append({"name": entry.name, "path": str(entry.resolve()), "type": "dir" if is_dir else "file"})
            except (PermissionError, OSError):
                continue
        entries.sort(key=lambda item: (item["type"] != "dir", item["name"].casefold()))
    except PermissionError:
        raise ValueError("Sem permissão para acessar este diretório.") from None
    except OSError:
        raise ValueError("Não foi possível listar este diretório.") from None
    return {"path": str(directory), "parent": str(directory.parent) if directory.parent != directory else None, "entries": entries[:1000]}
