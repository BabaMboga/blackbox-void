"""
Tests for blackbox.config - The Void's first-run setup (init_void) and the disguise-naming system
for sealed vault files
"""

import json
import shutil

import pytest
from blackbox.config import (
    DEFAULT_DISGUISE_NAMES,
    DEFAULT_VAULT_NAME,
    disguise_vault,
    get_disguise_name,
    init_void,
    undisguise_vault,
    _load_disguise_config,
    _load_disguise_registry,
)

# ----init_void(): the three-state lifecycle

def test_init_void_creates_fresh_void_when_nothing_exists(tmp_path):
    """
    With neither a folder nor a locked .vault file oresent, calling init_void() for the first time
    should create a brand-new- empty Void folder
    """
    result = init_void(base_path=tmp_path)
    assert result is not None
    assert result.exists()
    assert result.name == DEFAULT_VAULT_NAME

def test_init_void_creates_readme_inside_fresh_void(tmp_path):
    """
    A first-run Void should come with a welcome README explaining what the folderis for - a brand-new
    user shouldn't be dropped into an unexplained empty folder.
    """

    result = init_void(base_path=tmp_path)
    readme = result / "README.txt"
    assert readme.exists()
    assert "Void" in readme.read_text()

def test_init_void_does_not_recreate_unlocked_folder(tmp_path):
    """
    If The Void already exists (unlocked state) with user content inside it, calling init_void() again
    must leave it completely untouched - this is the critical guarantee that makes it safe to call on 
    every program startup without risking data loss.
    """
    first =init_void(base_path=tmp_path)
    (first / "my_secret.txt").write_text("do not delete me")

    second = init_void(base_path=tmp_path)

    assert second == first
    assert (second / "my_secret.txt").read_text() == "do not delete me"

def test_init_void_returns_none_when_locked(tmp_path):
    """
    If only a sealed .vault file exists (locked state), init_void() must
    NOT create a fresh empty folder over it - doing so would orphan the 
    sealed vault and confuse the user about which one is "real." Returning 
    None signals to the caller that The Void is currently locked, rather 
    than ready to use. 
    """

    void_path = init_void(base_path=tmp_path)
    # Simulate locking: remove the folder ( and its README ) entirely leaving
    # only a .vault file - rmdir() alonw qould fail here since init_void()
    # populates the folder with a README on creation,
    shutil.rmtree(void_path)
    vault_file = tmp_path / f"{DEFAULT_VAULT_NAME}.vault"
    vault_file.write_text("pretend encrypted content")

    result = init_void(base_path=tmp_path)

    assert result is None
    assert not (tmp_path / DEFAULT_VAULT_NAME).exists() # no phantom empty folder
    assert vault_file.exists() # the real locked vault is untouched

def test_init_void_respects_custom_name(tmp_path):
    """
    init_void() should support a custom vault folder name, not just the default "
    The Void" - useful for a user who wants a less on-the-nose name.
    """

    result = init_void(base_path=tmp_path, name="MyStuff")
    assert result.name == "MyStuff"

# --- get_disguise_name() _load_disguise_config() ----

def test_get_disguise_name_returns_a_default_when_no_config_exists(tmp_path):
    """
    With no user-provided config file, get_disguise_name() should fall 
    back to the shipped DEFAULT_DISGUISE_NAMES list.
    """
    name = get_disguise_name(base_path=tmp_path)
    assert name in DEFAULT_DISGUISE_NAMES

def test_load_disguise_config_returns_defaults_when_file_missing(tmp_path):
    """
    No config file present at all should silently fall back to defaults, not raise.
    """
    names = _load_disguise_config(base_path=tmp_path)
    assert names == DEFAULT_DISGUISE_NAMES

def test_load_disguise_config_retunrs_defaults_on_malformed_json(tmp_path):
    """
    A corrupted config file must fail open (return defaults), not rash — this is a 
    cosmetic deterrent feature, not a security boundary, so it should never be able
    to block a user from locking their vault just because a config file got 
    corrupted.
    """

    config_path = tmp_path / ".blackbox_disguise.json"
    config_path.write_text("{ this is not valid json}")

    names = _load_disguise_config(base_path=tmp_path)
    assert names == DEFAULT_DISGUISE_NAMES

def test_load_disguise_config_return_defaults_on_empty_list(tmp_path):
    """
    A config file with an explicitly empty disguise_names list should still fall back
    to defaults, rather than leaving get_disguise_name() with nothing to choose from.
    """

    config_path = tmp_path / ".blackbox_disguise.json"
    config_path.write_text(json.dumps({"disguise_names": []}))

    names = _load_disguise_config(base_path=tmp_path)
    assert names == DEFAULT_DISGUISE_NAMES

def test_load_disguise_config_uses_custom_names_when_valid(tmp_path):
    """
    A well-formed custom config file should override the shipped defaults entirely.
    """

    config_path = tmp_path / ".blackbox_disguise.json"
    custom_names = ["totally_not_a_vault.dat", "just_a_log_file.log"]
    config_path.write_text(json.dumps({"disguise_names": custom_names}))

    names = _load_disguise_config(base_path=tmp_path)
    assert names == custom_names


def test_get_disguise_name_uses_custom_config(tmp_path):
    """
    get_disguise_name() should actually pick from the custom list when one is 
    configured, not silently ignore it.
    """

    config_path = tmp_path/ ".blackbox_disguise.json"
    config_path.write_text(json.dumps({"disguise_names": ["only_option.tmp"]}))

    name = get_disguise_name(base_path=tmp_path)
    assert name == "only_option.tmp"

# --- disguise_value(): renaming and registry bookkeeping ----

def test_disguise_vault_renames_the_file(tmp_path):
    """
    Disguising a vault should rename it away from its original, recognizable name.
    """

    vault_file = tmp_path / "The Void.vault"
    vault_file.write_text("encrypted bytes")

    disguise_path = disguise_vault(vault_file, base_path=tmp_path)

    assert disguise_path != vault_file
    assert disguise_path.exists()
    assert not vault_file.exists()

def test_disguise_vault_preserves_file_content(tmp_path):
    """
    Renaming must never alter the file's actual bytes — this is supposed to be a 
    purely cosmetic operation.
    """

    vault_file = tmp_path / "The Void.vault"
    vault_file.write_text("precious encrypted cargo")

    digsuised_path = disguise_vault(vault_file, base_path=tmp_path)

    assert digsuised_path.read_text() == "precious encrypted cargo"

def test_disguise_vault_uses_a_name_from_the_candidate_list(tmp_path):
    """
    The chosen disguise name should come from the actual candidate pool, not be 
    arbitrary.
    """

    vault_file = tmp_path / "The Void.vault"
    vault_file.write_text("shh")

    disguised_path = disguise_vault(vault_file, base_path=tmp_path)

    assert disguised_path.name in DEFAULT_DISGUISE_NAMES

def test_disguise_vault_raises_for_missing_vault(tmp_path):
    """
    Attempting to dsiguise a vault file that doesn't exist should fail clearly 
    rather than silently doing nothing or crashing with an unrelated OS error.
    """

    with pytest.raises(FileNotFoundError):
        disguise_vault(tmp_path / "does_not_exist.vault", base_path=tmp_path)


def test_disguise_vault_records_mapping_in_registry(tmp_path):
    """
    After disguising, the registry file should contain a record mapping the
    original name to the new disguised name - this is what makes the operation
    reversible later.
    """

    vault_file = tmp_path / "The Void.vault"
    vault_file.write_text("shh")

    disguised_path = disguise_vault(vault_file, base_path=tmp_path)

    registry = _load_disguise_registry(base_path=tmp_path)
    assert registry.get("The Void.vault") == disguised_path.name


def test_disguise_vault_avoids_reusing_a_name_already_in_the_registry(tmp_path):
    """
    If one vault has already claimed a disguise name, a second vault being 
    disguised in the same directory should not be given that same name - colliding
    filenames would silently overwrite one vault with another.
    """

    # Force a single-candidate config so we can prove collision avoidance falls back
    # correctly when the only "preferred" name is already taken.

    config_path = tmp_path / ".blackbox_disguise.json"
    config_path.write_text(json.dumps({"disguise_names": ["name_a.tmp", "name_b.tmp"]}))

    vault_one = tmp_path / "vault_one.vault"
    vault_one.write_text("first")
    vault_two = tmp_path / "vault_two.vault"
    vault_two.write_text("second")

    disguised_one = disguise_vault(vault_one, base_path=tmp_path)
    disguised_two = disguise_vault(vault_two, base_path=tmp_path)

    assert disguised_one.name != disguised_two.name

# --- undisguise_vault(): the reverse operation ----

def test_undisguise_vault_restores_original_name(tmp_path):
    """
    The core promise: undisguising shoulf rename the file back to exactly its orignal name.
    """

    vault_file = tmp_path / "The Void.vault"
    vault_file.write_text("shh")
    disguise_vault(vault_file, base_path=tmp_path)

    restored = undisguise_vault("The Void.vault", base_path=tmp_path)

    assert restored == vault_file
    assert restored.exists()


def test_undisguise_vault_preserves_file_content(tmp_path):
    """
    Content must survive the full disguise -> undisguise round trip untouched.
    """
    vault_file = tmp_path / "The Void.vault"
    vault_file.write_text("precious encrypted cargo")
    disguise_vault(vault_file, base_path=tmp_path)

    restored = undisguise_vault("The Void.vault", base_path=tmp_path)

    assert restored.read_text() == "precious encrypted cargo"

def test_undisguise_vault_removes_registry_entry_after_restoring(tmp_path):
    """
    Once a vault is restored to its original name, its registry entry should be 
    cleaned up - leaving a stale entry behind could cause a future lookup to point
    at a file that's no longer disguised.
    """

    vault_file = tmp_path / "The Void.vault"
    vault_file.write_text("shh")
    disguise_vault(vault_file, base_path=tmp_path)

    undisguise_vault("The Void.vault", base_path=tmp_path)

    registry = _load_disguise_registry(base_path=tmp_path)
    assert "The Void.vault" not in registry

def test_undisguise_vault_raises_for_unknown_original_name(tmp_path):
    """
    Attempting to undisguise a name with no registry entry at all shpuld fall clearly,
    rather than silently doing nothing.
    """

    with pytest.raises(FileNotFoundError):
        undisguise_vault("Never Disguised.vault", base_path=tmp_path)

def test_undisguise_vault_raises_if_disguised_file_was_remobed_externally(tmp_path):
    """
    If the registry has a record but the actual disguised file is gone (e.g. manually 
    deleted outside of blackbox), undisguising should fail clearly rather than crash 
    with an unrelated OS error or silently create a new empty file.
    """

    vault_file = tmp_path / "The Void.vault"
    vault_file.write_text("shh")
    disguised_path = disguise_vault(vault_file, base_path=tmp_path)

    # Simulate the disguised file being deleted by something outside black box.

    disguised_path.unlink()

    with pytest.raises(FileNotFoundError):
        undisguise_vault("The Void.vault", base_path=tmp_path)

def test_disguise_then_undisguise_round_trip(tmp_path):
    """
    The full lifecycle, mirroring the equivalent round-trip test in test_hide.py: disguise
    a vault, then undisguise it, and confirm the result is indistinguishable from having 
    never touched it — same path, same content.
    """

    original = tmp_path / "The Void.vault"
    original.write_text("the actual secret data")

    disguised = disguise_vault(original, base_path=tmp_path)
    assert disguised != original  # confirm it actually got disguised

    restored = undisguise_vault("The Void.vault", base_path=tmp_path)

    assert restored == original
    assert restored.read_text() == "the actual secret data"

def test_init_void_detects_locked_vault_even_when_disguised(tmp_path):
    """
    This is the core regression test: init_void()must recognise a vault as locked even when it's
    currently hidden and disguised under a completely different filename - not just when the plain
    "<name>.vault" file happens to exist.
    """
    vault_file = tmp_path / "The Void.vault"
    vault_file.write_text("pretend encrypted content")
    disguised_path = disguise_vault(vault_file, base_path=tmp_path)

    result = init_void(base_path=tmp_path)

    assert result is None
    assert not (tmp_path / "The Void").exists()

def test_init_void_does_not_create_orphaned_second_vault(tmp_path):
    """
    The actual bug found in manual QA: locking, then having init_void() incorrectly create a fresh Void,
    then locking again, silently orphaned the first vault's contents. This conifmrs that can no longer 
    happen.
    """
    vault_file = tmp_path / "The Void.vault"
    vault_file.write_text("first vault's content")
    disguise_vault(vault_file, base_path=tmp_path)

    # Previously, this would have wrongly created a fresh empty Void.
    result = init_void(base_path=tmp_path)

    assert result is None
    # Confirm no plain "The Void" folder appeared alongside the still-locked (disguised/hidden) original.
    assert not (tmp_path / "The Void").exists()
