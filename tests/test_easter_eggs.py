"""
Tests for blackbox.easter_eggs — trivia facts and fake ominous system
messages, printed on each vault access attempt.

Output tests use rich's Console(record=True) capture feature rather
than mocking print/stdout — this verifies the actual rendered text
that would reach a real terminal, including that our markup tags
(e.g. [dim italic]) don't leak into the visible output as literal text.
"""

import random

import pytest
from rich.console import Console

from blackbox.easter_eggs import (
    FAKE_SYSTEM_MESSAGES,
    TRIVIA_FACTS,
    get_random_system_message,
    get_random_trivia,
    print_access_attempt_flavor,
    print_random_system_message,
    print_random_trivia,
)


# --- Content pools themselves --------------------------------------------

def test_trivia_facts_pool_is_non_empty():
    """There must be actual content to choose from — an empty list
    would make every other test in this file meaningless.
    """
    assert len(TRIVIA_FACTS) > 0


def test_fake_system_messages_pool_is_non_empty():
    """Same guarantee for the fake system messages pool."""
    assert len(FAKE_SYSTEM_MESSAGES) > 0


def test_trivia_facts_are_all_strings():
    """Every entry should be a real string, not accidentally a tuple,
    None, or some other type that would break formatting downstream.
    """
    assert all(isinstance(fact, str) for fact in TRIVIA_FACTS)


def test_fake_system_messages_are_all_strings():
    """Same type guarantee for the fake system messages pool."""
    assert all(isinstance(msg, str) for msg in FAKE_SYSTEM_MESSAGES)


def test_trivia_facts_have_no_duplicate_entries():
    """Duplicate facts would silently shrink the effective variety
    without it being obvious from len() alone.
    """
    assert len(TRIVIA_FACTS) == len(set(TRIVIA_FACTS))


def test_fake_system_messages_have_no_duplicate_entries():
    """Same duplicate-detection guarantee for the fake messages pool."""
    assert len(FAKE_SYSTEM_MESSAGES) == len(set(FAKE_SYSTEM_MESSAGES))


# --- get_random_trivia() / get_random_system_message() -------------------

def test_get_random_trivia_returns_a_known_fact():
    """The returned value must actually come from the real pool, not
    some unrelated or empty string.
    """
    result = get_random_trivia()
    assert result in TRIVIA_FACTS


def test_get_random_system_message_returns_a_known_message():
    """Same membership guarantee for the fake system message pool."""
    result = get_random_system_message()
    assert result in FAKE_SYSTEM_MESSAGES


def test_get_random_trivia_can_reach_every_entry():
    """Over enough draws, every fact in the pool should eventually be
    selected — this catches a broken or biased random selection (e.g.
    accidentally always returning TRIVIA_FACTS[0]) that a single call
    could never reveal.
    """
    seen = {get_random_trivia() for _ in range(500)}
    assert seen == set(TRIVIA_FACTS)


def test_get_random_system_message_can_reach_every_entry():
    """Same reachability guarantee for the fake system message pool."""
    seen = {get_random_system_message() for _ in range(500)}
    assert seen == set(FAKE_SYSTEM_MESSAGES)


# --- print_random_trivia() / print_random_system_message() ---------------

def test_print_random_trivia_writes_to_given_console():
    """Passing an explicit Console should result in that console
    actually receiving output — not silently going elsewhere.
    """
    console = Console(record=True, width=200)
    print_random_trivia(console)
    output = console.export_text()

    assert output.strip() != ""


def test_print_random_trivia_output_matches_a_known_fact():
    """The printed text should contain one of the real trivia facts
    verbatim, proving the print function isn't printing something
    unrelated to the content pool.
    """
    console = Console(record=True, width=200)
    print_random_trivia(console)
    output = console.export_text()

    assert any(fact in output for fact in TRIVIA_FACTS)


def test_print_random_trivia_does_not_leak_markup_tags():
    """rich markup like [dim italic] should be rendered as styling,
    not appear as literal bracket text in the output — this would
    indicate a malformed markup string.
    """
    console = Console(record=True, width=200)
    print_random_trivia(console)
    output = console.export_text()

    assert "[dim" not in output
    assert "[/dim" not in output


def test_print_random_system_message_writes_to_given_console():
    """Same output-reaches-console guarantee for the fake system
    message print function.
    """
    console = Console(record=True, width=200)
    print_random_system_message(console)
    output = console.export_text()

    assert output.strip() != ""


def test_print_random_system_message_output_matches_a_known_message():
    """The printed text should contain one of the real fake messages
    verbatim.
    """
    console = Console(record=True, width=200)
    print_random_system_message(console)
    output = console.export_text()

    assert any(msg in output for msg in FAKE_SYSTEM_MESSAGES)


def test_print_random_system_message_does_not_leak_markup_tags():
    """Same markup-doesn't-leak guarantee for the fake message print
    function.
    """
    console = Console(record=True, width=200)
    print_random_system_message(console)
    output = console.export_text()

    assert "[bold" not in output
    assert "[/bold" not in output


def test_print_functions_create_their_own_console_when_none_given():
    """Callers shouldn't be required to pass a Console — omitting it
    should just work, printing to a freshly created default console
    rather than raising.
    """
    # This should not raise. We can't easily capture stdout output
    # here without extra plumbing, so this test simply confirms the
    # no-argument code path is safe to call.
    print_random_trivia()
    print_random_system_message()


# --- print_access_attempt_flavor() ----------------------------------------

def test_print_access_attempt_flavor_writes_something(monkeypatch):
    """Calling the combined flavor function should always produce
    some output, regardless of which pool it happens to draw from.
    """
    console = Console(record=True, width=200)
    print_access_attempt_flavor(console)
    output = console.export_text()

    assert output.strip() != ""


def test_print_access_attempt_flavor_can_produce_trivia(monkeypatch):
    """Forcing the random coin flip to always favor trivia should
    result in trivia-shaped output — confirms the trivia branch is
    actually reachable, not dead code.
    """
    monkeypatch.setattr(random, "random", lambda: 0.0)  # always < 0.5
    console = Console(record=True, width=200)
    print_access_attempt_flavor(console)
    output = console.export_text()

    assert any(fact in output for fact in TRIVIA_FACTS)


def test_print_access_attempt_flavor_can_produce_system_message(monkeypatch):
    """Forcing the random coin flip to always favor the fake system
    message should result in that branch's output — confirms it's
    reachable too, not just the trivia path.
    """
    monkeypatch.setattr(random, "random", lambda: 0.99)  # always >= 0.5
    console = Console(record=True, width=200)
    print_access_attempt_flavor(console)
    output = console.export_text()

    assert any(msg in output for msg in FAKE_SYSTEM_MESSAGES)


def test_print_access_attempt_flavor_roughly_balanced_over_many_calls():
    """Over a large number of calls with real randomness (not forced),
    both trivia and system messages should appear — a badly broken
    50/50 split (e.g. accidentally always 0% or 100% one branch) would
    fail this, while normal random variance will not.
    """
    saw_trivia = False
    saw_system_message = False

    for _ in range(100):
        console = Console(record=True, width=200)
        print_access_attempt_flavor(console)
        output = console.export_text()

        if any(fact in output for fact in TRIVIA_FACTS):
            saw_trivia = True
        if any(msg in output for msg in FAKE_SYSTEM_MESSAGES):
            saw_system_message = True

        if saw_trivia and saw_system_message:
            break

    assert saw_trivia
    assert saw_system_message