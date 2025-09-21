# -*- mode: python ; coding: utf-8 -*-
from playwright.driver.package_path import get_driver_path

a = Analysis(
    ['src/viral_marketing_reporter/main.py'],
    pathex=['src'],
    binaries=[],
    datas=[(str(get_driver_path().joinpath('browsers.json')), 'playwright/driver'), (str(get_driver_path()), 'playwright/driver')],
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
    name='ViralMarketingReporter',
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
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ViralMarketingReporter',
)
app = BUNDLE(
    coll,
    name='ViralMarketingReporter.app',
    icon=None,
    bundle_identifier=None,
)
