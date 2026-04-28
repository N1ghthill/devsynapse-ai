# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for DevSynapse AI backend sidecar.
#
# Build command:
#   pyinstaller --clean --noconfirm backend.spec
#
# Output:
#   dist/devsynapse-backend          (linux/macOS)
#   dist/devsynapse-backend.exe      (Windows)
#
# Move the output to src-tauri/binaries/devsynapse-backend{-target-triple}
# before running `npm run tauri build`.

import os
import sys
from pathlib import Path

# PyInstaller runs specs via exec(), so __file__ is not available.
_PROJECT_ROOT = Path(os.getcwd())
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Analysis ──────────────────────────────────────────────────────────────────

a = Analysis(
    ["backend-entry.py"],
    pathex=[str(_PROJECT_ROOT)],
    binaries=[],
    datas=[
        # Include entire app packages so PyInstaller finds all imports.
        ("api", "api"),
        ("core", "core"),
        ("config", "config"),
        (".env.example", "."),
    ],
    hiddenimports=[
        # FastAPI internals
        "fastapi",
        "fastapi.middleware",
        "fastapi.middleware.cors",
        "starlette",
        # Uvicorn internals (PyInstaller cannot auto-discover them)
        "uvicorn.logging",
        "uvicorn.loops",
        "uvicorn.loops.auto",
        "uvicorn.protocols",
        "uvicorn.protocols.http",
        "uvicorn.protocols.http.auto",
        "uvicorn.protocols.websockets",
        "uvicorn.protocols.websockets.auto",
        "uvicorn.lifespan",
        "uvicorn.lifespan.on",
        "uvicorn.lifespan.off",
        # Pydantic internals
        "pydantic",
        "pydantic.deprecated",
        "pydantic_settings",
        # Passlib bcrypt back-end (loaded dynamically)
        "passlib.handlers.bcrypt",
        "passlib.hash",
        # Standard library modules sometimes missed
        "sqlite3",
        "asyncio",
        "email.mime",
        "json",
        "logging",
        "multiprocessing",
        # Project modules
        "core.memory",
        "core.memory.system",
        "core.memory.conversations",
        "core.memory.procedural",
        "core.memory.projects",
        "core.memory.settings",
        "core.deepseek",
        "core.brain",
        "core.bootstrap",
        "core.opencode_bridge",
        "core.migrations",
        "core.monitoring",
        "core.auth",
        "core.plugin_system",
        "core.runtime_config",
        "core.skills",
        "api.app",
        "api.models",
        "api.dependencies",
        "api.routes",
        "api.routes.bootstrap",
        "api.routes.chat",
        "api.routes.knowledge",
        "api.routes.settings",
        "api.routes.admin",
        "api.routes.auth",
        "api.routes.monitoring",
        "config.settings",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude heavy things we never need at runtime
        "tkinter",
        "matplotlib",
        "numpy",
        "scipy",
        "pandas",
        "PIL",
        "cv2",
        "tensorflow",
        "torch",
    ],
    noarchive=False,
)

# ── PYZ (compiled bytecode) ──────────────────────────────────────────────────

pyz = PYZ(a.pure)

# ── Executable ────────────────────────────────────────────────────────────────
# EXE produces a SINGLE executable — exactly what Tauri's sidecar expects.

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="devsynapse-backend",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
