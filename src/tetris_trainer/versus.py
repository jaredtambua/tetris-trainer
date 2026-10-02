"""Pure placement-based versus facts; evidence boundaries in VERSUS_MECHANICS.md.

No movement, collision, reward, or opponent logic belongs in this module.
"""
from dataclasses import dataclass
from enum import Enum
import math

from .board import WIDTH
from .pieces import Tetromino


MAX_PENDING_GARBAGE = 256


class Spin(str, Enum):
    NONE = 'none'
    MINI = 'mini'
    FULL = 'full'


@dataclass(frozen=True, slots=True)
class RotationHistory:
    amount: int
    kick_index: int
    spin: Spin = Spin.NONE


@dataclass(frozen=True, slots=True)
class GarbageEvent:
    """Externally supplied bottom-row holes, in insertion order."""
    holes: tuple[int, ...]
    ready: bool = True

    def __post_init__(self):
        object.__setattr__(self, 'holes', tuple(self.holes))
        if not self.holes or len(self.holes) > MAX_PENDING_GARBAGE:
            raise ValueError('garbage event must contain 1..256 rows')
        if any(type(h) is not int or not 0 <= h < WIDTH for h in self.holes):
            raise ValueError('garbage holes must be integer columns in [0,10)')
        if type(self.ready) is not bool:
            raise ValueError('garbage readiness must be bool')


@dataclass(frozen=True, slots=True)
class AttackResult:
    combo: int
    b2b: int
    base: int
    generated: int
    surge: int


def resolve_attack(piece: Tetromino, lines: int, spin: Spin, all_clear: bool,
                   garbage_lines: int, combo: int, b2b: int) -> AttackResult:
    """Resolve the documented local TL-oriented profile, rounding downward."""
    if not 0 <= lines <= 4:
        raise ValueError('tetromino clears must contain 0..4 lines')
    if not lines:
        return AttackResult(-1, b2b, 0, 0, 0)
    next_combo = combo + 1
    difficult_clear = lines == 4 or spin is not Spin.NONE
    difficult = difficult_clear or all_clear
    next_b2b = b2b + int(difficult_clear) + int(all_clear) if difficult else -1
    surge = b2b if not difficult and b2b >= 4 else 0
    if spin is Spin.FULL:
        base = (0, 2, 4, 6, 10)[lines]
    elif spin is Spin.MINI:
        base = (0, 0, 1, 2, 4)[lines]
    else:
        base = (0, 0, 1, 2, 4)[lines]
    boosted = base + int(difficult_clear and next_b2b >= 1)
    multiplied = boosted * (1 + .25 * next_combo)
    if next_combo >= 2:
        multiplied = max(multiplied, math.log1p(1.25 * next_combo))
    multiplied = math.floor(multiplied)
    garbage_bonus = int(garbage_lines > 0 and (lines == 4 or spin is not Spin.NONE))
    return AttackResult(next_combo, next_b2b, base,
                        multiplied + 5 * int(all_clear) + garbage_bonus + surge, surge)


@dataclass(frozen=True, slots=True)
class ClearEvent:
    piece: Tetromino
    cleared_rows: tuple[int, ...]
    spin: Spin
    all_clear: bool
    garbage_lines_cleared: int
    combo_before: int
    combo_after: int
    b2b_before: int
    b2b_after: int
    base_attack: int
    attack_generated: int
    surge_attack: int
    cancelled: int
    outgoing: int
    garbage_inserted: int
    pending_garbage: tuple[GarbageEvent, ...]
    game_over: bool

    @property
    def lines_cleared(self) -> int:
        return len(self.cleared_rows)

    @property
    def classification(self) -> str:
        clear = ('none', 'single', 'double', 'triple', 'quad')[self.lines_cleared]
        return clear if self.spin is Spin.NONE else f'{self.piece.value.lower()}_{self.spin.value}_{clear}'
