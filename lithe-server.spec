# -*- mode: python ; coding: utf-8 -*-
"""
Lithe — PyInstaller spec for the Python backend.

Produces a onedir bundle: dist/lithe-server/lithe-server.exe + _internal/.
Electron spawns that exe by name from resources/python-backend/ (see
stopPythonServer/startPythonServer in src/frontend/src/main/index.ts), so the
output name and the onedir layout are load-bearing — don't switch to onefile
without updating the installer's taskkill macro, which matches on the exe name.

Build with: powershell -ExecutionPolicy Bypass -File scripts/build-backend.ps1
"""

from PyInstaller.utils.hooks import collect_submodules

# uvicorn selects its loop and protocol implementations by string at runtime,
# so static analysis never sees these and the server dies on startup without
# them. "auto" resolves to the impl modules, which must also be present.
hiddenimports = [
    'uvicorn.logging',
    'uvicorn.loops.auto',
    'uvicorn.loops.asyncio',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.http.h11_impl',
    'uvicorn.protocols.http.httptools_impl',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.protocols.websockets.websockets_impl',
    'uvicorn.protocols.websockets.wsproto_impl',
    'uvicorn.lifespan.on',
    'uvicorn.lifespan.off',
]

# pandas resolves its Excel engine by name at call time, so nothing in the
# import graph points at openpyxl even though data_tools.profile_data and
# inline_chart both call pd.read_excel on .xlsx input.
hiddenimports += ['openpyxl']

# Several backend modules are imported lazily inside request handlers, which
# keeps startup fast but hides them from the dependency graph.
hiddenimports += collect_submodules('src.backend')

a = Analysis(
    ['src/backend/server_entry.py'],
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # data_tools pins matplotlib to the Agg backend, so no GUI toolkit is
        # ever loaded. Excluding them keeps a large amount of dead weight out.
        'tkinter',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'wx',
        'matplotlib.backends._backend_tk',
        'matplotlib.backends.backend_qt5agg',
        'matplotlib.backends.backend_qtagg',
        # Test-only dependency; never imported by the server.
        'pytest',
        '_pytest',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='lithe-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # Console subsystem, matching the previously shipped binary. Electron pipes
    # stdout/stderr into its own log (logChild), so this stays capturable.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='lithe-server',
)
