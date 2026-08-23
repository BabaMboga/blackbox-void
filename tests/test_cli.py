"""
Tests for blackbox.cli — end-to-end coverage of the init, status,
lock, and unlock commands.

Uses Click's CliRunner, which simulates real terminal input/output
without needing an actual terminal — including simulating password
entry via the `input=` parameter, exactly as a user typing at a
prompt would. Each test runs inside CliRunner's isolated_filesystem()
context manager, which chdir()s into a fresh temporary directory, since
these CLI commands work off cwd-relative paths.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from blackbox.cli import main


@pytest.fixture
def runner():
    """A fresh CliRunner for each test."""
    return CliRunner()


# --- status: before anything exists --------------------------------------

def test_status_reports_uninitialized_when_nothing_exists(runner):
    """Before `init` has ever been run, status should say so clearly
    rather than crashing or reporting a misleading state.
    """
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "hasn't been created yet" in result.output


# --- init ------------------------------------------------------------

def test_init_creates_the_void(runner):
    """Running init for the first time should create The Void folder
    and report success.
    """
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init"])
        assert result.exit_code == 0
        assert "Ready" in result.output
        assert Path("The Void").exists()


def test_init_is_safe_to_run_twice(runner):
    """Running init again on an already-existing, populated Void must
    not wipe out its contents — this is the same safety guarantee
    init_void() itself provides, verified here through the actual CLI
    command a user would run.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        (Path("The Void") / "keep_me.txt").write_text("important")

        result = runner.invoke(main, ["init"])

        assert result.exit_code == 0
        assert (Path("The Void") / "keep_me.txt").read_text() == "important"


def test_init_respects_custom_name(runner):
    """The --name option should let a user create a differently-named
    vault folder instead of the default "The Void".
    """
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["init", "--name", "MyStuff"])
        assert result.exit_code == 0
        assert Path("MyStuff").exists()


# --- status: after init ------------------------------------------------

def test_status_reports_unlocked_after_init(runner):
    """Once The Void exists as a plain folder, status should report
    the unlocked state.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "Unlocked" in result.output


# --- lock: happy path --------------------------------------------------

def test_lock_seals_the_folder(runner):
    """Locking should produce a .vault file and remove the original
    folder, confirmed via the actual CLI output and filesystem state.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        (Path("The Void") / "secret.txt").write_text("shh")

        result = runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        assert result.exit_code == 0
        assert "Sealed" in result.output
        assert Path("The Void.vault").exists()
        assert not Path("The Void").exists()


def test_lock_prompts_for_password_confirmation(runner):
    """The password prompt should ask twice (entry + confirmation) —
    confirmed by checking both prompt labels appear in the output.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        assert "Password" in result.output
        assert "Repeat for confirmation" in result.output


def test_lock_fails_when_password_confirmation_does_not_match(runner):
    """Click's confirmation_prompt should reject mismatched passwords
    before ever reaching vault.lock() — a typo in either entry should
    not silently proceed with the first (possibly wrong) value.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        result = runner.invoke(
            main, ["lock", "--fast"], input="hunter2\ndifferentpassword\n"
        )

        assert result.exit_code != 0
        # The vault should never have been created from a rejected,
        # mismatched confirmation.
        assert not Path("The Void.vault").exists()


def test_lock_updates_status_to_locked(runner):
    """After a successful lock, status should reflect the new locked
    state rather than still reporting unlocked or uninitialized.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        result = runner.invoke(main, ["status"])

        assert "Locked" in result.output


# --- lock: error paths --------------------------------------------------

def test_lock_fails_clearly_for_missing_folder(runner):
    """Attempting to lock a folder that doesn't exist should fail with
    a clear error and non-zero exit code, not an unhandled traceback.
    """
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["lock", "Nonexistent", "--fast"])

        assert result.exit_code != 0
        assert "does not exist" in result.output


def test_lock_fails_clearly_for_a_file_instead_of_a_folder(runner):
    """Pointing lock at a plain file (not a directory) should be
    rejected with a clear message.
    """
    with runner.isolated_filesystem():
        Path("not_a_folder.txt").write_text("oops")
        result = runner.invoke(main, ["lock", "not_a_folder.txt", "--fast"])

        assert result.exit_code != 0
        assert "not a folder" in result.output


# --- unlock: happy path --------------------------------------------------

def test_unlock_restores_the_folder(runner):
    """Unlocking with the correct password should restore the folder
    and its exact original content.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        (Path("The Void") / "secret.txt").write_text("the actual secret")
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        result = runner.invoke(main, ["unlock", "--fast"], input="hunter2\n")

        assert result.exit_code == 0
        assert "Restored" in result.output
        assert (Path("The Void") / "secret.txt").read_text() == "the actual secret"


def test_unlock_updates_status_back_to_unlocked(runner):
    """After a successful unlock, status should reflect the restored
    unlocked state.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")
        runner.invoke(main, ["unlock", "--fast"], input="hunter2\n")

        result = runner.invoke(main, ["status"])

        assert "Unlocked" in result.output


# --- unlock: error paths -------------------------------------------------

def test_unlock_fails_clearly_with_wrong_password(runner):
    """A wrong password should fail with a clear message and non-zero
    exit code, and must NOT restore the folder — leaving the sealed
    vault file exactly as it was.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        result = runner.invoke(main, ["unlock", "--fast"], input="wrongpassword\n")

        assert result.exit_code != 0
        assert "Unlock failed" in result.output
        assert not Path("The Void").exists()
        assert Path("The Void.vault").exists()  # still sealed, untouched


def test_unlock_fails_clearly_for_missing_vault_file(runner):
    """Attempting to unlock when no .vault file exists at all should
    fail with a clear error rather than an unhandled exception.
    """
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["unlock", "--fast"], input="anypassword\n")

        assert result.exit_code != 0
        assert "does not exist" in result.output


# --- Full lifecycle --------------------------------------------------

def test_full_lifecycle_init_lock_unlock(runner):
    """The complete user journey in one test: create, populate, lock,
    unlock, and confirm the content survived the entire round trip
    untouched — the same guarantee test_vault.py verifies at the
    module level, now confirmed through the actual CLI a user runs.
    """
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init"]).exit_code == 0

        (Path("The Void") / "diary.txt").write_text("dear diary, blackbox works")

        lock_result = runner.invoke(
            main, ["lock", "--fast"], input="correcthorse\ncorrecthorse\n"
        )
        assert lock_result.exit_code == 0
        assert Path("The Void.vault").exists()

        unlock_result = runner.invoke(
            main, ["unlock", "--fast"], input="correcthorse\n"
        )
        assert unlock_result.exit_code == 0
        assert (Path("The Void") / "diary.txt").read_text() == "dear diary, blackbox works"