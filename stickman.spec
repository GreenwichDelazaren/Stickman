# PyInstaller recipe for the stand-alone Windows program: pyinstaller --noconfirm stickman.spec
# The result is "dist/Stickman Poser.exe", one file that needs no Python on the other computer.

import os
import sys

sys.path.insert(0, SPECPATH)
import icons

os.makedirs(workpath, exist_ok=True)
icon_file = os.path.join(workpath, "stickman.ico")
icons.write_ico(icon_file)

analysis = Analysis(["main.py"])
archive = PYZ(analysis.pure)
exe = EXE(
    archive,
    analysis.scripts,
    analysis.binaries,
    analysis.datas,
    name="Stickman Poser",
    icon=icon_file,
    console=False,
    upx=False,
)
