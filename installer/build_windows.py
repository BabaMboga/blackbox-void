"""
installer/build_windows.py - package blackbox as a double-clickable Windows 
executable via PyInstaller.

Deliberately does NOT use --windowed. blackbox is an interactive CLI tool:
click.prompt(hide_input=True) needs a real, visible console attached to read
the password. --windowed builds a GUI-style exe with no console at all, which
would mean this app either flashes and exits immediately, or hangs waiting for
input the user has no way to see or type into. Omitting --windowed (the default,
console-mode build) is what makes double-clicking the .exe open a real terminal
window showing the prompts - the actual "clickable icon, asks for a password"
experience this project is going for.

PyInstaller cannot cross-compile: this script must be run ON Windows to produce
a Windows executable. Run it on macOS or Linux and PyInstaller will build a binary
for whichever OS it's actually running on, not a .exe.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = PROJECT_ROOT / "src" / "blackbox" / "cli.py"
ICON_PATH = PROJECT_ROOT / "assets" / "ICON.ico"

def main() -> int:
    if platform.system() != "Windows":
        print(
            f"ERROR: this script must run on WIndows to produce a "
            f"Windows .exe (PyInstaller does not cross-compile). "
            f"Current OS: {platform.system()}",
            file=sys.stderr,
        )
        return 1

    if not ENTRY_POINT.exists():
        print(
            f"ERROR: entry point not found at {ENTRY_POINT}",
            file=sys.stderr
        )
        return 1

    command = [
        "pyinstaller",
        "--onefile",
        "--name", "blackbox",
        str(ENTRY_POINT),
    ]

    if ICON_PATH.exists():
        command.extend(["--icon", str(ICON_PATH)])
    else:
        print(
            f"NOTE: no icon found at {ICON_PATH} - building without a "
            f"custom icon. Add assets/icon.ico and re-run to brand it.",
        )

    print("Running:", " ".join(command))
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())