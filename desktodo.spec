# -*- mode: python ; coding: utf-8 -*-
# 打包成单目录 (onedir) 应用：deskcal/assets 和 secrets/qweather 私钥一并打入。
# 私钥打包是有意为之的选择（项目只给身边几个人用，不计划大规模公开分发）。

a = Analysis(
    ["deskcal/main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("deskcal/assets", "deskcal/assets"),
        ("secrets/qweather", "secrets/qweather"),
    ],
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
    [],
    exclude_binaries=True,
    name="DeskToDo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="deskcal/assets/images/logo.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="DeskToDo",
)
