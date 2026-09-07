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
FILE_ATTRIBUTE_HIDDEN = 0x02
FILE_ATTRIBUTE_SYSTEM = 0x04
FILE_ATTRIBUTE_NORMAL = 0X80

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

def _undotted_name(path: Path) -> Path:
    """Return the un-prefixed version of a dotfile path — the reverse
    of _dotfile_name. A path that isn't dot-prefixed is returned
    unchanged, and ".." (parent-dir shorthand) is deliberately never
    touched, since stripping its leading dot would produce garbage.
    """
    if path.name.startswith("..") or not path.name.startswith("."):
        return path
    return path.with_name(path.name[1:])

def _hide_windows(path: Path) -> Path:
    """
    Set the hidden + system attributes via the Win32 API.
    """
    attrs = FILE_ATTRIBUTE_HIDDEN | FILE_ATTRIBUTE_SYSTEM
    success = ctypes.windll.kernel32.SetFileAttributesW(str(path), attrs)
    if not success:
        error_code = ctypes.windll.kernel32.GetLastError()
        raise HideError(
            f"Failed to hide '{path}' on Windows (error code {error_code})."
        )
    return path

def _hide_macos(path: Path) -> Path:
    """
    Rename to a dotfile AND set the BSD 'hidden' flag via chflags, for coverage across Finder,
    Terminal and other tools.
    """
    dotted_path = _dotfile_name(path)
    if dotted_path != path:
        path.rename(dotted_path)

    result = subprocess.run(
        ["chflags", "hidden", str(dotted_path)],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise HideError(
            f"Failed to set hidden flag on '{dotted_path}' via chflags: "
            f"{result.stderr.strip()}"
        )
    return dotted_path

def _hide_linux(path: Path) -> Path:
    """
    Rename to a dotfile - the entire Linux hiding convention.
    """
    dotted_path = _dotfile_name(path)
    if dotted_path != path:
        path.rename(dotted_path)
    return dotted_path

def hide_path(path: str | Path) -> Path:
    """
    Hide a file or folder from casual view, using the appropriate mechanism for the current OS.
 
    This is cosmetic/deterrent only — it is not a security boundary. Encryption (blackbox.vault) 
    is what actually protects the data; this just keeps it out of a casual glance at a file browser.
 
    Args:
        path: the file or folder to hide.
 
    Returns:
        The path to the now-hidden item — on macOS/Linux this may differ from the input path, 
        since hiding there means renaming to a dotfile. Callers should use the returned path 
        for any further operations, not the original.
 
    Raises:
        HideError: if the current OS isn't recognized, or the underlying OS call fails.
    """
    path = Path(path).resolve()
    system = platform.system()

    if system == "Windows":
        return _hide_windows(path)
    elif system == "Darwin":
        return _hide_macos(path)
    elif system == "Linux":
        return _hide_linux(path)
    else:
        raise HideError(f"Unsupported OS for hiding: {system!r}")

def _unhide_windows(path: Path) -> Path:
    """
    Clear the hidden + syste, attributes via the Win32 API, restoring the item to 
    FILE_ATTRIBUTE_NORMAL
    """

    try:
        success = ctypes.windll.kernel32.SetFileAttributesW(str(path), FILE_ATTRIBUTE_NORMAL)
    except AttributeError as exc:
        raise HideError(f"Windows API call failed unexpectedly: {exc}") from exc
    
    if not success:
        error_code = ctypes.windll.kernel32.GetLastError()
        raise HideError(
            f"Failed to unhide '{path}' on Windows (error code {error_code})."
        )
    return path

def _unhide_macos(path: Path) -> Path:
    """
    Clear the BSD 'hidden' flag via chflags AND rename away the dotfile prefix, 
    reversing both steps _hide_macos performed.
    """

    result = subprocess.run(
        ["chflags", "nohidden", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise HideError(
            f"Failed to clear hidden flag on '{path}' via chflags: "
            f"{result.stderr.strip()}"
        )

    undotted_path = _undotted_name(path)
    if undotted_path != path:
        path.rename(undotted_path)
    return undotted_path

def _unhide_linux(path: Path) -> Path:
    """
    Rename away the dotfile prefix - the entire Linux unhiding mechanism, 
    mirroring _hide_linux exactly.
    """

    undotted_path = _undotted_name(path)
    if undotted_path != path:
        path.rename(undotted_path)
    return undotted_path

def unhide_path(path: str | Path) -> Path:
    """
    Reverse of hide_path(): restore a previously hidden file or
    folder to normal visibility, using the appropriate mechanism for
    the current OS.
 
    Args:
        path: the currently-hidden file or folder to restore. On
            macOS/Linux this should be the dotfile path (i.e. the
            path hide_path() actually returned), not the original
            pre-hide name.
 
    Returns:
        The path to the now-visible item — on macOS/Linux this may
        differ from the input path, since unhiding there means
        renaming away the dotfile prefix.
 
    Raises:
        HideError: if the current OS isn't recognized, or the
            underlying OS call fails.
    """

    path = Path(path).resolve()
    system = platform.system()

    if system == "Windows":
        return _unhide_windows(path)
    elif system == "Darwin":
        return _unhide_macos(path)
    elif system == "Linux":
        return _unhide_linux(path)
    else:
        raise HideError(f"Unsupported OS for unhiding: {system!r}")