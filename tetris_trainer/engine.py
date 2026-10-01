"""The single authoritative, deterministic Tetris simulation.

There is intentionally no tick/update method: pieces move only when a semantic
action is applied.  The UI renders this state and maps keys to actions, but owns
no gameplay rules.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum, auto
import json
from importlib.resources import files
import random
from typing import Iterable

from .board import Board
from .pieces import ALL_TETROMINOES, CELLS, Orientation, Tetromino


class Action(Enum):
    MOVE_LEFT = auto()
    MOVE_RIGHT = auto()
    SOFT_DROP = auto()
    HARD_DROP = auto()
    ROTATE_CW = auto()
    ROTATE_CCW = auto()
    ROTATE_180 = auto()
    HOLD = auto()


@dataclass(frozen=True, slots=True)
class ActivePiece:
    kind: Tetromino
    orientation: Orientation = Orientation.SPAWN
    x: int = 3
    y: int = 0

    @property
    def cells(self) -> tuple[tuple[int, int], ...]:
        return tuple(
            (self.x + dx, self.y + dy)
            for dx, dy in CELLS[self.kind][self.orientation]
        )

    def moved(self, dx: int = 0, dy: int = 0) -> "ActivePiece":
        return ActivePiece(self.kind, self.orientation, self.x + dx, self.y + dy)


@dataclass(frozen=True, slots=True)
class Transition:
    accepted: bool
    locked: bool = False
    lines_cleared: int = 0
    game_over: bool = False


class BagRandomizer:
    """Owned seedable RNG and its deterministic stream of complete seven-bags."""

    def __init__(self, seed: int | str | bytes | None = 0) -> None:
        self._rng = random.Random(seed)
        self._pieces: deque[Tetromino] = deque()

    def _fill(self) -> None:
        bag = list(ALL_TETROMINOES)
        self._rng.shuffle(bag)
        self._pieces.extend(bag)

    def ensure(self, count: int) -> None:
        while len(self._pieces) < count:
            self._fill()

    def pop(self) -> Tetromino:
        self.ensure(1)
        return self._pieces.popleft()

    def peek(self, count: int = 5) -> tuple[Tetromino, ...]:
        self.ensure(count)
        return tuple(list(self._pieces)[:count])

    def snapshot(self) -> tuple[object, tuple[Tetromino, ...]]:
        return self._rng.getstate(), tuple(self._pieces)


def _load_kicks() -> dict[str, dict[str, tuple[tuple[int, int], ...]]]:
    raw = json.loads(files("tetris_trainer").joinpath("data/srs_plus.json").read_text())
    return {
        group: {transition: tuple(map(tuple, offsets)) for transition, offsets in table.items()}
        for group, table in ((name, raw[name]) for name in ("jlstz", "i"))
    }


_KICKS = _load_kicks()


class Game:
    """Mutable orchestration around immutable board/piece values.

    Mutability keeps interactive use simple. ``snapshot`` captures every item
    that affects future simulation, suitable for determinism tests and future
    cloning/state adapters.
    """

    PREVIEW_COUNT = 5

    def __init__(self, seed: int | str | bytes | None = 0) -> None:
        self.board = Board()
        self.randomizer = BagRandomizer(seed)
        self.active: ActivePiece | None = None
        self.hold_piece: Tetromino | None = None
        self.hold_used = False
        self.game_over = False
        self.total_lines = 0
        self._spawn(self.randomizer.pop())
        self.randomizer.ensure(self.PREVIEW_COUNT)

    @property
    def upcoming(self) -> tuple[Tetromino, ...]:
        return self.randomizer.peek(self.PREVIEW_COUNT)

    def _spawn(self, kind: Tetromino) -> bool:
        candidate = ActivePiece(kind)
        self.active = candidate
        if not self._legal(candidate):
            self.game_over = True
            return False
        return True

    def _legal(self, piece: ActivePiece) -> bool:
        return all(not self.board.occupied(x, y) for x, y in piece.cells)

    def ghost(self) -> ActivePiece | None:
        if self.active is None:
            return None
        result = self.active
        while self._legal(result.moved(dy=1)):
            result = result.moved(dy=1)
        return result

    def apply(self, action: Action) -> Transition:
        if self.game_over or self.active is None:
            return Transition(False, game_over=self.game_over)
        if action is Action.MOVE_LEFT:
            return Transition(self._try_move(-1, 0))
        if action is Action.MOVE_RIGHT:
            return Transition(self._try_move(1, 0))
        if action is Action.SOFT_DROP:
            return Transition(self._try_move(0, 1))
        if action is Action.ROTATE_CW:
            return Transition(self._try_rotate(1))
        if action is Action.ROTATE_CCW:
            return Transition(self._try_rotate(-1))
        if action is Action.ROTATE_180:
            return Transition(self._try_rotate(2))
        if action is Action.HOLD:
            return Transition(self._hold(), game_over=self.game_over)
        if action is Action.HARD_DROP:
            self.active = self.ghost()
            return self._lock()
        raise ValueError(f"unknown action: {action!r}")

    def _try_move(self, dx: int, dy: int) -> bool:
        assert self.active is not None
        candidate = self.active.moved(dx, dy)
        if not self._legal(candidate):
            return False
        self.active = candidate
        return True

    def _try_rotate(self, amount: int) -> bool:
        assert self.active is not None
        old = self.active.orientation
        new = Orientation((old + amount) % 4)
        if self.active.kind is Tetromino.O:
            self.active = ActivePiece(self.active.kind, new, self.active.x, self.active.y)
            return True
        group = "i" if self.active.kind is Tetromino.I else "jlstz"
        for kick_x, kick_y_up in _KICKS[group][f"{old.value}>{new.value}"]:
            candidate = ActivePiece(
                self.active.kind, new, self.active.x + kick_x, self.active.y - kick_y_up
            )
            if self._legal(candidate):
                self.active = candidate
                return True
        return False

    def _hold(self) -> bool:
        assert self.active is not None
        if self.hold_used:
            return False
        outgoing = self.active.kind
        incoming = self.hold_piece if self.hold_piece is not None else self.randomizer.pop()
        self.hold_piece = outgoing
        self.hold_used = True
        self._spawn(incoming)
        self.randomizer.ensure(self.PREVIEW_COUNT)
        return True

    def _lock(self) -> Transition:
        assert self.active is not None
        # A piece unable to enter the visible matrix is a project-specific
        # first-version top-out. It is not partially written into the board.
        if any(y < 0 for _, y in self.active.cells):
            self.game_over = True
            return Transition(True, locked=False, game_over=True)
        self.board = self.board.lock(self.active.cells, self.active.kind)
        self.board, cleared = self.board.clear_lines()
        self.total_lines += cleared
        self.hold_used = False
        self._spawn(self.randomizer.pop())
        self.randomizer.ensure(self.PREVIEW_COUNT)
        return Transition(True, locked=True, lines_cleared=cleared, game_over=self.game_over)

    def snapshot(self) -> tuple[object, ...]:
        return (
            self.board,
            self.active,
            self.hold_piece,
            self.hold_used,
            self.game_over,
            self.total_lines,
            self.randomizer.snapshot(),
        )

    def apply_many(self, actions: Iterable[Action]) -> tuple[Transition, ...]:
        return tuple(self.apply(action) for action in actions)
