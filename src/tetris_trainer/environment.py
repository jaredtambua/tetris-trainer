"""Framework-free numerical boundary for legal final-placement policies.

Contract v2 is documented in docs/RL_ENVIRONMENT.md. No reward policy, UI,
learning algorithm, or gameplay mechanics live here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType

from .board import GarbageCell, HEIGHT, WIDTH
from .engine import ClearEvent, Game, MAX_PENDING_GARBAGE, Placement
from .pieces import Tetromino
from .versus import Spin


CONTRACT_VERSION = 2
QUEUE_LENGTH = 5
BOARD_SHAPE = (HEIGHT, WIDTH)
BOARD_SLICE = slice(0, HEIGHT * WIDTH)
ACTIVE_SLICE = slice(BOARD_SLICE.stop, BOARD_SLICE.stop + 4)
HOLD_SLICE = slice(ACTIVE_SLICE.stop, ACTIVE_SLICE.stop + 2)
QUEUE_SLICE = slice(HOLD_SLICE.stop, HOLD_SLICE.stop + QUEUE_LENGTH)
TERMINATED_INDEX = QUEUE_SLICE.stop
GARBAGE_BOARD_SLICE = slice(TERMINATED_INDEX + 1, TERMINATED_INDEX + 1 + HEIGHT * WIDTH)
COMBO_INDEX = GARBAGE_BOARD_SLICE.stop
B2B_INDEX = COMBO_INDEX + 1
ROTATION_AMOUNT_INDEX = B2B_INDEX + 1
ROTATION_KICK_INDEX = ROTATION_AMOUNT_INDEX + 1
ROTATION_SPIN_INDEX = ROTATION_KICK_INDEX + 1
PENDING_GARBAGE_SLICE = slice(ROTATION_SPIN_INDEX + 1,
                              ROTATION_SPIN_INDEX + 1 + MAX_PENDING_GARBAGE * 2)
OBSERVATION_SIZE = PENDING_GARBAGE_SLICE.stop
PIECE_IDS = MappingProxyType({
    None: 0, Tetromino.I: 1, Tetromino.J: 2, Tetromino.L: 3,
    Tetromino.O: 4, Tetromino.S: 5, Tetromino.T: 6, Tetromino.Z: 7,
})
Observation = tuple[int, ...]
PLACEMENT_SIZE = 5
SPIN_IDS = MappingProxyType({Spin.NONE: 0, Spin.MINI: 1, Spin.FULL: 2})
PlacementValues = tuple[int, int, int, int, int]


def encode_observation(game: Game, *, terminated: bool) -> Observation:
    """Read numerical state without refilling the preview or consuming RNG."""
    board = tuple(int(cell is not None) for row in game.board.rows for cell in row)
    active = game.active
    pose = ((PIECE_IDS[active.kind], int(active.orientation), active.x, active.y)
            if active is not None else (0, 0, 0, 0))
    hold = (PIECE_IDS[game.hold_piece], int(
        active is not None and not game.hold_used and not game.game_over and not terminated
    ))
    queued = game.randomizer.snapshot()[1][:QUEUE_LENGTH]
    preview = tuple(PIECE_IDS[piece] for piece in queued) + (0,) * (QUEUE_LENGTH - len(queued))
    garbage = tuple(int(cell is GarbageCell.GARBAGE)
                    for row in game.board.rows for cell in row)
    rotation = game.last_rotation
    versus = (game.combo, game.b2b, rotation.amount if rotation else 0,
              rotation.kick_index if rotation else -1,
              SPIN_IDS[rotation.spin] if rotation else 0)
    pending = tuple(value for event in game.pending_garbage for hole in event.holes
                    for value in (hole + 1, int(event.ready)))
    padding = (0,) * (MAX_PENDING_GARBAGE * 2 - len(pending))
    return board + pose + hold + preview + (int(terminated),) + garbage + versus + pending + padding


@dataclass(frozen=True, slots=True)
class PlacementAction:
    """One policy row and its opaque, state-scoped execution handle."""

    index: int
    values: PlacementValues
    _placement: Placement = field(repr=False, compare=False)
    _token: object = field(repr=False, compare=False)


@dataclass(frozen=True, slots=True)
class TransitionFacts:
    placed: PlacementValues
    locked: bool
    lines_cleared: int
    total_lines: int
    game_over: bool
    terminal_reason: str | None
    step_count: int
    clear_event: ClearEvent | None = None


@dataclass(frozen=True, slots=True)
class StepResult:
    observation: Observation
    terminated: bool
    facts: TransitionFacts


class PlacementEnvironment:
    """Owned headless Game with a variable, deterministic placement action set.

    Candidates are issued on reset/step and valid only for that exact decision
    in this environment. The public observation has no Game references.
    """

    def __init__(self, seed: int | str | bytes | None = 0) -> None:
        self.reset(seed)

    @classmethod
    def from_game(cls, game: Game) -> PlacementEnvironment:
        """Create an isolated environment for an existing scenario."""
        env = object.__new__(cls)
        env._start(game.clone())
        return env

    def _start(self, game: Game) -> None:
        self._game = game
        self._step_count = 0
        self._refresh_actions()

    def _refresh_actions(self) -> None:
        self._token = object()
        placements = self._game.legal_placements()
        self._actions = tuple(
            PlacementAction(index, (PIECE_IDS[p.kind], int(p.orientation), p.x, p.y,
                                    SPIN_IDS[p.spin]),
                            p, self._token)
            for index, p in enumerate(placements)
        )
        self._terminal_reason = (
            'game_over' if self._game.game_over else
            'no_legal_placements' if not self._actions else None
        )

    @property
    def terminated(self) -> bool:
        return self._terminal_reason is not None

    @property
    def terminal_reason(self) -> str | None:
        return self._terminal_reason

    def reset(self, seed: int | str | bytes | None = 0) -> Observation:
        """Replace the owned game and invalidate every previously issued action."""
        self._start(Game(seed))
        return self.observe()

    def observe(self) -> Observation:
        return encode_observation(self._game, terminated=self.terminated)

    def legal_actions(self) -> tuple[PlacementAction, ...]:
        return self._actions

    def step(self, action: PlacementAction) -> StepResult:
        """Execute an issued candidate; invalid input raises ValueError atomically."""
        if (
            self.terminated or not isinstance(action, PlacementAction)
            or action._token is not self._token
            or type(action.index) is not int
            or not 0 <= action.index < len(self._actions)
            or self._actions[action.index] is not action
        ):
            raise ValueError('action must be a currently issued legal placement')
        transition = self._game.apply_placement(action._placement)
        if not transition.accepted:
            raise ValueError('placement is stale or invalid for the current game')
        self._step_count += 1
        self._refresh_actions()
        return StepResult(self.observe(), self.terminated, TransitionFacts(
            action.values, transition.locked, transition.lines_cleared,
            self._game.total_lines, transition.game_over,
            self.terminal_reason, self._step_count, transition.clear_event,
        ))
