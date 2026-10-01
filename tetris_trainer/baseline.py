"""Small interpretable one-ply reference agent, independent of UI and rules."""

from __future__ import annotations

from dataclasses import dataclass

from .board import Board
from .engine import Game, Placement


HOLE_WEIGHT = -5
AGGREGATE_HEIGHT_WEIGHT = -1
BUMPINESS_WEIGHT = -1
LINES_CLEARED_WEIGHT = 10


@dataclass(frozen=True, slots=True)
class BoardFeatures:
    holes: int
    aggregate_height: int
    bumpiness: int
    lines_cleared: int


def extract_features(board: Board, lines_cleared: int = 0) -> BoardFeatures:
    """Measure the post-clear board; a hole is any empty cell below a block.

    Column height is the distance from its highest block to the floor, or zero
    for an empty column. Bumpiness sums adjacent absolute height differences.
    Lines cleared is execution metadata supplied by the caller, not inferred
    by implementing line-clear rules here.
    """
    heights = []
    holes = 0
    for column in zip(*board.rows):
        height = 0
        covered = False
        for y, cell in enumerate(column):
            if cell is not None:
                if not covered:
                    height = len(column) - y
                    covered = True
            elif covered:
                holes += 1
        heights.append(height)
    bumpiness = sum(abs(left - right) for left, right in zip(heights, heights[1:]))
    return BoardFeatures(holes, sum(heights), bumpiness, lines_cleared)


def score_features(features: BoardFeatures) -> int:
    return (
        HOLE_WEIGHT * features.holes
        + AGGREGATE_HEIGHT_WEIGHT * features.aggregate_height
        + BUMPINESS_WEIGHT * features.bumpiness
        + LINES_CLEARED_WEIGHT * features.lines_cleared
    )


@dataclass(frozen=True, slots=True)
class Decision:
    placement: Placement
    score: int
    features: BoardFeatures
    placements_evaluated: int


class BaselineAgent:
    """Simulate every current-piece placement once; choose the highest score.

    Ties keep the first entry in authoritative legal_placements ordering.
    No hold, preview inspection, survival bonus, or future-piece search.
    """

    def decide(self, game: Game) -> Decision | None:
        placements = game.legal_placements()
        best = None
        for placement in placements:
            future = game.simulate_placement(placement)
            features = extract_features(future.board, future.total_lines - game.total_lines)
            score = score_features(features)
            if best is None or score > best.score:
                best = Decision(placement, score, features, len(placements))
        return best


@dataclass(frozen=True, slots=True)
class RunSummary:
    game: Game
    placements: int
    lines_cleared: int
    game_over: bool
    stop_reason: str


def run_headless(
    seed: int | str | bytes | None = 0, placement_limit: int = 100
) -> RunSummary:
    """Run the same baseline on an owned Game, without importing Tk.

    Stop at the limit, game over, or absence of visible legal locks. The latter
    can occur without engine game_over under the project's top-out boundary.
    """
    if isinstance(placement_limit, bool) or not isinstance(placement_limit, int) or placement_limit < 0:
        raise ValueError("placement_limit must be a nonnegative integer")
    game = Game(seed)
    agent = BaselineAgent()
    count = 0
    reason = "limit"
    while count < placement_limit:
        if game.game_over:
            reason = "game_over"
            break
        decision = agent.decide(game)
        if decision is None:
            reason = "no_legal_placements"
            break
        transition = game.apply_placement(decision.placement)
        if not transition.accepted:
            raise RuntimeError("baseline selected a placement rejected by its source game")
        count += 1
    if game.game_over:
        reason = "game_over"
    return RunSummary(game, count, game.total_lines, game.game_over, reason)
