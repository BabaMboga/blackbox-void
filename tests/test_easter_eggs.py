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
    GLYPH_TABLE,
    get_random_system_message,
    get_random_trivia,
    print_access_attempt_flavor,
    print_random_system_message,
    print_random_trivia,
    print_glyph_text,
    to_glyphs,
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
    console = Console(record=True, width=400)
    print_random_trivia(console)
    output = console.export_text()

    assert output.strip() != ""


def test_print_random_trivia_output_matches_a_known_fact():
    """The printed text should contain one of the real trivia facts
    verbatim, proving the print function isn't printing something
    unrelated to the content pool.
    """
    console = Console(record=True, width=400)
    print_random_trivia(console)
    output = console.export_text()

    assert any(fact in output for fact in TRIVIA_FACTS)


def test_print_random_trivia_does_not_leak_markup_tags():
    """rich markup like [dim italic] should be rendered as styling,
    not appear as literal bracket text in the output — this would
    indicate a malformed markup string.
    """
    console = Console(record=True, width=400)
    print_random_trivia(console)
    output = console.export_text()

    assert "[dim" not in output
    assert "[/dim" not in output


def test_print_random_system_message_writes_to_given_console():
    """Same output-reaches-console guarantee for the fake system
    message print function.
    """
    console = Console(record=True, width=400)
    print_random_system_message(console)
    output = console.export_text()

    assert output.strip() != ""


def test_print_random_system_message_output_matches_a_known_message():
    """The printed text should contain one of the real fake messages
    verbatim.
    """
    console = Console(record=True, width=400)
    print_random_system_message(console)
    output = console.export_text()

    assert any(msg in output for msg in FAKE_SYSTEM_MESSAGES)


def test_print_random_system_message_does_not_leak_markup_tags():
    """Same markup-doesn't-leak guarantee for the fake message print
    function.
    """
    console = Console(record=True, width=400)
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
    console = Console(record=True, width=400)
    print_access_attempt_flavor(console)
    output = console.export_text()

    assert output.strip() != ""


def test_print_access_attempt_flavor_can_produce_trivia(monkeypatch):
    """Forcing the random coin flip to always favor trivia should
    result in trivia-shaped output — confirms the trivia branch is
    actually reachable, not dead code.
    """
    monkeypatch.setattr(random, "random", lambda: 0.0)  # always < 0.5
    console = Console(record=True, width=400)
    print_access_attempt_flavor(console)
    output = console.export_text()

    assert any(fact in output for fact in TRIVIA_FACTS)


def test_print_access_attempt_flavor_can_produce_system_message(monkeypatch):
    """Forcing the random coin flip to always favor the fake system
    message should result in that branch's output — confirms it's
    reachable too, not just the trivia path.
    """
    monkeypatch.setattr(random, "random", lambda: 0.99)  # always >= 0.5
    console = Console(record=True, width=400)
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
        console = Console(record=True, width=400)
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


# --- GLYPH_TABLE: content integrity ---------------------------------------

def test_glyph_table_covers_all_lowercase_letters():
    """Every lowercase Latin letter must have a rune mapping — a gap
    here would mean some letters silently pass through untransformed
    in to_glyphs(), breaking the illusion for whatever word happened
    to contain that letter.
    """
    assert all(char in GLYPH_TABLE for char in "abcdefghijklmnopqrstuvwxyz")


def test_glyph_table_covers_all_uppercase_letters():
    """Same full-coverage guarantee for uppercase letters."""
    assert all(char in GLYPH_TABLE for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ")


def test_glyph_table_maps_upper_and_lower_to_the_same_glyph():
    """Runes have no case distinction, so the same letter in either
    case should transliterate to an identical glyph — two different
    glyphs for 'a' and 'A' would look like an inconsistency rather
    than an intentional stylistic choice.
    """
    for lower_char in "abcdefghijklmnopqrstuvwxyz":
        upper_char = lower_char.upper()
        assert GLYPH_TABLE[lower_char] == GLYPH_TABLE[upper_char]


def test_glyph_table_values_are_all_non_empty_strings():
    """Every mapped glyph should be real, renderable content — not an
    empty string, which would silently delete letters during
    transliteration instead of replacing them.
    """
    assert all(isinstance(v, str) and len(v) > 0 for v in GLYPH_TABLE.values())


# --- to_glyphs(): transliteration behavior --------------------------------

def test_to_glyphs_transforms_known_letters():
    """A string made entirely of mapped letters should come out
    entirely transformed — no original Latin characters left behind.
    """
    result = to_glyphs("abc")
    assert result == GLYPH_TABLE["a"] + GLYPH_TABLE["b"] + GLYPH_TABLE["c"]


def test_to_glyphs_preserves_length():
    """The transliteration is a strict one-for-one character swap —
    the output must always be exactly as long as the input, with
    nothing merged, dropped, or expanded.
    """
    sample = "Hello, World! 123"
    assert len(to_glyphs(sample)) == len(sample)


def test_to_glyphs_preserves_digits_punctuation_and_spaces():
    """Characters with no rune equivalent (digits, punctuation,
    whitespace) should pass through completely unchanged, since
    forcing a substitution for them wouldn't have any sensible
    "alien" equivalent and would just look broken.
    """
    sample = "1, 2, 3 - go!"
    result = to_glyphs(sample)
    assert result.count("1") == sample.count("1")
    assert result.count(",") == sample.count(",")
    assert result.count(" ") == sample.count(" ")
    assert result.count("!") == sample.count("!")


def test_to_glyphs_handles_empty_string():
    """An empty input should produce an empty output, not raise."""
    assert to_glyphs("") == ""


def test_to_glyphs_is_case_consistent_with_glyph_table():
    """Transliterating the same word in both cases should produce
    identical glyph output, mirroring the case-insensitivity already
    verified directly on GLYPH_TABLE itself.
    """
    assert to_glyphs("void") == to_glyphs("VOID")


def test_to_glyphs_output_contains_no_original_latin_letters():
    """A sanity check on the illusion itself: transliterating a
    letters-only string should leave zero recognizable Latin
    characters in the output — if even one slipped through untouched,
    the "alien transmission" effect would be broken.
    """
    result = to_glyphs("blackbox")
    assert not any(char in result for char in "blackbox")


# --- print_glyph_text(): rendering -----------------------------------------

def test_print_glyph_text_writes_to_given_console():
    """Passing an explicit Console should result in that console
    actually receiving the rendered glyph output.
    """
    console = Console(record=True, width=200)
    print_glyph_text("The Void", console)
    output = console.export_text()

    assert output.strip() != ""


def test_print_glyph_text_output_matches_transliteration():
    """The printed text should contain the exact glyph transliteration
    of the input, proving the print function doesn't alter or
    re-transform the already-converted text.
    """
    console = Console(record=True, width=200)
    print_glyph_text("void", console)
    output = console.export_text()

    assert to_glyphs("void") in output


def test_print_glyph_text_does_not_leak_markup_tags():
    """rich markup like [bold magenta] should be rendered as styling,
    not appear as literal bracket text in the output.
    """
    console = Console(record=True, width=200)
    print_glyph_text("test", console)
    output = console.export_text()

    assert "[bold" not in output
    assert "[/bold" not in output


def test_print_glyph_text_creates_its_own_console_when_none_given():
    """Callers shouldn't be required to pass a Console — omitting it
    should just work without raising.
    """
    print_glyph_text("The Void")  # should not raise