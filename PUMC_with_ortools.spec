# -*- mode: python ; coding: utf-8 -*-
import os

block_cipher = None

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[
        # 只包含OR-Tools，不包含文档文件
        (r'C:\Users\95678\Desktop\PUMC_Course_Scheduling\PUMC_venv\Lib\site-packages\ortools', 'ortools'),
    ],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtGui', 
        'PyQt5.QtWidgets',
        'pandas',
        'numpy',
        'openpyxl',
        'ortools',
        'ortools.sat',
        'ortools.sat.python',
        'ortools.sat.python.cp_model',
        'ortools.linear_solver',
        'ortools.constraint_solver',
        'ortools.util',
        'ortools.algorithms',
        'ortools.graph',
        'ortools.init',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'streamlit',
        'plotly',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'pytest',
        'pytest-cov',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PUMC_Course_Scheduling',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='PUMClogo.ico',  # 添加图标文件
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PUMC_Course_Scheduling'
)
