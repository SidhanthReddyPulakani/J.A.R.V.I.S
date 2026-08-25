import os
import sys
from pathlib import Path
from jarvis.core.config import settings

STARTUP_DIR = Path(os.environ.get("APPDATA", "")) / r"Microsoft\Windows\Start Menu\Programs\Startup"
SHORTCUT_NAME = "Jarvis.lnk"

def ensure_startup() -> None:
    """Create a Windows Startup shortcut when enabled.

    This is intentionally best-effort. It does nothing if startup is disabled.
    """
    if not settings.start_with_windows:
        return

    STARTUP_DIR.mkdir(parents=True, exist_ok=True)
    shortcut = STARTUP_DIR / SHORTCUT_NAME

    # Phase 1 keeps startup simple. We generate a .cmd launcher rather than
    # requiring third-party shortcut libraries.
    launcher = STARTUP_DIR / "JarvisStartup.cmd"
    project_root = Path(__file__).resolve().parents[2]
    launcher.write_text(
        f'@echo off\ncd /d "{project_root}"\n'
        f'"{sys.executable}" "{project_root / "main.py"}"\n',
        encoding="utf-8",
    )

    # The cmd launcher itself is what Windows executes at startup.
    # Keep a marker .lnk filename out of the way; the launcher is sufficient.
    if shortcut.exists():
        try:
            shortcut.unlink()
        except OSError:
            pass
