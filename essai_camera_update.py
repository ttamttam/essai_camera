#!/usr/bin/env python

import sys
import subprocess

python_files = ("essai_camera.py",)
ui_files = ("essai_camera.ui",)
languages = ("en_GB", "fr_FR")

# TRANSLATIONS

cmd = ["pyside2-lupdate"]

if len(sys.argv) > 1 and sys.argv[1] == "-noobsolete":
    cmd.append("-noobsolete")

for pf in python_files:
    cmd.append(pf)

for uif in ui_files:
    cmd.append(uif)

cmd.append("-ts")

for ll in languages:
    cmd.append(f"essai_camera_{ll}.ts")

subprocess.run(cmd)

# RESOURCES

cmd = [
    "pyside2-rcc", "-g", "python", "essai_camera.qrc", "-o", "essai_camera_rc.py"
]
subprocess.run(cmd)
