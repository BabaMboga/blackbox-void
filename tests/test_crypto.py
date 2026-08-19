""" Test for blackbox.crypto module - password-to-key derivation. """

import pytest
from blackbox.crypto import (
    KEY_SIZE,
    SALT_SIZE,
    derive_key,
    new_key_material,
    rederive_key,
    generate_salt,
    KeyMaterial,
)

def test_generate_salt_is_correct_size():
    salt = generate_salt()
    assert isinstance(salt, bytes)
    assert len(salt) == SALT_SIZE

def test_generate_salt_is_random():
    salt1 = generate_salt()
    salt2 = generate_salt()
    assert salt1 != salt2  # Very low probability of collision  

def test_derive_key_returns_correct_length():
    salt = generate_salt()
    key = derive_key("correct horse battery staple", salt)
    assert isinstance(key, bytes)
    assert len(key) == KEY_SIZE

def test_same_password_and_salt_produce_same_key():
    password = "correct horse battery staple"
    salt = generate_salt()
    key1 = derive_key(password, salt)
    key2 = derive_key(password, salt)
    assert key1 == key2

def test_same_password_different_salt_produce_different_keys():
    salt1 = generate_salt()
    salt2 = generate_salt()
    key1 = derive_key("hunter2", salt1)
    key2 = derive_key("hunter2", salt2)
    assert key1 != key2

def test_different_password_same_salt_produce_different_keys():
    salt = generate_salt()
    key1 = derive_key("hunter2", salt)
    key2 = derive_key("hunter3", salt)
    assert key1 != key2

def test_empty_password_raises_value_error():
    salt = generate_salt()
    with pytest.raises(ValueError):
        derive_key("", salt)

def test_wrong_salt_size_raises_value_error():
    with pytest.raises(ValueError):
        derive_key("hunter2", b"too-short")

def test_new_key_material_returns_key_and_salt():
    material = new_key_material("hunter2")
    assert isinstance(material, KeyMaterial)
    assert len(material.key) == KEY_SIZE
    assert len(material.salt) == SALT_SIZE

    # Simulate unlocking later: same password  stored salt -> same key
    rederived_key = rederive_key("hunter2", material.salt)
    assert rederived_key == material.key