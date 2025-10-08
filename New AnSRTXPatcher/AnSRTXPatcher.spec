# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['AnSRTXPatcher.py'],
    pathex=[],
    binaries=[],
    datas=[('xdelta3/exec', 'xdelta3/exec'), ('xdelta3/manifest', 'xdelta3/manifest'), ('AnSPatchericon.ico', '.')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='AnSRTXPatcher',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['AnSPatchericon.ico'],
)
