# PyInstaller spec for gitget — produces a single-file binary.
# Build:
#   uv run pyinstaller packaging/gitget.spec
#
# Output: dist/gitget (used by both the AppImage build and the .deb).

# ruff: noqa
# fmt: off

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

hidden_imports = (
    collect_submodules("PySide6")
    + collect_submodules("gitget")
    + ["uvicorn.logging", "uvicorn.loops.auto", "uvicorn.protocols.http.auto",
       "uvicorn.protocols.websockets.auto", "uvicorn.lifespan.on"]
)

datas = collect_data_files("PySide6")

a = Analysis(
    ["../src/gitget/__main__.py"],
    pathex=["../src"],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz, a.scripts, a.binaries, a.zipfiles, a.datas,
    name="gitget",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
