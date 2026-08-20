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

# ---- unlock(): integrity handling ----

def test_unlock_wrong_password_raises_vault_error(secret_folder):
    vault_path = lock(str(secret_folder), password="hunter2")
    with pytest.raises(VaultError):
        unlock(str(vault_path), password="wrongpassword")

def test_unlock_wrong_password_does_not_raise_raw_invalidtag(secret_folder):
    """
    Callers should only ever see VaultError from this module,never a raw
    cryptography.exceptions.InvalidTag leaking through.
    """

    vault_path = lock(str(secret_folder), password="hunter2")
    try:
        unlock(str(vault_path), password="wrongpassword")

    except VaultError as e:
        assert "wrong password" in str(e).lower() or "corrupted" in str(e).lower()
    else:
        pytest.fail("Expected VaultError, but unlock() succeeded wuth a wrong password.")

def test_unlock_corrupted_vault_raises_vault_error(secret_folder):
    vault_path = lock(str(secret_folder), password="hunter2")
 
    # Flip some bytes near the end of the file (inside the ciphertext).
    with open(vault_path, "r+b") as f:
        f.seek(-5, 2)
        f.write(b"\x00\x00\x00\x00\x00")
 
    with pytest.raises(VaultError):
        unlock(str(vault_path), password="hunter2")

# --- failed-attempt cooldown: unit-level ---

def test_cooldown_seconds_is_zereo_with_no_failures():
    assert _cooldown_seconds(0) == 0.0

def test_cooldown_seconds_doubles_with_each_failure(monkeypatch):
    monkeypatch.setattr(vault, "BASE_COOLDOWN_SECONDS", 1.0)
    monkeypatch.setattr(vault, "MAX_COOLDOWN_SECONDS", 1000.0)

    assert _cooldown_seconds(1) == 1.0
    assert _cooldown_seconds(2) == 2.0
    assert _cooldown_seconds(3) == 4.0
    assert _cooldown_seconds(4) == 8.0

def test_cooldown_seconds_is_capped(monkeypatch):
    monkeypatch.setattr(vault, "BASE_COOLDOWN_SECONDS", 1.0)
    monkeypatch.setattr(vault, "MAX_COOLDOWN_SECONDS", 5.0)

    assert _cooldown_seconds(10) == 5.0 # would be huge uncapped, but pinned at max

# --- failed-attempt cooldown: integration through unlock() ----

def test_failed_attempts_increment_on_worng_password(secret_folder):
    vault_path = lock(str(secret_folder), password="hunter2")

    assert _load_failed_attempts(vault_path) == 0

    with pytest.raises(VaultError):
        unlock(str(vault_path), password="wrongpassword")
    assert _load_failed_attempts(vault_path) == 1

    with pytest.raises(VaultError):
        unlock(str(vault_path), password="wrongpassword")
    assert _load_failed_attempts(vault_path) == 2

def test_failed_attempts_reset_after_successful_unlock(secret_folder):
    vault_path = lock(str(secret_folder), password="hunter2")

    with pytest.raises(VaultError):
        unlock(str(vault_path), password="Wrongpassword")
    assert _load_failed_attempts(vault_path) == 1

    unlock(str(vault_path),password="hunter2")

    # vault_path itself is gone now (unlocked successfully), but the
    # sidecar convention is what we're really checking: it should not
    # have been left behind at 1 for a vault that no longer exists.
    sidecar = vault_path.parent / f"{vault_path.name}.attempts.json"
    assert not sidecar.exists()

def test_correct_password_still_pays_cooldown_from_prior_failures(secret_folder, monkeypatch):
    """
    A correct passwordon attempt N still pays whatever cooldown was earned by the preview
    N-1 failures - the check happens before we know the attempt will succeed. This is 
    intentional: an attacker shouldn't be able to skip the delay by eventually guessing
    right.
    """

    monkeypatch.setattr(vault, "BASE_COOLDOWN_SECONDS", 0.05)
    monkeypatch.setattr(vault, "MAX_COOLDOWN_SECONDS", 1.0)

    vault_path = lock(str(secret_folder), password="hunter2")

    with pytest.raises(VaultError):
        unlock(str(vault_path), password="wrongpassword")

    start = time.monotonic()
    unlock(str(vault_path),password="hunter2")
    elapsed = time.monotonic() - start
    assert elapsed >= 0.05 # paid at least the 1-failure cooldown