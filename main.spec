# main.spec
a = Analysis(
    ['src/main.py'],
    pathex=[],
    binaries=[],
    # THE FIX for ASSETS: Tell PyInstaller to bundle the 'assets' folder.
    # It copies 'src/assets' into a folder named 'assets' inside the .exe
    datas=[('src/assets', 'assets','assets/icons')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=None)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PriestyCode',
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
    # THE FIX for the ICON: Add the path to your .ico file here.
    icon='src/assets/icon.ico',
)