"""
installer/build_linux.py — package blackbox as a double-clickable Linux executable 
via PyInstaller.

Same reasoning as the other two scripts: no --windowed/--noconsole, since this is 
a console-mode CLI tool that needs a real terminal for password prompts.

Note: unlike Windows (.ico) and macOS (.icns), PyInstaller does not embed an icon 
into a Linux ELF binary — there's no equivalent flag to use here. Icon association 
on Linux desktops is handled separately, via a .desktop launcher file pointing at a
standalone icon image; that launcher is a future addition, not something PyInstaller
controls.

PyInstaller cannot cross-compile: this script must run ON Linux to produce a Linux 
binary.
"""

from __future__ import annotations

import platform
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENTRY_POINT = PROJECT_ROOT / "src" / "blackbox" / "cli.py"


def main() -> int:
    if platform.system() != "Linux":
        print(
            f"ERROR: this script must run on Linux to produce a "
            f"Linux binary (PyInstaller does not cross-compile). "
            f"Current OS: {platform.system()}.",
            file=sys.stderr,
        )
        return 1

    if not ENTRY_POINT.exists():
        print(f"ERROR: entry point not found at {ENTRY_POINT}", file=sys.stderr)
        return 1

    command = [
        "pyinstaller",
        "--onefile",
        "--name", "blackbox",
        str(ENTRY_POINT),
    ]

    print("Running:", " ".join(command))
    result = subprocess.run(command, cwd=PROJECT_ROOT)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())