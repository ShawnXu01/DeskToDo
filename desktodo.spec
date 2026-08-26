# -*- mode: python ; coding: utf-8 -*-
# 打包成单目录 (onedir) 应用：deskcal/assets 和 secrets/qweather 私钥一并打入。
# 私钥打包是有意为之的选择（项目只给身边几个人用，不计划大规模公开分发）。
from pathlib import Path
import sys


# Conda 的 Python 扩展会从 Library/bin 动态加载这些运行库，PyInstaller 不会自动找到。
# 普通 CPython 环境没有该目录时列表为空，不影响其他机器打包。
conda_bin = Path(sys.base_prefix) / "Library" / "bin"
conda_runtime_names = [
    "libcrypto-3-x64.dll",
    "libssl-3-x64.dll",
    "liblzma.dll",
    "libbz2.dll",
    "libexpat.dll",
    "ffi.dll",
]
conda_runtime_binaries = [
    (str(conda_bin / name), ".")
    for name in conda_runtime_names
    if (conda_bin / name).exists()
]

a = Analysis(
    ["deskcal/main.py"],
    pathex=[],
    binaries=conda_runtime_binaries,
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
