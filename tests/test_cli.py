"""
Tests for blackbox.cli — end-to-end coverage of init, status, lock,
and unlock, including the hide/disguise concealment integration.

Uses Click's CliRunner, which simulates real terminal input/output
without needing an actual terminal — including simulating password
entry via the `input=` parameter. Each test runs inside CliRunner's
isolated_filesystem() context manager, since these CLI commands work
off cwd-relative paths.
"""

import random
from pathlib import Path

import pytest
from click.testing import CliRunner

import blackbox.cli as cli_module
from blackbox.cli import main



@pytest.fixture
def runner():
    """A fresh CliRunner for each test."""
    return CliRunner()

@pytest.fixture(autouse=True)
def fast_mainframe_delay(monkeypatch):
    """
    Shrink the fake "connecting to mainframe" delay to near-zero for every
    test in this file. Without this, every test calling `status` pays the 
    ~1.2s theatrical delay,which is fine for a human watching the terminal 
    but turns the test suite from milliseconds into tens of seconds. Applied
    automatically via autouse=True - no test needs to opt in.
    """
    monkeypatch.setattr(cli_module, "_MAINFRAME_DELAY_SECONDS", 0.0)


def _visible_entries() -> list[str]:
    """List filenames in the current directory that are NOT
    dotfile-hidden — i.e. what a plain `ls` would show.
    """
    return [p.name for p in Path(".").iterdir() if not p.name.startswith(".")]

def _normalised(text: str) -> str:
    """
    Collapse all whitespace (including newlines inserted by rich's word-wrapping
    at the console width) into single spaces.

    Needed because rich.Console wraps long lines to fit the terminal width, which
    can insert a newline in the middle of a longer piece of flavor text. An exact
    substring check against the original unwrapped string would then fail even 
    though the text printed correctly - this normalizes both sides so wrapping can
    never break the comparison.
    """

    return " ".join(text.split())


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
    not wipe out its contents.
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


# --- lock: happy path, now including concealment ------------------------

def test_lock_produces_no_plainly_named_vault_file(runner):
    """After locking, there should be NO file visibly named
    "The Void.vault" sitting in plain sight — it must be disguised
    under a boring name AND hidden, not just encrypted.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        assert result.exit_code == 0
        assert not Path("The Void.vault").exists()


def test_lock_removes_the_original_folder(runner):
    """The original plaintext folder must be gone after a successful
    lock, regardless of what the sealed file ends up disguised as.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        assert result.exit_code == 0
        assert not Path("The Void").exists()


def test_lock_hides_the_disguised_vault_file(runner):
    """The disguised vault file should end up dot-prefixed (hidden),
    not just renamed to a boring name while remaining fully visible.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        hidden_entries = [
            p.name for p in Path(".").iterdir()
            if p.name.startswith(".") and p.name != ".blackbox_disguise_registry.json"
        ]
        assert len(hidden_entries) == 1


def test_lock_leaves_no_recognizable_vault_name_visible(runner):
    """A plain directory listing (excluding dotfiles) should show
    nothing recognizably related to the vault after locking — this is
    the actual observable behavior the disguise+hide system exists to
    provide.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        assert _visible_entries() == []


def test_lock_prompts_for_password_confirmation(runner):
    """The password prompt should ask twice (entry + confirmation)."""
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        assert "Password" in result.output
        assert "Repeat for confirmation" in result.output


def test_lock_fails_when_password_confirmation_does_not_match(runner):
    """Mismatched passwords should be rejected before ever reaching
    vault.lock() — nothing should get sealed, disguised, or hidden
    from a rejected confirmation.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        result = runner.invoke(
            main, ["lock", "--fast"], input="hunter2\ndifferentpassword\n"
        )

        assert result.exit_code != 0
        assert _visible_entries() == ["The Void"]  # untouched, still there


def test_lock_updates_status_to_locked(runner):
    """After a successful lock, status should reflect the new locked
    state.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        result = runner.invoke(main, ["status"])

        assert "Locked" in result.output


def test_status_does_not_leak_the_disguised_filename(runner):
    """status should confirm a vault is locked without printing the
    actual disguised/hidden filename — revealing it would defeat the
    entire purpose of disguising it in the first place.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        result = runner.invoke(main, ["status"])

        # None of the shipped default disguise names should appear in
        # the status output.
        from blackbox.config import DEFAULT_DISGUISE_NAMES
        for name in DEFAULT_DISGUISE_NAMES:
            assert name not in result.output


# --- lock: error paths --------------------------------------------------

def test_lock_fails_clearly_for_missing_folder(runner):
    """Attempting to lock a folder that doesn't exist should fail with
    a clear error and non-zero exit code.
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

def test_unlock_restores_the_folder_and_content(runner):
    """Unlocking with the correct password should restore the folder
    and its exact original content, having correctly reversed both
    the disguise and the hide steps first.
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


def test_unlock_leaves_no_stale_disguise_registry_entry(runner):
    """Once a vault is fully unlocked, its disguise registry entry
    should be cleaned up — a stale entry could confuse a future
    status/unlock call about whether this vault is still locked.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")
        runner.invoke(main, ["unlock", "--fast"], input="hunter2\n")

        from blackbox.config import _load_disguise_registry
        registry = _load_disguise_registry(Path("."))
        assert "The Void.vault" not in registry


# --- unlock: wrong password must never expose the vault -----------------

def test_unlock_wrong_password_does_not_restore_the_folder(runner):
    """A wrong password must fail without restoring the original
    folder — the plaintext content must never appear on disk from a
    failed attempt.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        result = runner.invoke(main, ["unlock", "--fast"], input="wrongpassword\n")

        assert result.exit_code != 0
        assert "Unlock failed" in result.output
        assert not Path("The Void").exists()


def test_unlock_wrong_password_leaves_vault_still_concealed(runner):
    """This is the critical regression test: a failed unlock attempt
    must re-conceal the vault (re-disguise and re-hide it), not leave
    it sitting around in a plain, visible, undisguised form. Without
    this guarantee, an attacker could brute-force a password, and even
    on failure, permanently strip the vault's concealment on the first
    wrong guess.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        runner.invoke(main, ["unlock", "--fast"], input="wrongpassword\n")

        # No recognizable vault name should be sitting visibly on disk.
        assert _visible_entries() == []


def test_unlock_wrong_password_still_reports_locked_status(runner):
    """After a failed unlock attempt, status must still say the vault
    is locked — not "unlocked" (it wasn't restored) and not
    "uninitialized" (the vault still genuinely exists, just failed to
    open).
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")
        runner.invoke(main, ["unlock", "--fast"], input="wrongpassword\n")

        result = runner.invoke(main, ["status"])

        assert "Locked" in result.output


def test_correct_password_still_works_after_a_prior_wrong_attempt(runner):
    """After being re-concealed under a (possibly new) disguised name
    following a failed attempt, the vault must still be fully
    recoverable with the correct password on a later try.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        (Path("The Void") / "secret.txt").write_text("still here")
        runner.invoke(main, ["lock", "--fast"], input="hunter2\nhunter2\n")

        runner.invoke(main, ["unlock", "--fast"], input="wrongpassword\n")
        result = runner.invoke(main, ["unlock", "--fast"], input="hunter2\n")

        assert result.exit_code == 0
        assert (Path("The Void") / "secret.txt").read_text() == "still here"


# --- unlock: error paths -------------------------------------------------

def test_unlock_fails_clearly_for_missing_vault(runner):
    """Attempting to unlock when no vault exists at all (nothing ever
    locked) should fail with a clear error rather than a crash.
    """
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["unlock", "--fast"], input="anypassword\n")

        assert result.exit_code != 0
        assert "no locked vault found" in result.output


# --- Full lifecycle --------------------------------------------------

def test_full_lifecycle_init_lock_unlock(runner):
    """The complete user journey in one test: create, populate, lock
    (with concealment), unlock, and confirm the content survived the
    entire round trip untouched.
    """
    with runner.isolated_filesystem():
        assert runner.invoke(main, ["init"]).exit_code == 0

        (Path("The Void") / "diary.txt").write_text("dear diary, blackbox works")

        lock_result = runner.invoke(
            main, ["lock", "--fast"], input="correcthorse\ncorrecthorse\n"
        )
        assert lock_result.exit_code == 0
        assert _visible_entries() == []  # nothing recognizable left in plain sight

        unlock_result = runner.invoke(
            main, ["unlock", "--fast"], input="correcthorse\n"
        )
        assert unlock_result.exit_code == 0
        assert (Path("The Void") / "diary.txt").read_text() == "dear diary, blackbox works"

# ---- Hidden --konami flag easter egg ---------------

def test_konami_flag_triggers_hidden_easter_egg(runner):
    """
    The hidden --konami flag should trigger the CLI easter egg.
    """
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["--konami"])
        assert result.exit_code == 0
        assert "KONAMI PROTOCOL ACCEPTED!" in result.output
        assert "BLACKBOX CHEAT CODE: +30 hacker points." in result.output

def test_konami_flag_is_hidden_from_help(runner):
    """
    The eeaster-egg flag should not clutter normal CLI help output.
    """
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["--help"])

        assert result.exit_code == 0
        assert "--konami" not in result.output

def test_konami_flag_does_not_run_any_real_subcommand(runner):
    """
    Passing --konami should short-circuit before any real subcommand logic runs
    - it must not accidentally create The Void, check status, or touch the filesystem
    at all.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["--konami"])
        assert not Path("The Void").exists()

def test_no_args_without_konami_shows_normal_help(runner):
    """
    Running blackbox with no arguments and no --konami flag should behave normally -
    showing the regular help text, not triggering the easter egg or crashing.
    """
    with runner.isolated_filesystem():
        result = runner.invoke(main, [])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "KONAMI PROTOCOL ACCEPTED!" not in result.output

def test_unlock_rare_joke_is_shown_when_random_roll_hits(
    runner,
    monkeypatch,
):
    """A successful unlock gets the joke only when the 5% roll succeeds."""
    monkeypatch.setattr(
        "blackbox.cli.random.random",
        lambda: 0.01,
    )

    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(
            main,
            ["lock", "--fast"],
            input="hunter2\nhunter2\n",
        )

        result = runner.invoke(
            main,
            ["unlock", "--fast"],
            input="hunter2\n",
        )

        assert result.exit_code == 0
        assert "mainframe is mildly impressed" in result.output


def test_unlock_rare_joke_is_not_shown_when_random_roll_misses(
    runner,
    monkeypatch,
):
    """A successful unlock normally remains free of the rare joke."""
    monkeypatch.setattr(
        "blackbox.cli.random.random",
        lambda: 0.50,
    )

    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        runner.invoke(
            main,
            ["lock", "--fast"],
            input="hunter2\nhunter2\n",
        )

        result = runner.invoke(
            main,
            ["unlock", "--fast"],
            input="hunter2\n",
        )

        assert result.exit_code == 0
        assert "mainframe is mildly impressed" not in result.output


def test_status_runs_fake_mainframe_connection_before_real_action(
    runner,
    monkeypatch,
):
    """Status should show the fake connection before its real vault check."""
    events = []

    monkeypatch.setattr(
        "blackbox.cli._MAINFRAME_DELAY_SECONDS",
        1.5,
    )

    monkeypatch.setattr(
        "blackbox.cli.time.sleep",
        lambda seconds: events.append(seconds),
    )

    with runner.isolated_filesystem():
        result = runner.invoke(main, ["status"])

        assert result.exit_code == 0
        assert events == [1.5]

        assert result.output.index(
            "Connecting to mainframe"
        ) < result.output.index(
            "hasn't been created yet"
        )

# --- Fake "connecting to mainframe" delay on status -----------------------

def test_status_shows_mainframe_flavor_text(runner):
    """status should print the fake "connecting to mainframe" line
    before its real, mundane output — pure theatrical flavor.
    """
    with runner.isolated_filesystem():
        result = runner.invoke(main, ["status"])
        assert "Connecting to mainframe" in result.output


def test_status_mainframe_delay_is_actually_configurable(runner, monkeypatch):
    """The delay duration should be a real, controllable value — not
    hardcoded inline where it couldn't be adjusted or tested. Confirmed
    by setting it to a distinctive nonzero value and timing the call.
    """
    import time

    monkeypatch.setattr(cli_module, "MAINFRAME_DELAY_SECONDS", 0.15)

    with runner.isolated_filesystem():
        start = time.monotonic()
        runner.invoke(main, ["status"])
        elapsed = time.monotonic() - start

        assert elapsed >= 0.15


def test_status_still_reports_correct_state_after_the_delay(runner):
    """The theatrical delay is purely cosmetic — it must never change
    or delay-corrupt the actual, real status determination that
    follows it.
    """
    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        result = runner.invoke(main, ["status"])
        assert "Unlocked" in result.output


# --- Rare joke on successful unlock ----------------------------------

def test_rare_joke_appears_when_random_forced_below_threshold(runner, monkeypatch):
    """Forcing random.random() to always return 0.0 (guaranteed below
    any positive probability threshold) should make the joke fire on
    every successful unlock — confirms the branch is genuinely
    reachable and wired correctly. Patches random.random() directly,
    the same deterministic technique used in test_easter_eggs.py and
    test_ui.py, rather than relying on RARE_JOKE_PROBABILITY alone.
    """
    monkeypatch.setattr(random, "random", lambda: 0.0)

    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        (Path("The Void") / "f.txt").write_text("x")
        runner.invoke(main, ["lock", "--fast"], input="pass1\npass1\n")

        result = runner.invoke(main, ["unlock", "--fast"], input="pass1\n")

        assert any(
            _normalised(joke) in _normalised(result.output)
            for joke in cli_module.j
        )


def test_rare_joke_never_appears_when_random_forced_above_threshold(runner, monkeypatch):
    """Forcing random.random() to always return a value above the
    default RARE_JOKE_PROBABILITY (0.05) should mean the joke never
    fires — confirms the "rare" branch doesn't leak into every normal
    unlock by mistake.
    """
    monkeypatch.setattr(random, "random", lambda: 0.99)

    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        (Path("The Void") / "f.txt").write_text("x")
        runner.invoke(main, ["lock", "--fast"], input="pass2\npass2\n")

        result = runner.invoke(main, ["unlock", "--fast"], input="pass2\n")

        assert not any(
            _normalized(joke) in _normalized(result.output)
            for joke in cli_module.RARE_UNLOCK_JOKES
        )


def test_rare_joke_never_appears_on_a_failed_unlock(runner, monkeypatch):
    """The joke celebrates a *successful* unlock specifically — it
    must never appear after a wrong password, even with random.random()
    forced to always return 0.0, since the success path (where the
    joke lives) never executes on failure.
    """
    monkeypatch.setattr(random, "random", lambda: 0.0)

    with runner.isolated_filesystem():
        runner.invoke(main, ["init"])
        (Path("The Void") / "f.txt").write_text("x")
        runner.invoke(main, ["lock", "--fast"], input="pass3\npass3\n")

        result = runner.invoke(main, ["unlock", "--fast"], input="wrongpassword\n")

        assert not any(
            _normalized(joke) in _normalized(result.output)
            for joke in cli_module.RARE_UNLOCK_JOKES
        )