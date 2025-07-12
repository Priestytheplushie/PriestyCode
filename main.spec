# main.spec
a = Analysis(
    ['src/main.py'], # main.py is still in src/
    pathex=[], # We need to add the root directory to pathex so PyInstaller can find 'assets'
    binaries=[],
    # Corrected DATAS path: 'assets' is in the root relative to where you run pyinstaller,
    # so we just need 'assets' as the source.
    # The destination within the exe can still be 'assets'.
    datas=[('assets', 'assets')], # Corrected this line
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
    # Corrected ICON path: 'icon.ico' is inside the 'assets' folder in the root.
    icon='assets/icon.ico', # Corrected this line
)