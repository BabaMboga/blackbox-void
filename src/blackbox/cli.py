"""
blackbox.cli - the blackbox command-line interface.

Ties together everything built so far: config.init_void() for first-run setup, vault.lock()/unlock()
for the actual encryption, ui.matrix_rain_during() for the loading animation, and 
easter_eggs.print_access_attempt_flavor() for the trivia/fake-message flair. Every cinnabd's output
is styled through a single shared rich Console instance.

Not yet wired in: blackbox.hide (OS-level hiding) and the disguise naming system 
(config.disguise_vault/undisguise_vault). Those involve real cross-platform ordering questions 
(hide-then-disguise vs. disguise-then-hide behave differently depending on OS) that deserve their own 
focused integration pass rather than being bolted on here.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from rich.console import Console

from blackbox.config import DEFAULT_VAULT_NAME, init_void
from blackbox.easter_eggs import print_access_attempt_flavor
from blackbox.ui import matrix_rain_during
from blackbox.vault import VaultError
from blackbox.vault import lock as vault_lock
from blackbox.vault import unlock as vault_unlock

console = Console()

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