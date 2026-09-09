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
from blackbox.hide import hide_path, HideError

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



def _is_vault_locked(name: str, base_path: Path) -> bool:
    """
    Determine whether a vault under this name is currently locked - checking not just the plain vault filename,
    but the disguise registry too, since a locked vault is very likely hidden and disguised under a completely
    different, boring-looking name.

    Without this check, init_void() could not detect an already-locked vault once disguising was introduced, 
    silently creating a second, orphaned vault instead of correctly regusing to touch anything - exactly the 
    bug this function exists to prevent.
    """
    original_vault_name = f"{name}.vault"

    # Legacy / fallback: a plain, undisguised vault file.
    if (base_path / original_vault_name).exists():
        return True

    # The much more common real case: disguised, possibly hidden.
    registry = _load_disguise_registry(base_path)
    disguised_name = registry.get(original_vault_name)
    if disguised_name is not None:
        if (base_path / disguised_name).exists():
            return True
        if (base_path / f".{disguised_name}").exists():
            return True

    return False

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
    # vault_file_path = base_path / f"{name}.vault"

    # if vault_file_path.exists():
    #     # Locked. Do NOT create an empty folder over it - that would silently orphan the sealed vault
    #     # confuse the user about which one is "real"
    #     return None

    if _is_vault_locked(name, base_path):
        return None

    if void_path.exists():
        return void_path

    void_path.mkdir(parents=True)

    readme_path = void_path / "README.txt"
    readme_path.write_text(_WELCOME_MESSAGE.format(folder_name=name), encoding="utf-8")

    return void_path

# --- Disguise naming ----------

# Renaming the sealed .vault file to something boring and system-looking is pure deterrent, exactly
# like blackbox.hide - it doesn't add any actual security, it just means a casual glance at a directory
# listing sees "ntuser.dat.tmp" instead of "The Void.vault" and moves on.

DISGUISE_CONFIG_FILENAME = ".blackbox_disguise.json"

# Shipped as a sensible, boring-looking default. Users can override or extend this list by editing the
# JSON config file - see _load_disguise_config() below.

DEFAULT_DISGUISE_NAMES = [
    "ntuser.dat.tmp",
    "swapfile.sys",
    "systemd-private-cache.db",
    "Trash-1000-cache",
    "com.apple.diagnostics.plist",
    "-$cachefile.tmp",
    "DS_Store.bak",
]

def _disguise_config_path(base_path: str | Path = ".") -> Path:
    """
    Return the path to the disguise-name JSON config file.

    Lives alongside The Void itself (same base_path as init_void), so a user can drop their own list of
    preferred boring names right next to their vault without needing to hunt for a config file buried
    somewhere in a system-wude config directory.
    """
    return Path(base_path).resolve() / DISGUISE_CONFIG_FILENAME

def _load_disguise_config(base_path: str | Path = ".") -> list[str]:
    """
    Load the list of candidate disguise names from the JSON config file, falling back to DEFAULT_DISGUISE_NAMES
    if the file is missing, empty or malformed.

    Failing open here (returning defaults rather than raising) is the right call - this is a cosmetic deterrent
    feature, not a security boundary, so a corrupted config file should never block a user from locking their 
    vault.
    """
    config_path = _disguise_config_path(base_path)
    if not config_path.exists():
        return DEFAULT_DISGUISE_NAMES

    try: 
        data = json.loads(config_path.read_text(encoding="utf-8"))
        names = data.get("disguise_names")
        if isinstance(names, list) and all(isinstance(n, str) for n in names) and names:
            return names
        return DEFAULT_DISGUISE_NAMES
    except (json.JSONDecodeError, OSError, ValueError):
        return DEFAULT_DISGUISE_NAMES


def get_disguise_name(base_path: str | Path = ".") -> str:
    """
    Return a randomly chosen disguise filename from the configured(or default) candidate list.

    A random pick, rather than always the first entry, means two vaults on the same machine
    are less likely to share an identical disguised name - a small but free improvement to the
    deterrent
    """

    candidates = _load_disguise_config(base_path)
    return random.choice(candidates)

# ---- Disguise Registry -----
# Disguising a vault is only useful if blackbox can find it again later - a random rename with no memory of 
# what happened would strand the vault under an unpredictable name forever. This registry is what makes
# disguise_vault() reversible, mirroring how blackbox.hide keeps hide_path() as a matched pair.

DISGUISE_REGISTRY_FILENAME = ".blackbox_disguise_registry.json"

def _disguise_registry_path(base_path: str | Path = ".") -> Path:
    """
    Return the path to the disguise registry file.
    """
    return Path(base_path).resolve() / DISGUISE_REGISTRY_FILENAME

def _load_disguise_registry(base_path: str | Path = ".") -> dict[str, str]:
    """
    Load the original_name -> disguised_name mapping. Missing or corrupted registries are treated as empty
    - this is a convenience lookup, not the source of truth for the vault's actual consent, so failing open
    here is correct
    """
    registry_path = _disguise_registry_path(base_path)
    if not registry_path.exists():
        return {}
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
        return {}
    except (json.JSONDecodeError, OSError, ValueError):
        return {}

def _save_disguise_registry(base_path: str | Path, registry: dict[str, str]) -> None:
    """
    Persist the original_name -> disguised_name mapping, and ensure the registry file itself is hidden via the
    OS-appropriate mechanism - not just relying on its filename's leading dot, which is cosmetic on its own and
    doesn't set the real hidden attribute on Windows.
    """

    registry_path = _disguise_registry_path(base_path)
    registry_path.write_text(json.dumps(registry), encoding="utf-8")

    try:
        hide_path(registry_path)
    except HideError:
        pass # best-effort; the registry still works, just less concealed


def disguise_vault(vault_path: str | Path, base_path: str | Path = ".") -> Path:
    """
    Rename a sealed .vault file to a boring, system-looking name.

    This is cosmetic/deterrent only, exactly like blackbox.hide - it does not add encryption or access control. 
    The actual protection is AES-256-GCM (blackbox.vault); this just means a vault file doesn't announce itself
    as "The Void.vault" in a directory listing.

    Args:
        vault_path: the sealed .vault file to rename.
        base_path: where to look for a disguise-name config file.
            Defaults to the current directory.

    Returns:
        The new,disguised path.

    Raises:
        FileNotFoundError: if vault_path doesn't exist.
    """

    vault_path = Path(vault_path).resolve()
    if not vault_path.exists():
        raise FileNotFoundError(f"'{vault_path}' does not exist.")

    original_name = vault_path.name
    candidates = _load_disguise_config(base_path)
    existing_disguised_names = set(_load_disguise_registry(base_path).values())

    # Prefer a name not already in use by another disguised vault it this same directory, to avoid two vaults
    # colliding under one filename. Falls back to any candidate if every one is somehow already taken 
    # (exceedingly unlikely with the default list size.)

    available = [c for c in candidates if c not in existing_disguised_names]
    disguised_name = random.choice(available) if available else random.choice(candidates)
    disguised_path = vault_path.parent / disguised_name

    os.rename(vault_path, disguised_path)

    registry = _load_disguise_registry(base_path)
    registry[original_name] = disguised_name
    _save_disguise_registry(base_path, registry)

    return disguised_path

def forget_disguise_entry(original_name: str, base_path: str | Path = ".") -> None:
    """
    Remove a disguise registry entry without touching the filesystem.

    Used after vault.unlock() has already deleted the disguised file itself (its default behavior on success ) - at
    that point there's nothing left to rename, only a now-stale registry mapping to clean up so it doesn't linger 
    and confuse a future lookup. 
    """
    registry = _load_disguise_registry(base_path)
    if original_name in registry:
        del registry[original_name]
        _save_disguise_registry(base_path, registry)

def undisguise_vault(original_name: str, base_path: str | Path = ".") -> Path:
    """
    Reverse of disguise_vault(): look up a vault's disguised name in the registry, rename it back to its original, 
    and forget the mapping now that it's no longer needed.

    Args:
        original_name: the vault's original filename (e.g. "The Void.vault") - what it was called before disguising.
        base_path: where the registry file and disguised vault live.

    Returns:
        The restored, original path.

    Raises:
        FileNotFoundError: if there's no registry entry for originial_name, or the disguised file it points to is 
            missing (e.g. it was manually renamed or deleted outside of blackbox).
    """

    base_path = Path(base_path).resolve()
    registry = _load_disguise_registry(base_path)

    disguised_name = registry.get(original_name)
    if disguised_name is None:
        raise FileNotFoundError(
            f"No disguise record found for '{original_name}'"
        )

    disguised_path = base_path / disguised_name
    if not disguised_path.exists():
        raise FileNotFoundError(
            f"Registry points to '{disguised_path}', but it doesn't exist."
        )

    original_path = base_path / original_name 
    os.rename(disguised_path, original_path)

    del registry[original_name]
    _save_disguise_registry(base_path, registry)

    return original_path