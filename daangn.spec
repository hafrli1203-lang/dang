# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for 당근 광고 기획 도우미.

Usage:
    pyinstaller daangn.spec           # onedir 모드 (기본)
    pyinstaller daangn.spec --clean   # 캐시 초기화 후 빌드

빌드 결과: dist/당근광고도우미/당근광고도우미.exe
"""
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_data_files

ROOT = Path(SPECPATH)

# ── Collect NiceGUI (static files, templates, etc.) ──
nicegui_datas, nicegui_binaries, nicegui_hiddenimports = collect_all('nicegui')

# ── Collect matplotlib data (fonts, colormaps, etc.) ──
mpl_datas = collect_data_files('matplotlib')

# ── Collect python-docx data ──
docx_datas = collect_data_files('docx')

# ── Project data files ──
project_datas = [
    (str(ROOT / 'templates'), 'templates'),
    (str(ROOT / '.env.example'), '.'),
]

block_cipher = None

a = Analysis(
    [str(ROOT / 'main.py')],
    pathex=[str(ROOT)],
    binaries=nicegui_binaries,
    datas=nicegui_datas + mpl_datas + docx_datas + project_datas,
    hiddenimports=nicegui_hiddenimports + [
        'anthropic',
        'openai',
        'openpyxl',
        'dotenv',
        'app.pages.project',
        'app.pages.planning',
        'app.pages.report',
        'app.ai.providers',
        'app.reporting.docx_report',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='당근광고도우미',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # windowed mode
    disable_windowed_traceback=False,
    argv_emulation=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='당근광고도우미',
)
