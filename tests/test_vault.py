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

    Used as the starting point for nearly every test in this file -
    centralising it here means every test locks/unlocks the exact
    same known content, so assertions about "was it restored correctly"
    have a fixed, predictable baseline to compare against.
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
    automatically to every test via autouse=True - no test needs to opt in,
    since nothing in this file should ever need the real, production-sized
    cooldown values to prove its point.
    """

    monkeypatch.setattr(vault, "BASE_COOLDOWN_SECONDS", 0.01)
    monkeypatch.setattr(vault, "MAX_COOLDOWN_SECONDS", 0.05)


# --- lock() ----
def test_lock_creates_vault_file(secret_folder):
    """
    lock() should produce a real .vault file on disk, with the expected
    extension, as its primary observable output.
    """
    vault_path = lock(str(secret_folder), password="hunter2")
    assert vault_path.exists()
    assert vault_path.suffix == ".vault"

def test_lock_remove_original_by_default(secret_folder):
    """
    By default, lock() should remove the original plaintext folder once 
    encryption succeeds - leaving an unencrypted copy sitting next to 
    the vault would defeat the entire point of locking it.
    """
    lock(str(secret_folder),password="hunter2")
    assert not secret_folder.exists()

def test_lock_keeps_original_when_secure_delete_false(secret_folder):
    """
    When secure_delete=False, the original folder must be left untouched.
    This exists for testing/verification workflows where a user wants to 
    confirm a vault is valid before trusting it with the only copy of their data.
    """
    lock(str(secret_folder), password="hunter2", secure_delete=False)
    assert secret_folder.exists()

def test_lock_raises_if_folder_missing(tmp_path):
    """
    Locking a path that doesn't exist at all should fail loudly with a clear 
    VaultError, not an unhandled OSError ora silent no-op.
    """
    with pytest.raises(VaultError):
        lock(str(tmp_path / "does_not_exist"), password="hunter2")

def test_lock_raises_if_path_is_a_file_not_a_folder(tmp_path):
    """
    lock() only knows how to archive folders. Pointing it at a plain file
    should be rejected explicitly rather than producing a malformed or empty
    archive.
    """
    a_file = tmp_path / "not_a_folder.txt"
    a_file.write_text("oops")
    with pytest.raises(VaultError):
        lock(str(a_file), password="hunter2")

def test_lock_writes_to_custom_output_path(secret_folder, tmp_path):
    """
    Callers should be able to override where the .vault file gets written,
    rather than always accepting the default "next to the original folder" 
    location.
    """
    custom_output = tmp_path / "custom_name.vault"
    result = lock(str(secret_folder), password="hunter2", output_path=str(custom_output))
    assert result == custom_output
    assert custom_output.exists()

# --- unlock(): round trip ----

def test_unlock_restores_original_content(secret_folder):
    """
    The core promise of the whole module: what goes in via lock() must
    come backout via unlock() byte-for-byte identical. This is the single 
    most important test in the file - if this fails, nothing else here 
    matters.
    """
    original_diary = (secret_folder / "diary.txt").read_text()
    original_notes = (secret_folder / "notes.txt").read_text()

    vault_path = lock(str(secret_folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")

    assert restored.exists()
    assert (restored / "diary.txt").read_text() == original_diary
    assert (restored / "notes.txt").read_text() == original_notes

def test_unlock_remove_vault_file_by_default(secret_folder):
    """
    By default, a successful unlock should clean up the .vault file it just
    consumed - enforcing the rule that a given vault is either "a folder" or
    "a .vault file," never both existing at once.
    """
    vault_path = lock(str(secret_folder), password="hunter2")
    unlock(str(vault_path), password="hunter2")
    assert not vault_path.exists()

def test_unlock_keeps_vault_file_when_delete_vault_file_false(secret_folder):
    """
    When delete_vault_file=False, the sealed .vault file should survive a 
    successful unlock - useful for anyone who wants to keep the sealed original
    as a backup rather than trusting the freshly restored copy alone.
    """
    value_path = lock(str(secret_folder), password="hunter2")
    unlock(str(value_path), password="hunter2", delete_vault_file=False)
    assert value_path.exists()

def test_unlock_raises_if_vault_missing(tmp_path):
    """
    Attempting to unlock a path that isn't an actual vault file should fail
    with a clear VaultError rather than an unhandled exception from deep inside
    the file-reading logic.
    """
    with pytest.raises(VaultError):
        unlock(str(tmp_path / "nope.vault"), password="hunter2")

def test_unlock_refuses_to_overwrite_existing_folder(secret_folder):
    """
    If a folder already exists where unlock() would restore to, it must refuse rather
    than silently overwrite whatever's already there. This guards against accidental
    data loss in the edge case where a vault and a same=named folder both exist 
    simultaneously.
    """
    vault_path = lock(str(secret_folder), password="hunter2", secure_delete=False)
    # secret_folder is still on disk (secure_delete=False), so unlocking
    # into the same location should refuse rather than clobber it.
    with pytest.raises(VaultError):
        unlock(str(vault_path), password="hunter2")

# ---- unlock(): integrity handling ----

def test_unlock_wrong_password_raises_vault_error(secret_folder):
    """
    The most basic integrity check: an incorrect password must prevent the vault
    from unlocking, full stop.
    """
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
    """
    A tempered or corrupted .vault file should fail the exact same way a 
    wrong password does - GCM's auth tag can't tell the two apart, and that
    ambiguity is a deliberate security property, not a bug. This test proves
    corruption is caught, not just bad passwords. 
    """
    vault_path = lock(str(secret_folder), password="hunter2")
 
    # Flip some bytes near the end of the file (inside the ciphertext).
    with open(vault_path, "r+b") as f:
        f.seek(-5, 2)
        f.write(b"\x00\x00\x00\x00\x00")
 
    with pytest.raises(VaultError):
        unlock(str(vault_path), password="hunter2")

# --- failed-attempt cooldown: unit-level ---

def test_cooldown_seconds_is_zero_with_no_failures():
    """
    With zero prior failure, there should be no cooldown at all - a first
    attempt (or a fresh vault) should never be artificially slowed down
    """
    assert _cooldown_seconds(0) == 0.0

def test_cooldown_seconds_doubles_with_each_failure(monkeypatch):
    """
    The cooldown should follow a clean doubling pattern (1s, 2s, 4s, 8s...) 
    as failures accumulate — this is what makes rapid-fire guessing 
    progressively more expensive for an attacker, while a single mistyped 
    password barely costs the legitimate user anything.
    """
    monkeypatch.setattr(vault, "BASE_COOLDOWN_SECONDS", 1.0)
    monkeypatch.setattr(vault, "MAX_COOLDOWN_SECONDS", 1000.0)

    assert _cooldown_seconds(1) == 1.0
    assert _cooldown_seconds(2) == 2.0
    assert _cooldown_seconds(3) == 4.0
    assert _cooldown_seconds(4) == 8.0

def test_cooldown_seconds_is_capped(monkeypatch):
    """
    Uncapped exponential growth would eventually make a vault functionally
    unusable even for its legitimate owner. The cap ensures the cooldown stays
    "annoying," never "punishing" - confirmed here by checking a failure count
    high enough that the uncapped formula would be enormous, yet the result stays
    pinned at MAX_COOLDOWN_SECONDS.
    """
    monkeypatch.setattr(vault, "BASE_COOLDOWN_SECONDS", 1.0)
    monkeypatch.setattr(vault, "MAX_COOLDOWN_SECONDS", 5.0)

    assert _cooldown_seconds(10) == 5.0 # would be huge uncapped, but pinned at max

# --- failed-attempt cooldown: integration through unlock() ----

def test_failed_attempts_increment_on_wrong_password(secret_folder):
    """
    Each wrong-password attempt should increment the persisted failed-attempt
    counter by exactly one - this is the actual state that _cooldown_seconds()
    reads from on the next attempt, so if this doesn't work, the cooldown feature 
    doesnt work at all regardless of how correct the math functions are in isolation.
    """
    vault_path = lock(str(secret_folder), password="hunter2")

    assert _load_failed_attempts(vault_path) == 0

    with pytest.raises(VaultError):
        unlock(str(vault_path), password="wrongpassword")
    assert _load_failed_attempts(vault_path) == 1

    with pytest.raises(VaultError):
        unlock(str(vault_path), password="wrongpassword")
    assert _load_failed_attempts(vault_path) == 2

def test_failed_attempts_reset_after_successful_unlock(secret_folder):
    """
    Once the correct password is finally entered,the failed-attempt count must reset
    - otherwise a legitimate user who mistyped their password a couple of times would
    carry that penalty forward forever, which would violate the "cosmetic friction, 
    never punishing" design goal.
    """
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
    right. Verified here by timing the correct-password call and confirming it takes at 
    least as long as the cooldown a single prior failure should have earned.
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