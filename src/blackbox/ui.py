"""
blackbox.ui - visual fair shown during encrypt/decrypt: the Matrix-rain loading animation.

Purely comsetic. This module never touches passwords, keys, archives or files - it only renders falling characters to the terminal
for as long as the real work (lock/unlock) is running, using rich.live.Live to redraw a grid of randomised characters each frame.

Because real encrypt/decrypt operation are fast (a few hundred milliseconds), the animation runs on a background thread rather than
sleeping for a fixed duration - it starts right before the real work begins and stops the instant it finishes, so the animation
genuinely tracks the operation rather than decorating an arbitrary time window.

Skippable via the 'fast' parameter, which the CLI's `---fast` glag maps to directly: when fast=True, no thread is started, no frames
are rendered, and the wrapped operation runs at full, undecorated speed.
"""

from __future__ import annotations

import random
import string
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Iterator

from rich.console import Console
from rich.live import Live
from rich.style import Style
from rich.text import Text


# Character pool: digits, letters, katakana (a classic homage to the original Matrix film's on-screen character set), and a few
# block/shade glyphs for texture - echoing the project's original brief for occasional "alien transmission" -looking text.

_CHAR_POOL = (
    string.ascii_uppercase
    + string.digits
    + "アイウエオカキクケコサシスセソ"
    + "░▒▓█▚▞"
)

DEFAULT_WIDTH = 60
DEFAULT_HEIGHT = 12
DEFAULT_FRAME_DELAY = 0.08 # seconds between frames
_TRIAL_LENGTH = 4 # rows behind the bright head that stay lit, dimmer

def _random_char() -> str:
    """
    Return one random character from the animation's character pool.
    """
    return random.choice(_CHAR_POOL)

@dataclass
class _MatrixRainFrame:
    """
    The mutable state of one falling-character grid.

    Each column has a "head" - the row position of its brightest, currently-falling character. Rows just behind the head render
    progressively dimmer, mimicking the classic Matrix-rain trail fading into darkness. 
    """

    width: int
    height: int
    grid: list[list[str]] = field(default_factory=list)
    heads: list[int] = field(default_factory=list)

    @classmethod
    def new(cls, width: int, height: int) -> "_MatrixRainFrame":
        grid = [[_random_char() for _ in range(width)] for _ in range(height)]
        # Stagger starting head positions above the visible grid so columns dont all begind falling in visible unison.
        heads = [random.randint(-height, 0) for _ in range(width)]
        return cls(width=width, height=height, grid=grid, heads=heads)

    def step(self) -> None:
        """
        Advance the animation by one frame.
        """
        for col in range(self.width):
            self.heads[col] += 1
            # Once a column's head falls well past the bottom, reset it back above the top at a new random offset, so
            # columns dont all loop in lockstep

            if self.heads[col] > self.height + random.randint(0, self.height):
                self.heads[col] = random.randint(-self.height, 0)

            # Flicker one random cell per column per frame, independent of head position, so the whole grid stays 
            # visually alive

            row = random.randint(0, self.height - 1)
            self.grid[row][col] = _random_char()

    def render(self) -> Text:
        """
        Render the current frame as a styled rich Text block.
        """
        text = Text()
        for row in range(self.height):
            for col in range(self.width):
                char = self.grid[row][col]
                distance = row - self.heads[col]
                if distance == 0:
                    style = Style(color="bright_green", bold=True)
                elif 0 < distance <= _TRIAL_LENGTH:
                    style = Style(color="green") 
                elif distance > _TRIAL_LENGTH:
                    style = Style(color="green", dim=True)
                else:
                    # Above the head: not yet "fallen" here this cycle.
                    style = Style(color="grey15")
                text.append(char, style=style)
            if row < self.height - 1:
                text.append("\n")
        return text
