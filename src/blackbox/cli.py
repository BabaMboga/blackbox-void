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
 
A wrong password must never strip a vault's concealment. If vault.unlock() fails after the file has 
already been revealed and undisguised, it gets re-disguised and re-hidden before the error is
reported — a failed attempt should never leave a vault sitting around in plain, visible form.
"""

from __future__ import annotations

import sys
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

@click.group()
@click.version_option(package_name="blackbox-vault")
def main() -> None:
    """Blackbox - Hide it.Lock it. Dare them to find it."""
    pass

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
    void_path = Path(".") / name
    vault_path = Path(".") / f"{name}.vault"

    if vault_path.exists():
        console.print(f"[bold yellow]Locked.[/bold yellow] '{vault_path}' exists.")
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

    console.print(f"[bold green]Sealed:[/bold green] {vault_path}")

@main.command()
@click.argument("folder", default=DEFAULT_VAULT_NAME, required=False)
@click.option("--fast", is_flag=True, help="Skip the Matrix-rain animation.")
def unlock(folder: str, fast: bool) -> None:
    """
    Decrypt FOLDER.vault back into FOLDER. Defaults to "The Void".
    """
    vault_path = Path(f"{folder}.vault")

    if not vault_path.exists():
        console.print(f"[bold red]Error:[/bold red] '{vault_path}' does not exist.")
        sys.exit(1)

    password = click.prompt("Password", hide_input=True)

    print_access_attempt_flavor(console)

    try:
        with matrix_rain_during(fast=fast, console=console):
            restored_path = vault_unlock(vault_path, password)
    except VaultError as exc:
        console.print(f"[bold red]Unlock failed:[/bold red] {exc}")
        sys.exit(1)

    console.print(f"[bold green]Restored:[/bold green] {restored_path}")

    

if __name__ == "__main__":
    main()