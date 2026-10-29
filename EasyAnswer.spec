# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Hidden imports needed for dynamic loading
hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'watchdog',
    'watchdog.observers',
    'watchdog.observers.read_directory_changes',
    'watchdog.events',
    'google.genai',
    'google.genai.types',
    'PIL',
    'PIL.Image',
    'PIL.ImageGrab',
    'dotenv',
    'winreg',
    'ctypes',
    'ctypes.wintypes',
]
hiddenimports += collect_submodules('google.genai')
hiddenimports += collect_submodules('watchdog')
hiddenimports += collect_submodules('screenshot_ai')

datas = []
# Include .env.example
datas.append(('screenshot_ai/.env.example', '.'))
# Include app.ico in assets
datas.append(('screenshot_ai/assets/app.ico', 'assets'))
# Bundle local .env into executable if present so it works standalone with zero setup
if os.path.exists('.env'):
    datas.append(('.env', '.'))

a = Analysis(
    ['main.py'],
    pathex=['.'],

    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter',
        'matplotlib',
        'numpy',
        'scipy',
        'pytest',
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.QtWebEngineQuick',
        'PySide6.QtPdf',
        'PySide6.QtPdfWidgets',
        'PySide6.QtQml',
        'PySide6.QtQuick',
        'PySide6.QtQuickWidgets',
        'PySide6.QtQuick3D',
        'PySide6.QtMultimedia',
        'PySide6.QtMultimediaWidgets',
        'PySide6.QtDesigner',
        'PySide6.QtSql',
        'PySide6.QtTest',
        'PySide6.QtXml',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtSpatialAudio',
        'PySide6.QtVirtualKeyboard',
        'PySide6.QtSensors',
        'PySide6.QtPositioning',
        'PySide6.QtLocation',
        'PySide6.QtBluetooth',
        'PySide6.QtNfc',
        'PySide6.QtSerialPort',
        'PySide6.QtRemoteObjects',
        'PySide6.QtScxml',
        'PySide6.QtStateMachine',
        'google.genai.tests',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

import os
unneeded_names = {
    'opengl32sw.dll',
    'Qt6Qml.dll',
    'Qt6Quick.dll',
    'Qt6QmlModels.dll',
    'Qt6QmlWorkerScript.dll',
    'Qt6QmlMeta.dll',
    'Qt6OpenGL.dll',
    'Qt6ShaderTools.dll',
    'Qt6Pdf.dll',
    'Qt6Svg.dll',
    'Qt6VirtualKeyboard.dll',
    'qsqlite.dll',
    'qtvkbopenwnnplugin.dll',
    'qtvkbpinyinplugin.dll',
    'assimp.dll',
    'assimpsceneimport.dll',
    'avcodec-63.dll',
    'avformat-63.dll',
    'avutil-61.dll',
    'swscale-10.dll',
}

a.binaries = [x for x in a.binaries if not any(u.lower() in x[0].lower() for u in unneeded_names)]
a.datas = [x for x in a.datas if not any(u.lower() in x[0].lower() for u in unneeded_names)]

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='EasyAnswer',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_dir='.venv/Scripts',
    upx_exclude=['vcruntime140.dll', 'python312.dll'],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='screenshot_ai/assets/app.ico',
)
