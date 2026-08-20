"""
Tests for blackbox.vault — lock/unlock, integrity handling, and the
failed-attempt cooldown.
 
Cooldown-related tests monkeypatch the timing constants down to
fractions of a second so the suite stays fast — the *logic* being
tested (growth curve, cap, reset) doesn't depend on the actual
magnitude of the constants, only their relationship to each other.
"""

import time

import pytest
from blackbox import vault
from blackbox.vault import (
    VaultError,
    _cooldown_seconds,
    _load_failed_attempts,
    lock,
    unlock,
)

# --- Fixture ----

@pytest.fixture
def secret_folder(tmp_path):
    """
    A small folder with real content, ready to be locked.
    """
    folder = tmp_path / "my_secrets"
    folder.mkdir()
    (folder / "diary.txt").write_text("dear diary...")
    (folder / "notes.txt").write_text("remember the milk")
    return folder

@pytest.fixture(autouse=True)
def fast_cooldown(monkeypatch):
    """
    Shrink the cooldown constants for every test in this file, so tests that 
    trigger real sleeps take milliseconds,not tens of seconds. Applied 
    automatically to every test via autouse=True
    """

    monkeypatch.setattr(vault, "BASE_COOLDOWN_SECONDS", 0.01)
    monkeypatch.setattr(vault, "MAX_COOLDOWN_SECONDS", 0.05)

    