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