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
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from blackbox.crypto import (
    MEMORY_COST,
    PARALLELISM,
    TIME_COST,
    new_key_material
)

# --- Format Constants ----
VAULT_EXTENSION = ".vault"
NONCE_SIZE = 12
FORMAT_VERSION = 1
DEFAULT_SECURE_DELETE_PASSES = 3

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