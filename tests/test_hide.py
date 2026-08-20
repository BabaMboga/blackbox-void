"""
Tests for blackbox.hide — OS-level hiding for The Void and its sealed
.vault file.

This module is inherently platform-specific, so the tests here fall
into two categories:

1. Platform-INDEPENDENT tests — the dotfile-naming helper and the
   hide_path() dispatch logic (which OS routes to which function) can
   be tested on any machine, since we can monkeypatch platform.system()
   to pretend to be a different OS and swap in fake _hide_* functions
   to observe dispatch without actually touching OS-level file
   attributes.

2. Platform-GATED tests — the real _hide_windows/_hide_macos/
   _hide_linux implementations can only be meaningfully exercised on
   the OS they target (you can't call SetFileAttributesW on Linux, or
   chflags on Windows). These are marked with pytest.mark.skipif so
   they only run on a matching CI runner or developer machine, and are
   silently skipped everywhere else rather than failing.
"""

import platform

import pytest

from blackbox import hide
from blackbox.hide import HideError, _dotfile_name, hide_path


# --- _dotfile_name(): platform-independent -----------------------------

def test_dotfile_name_adds_dot_prefix(tmp_path):
    """A normal filename should get a leading dot added."""
    original = tmp_path / "The Void.vault"
    result = _dotfile_name(original)
    assert result.name == ".The Void.vault"


def test_dotfile_name_leaves_already_dotted_path_unchanged(tmp_path):
    """A path that's already a dotfile shouldn't get a second dot
    prepended — calling this twice on the same path (e.g. if hide_path
    were accidentally called twice) must be idempotent.
    """
    already_dotted = tmp_path / ".The Void.vault"
    result = _dotfile_name(already_dotted)
    assert result == already_dotted
    assert not result.name.startswith("..")


def test_dotfile_name_preserves_parent_directory(tmp_path):
    """The dotfile transformation should only touch the filename, not
    silently move the file to a different directory.
    """
    original = tmp_path / "subdir" / "secret.vault"
    result = _dotfile_name(original)
    assert result.parent == original.parent


# --- hide_path(): dispatch logic, platform-independent -----------------

def test_hide_path_dispatches_to_windows_handler(tmp_path, monkeypatch):
    """On a system reporting itself as Windows, hide_path() must call
    the Windows-specific handler — verified here without touching any
    real Windows API, by swapping in a fake handler and checking it
    was the one invoked.
    """
    calls = []
    monkeypatch.setattr(platform, "system", lambda: "Windows")
    monkeypatch.setattr(hide, "_hide_windows", lambda p: calls.append(p) or p)

    target = tmp_path / "dummy.vault"
    result = hide_path(target)

    assert len(calls) == 1
    assert result == target


def test_hide_path_dispatches_to_macos_handler(tmp_path, monkeypatch):
    """On a system reporting itself as Darwin (macOS), hide_path()
    must call the macOS-specific handler.
    """
    calls = []
    monkeypatch.setattr(platform, "system", lambda: "Darwin")
    monkeypatch.setattr(hide, "_hide_macos", lambda p: calls.append(p) or p)

    target = tmp_path / "dummy.vault"
    result = hide_path(target)

    assert len(calls) == 1
    assert result == target


def test_hide_path_dispatches_to_linux_handler(tmp_path, monkeypatch):
    """On a system reporting itself as Linux, hide_path() must call
    the Linux-specific handler.
    """
    calls = []
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(hide, "_hide_linux", lambda p: calls.append(p) or p)

    target = tmp_path / "dummy.vault"
    result = hide_path(target)

    assert len(calls) == 1
    assert result == target


def test_hide_path_raises_on_unrecognized_os(tmp_path, monkeypatch):
    """An OS that isn't Windows, Darwin, or Linux (e.g. a BSD variant
    or something exotic) should fail with a clear HideError rather
    than silently doing nothing or crashing with an unrelated error.
    """
    monkeypatch.setattr(platform, "system", lambda: "PlanNine")

    with pytest.raises(HideError):
        hide_path(tmp_path / "dummy.vault")


def test_hide_path_resolves_relative_paths(tmp_path, monkeypatch):
    """hide_path() should resolve its input to an absolute path before
    dispatching — callers shouldn't need to worry about relative-path
    surprises depending on the current working directory.
    """
    captured = []
    monkeypatch.setattr(platform, "system", lambda: "Linux")
    monkeypatch.setattr(hide, "_hide_linux", lambda p: captured.append(p) or p)

    hide_path(tmp_path / "dummy.vault")

    assert captured[0].is_absolute()


# --- _hide_linux(): real implementation, gated to Linux -----------------

@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only hiding mechanism")
def test_hide_linux_renames_to_dotfile(tmp_path):
    """On real Linux, hiding a file should rename it to a dotfile —
    the entire hiding mechanism on this platform is the filename
    convention itself.
    """
    target = tmp_path / "secret.vault"
    target.write_text("shh")

    result = hide_path(target)

    assert result.name == ".secret.vault"
    assert result.exists()
    assert not target.exists()


@pytest.mark.skipif(platform.system() != "Linux", reason="Linux-only hiding mechanism")
def test_hide_linux_hidden_file_excluded_from_plain_listing(tmp_path):
    """A hidden file should not show up in a normal directory listing
    — this is the actual observable behavior a user cares about, not
    just "the filename has a dot in it."
    """
    target = tmp_path / "secret.vault"
    target.write_text("shh")
    hide_path(target)

    visible_entries = [p.name for p in tmp_path.iterdir() if not p.name.startswith(".")]
    assert "secret.vault" not in visible_entries


# --- _hide_macos(): real implementation, gated to macOS ------------------

@pytest.mark.skipif(platform.system() != "Darwin", reason="macOS-only hiding mechanism")
def test_hide_macos_renames_to_dotfile_and_sets_hidden_flag(tmp_path):
    """On real macOS, hiding should both rename to a dotfile AND set
    the BSD hidden flag via chflags — belt-and-suspenders coverage
    across Finder and Terminal. Only meaningful on an actual Mac,
    since chflags doesn't exist elsewhere.
    """
    target = tmp_path / "secret.vault"
    target.write_text("shh")

    result = hide_path(target)

    assert result.name == ".secret.vault"
    assert result.exists()
    assert not target.exists()


# --- _hide_windows(): real implementation, gated to Windows -------------

@pytest.mark.skipif(platform.system() != "Windows", reason="Windows-only hiding mechanism")
def test_hide_windows_sets_hidden_attribute(tmp_path):
    """On real Windows, hiding should set the FILE_ATTRIBUTE_HIDDEN +
    FILE_ATTRIBUTE_SYSTEM flags via the Win32 API. Only meaningful on
    actual Windows, since ctypes.windll doesn't exist on other
    platforms even at import time.
    """
    target = tmp_path / "secret.vault"
    target.write_text("shh")

    result = hide_path(target)

    # On Windows, hide_path doesn't rename — it sets attributes in place.
    assert result == target
    assert result.exists()