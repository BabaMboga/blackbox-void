"""
blackbox.vault - pack, encrypt and seal a folder named The Void into a .vault file.

This module is where "a folder or disk" becomes "an encrypted blob of data". It knows 
nothing about passwords or keys - it just takes a key and a folder and produces a .vault
file. That separation makes it easy to test in isolation and easy to audit ( this is the
file a security-minded contributor would want to read second ).

It builds on blackbox.crypto (password -> key) but adds everything crypto.py deliberately
knows nothing about: archiving, file formats, touching the filesystem, and so on. It also
adds a few extra security measures that are not strictly necessary for correctness, but make
it harder for an attacker to get useful information from a .vault file if they do manage to
get hold of one.

Sealed .vault file format (all integers big-endian):

    [4 bytes] header_length (N)
    [N bytes] JSON header (metadata - NOT secret, see below)
    [remainder] ciphertext (AES-256-GCM; includes the 16-byte auth tag
                appended automatically by the `cryptography` library)

The JSON header contains the salt, the nonce, the KDF cost parameters, 
and the original folder name. None of this is secret - a salt and nonce 
only need to be unique, not hidden and the KDF  parameters must be known
to unlock the vault later. The actual folder contents live only inside
the ciphertext.

Did you know: GCM stands for "Galois/Counter Mode" - named after Evariste 
Galois, a mathematician who did some of his most important work the night
before a fatal duel at age 20. Somewhere in there is a metaphor about
encrypting things under pressure
"""

from __future__ import annotations

import base64
import io
import json
import os
import struct
import tarfile
import time
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from blackbox.crypto import (
    MEMORY_COST,
    PARALLELISM,
    TIME_COST,
    new_key_material,
    rederive_key
)

# --- Format Constants ----
VAULT_EXTENSION = ".vault"
NONCE_SIZE = 12 # bytes - the standard/recommended size for GCM
FORMAT_VERSION = 1
DEFAULT_SECURE_DELETE_PASSES = 3

# --- Failed-attempt cooldown constants ---
# Cosmetic friction only - this NEVER locks anyone out permanently, deletes
# anything, orblocks a correct password. it just makes rapid-fire guessing
# progressively more annoying, the same way a bouncer walks slower to the 
# door on the third time you've forgotten the password to the speakeasy.

ATTEMPTS_SIDECAR_SUFFIX = ".attempts.json"
BASE_COOLDOWN_SECONDS = 1.0
MAX_COOLDOWN_SECONDS = 30.0

class VaultError(Exception):
    """
    Raised for any vault-specific failure (bad folder, write failure,
    etc.) so callers can catch blackbox errors distinctly from generic 
    OS/crypto exceptions.
    """

# --- Archiving -----

def _archive_folder(folder_path: Path) -> bytes:
    """
    Pack a folder into an in-memory tar archive and return its raw bytes.

    Using an in-memory BytesIO buffer (rather than writing a temp .tar
    file to disk first) means the unencrypted archive never touches
    the filesystem at all — it exists only in RAM for the brief moment
    between packing and encrypting.
    """
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as tar:
        tar.add(folder_path,arcname=folder_path.name)
    return buffer.getvalue()

# --- Secure deletion ----

def _secure_delete_file(path: Path, passes: int = DEFAULT_SECURE_DELETE_PASSES) -> None:
    """
    Best-effort secure deletion of a single file: overwrite its contents with
    random bytes several times before unlinking it.

    IMPORTANT CAVEATS (read before assuming this is bulletproof):

    - On SSDs, wear-leveling means the physical cells you overwrite are often
    NOT the same cells the drive originally wrote your data to. The drive's 
    controller silently remaps writes, so "overwriting" a file logically does
    not guarantee the original data is physically destroyed.
    - Filesystem journaling (common on modern Linux/macOS/Windows filesystems) 
    can retain copies of file data or metadata in the journal, outside the file's
    own overwritten bytes.
    - OS-level caching may delay or coalesce writes, meaning your overwrite passes
    might not all reach physical storage in order.

    In short: this raises the bar against casual undelete/recovery tools, but is NOT 
    a guarantee against a determined attacker with forensic tools and physical access
    to the drive. Document this limitation for users rather than promising something
    we can't deliver.
    """

    if not path.is_file():
        return

    file_size = path.stat().st_size
    with open(path, "r+b") as f:
        for _ in range(passes):
            f.seek(0)
            f.write(os.urandom(file_size))
            f.flush()
            os.fsync(f.fileno())

    path.unlink()

def _secure_delete_folder(folder_path: Path, passes: int = DEFAULT_SECURE_DELETE_PASSES) -> None:
    """
    Recursively secure-delete every file in a folder, then remove the now-empty directory
    tree. See _secure_delete_file for caveats.
    """

    for root, dirs, files in os.walk(folder_path, topdown=False):
        root_path = Path(root)
        for filename in files:
            _secure_delete_file(root_path / filename, passes=passes)
        for dirname in dirs:
            (root_path / dirname).rmdir()
    folder_path.rmdir()

# --- Sealed file writing ----

def _write_sealed_vault(
        output_path: Path,
        salt: bytes,
        nonce: bytes,
        ciphertext: bytes,
        original_name: str,
) -> None:
    """
    Write the header + ciphertext to a single sealed .vault file.
    """
    header = {
        "format_version": FORMAT_VERSION,
        "salt": base64.b64encode(salt).decode("ascii"),
        "nonce": base64.b64encode(nonce).decode("ascii"),
        "kdf": {
            "algorithm" : "argon2id",
            "time_cost" : TIME_COST,
            "memory_cost" : MEMORY_COST,
            "parallelism" : PARALLELISM,
        },
        "original_name" : original_name,

    }
    header_bytes = json.dumps(header).encode("utf-8")

    with open(output_path, "wb") as f:
        f.write(struct.pack(">I", len(header_bytes)))
        f.write(header_bytes)
        f.write(ciphertext)


# --- Public API ----

def lock(
        folder_path: str | Path,
        password: str,
        output_path: str | Path | None = None,
        secure_delete: bool = True,
        passes: int = DEFAULT_SECURE_DELETE_PASSES,
) -> Path:
    """
    Encrypt a folder into a sealed .vault file and remove the original.

    Args:
        folder_path: the folder to lock.
        password: the password toprotect it with (never stored).
        output_path: where to write the .vault file. Defaults to placing 
            it alongside the original folder, named "<folder_name>.vault"
        secure_delete: if True (default), best-effort overwrite and remove
            the original folder after a successful encryption. If False,
            the original folder is left untouched - useful for testing, o
            for users who want to verify the vault before trusting it with
            the only copy of their data.
        passes: number of overwrite passes during secure deletion.

    Returns:
        The path to the newly created .vault file.

    Raises:
        VaultError: if folder_path doesn't exist or ins't a directory
    

    """

    folder_path = Path(folder_path).resolve()

    if not folder_path.exists():
        raise VaultError(f"'{folder_path}' does not exist.")
    if not folder_path.is_dir():
        raise VaultError(f"'{folder_path}' is not a folder.")

    if output_path is None:
        output_path = folder_path.parent / f"{folder_path.name}{VAULT_EXTENSION}"
    else:
        output_path = Path(output_path)

    # 1. Pack the folder into an in-memory tar archive.
    archive_bytes = _archive_folder(folder_path)

    # 2. Derive a fresh key + salt from the password
    key_material = new_key_material(password)

    # 3. Encrypt the archive with AES-256-GCM.
    nonce = os.urandom(NONCE_SIZE)
    aesgcm = AESGCM(key_material.key)
    ciphertext = aesgcm.encrypt(nonce, archive_bytes, associated_data=None)

    # 4. Write the sealed .vault file (header + ciphertext).
    _write_sealed_vault(
        output_path=output_path,
        salt=key_material.salt,
        nonce=nonce,
        ciphertext=ciphertext,
        original_name=folder_path.name,
    )

    # 5 Remove the original - only after the vault write succeeded
    if secure_delete:
        _secure_delete_folder(folder_path, passes=passes)

    return output_path

def _read_sealed_vault(vault_path: Path) -> tuple[dict,bytes]:
    """
    Read a sealed .vault file and split it into its header dict and raw 
    ciphertext bytes.
    """

    with open(vault_path, "rb") as f:
        header_len = struct.unpack(">I", f.read(4))[0]
        header = json.loads(f.read(header_len))
        ciphertext = f.read()
    return header, ciphertext

# ---Failed-attempt cooldown ---
def _attempt_sidecar_path(vault_path: Path) -> Path:
    """
    Return the path to a vault's failed-attempt sidecar file.

    Deliberately a *seperate* file from the .vault file itself - a corrupted
    or missing sidecar should never be able to affect the actual encrypted
    data and vice versa.
    """

    return vault_path.parent / f"{vault_path.name}{ATTEMPTS_SIDECAR_SUFFIX}"

def _load_failed_attenpts(vault_path: Path) -> int:
    """
    Read the current failed-attempt count for a vault. Missing or unreadable
    sidecar files are treated as zero attempts - this is a friction mechanism,
    nota security boundary, so failing open here (rather than raising) is the right call.
    """
    sidecar = _attempt_sidecar_path(vault_path)
    if not sidecar.exists():
        return 0
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        return int(data.get("failed_attempts", 0))
    except (json.JSONDecodeError, ValueError, OSError):
        return 0

def _save_failed_attempts(vault_path: Path, count: int) -> None:
    """Persist the failed-attempt count for a vault."""
    sidecar = _attempt_sidecar_path(vault_path)
    sidecar.write_text(json.dumps({"failed_attempts": count}), encoding="utf-8")

def _reset_failed_attempts(vault_path: Path) -> None:
    """Clear the failed-attempt count after a successful unlock."""
    sidecar = _attempt_sidecar_path(vault_path)
    if sidecar.exists():
        sidecar.unlink()

def _cooldown_seconds(failed_attempts: int) -> float:
    """
    Compute the cooldown delay for a given number of prior failures.

    Doubles with each failure (1s, 2s, 4s, 8s, ...), capped at 
    MAX_COOLDOWN_SECONDS so a forgetful legitimate user is never stuck
    waiting an unreasonable amount of time - this is meant to be annoying,
    not punishing.
    """

    if failed_attempts <= 0:
        return 0.0
    delay = BASE_COOLDOWN_SECONDS * (2 ** (failed_attempts - 1))
    return min(delay, MAX_COOLDOWN_SECONDS)

def unlock(
        vault_path: str | Path,
        password: str,
        output_dir: str | Path | None = None,
        delete_vault_file: bool = True,
) -> Path:
    """
    Decrypt a sealed .vault file back into its original folder.
 
    This is the reverse of lock(): a .vault file and a correct password
    go in, the restored folder comes out. A wrong password fails loudly
    (InvalidTag, via GCM's built-in authentication) rather than
    producing corrupted output — there is no such thing as a "partial"
    or "garbled" unlock with this scheme.
 
    Args:
        vault_path: path to the .vault file to unlock.
        password: the password used when the vault was locked.
        output_dir: where to restore the folder. Defaults to the same
            directory the .vault file lives in.
        delete_vault_file: if True (default), remove the .vault file
            after a successful restore — enforces the rule that a
            given vault is either "a folder" or "a .vault file," never
            both at once. Set False to keep the sealed file as a backup.
 
    Returns:
        The path to the restored folder.
 
    Raises:
        VaultError: if vault_path doesn't exist, if the restored folder
            would overwrite an existing one, or if the password is wrong / 
            the vault file is corrupted or tampered with. 
    """

    vault_path = Path(vault_path).resolve()

    if not vault_path.exists():
        raise VaultError(f"'{vault_path}' does not exist.")

    header, ciphertext = _read_sealed_vault(vault_path)

    salt = base64.b64decode(header["salt"])
    nonce = base64.b64decode(header["nonce"])
    original_name = header["original_name"]

    # If there have been prior failed attempts on this vault, make the
    # user wait before we even try this one. Cosmetic friction only —
    # this never blocks a correct password forever, never deletes
    # anything, and the wait is capped so it stays annoying rather
    # than genuinely punishing.

    failed_attempts = _load_failed_attenpts(vault_path)
    cooldown = _cooldown_seconds(failed_attempts)
    if cooldown > 0:
        time.sleep(cooldown)

    key = rederive_key(password, salt)

    # AESGCM's auth tag self-verifies on decrypt: any wrong password OR
    # any tampering/corruption of the ciphertext raises InvalidTag. We
    # can't distinguish "wrong password" from "corrupted file" from the
    # exception alone — both look identical from the outside, which is
    # itself a deliberate security property (it doesn't leak *why* the
    # attempt failed). We catch it here and surface one clear, honest
    # message instead of a raw crypto traceback.

    aesgcm = AESGCM(key)
    try:
        archive_bytes = aesgcm.decrypt(nonce, ciphertext, associated_data=None)

    except InvalidTag as exc:
        raise VaultError(
            "Could not unlock - wrong password or this .vault file is corrupted/tampered "
            "with. Nice try, though."
        ) from exc

    if output_dir is None:
        output_dir = vault_path.parent
    else:
        output_dir = Path(output_dir)

    restored_path = output_dir / original_name
    if restored_path.exists():
        raise VaultError(
            f"'{restored_path}' already exists - refusing to overwrite it."
        )

    buffer = io.BytesIO(archive_bytes)
    with tarfile.open(fileobj=buffer, mode="r") as tar:
        tar.extractall(path=output_dir, filter="data")

    if delete_vault_file:
        vault_path.unlink()

    return restored_path