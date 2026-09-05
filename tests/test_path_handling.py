"""
Tests for path handling in blackbox.vault's lock()/unlock() round trip - unicode names, spaces,
and platform-specific edge cases. Complements the encrypt/decrypt correctness already covered in
test_vault.py and the OS-specific hiding mechanics already covered in test_hide.py; this file 
focuses specifically on "does the round trip survive an unusual but legal folder name," which 
is a distinct concern from  "is the encryption correct"
"""

import platform

import pytest

from blackbox.vault import lock, unlock

# ---- Names with spaces ------

def test_folder_name_with_spaces_round_trips(tmp_path):
    """
    A folder name containing spaces (like the project's own default, "The Void") must survive
    a full lock/unlock cycle without the space causing any path-splitting or quoting issues.
    """
    folder = tmp_path / "My Secret Folder"
    folder.mkdir()
    (folder / "file.txt").write_text("spaces are fine")

    vault_path = lock(str(folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")

    assert (restored / "file.txt").read_text() == "spaces are fine"

def test_file_name_with_spaces_inside_folder_round_trips(tmp_path):
    """
    Spaces inside a file name (not just the folder name) must also survive archiving and 
    extraction correctly.
    """
    folder = tmp_path / "vault_test"
    folder.mkdir()
    (folder / "my important file.txt").write_text("content")

    vault_path = lock(str(folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")

    assert (restored / "my important file.txt").read_text() == "content"

# ---- Unicode names ------

def test_unicode_folder_name_round_trips(tmp_path):
    """
    Folder names using non-ASCII characters (accents, non-latin scripts, emoji) must 
    round-trip correctly - a real concern for international users, not an edge case
    to skip.
    """

    folder = tmp_path / "Café Secrets 日本語"
    folder.mkdir()
    (folder / "note.txt").write_text("unicode folder name")

    vault_path = lock(str(folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")
    
    assert restored.name == "Café Secrets 日本語"
    assert (restored / "my important file.txt").read_text() == "unicode folder name"

def test_unicode_file_content_and_name_round_trip(tmp_path):
    """
    Both the file name AND its content should support unicode, surviving the tar archive + 
    AES-GCM encryption + extraction pipeline without corruption.
    """

    folder = tmp_path / "vault_test"
    folder.mkdir()

    (folder / "日記.txt").write_text("親愛なる日記へ — blackbox は動作します", encoding="utf-8")

    vault_path = lock(str(folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")

    content = (restored / "日記.txt" ).read_text(encoding="utf-8")
    assert content == "親愛なる日記へ — blackbox は動作します"

def test_emoji_in_folder_name_round_trips(tmp_path):
    """
    Emoji are valid Unicode and increasingly common in real folder names - a full round trip 
    should handle them without issue.
    """
    folder = tmp_path / "Secrets 🔒📁"
    folder.mkdir()
    (folder / "file.txt").write_text("emoji folder test")

    vault_path = lock(str(folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")

    assert restored.name == "Secrets 🔒📁"

# ---- Nested structure -----

def test_deeply_nested_subfolders_round_trip(tmp_path):
    """
    A folder containing multiple levels of subfolders must be archived and restored with its full
    structure intact, not just its top-level files. 
    """

    folder = tmp_path / "vault_test"
    (folder/ "level1" / "level2"/ "level3").mkdir(parents=True)
    (folder/ "level1" / "level2" / "level3" / "deep.txt").write_text("found me")
    (folder/ "level1"/ "shallow.txt").write_text("shallow file")

    vault_path = lock(str(folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")

    assert (restored / "level1" / "shallow.txt").read_text() == "shallow file"
    assert (restored / "level1" / "level2" / "level3" / "deep.txt").read_text() == "found me"

def test_multiple_files_and_subfolders_all_preserved(tmp_path):
    """
    A more realistic folder with a mix of files at different levels should have every single item
    survive the round trip, not just a lucky subset.
    """
    folder = tmp_path / "vault_test"
    folder.mkdir()
    (folder / "root_file.txt").write_text("root")
    subdir = folder / "subdir"
    subdir.mkdir()
    (subdir / "nested_file.txt").write_text("nested")
    (subdir / "another_file.txt").write_text("also nested")

    vault_path = lock(str(folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")

    assert (restored / "root_file.txt").read_text() == "root"
    assert (restored / "subdir" / "nested_file.txt").read_text() == "nested"
    assert (restored / "subdir" / "another_file.txt").read_text() == "also nested"

def test_empty_subfolder_is_preserved(tmp_path):
    """
    An empty subfolder (no files inside it) should still exist after the round trip - tar archives
    can represent empty directpries, and blackbox shouldnt't silently drop them.
    """
    folder = tmp_path / "vault_test"
    folder.mkdir()
    (folder / "empty_subdir").mkdir()
    (folder / "file.txt").write_text("keep me company")

    vault_path = lock(str(folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")

    assert (restored / "empty_subdir").is_dir()

# --- Long-ish names ------

def test_long_folder_name_round_trips(tmp_path):
    """
    A long (but not absurd) folder name should round-trip without issue - real 
    users do sometimes use long, descriptive names.
    """

    long_name = "A" * 100 + "_very_long_folder_name_indeed"
    folder = tmp_path / long_name
    folder.mkdir()
    (folder / "file.txt").write_text("long name test")

    vault_path = lock(str(folder), password="hunter2")
    restored = unlock(str(vault_path), password="hunter2")

    assert restored.name == long_name

