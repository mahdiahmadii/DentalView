# DentaView.spec
# -*- mode: python ; coding: utf-8 -*-

import sys
from PyInstaller.utils.hooks import collect_all, collect_data_files

# Collect ultralytics and its data/binaries
datas_ultralytics, binaries_ultralytics, hiddenimports_ultralytics = collect_all('ultralytics')

# PySide6 Qt plugins needed for image formats
datas_pyside6 = collect_data_files('PySide6')

block_cipher = None

a = Analysis(
    ['main.py'],  # ✅ اصلاح: main.py کنار spec هست، نه توی dental_opg_detector
    pathex=['.'],
    binaries=binaries_ultralytics,
    datas=[
        *datas_ultralytics,
        *datas_pyside6,
        ('dental_data', 'dental_data'),  # ✅ اضافه شد: پوشهٔ دیتابیس و تصاویر
    ],
    hiddenimports=[
        *hiddenimports_ultralytics,
        'PIL._tkinter_finder',
        'reportlab',
        'reportlab.graphics',
        'reportlab.platypus',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'reportlab.lib.styles',
        'openpyxl',
        'openpyxl.cell._writer',
        'PySide6.QtSvg',
        'PySide6.QtXml',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'scipy',
        'IPython',
        'jupyter',
        'notebook',
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
    exclude_binaries=True,          # --onedir mode
    name='DentaView',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,                  # no terminal window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico',
    version='version_info.txt',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='DentaView',
)
