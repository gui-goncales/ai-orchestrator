"""Absolute import entrypoint for launchd, independent of launcher cwd changes."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root))
from backend.server import serve
serve()
