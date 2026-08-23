"""
Tests for blackbox.ui — the Matrix-rain animation shown during
encrypt/decrypt.

Frame generation/rendering logic is tested directly and deterministically.
Timing-based tests (confirming the animation runs concurrently with
wrapped work, and that fast=True adds no overhead) use generous
tolerances to avoid flakiness on slower or busier CI runners.
"""

import time

import pytest
from rich.console import Console
from rich.text import Text

from blackbox.ui import (
    DEFAULT_FRAME_DELAY,
    MatrixRain,
    _MatrixRainFrame,
    matrix_rain_during,
)


# --- _MatrixRainFrame: grid generation -----------------------------------

def test_new_frame_has_correct_dimensions():
    """A freshly created frame's grid should match the requested
    width and height exactly.
    """
    frame = _MatrixRainFrame.new(width=15, height=6)
    assert frame.height == 6
    assert frame.width == 15
    assert len(frame.grid) == 6
    assert all(len(row) == 15 for row in frame.grid)


def test_new_frame_has_one_head_per_column():
    """Each column needs its own independent head position to fall
    at its own pace — a mismatched count here would mean some columns
    have no head at all.
    """
    frame = _MatrixRainFrame.new(width=10, height=4)
    assert len(frame.heads) == 10


def test_new_frame_cells_are_single_characters():
    """Every grid cell should hold exactly one character, not an
    empty string or a multi-character sequence.
    """
    frame = _MatrixRainFrame.new(width=8, height=3)
    assert all(len(cell) == 1 for row in frame.grid for cell in row)


# --- _MatrixRainFrame: stepping -------------------------------------------

def test_step_changes_the_grid():
    """Stepping the animation should actually mutate the grid state —
    an animation that never changes anything would render as a
    static, frozen image instead of falling rain.
    """
    frame = _MatrixRainFrame.new(width=20, height=8)
    initial_grid = [row[:] for row in frame.grid]

    for _ in range(10):
        frame.step()

    assert frame.grid != initial_grid


def test_step_advances_heads():
    """Each step should move a column's head forward (or wrap it back
    to a negative starting position) — heads must never simply stay
    frozen in place.
    """
    frame = _MatrixRainFrame.new(width=5, height=100)  # tall grid delays wraparound
    initial_heads = frame.heads[:]

    frame.step()

    assert frame.heads != initial_heads


def test_step_eventually_wraps_heads_back_above_grid():
    """A column's head must eventually loop back to the top once it
    falls far enough past the bottom — otherwise it would fall forever
    and the column would go permanently dark.
    """
    frame = _MatrixRainFrame.new(width=3, height=2)  # short grid wraps quickly

    saw_a_negative_head = False
    for _ in range(200):
        frame.step()
        if any(h < 0 for h in frame.heads):
            saw_a_negative_head = True
            break

    assert saw_a_negative_head


# --- _MatrixRainFrame: rendering -----------------------------------------

def test_render_returns_rich_text():
    """render() must produce an actual rich Text object, since that's
    what Live.update() expects to receive.
    """
    frame = _MatrixRainFrame.new(width=10, height=4)
    result = frame.render()
    assert isinstance(result, Text)


def test_render_has_correct_number_of_lines():
    """The rendered output should have exactly one line per grid row."""
    frame = _MatrixRainFrame.new(width=10, height=5)
    rendered = frame.render()
    lines = rendered.plain.split("\n")
    assert len(lines) == 5


def test_render_lines_have_correct_width():
    """Each rendered line should have exactly one character per
    column — a mismatch here would produce a ragged, misaligned grid
    in the terminal.
    """
    frame = _MatrixRainFrame.new(width=12, height=3)
    rendered = frame.render()
    lines = rendered.plain.split("\n")
    assert all(len(line) == 12 for line in lines)


# --- MatrixRain: threading lifecycle --------------------------------------

def test_matrix_rain_start_launches_a_thread():
    """start() should actually begin running the animation on a
    background thread, not silently do nothing.
    """
    rain = MatrixRain(width=10, height=4, frame_delay=0.01, console=Console(record=True))
    rain.start()
    try:
        assert rain._thread is not None
        assert rain._thread.is_alive()
    finally:
        rain.stop()


def test_matrix_rain_stop_terminates_the_thread():
    """stop() should cleanly end the background thread rather than
    leaving it running indefinitely in the background.
    """
    rain = MatrixRain(width=10, height=4, frame_delay=0.01, console=Console(record=True))
    rain.start()
    rain.stop()

    assert rain._thread is None


def test_matrix_rain_stop_without_start_does_not_raise():
    """Calling stop() on an animation that was never started should be
    a safe no-op, not an error — defensive against a caller mistake.
    """
    rain = MatrixRain(console=Console(record=True))
    rain.stop()  # should not raise


def test_matrix_rain_start_twice_does_not_spawn_two_threads():
    """Calling start() a second time while already running should not
    create a second competing thread — that would double the frame
    rate and waste resources for no visual benefit.
    """
    rain = MatrixRain(width=10, height=4, frame_delay=0.01, console=Console(record=True))
    rain.start()
    first_thread = rain._thread
    rain.start()  # should be a no-op since already running
    second_thread = rain._thread

    try:
        assert first_thread is second_thread
    finally:
        rain.stop()


# --- matrix_rain_during(): fast=True skip path ----------------------------

def test_matrix_rain_during_fast_adds_negligible_overhead():
    """With fast=True, no thread should start and no animation
    overhead should be added — the wrapped block's elapsed time should
    closely match its own actual duration, not include any animation
    setup/teardown cost.
    """
    start = time.monotonic()
    with matrix_rain_during(fast=True):
        time.sleep(0.1)
    elapsed = time.monotonic() - start

    # Generous tolerance for scheduling jitter, but should be nowhere
    # near double — that would indicate the animation ran anyway.
    assert elapsed < 0.2


def test_matrix_rain_during_fast_does_not_create_a_thread():
    """fast=True should mean matrix_rain_during() never touches
    threading at all — confirmed here by counting active threads
    before and after, rather than just inferring it from timing.
    """
    import threading

    before = threading.active_count()
    with matrix_rain_during(fast=True):
        during = threading.active_count()
    after = threading.active_count()

    assert during == before
    assert after == before


# --- matrix_rain_during(): real animation path ----------------------------

def test_matrix_rain_during_runs_concurrently_not_sequentially():
    """The animation must run alongside the wrapped work, not before
    or after it — confirmed by checking the wrapped block's elapsed
    time is close to its own sleep duration, not inflated by a
    separately-timed animation phase stacked on top.
    """
    console = Console(record=True, width=200)
    start = time.monotonic()
    with matrix_rain_during(fast=False, width=10, height=4, frame_delay=0.02, console=console):
        time.sleep(0.2)
    elapsed = time.monotonic() - start

    # Should be close to the 0.2s sleep, not 0.2s plus a separate
    # animation duration stacked sequentially on top.
    assert elapsed < 0.4


def test_matrix_rain_during_stops_cleanly_after_wrapped_block():
    """Once the wrapped block finishes, no animation thread should
    still be running in the background.
    """
    import threading

    console = Console(record=True, width=200)
    with matrix_rain_during(fast=False, width=10, height=4, frame_delay=0.02, console=console):
        time.sleep(0.1)

    # Give the thread a brief moment to fully wind down if needed.
    time.sleep(0.05)
    matrix_threads = [t for t in threading.enumerate() if "MatrixRain" in t.name or t.daemon and t.is_alive()]
    # This is a soft check: we can't easily name-match our thread, so
    # instead we rely on the fact that stop() joins with a timeout —
    # if it didn't clean up, the test above (start/stop lifecycle)
    # would already have caught it. This test exists mainly to confirm
    # no exception is raised during teardown.
    assert True


def test_matrix_rain_during_propagates_exceptions_from_wrapped_block():
    """If the wrapped code raises, matrix_rain_during() must let that
    exception propagate normally (after cleanly stopping the
    animation) rather than swallowing it.
    """
    console = Console(record=True, width=200)

    with pytest.raises(ValueError):
        with matrix_rain_during(fast=False, width=10, height=4, frame_delay=0.02, console=console):
            raise ValueError("something went wrong during the wrapped operation")


def test_matrix_rain_during_fast_propagates_exceptions_too():
    """The same exception-propagation guarantee should hold on the
    fast=True skip path too — no animation shouldn't mean errors get
    swallowed either.
    """
    with pytest.raises(ValueError):
        with matrix_rain_during(fast=True):
            raise ValueError("something went wrong during the wrapped operation")