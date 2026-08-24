"""
installer/build_macos.py - package blackbox as a double-clickable macOS 
executable via PyInstaller.

Same reasoning as build_windows.py: no --windowed/--noconsole. This is a 
console-mode CLI tool that needs a real terminal for click.prompt(hide_input=True)
to read the password from. Building without --windowed is what makes 
double-clicking the app open Terminal.app and show the prompts.

PyInstaller cannot cross-compile: this script must run ON macOS to produce 
a macOS binary.
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
    if platform.system() != "Darwin":
        print(
            f"ERROR: this script must run on macOS to produce a "
            f"macOS binary (PyInstaller does not cross-compile). "
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