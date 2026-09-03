"""
blackbox.cli - the blackbox command-line interface.

Ties together everything built so far: config.init_void() for first-run setup, vault.lock()/unlock()
for the actual encryption, ui.matrix_rain_during() for the loading animation, and 
easter_eggs.print_access_attempt_flavor() for the trivia/fake-message flair. Every cinnabd's output
is styled through a single shared rich Console instance.

Concealment ordering (resolved cross-platform question):

    LOCK: vault.lock() -> disguise_vault() -> hide_path()
    UNLOCK: locate on disk -> unhide_path() -> undisguise_vault() -> vault.unlock()

Locating the file on unlock is the tricky part, since hiding behaves differently per OS: on macOS/Linux, 
hide_path() renames the disguised file to a dotfile; on Windows, it sets attributes in place without 
renaming at all. So the disguised file could currently exist on disk under EITHER its plain disguised 
name OR its dotfile-prefixed name, depending on which OS locked it. _locate_locked_vault() checks both
candidate paths and uses whichever actually exists.

vault.unlock() is deliberately called on the disguised name, not the plain original name — it reads the 
real folder name from the encrypted header, not from the filename, so there's no need to expose the recognizable 
plain name during an attempt at all. This also means vault.py's own failed-attempt cooldown sidecar (step 10) 
inherits the boring disguised name rather than leaking the vault's real identity.
 
A wrong password must never strip a vault's concealment. If vault.unlock() fails after the file has 
already been revealed and undisguised, it gets re-disguised and re-hidden before the error is
reported — a failed attempt should never leave a vault sitting around in plain, visible form.
"""

from __future__ import annotations

import random
import sys
import time
from pathlib import Path

import click
from rich.console import Console

from blackbox.config import (
    DEFAULT_VAULT_NAME,
    _load_disguise_registry,
    disguise_vault,
    forget_disguise_entry,
    init_void,
)

from blackbox.easter_eggs import print_access_attempt_flavor
from blackbox.hide import HideError, hide_path, unhide_path
from blackbox.ui import matrix_rain_during
from blackbox.vault import VaultError
from blackbox.vault import ATTEMPTS_SIDECAR_SUFFIX
from blackbox.vault import lock as vault_lock
from blackbox.vault import unlock as vault_unlock

console = Console()

# purely cosmetic easter-egg timing.This deliberately has no relationship to the vault's
# actual security or cryptographic operations.
_MAINFRAME_DELAY_SECONDS = 1.5 + random.random() * 2.0

def _fake_mainframe_connection() -> None:
    """
    A purely cosmetic easter-egg: Preteneds to connect to a mainframe before a mundane CLI action.
    """
    console.print("[dim]Connecting to mainframe...[/dim]")
    time.sleep(_MAINFRAME_DELAY_SECONDS)
    console.print(" [green]Connected.[/green]")
    console.print("[dim]Mainframe reports: everything is surprisingly and astonishingly normal.[/dim]")

def _print_unlock_joke() -> None:
    """
    A purely cosmetic easter-egg: prints the rare-successful-unlock joke easter-egg.
    This is deliberately not called automatically, but for only a fraction of the time.
    """
    jokes = [
        "The vault opens, and inside is... a single, lonely sock. It seems to be waiting for its mate or the other unsannary activities you do with it.",
        "You unlock the vault, and a tiny voice whispers: 'I knew you'd come back.'",
        "Inside the vault, you find a note that says: 'Congratulations! You've unlocked the secrets of the universe. Just kidding, it's just a vault.'",
        "The vault creaks open, revealing... a perfectly organized collection of rubber ducks. Quack! Quack! Quack!",
        "As you unlock the vault, a holographic cat appears and says: 'Meow. You may proceed young padwan.'",
        "Vault unlocked. Unfortunately, the treasure appears to be three screenshots of a meme you saved in 2019.",
        "The Void has been opened. Please remain calm. The Void is also unsure what to do next.",
        "Scanning encrypted contents... 47 files found. 46 are important. One is named 'final_FINAL_really_final.txt'. Good Luck figuring out which one is which.",
        "The vault requests a sacrifice. We offered it a USB cable. It accepted said phenomenon.",
        "Authentication successful. You are officially more trustworthy than the average house cat.",
        "The encryption is flawless. Your folder organization, however, is a completely different international security incident.",
        "Opening The Void... please wait. The Void is putting on its shoes. Seems like The Void owns no shoes. The Void is a mysterious entity.",
        "You have successfully entered the forbidden vault. Please remember to close the door. We are not paying for another haunted filesystem, especially in this economy",
        "The Void contains many secrets. Most of them appear to be images you forgot you took.",
        "Vault unlocked. The security system has determined that you are, in fact, you. Impressive work. Very impressive work.",
        "A mysterious signal has been detected inside the vault. It appears to be coming from a file called 'DO_NOT_DELETE.txt'.Please acknowledge that you have read this message by sending a carrier pigeon to the nearest post office.",
        "The vault is open. Somewhere, a security engineer just felt a disturbance in the logs.",
        "Congratulations. You defeated the password prompt. Your reward is... access to your own files. Like what did you expect was going to happen?",
        "The Void is pleased with your credentials. It has requested snacks as compensation.",
        "Decrypting contents... please do not stare directly at the terminal. The terminal gets nervous and quite shy.",

    ]

    console.print("[dim]As the vault opens, a mysterious message appears...[/dim]")
    console.print(
        "[bold magenta]ACCESS GRANTED![/bold magenta] "
        "The mainframe is mildly impressed. "
    )
    console.print(f"[dim]{random.choice(jokes)}[/dim]")

def _locate_locked_vault(original_vault_name: str, base_path: Path) -> Path | None:
    """
    Find a locked (disguised + hidden) vault's actual current path on disk, 
    without modifying anything.

    Checks the disguise registry for the original vault filename's disguised 
    name, then checks both possible on-disk forms that name could currently 
    have — plain (Windows, or not-yet-hidden) or dotfile-prefixed (macOS/Linux, 
    once hidden) — since we don't know which OS locked this vault or whether 
    hiding fully succeeded.
 
    Falls back to checking for the plain original filename directly, for vaults 
    that were sealed without disguise/hide ever being applied (e.g. an older vault, 
    or if hiding failed during lock).
 
    Returns:
        The vault's actual current path, or None if no locked vault is found under 
        this name at all. 
    """

    registry = _load_disguise_registry(base_path)
    disguised_name = registry.get(original_vault_name)

    if disguised_name is not None:
        plain_disguised = base_path / disguised_name
        dotted_disguised = base_path / f".{disguised_name}"
        if plain_disguised.exists():
            return plain_disguised
        if dotted_disguised.exists():
            return dotted_disguised

    # Fall back: no registry entry, or the registry pointed nowhere real. Check for
    # a plain, undisguised, unhidden vault file.

    plain_original = base_path / original_vault_name
    if plain_original.exists():
        return plain_original

    return None

def _conceal(vault_path: Path, base_path: Path) -> None:
    """
    Disguise and hide a sealed vault file. Best-effort on the hide step: 
    if OS-level hiding fails (e.g. permissions), the vault stays disguised
    but visible rather than failing the whole operation - the disguise alone
    still provides some deterrent value.
    """

    disguised_path = disguise_vault(vault_path, base_path=base_path)
    try:
        hide_path(disguised_path)
    except HideError as exc:
        console.print(
            f"[bold yellow]Warning:[/bold yellow] vault sealed and "
            f"disguised, but hiding failed: {exc}"
        )

@click.group(invoke_without_command=True)
@click.version_option(package_name="blackbox-vault")
@click.option(
    "--konami",
    is_flag=True,
    hidden=True,
    is_eager=True,
    help="Trigger the hidden Blackbox easter egg."
)
def main(konami: bool) -> None:
    """Blackbox - Hide it.Lock it. Dare them to find it."""

    if konami:
        console.print("[bold magenta] KONAMI PROTOCOL ACCEPTED![/bold magenta]")
        console.print("[dim]↑ ↑ ↓ ↓ ← → ← → B A[/dim] ")
        console.print("[bold green]BLACKBOX CHEAT CODE: +30 hacker points.[/bold green]")

@main.command()
@click.option(
    "--name",
    default=DEFAULT_VAULT_NAME,
    show_default=True,
    help="Name to use for the vault folder."
)
def init(name: str) -> None:
    """
    Create The Void, if it doesn't already exist
    """
    result = init_void(name=name)

    if result is None:
        console.print(
            f"[bold yellow]'{name}' is currently locked.[/bold yellow] "
            f"Run [bold]blackbox unlock \"{name}\"[/bold] to access it."
        )
        return
    console.print(f"[bold green]Ready:[/bold green] {result}")

@main.command()
@click.option(
    "--name",
    default=DEFAULT_VAULT_NAME,
    show_default=True,
    help="Name of the vault to check.",
)
def status(name: str) -> None:
    """
    Show whether a vault is currently locked or unlocked.
    """
    base_path = Path(".").resolve()
    void_path = base_path / name

    _fake_mainframe_connection()
    original_vault_name = f"{name}.vault"

    locked_path = _locate_locked_vault(original_vault_name, base_path)

    if locked_path is not None:
        # Delibearately do NOT reveal the disguised filename here - printing
        # it would defeat the entire point of disguising it.
        console.print(f"[bold yellow]Locked.[/bold yellow] (hidden and disguised)")
    elif void_path.exists():
        console.print(f"[bold green]Unlocked.[/bold green] '{void_path}' exists.")
    else:
        console.print(
            f"[dim]'{name}' hasn't been created yet. Run "
            f"[bold]blackbox init[/bold] to get started.[/dim]"
        )

@main.command()
@click.argument("folder", default=DEFAULT_VAULT_NAME, required=False)
@click.option("--fast", is_flag=True, help="Skip the Matrix-rain animation.")
def lock(folder: str, fast: bool) -> None:
    """
    Encrypt FOLDER into a sealed .vault file. Defaults to "The Void".
    """
    folder_path = Path(folder)

    if not folder_path.exists():
        console.print(f"[bold red]Error:[/bold red] '{folder}' does not exist.")
        sys.exit(1)
    if not folder_path.is_dir():
        console.print(f"[bold red]Error:[/bold red] '{folder}' is not a folder.")
        sys.exit(1)

    password = click.prompt(
        "Password", hide_input=True, confirmation_prompt=True
    )

    print_access_attempt_flavor(console)

    try:
        with matrix_rain_during(fast=fast, console=console):
            vault_path = vault_lock(folder_path, password)
            _conceal(vault_path, base_path=vault_path.parent)
    except VaultError as exc:
        console.print(f"[bold red]Lock failed:[/bold red] {exc}")
        sys.exit(1)

    console.print(
        f"[bold green]Sealed:[/bold green] The vault is now encrypted, "
        "disguised, and hidden."
    )

@main.command()
@click.argument("folder", default=DEFAULT_VAULT_NAME, required=False)
@click.option("--fast", is_flag=True, help="Skip the Matrix-rain animation.")
def unlock(folder: str, fast: bool) -> None:
    """
    Decrypt FOLDER.vault back into FOLDER. Defaults to "The Void".

    Deliberately calls vault.unlock() directly on the still-disguised
    filename, rather than undisguising to the plain original name
    first. vault.unlock() reads the real original folder name from
    the encrypted header, not from the vault file's own name — so
    there's no need to expose the recognizable plain name at all
    during an attempt. This matters concretely: if the password is
    wrong, vault.unlock()'s own failed-attempt cooldown sidecar
    (blackbox.vault step 10) gets created next to whatever filename it
    was called with. Calling it on the disguised name means even that
    sidecar file stays boring-looking, rather than leaking the vault's
    real identity via a file like "The Void.vault.attempts.json"
    sitting in plain sight after a failed guess.
    """
    base_path = Path(".").resolve()
    original_vault_name = f"{folder}.vault"

    located = _locate_locked_vault(original_vault_name, base_path)

    if located is None:

        console.print(f"[bold red]Error:[/bold red]no locked vault found for '{folder}'.")
        sys.exit(1)

    password = click.prompt("Password", hide_input=True)

    print_access_attempt_flavor(console)

    revealed_path: Path | None = None

    try:
        with matrix_rain_during(fast=fast, console=console):
            revealed_path = unhide_path(located)
            # Call unlock directly on the still-dsiguised name - see 
            # docstring above for why this ordering matters.
            restored_folder = vault_unlock(revealed_path, password)
    except VaultError as exc:
        # Wrong password or corruption. vault.unlock() has NOT deleted 
        # the file in this case (it only deletes on success), so the 
        # disguised file is still sitting there; its disguised name never
        # changed) so a failed attempt never leaves it exposed.

        if revealed_path is not None and revealed_path.exists():
            try:
                hide_path(revealed_path)
            except Exception:
                pass # best-effort; dont mask the real failure below

            # vault.unlock() also writes a failed-attempt cooldown
            # sidecar next to whatever filename it was called with -
            # in this case, the still-boring disguised name, so it doesn't
            # leak the vault's real identity. It's still plainly visible on its
            # own, though, so hide it too for full concealment consistency.

            sidecar_path = revealed_path.parent / f"{revealed_path.name}{ATTEMPTS_SIDECAR_SUFFIX}"

            if sidecar_path.exists():
                try:
                    hide_path(sidecar_path)
                except Exception:
                    pass

        console.print(f"[bold red]Unlock failed:[/bold red] {exc}")
        sys.exit(1)
    except HideError as exc:
        console.print(f"[bold red]Unlock failed:[/bold red] could not reveal vault: {exc}")
        sys.exit(1)

    # Success: vault.unlock() already deleted the disguised file itself, so there's
    # nothing left to rename - just clean up the now-stale registry entry.
    forget_disguise_entry(original_vault_name, base_path=base_path)

    console.print(f"[bold green]Restored:[/bold green] {restored_folder}")

    # A deliberately rare, harmless joke on successful unlock.
    if random.random() < 0.05:
        _print_unlock_joke()

    

if __name__ == "__main__":
    main()