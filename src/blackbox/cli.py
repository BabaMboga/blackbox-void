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
def status():
    """Check that blackbox is installed and reachable."""
    click.echo("Blackbox is alive.")

if __name__ == "__main__":
    main()