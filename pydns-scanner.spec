# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Collect all submodules for packages that rely on dynamic imports
textual_hidden  = collect_submodules('textual')
dns_hidden      = collect_submodules('dns')
rich_hidden     = collect_submodules('rich')
textual_datas   = collect_data_files('textual')   # CSS / widget assets

scanner_hidden = [
    'scanner',
    'scanner.config_mixin',
    'scanner.constants',
    'scanner.extra_tests',
    'scanner.ip_streaming',
    'scanner.isp_cache',
    'scanner.proxy_testing',
    'scanner.results',
    'scanner.slipstream',
    'scanner.slipnet',
    'scanner.utils',
    'scanner.widgets',
    'scanner.worker_pool',
]

extra_hidden = [
    'aiodns',
    'httpx',
    'loguru',
    'pyperclip',
    '_cffi_backend',
]

all_hidden = textual_hidden + dns_hidden + rich_hidden + scanner_hidden + extra_hidden

a = Analysis(
    ['python/dnsscanner_tui.py'],
    pathex=['python'],
    binaries=[],
    datas=[
        ('python/iran-ipv4.cidrs', '.'),
        ('python/slipstream-client', 'slipstream-client'),
        ('python/slipnet-client', 'slipnet-client'),
        *textual_datas,
    ],
    hiddenimports=all_hidden,
    hookspath=['./'],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'tkinter',
        'PyQt5',
        'PySide2',
        'wx',
        'jupyter',
        'notebook',
        'IPython',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='pydns-scanner',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='static/icon.ico',
)
