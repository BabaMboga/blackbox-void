"""
blackbox_void.crypto - password-to-key derivation.

This module answers exactly one question: "given a password and a salt, what
256-bit encryption key do we get?" It knows nothing aobut folders, files or the 
CLI - just password -> key. That seperation makes it easy to test in isolation
and easy to audit ( this is the file a security-minded contributor would want to read first ).

Algorithm choice: Aron2id
    Argon2id won the Password Hashinng Competition ( 2015 ) and is the current OWASP-recommended
    choice for password-based key derivation. It's deliberately slow and memory-hungry, which is
    exactly what you want to here - it makes brute-forcing the password computationally expensive
    even if an attacker gets hold of the salt. 

Did you know: Argon2 is named after the noble gas argon — inert,
colorless, and famously hard to react with. Fitting, for something whose
entire job is to resist being cracked open.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from argon2.low_level import Type, hash_secret_raw

# --- Turnable KDF parameters ---
# These control the time/memory cost of deriving a key, Higher = slower.
# to brute-force, but also slower for the legitimate user on every unlock.
# Values below follow OWASP's current baseline recommendation for
# Argon2id used inreractively ( not for high-throughput server auth ).

SALT_SIZE = 16 # bytes - 128 bits, standard for Argon2
KEY_SIZE = 32 # bytes - 256 bits, required by AES-256
TIME_COST = 3 #number of iterations
MEMORY_COST = 65536 # KiB (= 64 MB) of RAM required per attempt
PARALLELISM = 4 # number of parallel threads/lanes

@dataclass(frozen=True)
class KeyMaterial:
    """
    The output of a key derivation: the key itself plus the salt
    that produced it. The salt is not secret - it exists purely to make
    every derived key unique, even if two vaults share the same password.
    """

    key: bytes
    salt: bytes

def generate_salt() -> bytes:
    """
    Generate a new, cryptographically random salt for a vault.

    Each vault gets its own salt, generated once at creation time and
    stored (unencrypted - that's fine, salts aren't secret) alongside
    the vault's metadata. Reusing a saltacross vaults would let an 
    attacker rpecompute a single rainbow table that works against all
    of them; a fresh salt per vault kills that shortcut entirely.
    """

    return os.urandom(SALT_SIZE)

def derive_key(password: str, salt: bytes) -> bytes:
    """
    Derive a 256-bit encryption key from a password and salt.
    
    This is deliberately slow (that's the point!).On typical consumer
    hardware, expect derivation to take somewhere in the range of a
    hundred milliseconds - barely noriceablefor a human typing a 
    password once, but expensive to repeat billions of times as an 
    attacker trying to brute-force it.

    Args:
        password: the user's plaintext password to derive the
        salted key from. (never stored, ever).
        salt: the per-vault salt from generate_salt() (or loaded
        from the vault's stored metadata when unlocking). Must be exactly SALT_SIZE bytes.

    Returns:
        A 32-byte (256-bit) encryption key suitable for use with AES-256-GCM or similar.
    """

    if not password:
        raise ValueError("Password must not be empty. Even a bad password beats none.")
    if len(salt) != SALT_SIZE:
        raise ValueError(f"Salt must be exactly {SALT_SIZE} bytes long, got {len(salt)} instead.")

    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=TIME_COST,
        memory_cost=MEMORY_COST,
        parallelism=PARALLELISM,
        hash_len=KEY_SIZE,
        type=Type.ID,  # Argon2id - the hybrid variant, resistant to both GPU and side-channel attacks
    )

def new_key_material(password: str) -> KeyMaterial:
    """
    Generate a new salt and derive a key from the given password in one call.

    This is the function to call when creating a new vault. It generates
    a fresh salt, derives the key, and returns both in a KeyMaterial object.

    Use this when creating a brand-new vault. For unlocking an existing vault, use derive_key() with the stored salt instead.
    """

    salt = generate_salt()
    key = derive_key(password, salt)
    return KeyMaterial(key=key, salt=salt)

def rederive_key(password: str, stored_salt: bytes) -> bytes:
    """
    Re-derive the same key from a password and a previously stored salt.

    Use this when unlocking an existing vault - the salt comes from the 
    vault's metadata file, not freshly generated. The derived key will be
    identical to the one originally created with new_key_material() if 
    the password is correct.
    """

    return derive_key(password, stored_salt)