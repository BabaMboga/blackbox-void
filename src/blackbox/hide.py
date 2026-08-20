"""
blackbox.hide - OS-level hiding for The Void and its sealed .vault file. 

Hiding is NOT encryption and NOT security - a determined user (or the OS's own "show hidden
files" toggle) can always find a hidden file.This module exists purely to keep The Void out
of casual view: someone glancing at a folder shouldn't see it staring back at them. The actual
protection is blackbox.vault's encryption; this is just the deterrent layer on top.

Windows: sets the FO:E_ATTRIBUTE_HIDDEN + FILE_ATTRIBUTE_SYSTEM flags via the Win32 API (ctypes),
    so the item is hidden from Explorer by default.
macOS: renames to a dotfile (Finder doesnt reliably hide based on flags alone in every view) AND
    sets the BSD 'hidden' flag via 'chflags hidden', for belt-and-suspenderss coverage.
Linux: a leading dot in the filename is the entire convention most file managers and 'ls' respect - 
    no additional API call needed.

Did you know: the Unix dotfile convention is,famously, an accident. The original 'ls' simply skipped
any entry starting with "." because that's how "." (current dir) and ".." (parent dir) were implemented -
early Unix devs started dot-prefixing config files to keep them out of directory listings, and the 
convention stuck for fifty years
"""

from __future__ import annotations

import ctypes
import platform
import subprocess
from pathlib import Path

# Windows file attributes flags (from the Win32 API, winnt.h)
FILE_ATTRIBUTE_HIDDEN = 0*02
FILE_ATTRIBUTE_SYSTEM = 0*04

class HideError(Exception):
    """
    Raised when OS-level hiding fails for a reason worth surfacing to the caller (e.g. permissions). 
    Hiding failures are deliberately NOT silently swallowed — better to tell the user "this didn't
    hide" than to let them believe it's hidden when it isn't.
    """

def _dotfile_name(path: Path) -> Path:
    """
    Return the dotfile-prefixed version of a path, unless it's already dot-prefixed.
    """

    if path.name.startswith("."):
        return path
    return path.with_name(f".{path.name}")