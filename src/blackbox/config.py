"""
blackbox.config - shared defaults, first-run setup logic, and the disguise-naming system for sealed
vault files.

This is where "The Void" - blackbox's signature default vault folder - actually gets created. vault.py
itself says folder-name agnostic ( it can lock *any* folder); this module is what decides *which* folder
a brand-new user starts with, and later, what a sealed vault pretends to be called once it's locked.
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

# The default name used for a user's first vault folder. "The Void" is blackbox's signature vault name -
# the place things go to disappear

DEFAULT_VAULT_NAME = "The Void"

_WELCOME_MESSAGE = """\
You have entered The Void.

Nothing you put here is safe from prying eyes yet - that only happens once you run `blackbox lock`. Until then,
this is just a regular folder with a dramatic name

Drop in whatever you want to disappear. When you're ready, seal it:

    blackbox lock "{folder_name}"

Did you know: the concept of a mathematical "void" (the empty set) was formalised by Ernst Zermelo in 1908 - 
meaning the idea of "nothing" is,  itself, younger than the light bulb.
"""

def init_void(base_path: str | Path = ".", name: str = DEFAULT_VAULT_NAME) -> Path | None:
    """
    Create The Void folder on first run - but only if it has never existed before, in either state.

    The Void has exactly two states and this function must never clobber either one:
        - Unlocked: "<name>/" exists as a plain folder.
        - Locked: "<name>.vault" exists as a sealed file.

    Calling this on every program startup is always safe:
        - Neither exists yet -> a fresh, empty Void is created.
        - The folder already exists (unlocked) -> left untouched, its path is returned.
        - Only the .vault file exist (locked) -> nothing is created; this function returns None so the
        caller knows to prompt for a password to unlock, rather than assuming a fresh empty Void is ready
        to use.

    Args:
        base_path: where The Void should live. Defaults to the current working directory.
        name: the folder name to use. Defaults to "The Void" but is configurable in case a user wants a 
            less on-the-nose name.

    Returns:
        The path to The Void folder if it exists (or was just created), or None if The Void currently 
        exists only in its locked (.vault) form. 
    """

    base_path = Path(base_path).resolve()
    void_path = base_path / name
    vault_file_path = base_path / f"{name}.vault"

    if vault_file_path.exists():
        # Locked. Do NOT create an empty folder over it - that would silently orphan the sealed vault
        # confuse the user about which one is "real"
        return None

    if void_path.exists():
        return void_path

    void_path.mkdir(parents=True)

    readme_path = void_path / "README.txt"
    readme_path.write_text(_WELCOME_MESSAGE.format(folder_name=name), encoding="utf-8")

    return void_path

