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


# --- lock() ----
def test_lock_creates_vault_file(secret_folder):
    vault_path = lock(str(secret_folder), password="hunter2")
    assert vault_path.exists()
    assert vault_path.suffix == ".vault"

def test_lock_remove_origina_by_default(secret_folder):
    lock(str(secret_folder),password="hunter2")
    assert not secret_folder.exists()

def test_lock_keeps_original_when_secure_delete_false(secret_folder):
    lock(str(secret_folder), password="hunter2", secure_delete=False)
    assert secret_folder.exists()

def test_lock_raises_if_folder_missing(tmp_path):
    with pytest.raises(VaultError):
        lock(str(tmp_path / "does_not_exist"), password="hunter2")

def test_lock_raises_if_path_is_a_file_not_a_folder(tmp_path):
    a_file = tmp_path / "not_a_folder.txt"
    a_file.write_text("oops")
    with pytest.raises(VaultError):
        lock(str(a_file), password="hunter2")

def test_lock_writes_to_custom_output_path(secret_folder, tmp_path):
    custom_output = tmp_path / "custom_name.vault"
    result = lock(str(secret_folder), password="hunter2", output_path=str(custom_output))
    assert result == custom_output
    assert custom_output.exists()

# --- unlock(): round trip ----

def test_unlock_restroes_original_content(secret_folder):
    original_diary = (secret_folder / "diary.txt").read_text()
    original_notes = (secret_folder / "notes.txt").read_text()

    vault_path = lock(str(secret_folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")

    assert restored.exists()
    assert (restored / "diary.txt").read_text() == original_diary
    assert (restored / "notes.txt").read_text() == original_notes

def test_unlock_remove_vault_file_by_default(secret_folder):
    vault_path = lock(str(secret_folder), password="hunter2")
    unlock(str(vault_path), password="hunter2")
    assert not vault_path.exists()

def test_unlock_keeps_vault_file_when_delete_vault_file_false(secret_folder):
    value_path = lock(str(secret_folder), password="hunter2")
    unlock(str(value_path), password="hunter2", delete_vault_file=False)
    assert value_path.exists()

def test_unlock_raises_if_vault_missing(tmp_path):
    with pytest.raises(VaultError):
        unlock(str(tmp_path / "nope.vault"), password="hunter2")

def test_unlock_refuses_to_overwrite_existing_folder(secret_folder):
    vault_path = lock(str(secret_folder), password="hunter2", secure_delete=False)
    # secret_folder is still on disk (secure_delete=False), so unlocking
    # into the same location should refuse rather than clobber it.
    with pytest.raises(VaultError):
        unlock(str(vault_path), password="hunter2")
