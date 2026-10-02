"""The single authoritative, deterministic Tetris simulation.

There is intentionally no tick/update method: pieces move only when a semantic
action is applied.  The UI renders this state and maps keys to actions, but owns
no gameplay rules.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
import json
from importlib.resources import files
import random
from typing import Iterable

from .board import Board
from .pieces import ALL_TETROMINOES, CELLS, Orientation, Tetromino
from .versus import (MAX_PENDING_GARBAGE, ClearEvent, GarbageEvent,
                     RotationHistory, Spin, resolve_attack)


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
    clear_event: ClearEvent | None = None


@dataclass(frozen=True, slots=True)
class Placement:
    """A reachable visible lock position, bound to its originating game state."""

    kind: Tetromino
    orientation: Orientation
    x: int
    y: int
    _source: tuple[object, ...] = field(default=(), repr=False, compare=False)
    _rotation: RotationHistory | None = field(default=None, repr=False)
    _path: tuple[Action, ...] = field(default=(), repr=False, compare=False)
    spin: Spin = Spin.NONE

    @property
    def cells(self) -> tuple[tuple[int, int], ...]:
        return ActivePiece(self.kind, self.orientation, self.x, self.y).cells


@dataclass(frozen=True, slots=True)
class SimulationResult:
    """Independent mutable game branch and immutable execution metadata."""

    game: Game
    transition: Transition


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

    def clone(self) -> BagRandomizer:
        """Copy queue and RNG without generating or consuming any pieces."""
        clone = BagRandomizer(0)
        clone._rng.setstate(self._rng.getstate())
        clone._pieces = self._pieces.copy()
        return clone


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
        self.combo = -1
        self.b2b = -1
        self.last_rotation: RotationHistory | None = None
        self.pending_garbage: tuple[GarbageEvent, ...] = ()
        # One immutable, derived result; never part of future-affecting state.
        # Full snapshot equality protects reuse even after public-field edits.
        self._placement_cache: tuple[tuple[object, ...], tuple[Placement, ...]] | None = None
        self._spawn(self.randomizer.pop())
        self.randomizer.ensure(self.PREVIEW_COUNT)

    @property
    def upcoming(self) -> tuple[Tetromino, ...]:
        return self.randomizer.peek(self.PREVIEW_COUNT)

    def clone(self) -> Game:
        """Fork all simulation state, sharing only immutable board/piece values.

        Bypass initialization so no spawn, queue refill, or random draw occurs.
        Keep this field list in sync with snapshot when adding engine state.
        """
        clone = object.__new__(Game)
        clone.board = self.board
        clone.active = self.active
        clone.randomizer = self.randomizer.clone()
        clone.hold_piece = self.hold_piece
        clone.hold_used = self.hold_used
        clone.game_over = self.game_over
        clone.total_lines = self.total_lines
        clone.combo = self.combo
        clone.b2b = self.b2b
        clone.last_rotation = self.last_rotation
        clone.pending_garbage = self.pending_garbage
        clone._placement_cache = self._placement_cache
        return clone

    def simulate_placement(self, placement: Placement) -> Game:
        """Return an independent future Game after a validated placement.

        Raise ValueError for invalid or stale choices without changing the
        source. Use simulate_placement_result when transition metadata or
        non-raising rejection handling is needed.
        """
        result = self.simulate_placement_result(placement)
        if not result.transition.accepted:
            raise ValueError("placement is invalid, stale, or unreachable in this game")
        return result.game

    def simulate_placement_result(self, placement: Placement) -> SimulationResult:
        """Apply a choice on a fresh branch, leaving this game untouched.

        Invalid/stale choices return an unaccepted transition and an unchanged,
        independent clone, following apply_placement's rejection convention.
        The returned game supports further enumeration and simulation.
        """
        branch = self.clone()
        transition = branch.apply_placement(placement)
        return SimulationResult(branch, transition)

    def _spawn(self, kind: Tetromino) -> bool:
        self.last_rotation = None
        candidate = ActivePiece(kind)
        self.active = candidate
        if not self._legal(candidate):
            self.game_over = True
            return False
        return True

    def _legal(self, piece: ActivePiece) -> bool:
        # Use authoritative geometry/occupancy without allocating absolute-cell
        # tuples and generators for every movement/rotation candidate.
        for dx, dy in CELLS[piece.kind][piece.orientation]:
            if self.board.occupied(piece.x + dx, piece.y + dy):
                return False
        return True

    def ghost(self) -> ActivePiece | None:
        if self.active is None:
            return None
        return self._ghost_piece(self.active)

    def _ghost_piece(self, piece: ActivePiece) -> ActivePiece:
        result = piece
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
            # The live client's instant hard drop retains rotation provenance;
            # unlike an accepted semantic soft drop, descent does not reset it.
            self.active = self.ghost()
            return self._lock()
        raise ValueError(f"unknown action: {action!r}")

    def _try_move(self, dx: int, dy: int) -> bool:
        assert self.active is not None
        candidate = self._move_piece(self.active, dx, dy)
        if candidate is None:
            return False
        self.active = candidate
        self.last_rotation = None
        return True

    def _move_piece(self, piece: ActivePiece, dx: int, dy: int) -> ActivePiece | None:
        candidate = piece.moved(dx, dy)
        return candidate if self._legal(candidate) else None

    def _try_rotate(self, amount: int) -> bool:
        assert self.active is not None
        result = self._rotation_result(self.active, amount)
        if result is None:
            return False
        self.active, self.last_rotation = result
        return True

    def _rotate_piece(self, piece: ActivePiece, amount: int) -> ActivePiece | None:
        result = self._rotation_result(piece, amount)
        return result[0] if result is not None else None

    def _rotation_result(self, piece: ActivePiece, amount: int
                         ) -> tuple[ActivePiece, RotationHistory] | None:
        old = piece.orientation
        new = Orientation((old + amount) % 4)
        if piece.kind is Tetromino.O:
            candidate = ActivePiece(piece.kind, new, piece.x, piece.y)
            return candidate, RotationHistory(amount, 0, self._classify_spin(candidate, 0))
        group = "i" if piece.kind is Tetromino.I else "jlstz"
        for index, (kick_x, kick_y_up) in enumerate(_KICKS[group][f"{old.value}>{new.value}"]):
            candidate = ActivePiece(
                piece.kind, new, piece.x + kick_x, piece.y - kick_y_up
            )
            if self._legal(candidate):
                return candidate, RotationHistory(amount, index, self._classify_spin(candidate, index))
        return None

    def _spin(self, piece: ActivePiece, history: RotationHistory | None) -> Spin:
        return Spin.NONE if history is None else history.spin

    def _classify_spin(self, piece: ActivePiece, kick_index: int) -> Spin:
        if piece.kind is Tetromino.T:
            corners = tuple(self.board.occupied(piece.x + dx, piece.y + dy)
                            for dx, dy in ((0, 0), (2, 0), (2, 2), (0, 2)))
            if sum(corners) >= 3:
                front = ((0, 1), (1, 2), (2, 3), (3, 0))[piece.orientation]
                upgraded = kick_index == 4
                return Spin.FULL if all(corners[i] for i in front) or upgraded else Spin.MINI
        if all(self._move_piece(piece, dx, dy) is None
               for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))):
            return Spin.MINI
        return Spin.NONE

    def legal_placements(self) -> tuple[Placement, ...]:
        """Enumerate visible reachable locks without changing simulation state.

        BFS retains orientation even for equal geometry: kick behavior depends on
        it. Final locks are deduplicated by occupied cells and Spin outcome.
        Legacy first-BFS geometry representatives are preserved. With the current
        SRS+ tables, wall-only rotations above the board use horizontal kicks;
        upward kicks require nearby board/floor collisions. The graph is finite
        even though board collision allows cells above row zero. No artificial
        ceiling or spawn reset is imposed.
        """
        if self.game_over or self.active is None or not self._legal(self.active):
            return ()
        source = self.snapshot()
        if self._placement_cache is not None and self._placement_cache[0] == source:
            return self._placement_cache[1]
        pending = deque([self.active])
        visited = {self.active}
        histories = {self.active: self.last_rotation}
        parents = {self.active: None}
        translated = {}
        rotated = {}
        grounded = set()
        locks = {}
        variants = {}

        def path_for(piece, final_edge=None):
            actions = []
            edge = final_edge if final_edge is not None else parents[piece]
            while edge is not None:
                predecessor, action = edge
                actions.append(action)
                edge = parents[predecessor]
            return tuple(reversed(actions))

        def add_lock(piece, history, final_edge=None, *, primary=False, path_override=None):
            if self._move_piece(piece, 0, 1) is not None or any(y < 0 for _, y in piece.cells):
                return
            # A final geometry can have different factual outcomes depending on
            # its rotation witness. Preserve each Spin outcome, not every path.
            cells = tuple(sorted(piece.cells))
            key = (cells, self._spin(piece, history))
            if key in variants and (not primary or cells in locks):
                return
            placement = Placement(piece.kind, piece.orientation, piece.x,
                                  piece.y, source, history,
                                  path_for(piece, final_edge) if path_override is None else path_override,
                                  key[1])
            if primary:
                locks.setdefault(cells, placement)
            variants.setdefault(key, placement)

        while pending:
            piece = pending.popleft()
            down = self._move_piece(piece, 0, 1)
            if down is None:
                grounded.add(piece)
                add_lock(piece, histories[piece], primary=True)
            neighbors = [
                (self._move_piece(piece, -1, 0), None, Action.MOVE_LEFT),
                (self._move_piece(piece, 1, 0), None, Action.MOVE_RIGHT),
                (down, None, Action.SOFT_DROP),
            ]
            for amount, action in ((1, Action.ROTATE_CW), (-1, Action.ROTATE_CCW),
                                   (2, Action.ROTATE_180)):
                result = self._rotation_result(piece, amount)
                if result is not None:
                    candidate, history = result
                    # Spin flags are determined at rotation and survive instant
                    # hard drop, so retain witnesses even above the final lock.
                    if history.spin is not Spin.NONE:
                        rotated.setdefault((candidate, history.spin), (history, (piece, action)))
                    neighbors.append((candidate, history, action))
            for candidate, history, action in neighbors:
                if candidate is not None and history is None and histories.get(candidate) is not None:
                    translated.setdefault(candidate, (piece, action))
                if candidate is not None and candidate not in visited:
                    visited.add(candidate)
                    histories[candidate] = history
                    parents[candidate] = (piece, action)
                    pending.append(candidate)
        for piece, path in translated.items():
            if piece in grounded:
                add_lock(piece, None, path)
        for (piece, _), (history, path) in rotated.items():
            add_lock(self._ghost_piece(piece), history, path)
        if self.last_rotation is not None and self.last_rotation.spin is not Spin.NONE:
            add_lock(self._ghost_piece(self.active), self.last_rotation, path_override=())
        choices = list(locks.values())
        outcomes = {(tuple(sorted(p.cells)), self._spin(
            ActivePiece(p.kind, p.orientation, p.x, p.y), p._rotation)) for p in choices}
        extra = [p for key, p in variants.items() if key not in outcomes]
        order = lambda p: (p.orientation, p.x, p.y)
        placements = tuple(sorted(choices, key=order) + sorted(extra, key=order))
        self._placement_cache = (source, placements)
        return placements

    def apply_placement(self, placement: Placement) -> Transition:
        """Reject stale/unreachable choices atomically; use authoritative locking."""
        if not isinstance(placement, Placement) or placement._source != self.snapshot():
            return Transition(False, game_over=self.game_over)
        if placement not in self.legal_placements():
            return Transition(False, game_over=self.game_over)
        self.active = ActivePiece(
            placement.kind, placement.orientation, placement.x, placement.y
        )
        self.last_rotation = placement._rotation
        return self._lock()

    def enqueue_garbage(self, event: GarbageEvent) -> None:
        """Append externally supplied rows atomically; no hidden RNG or clock."""
        if not isinstance(event, GarbageEvent):
            raise ValueError('expected GarbageEvent')
        if sum(len(e.holes) for e in self.pending_garbage) + len(event.holes) > MAX_PENDING_GARBAGE:
            raise ValueError('pending garbage capacity is 256 rows')
        self.pending_garbage += (event,)

    def set_garbage_ready(self, index: int) -> None:
        if type(index) is not int or not 0 <= index < len(self.pending_garbage):
            raise ValueError('invalid pending garbage event index')
        event = self.pending_garbage[index]
        self.pending_garbage = (self.pending_garbage[:index] +
                                (GarbageEvent(event.holes, True),) + self.pending_garbage[index + 1:])

    def _resolve_garbage(self, attack: int, cleared: int) -> tuple[int, int, bool]:
        remaining = []
        cancelled = 0
        for event in self.pending_garbage:
            count = min(attack - cancelled, len(event.holes))
            cancelled += count
            if count < len(event.holes):
                remaining.append(GarbageEvent(event.holes[count:], event.ready))
        holes = []
        if not cleared:
            pending = []
            for event in remaining:
                count = min(8 - len(holes), len(event.holes)) if event.ready else 0
                holes.extend(event.holes[:count])
                if count < len(event.holes):
                    pending.append(GarbageEvent(event.holes[count:], event.ready))
            remaining = pending
        self.pending_garbage = tuple(remaining)
        self.board, overflow = self.board.insert_garbage(tuple(holes))
        return cancelled, len(holes), overflow

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
        self._placement_cache = None
        # A piece unable to enter the visible matrix is a project-specific
        # first-version top-out. It is not partially written into the board.
        if any(y < 0 for _, y in self.active.cells):
            self.game_over = True
            return Transition(True, locked=False, game_over=True)
        piece = self.active
        spin = self._spin(piece, self.last_rotation)
        self.board = self.board.lock(piece.cells, piece.kind)
        clear = self.board.clear_lines_result()
        self.board = clear.board
        cleared = clear.cleared_lines
        all_clear = cleared > 0 and not any(cell is not None for row in self.board.rows for cell in row)
        combo_before, b2b_before = self.combo, self.b2b
        attack = resolve_attack(piece.kind, cleared, spin, all_clear,
                                clear.garbage_lines, self.combo, self.b2b)
        self.combo, self.b2b = attack.combo, attack.b2b
        cancelled, inserted, overflow = self._resolve_garbage(attack.generated, cleared)
        self.total_lines += cleared
        self.hold_used = False
        self._spawn(self.randomizer.pop())
        self.game_over = self.game_over or overflow
        self.randomizer.ensure(self.PREVIEW_COUNT)
        event = ClearEvent(piece.kind, clear.cleared_rows, spin, all_clear,
                           clear.garbage_lines, combo_before, self.combo,
                           b2b_before, self.b2b, attack.base, attack.generated,
                           attack.surge, cancelled, attack.generated - cancelled,
                           inserted, self.pending_garbage, self.game_over)
        return Transition(True, locked=True, lines_cleared=cleared,
                          game_over=self.game_over, clear_event=event)

    def snapshot(self) -> tuple[object, ...]:
        return (
            self.board,
            self.active,
            self.hold_piece,
            self.hold_used,
            self.game_over,
            self.total_lines,
            self.randomizer.snapshot(),
            self.combo, self.b2b, self.last_rotation, self.pending_garbage,
        )

    def apply_many(self, actions: Iterable[Action]) -> tuple[Transition, ...]:
        return tuple(self.apply(action) for action in actions)
