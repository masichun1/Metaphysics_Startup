# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["pet/main.py"],
    pathex=[],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="cat-pet",
    debug=False,
    strip=False,
    upx=False,
    console=False,
)
