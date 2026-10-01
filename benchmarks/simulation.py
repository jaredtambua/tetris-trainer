"""Reproducible infrastructure timings: python -m benchmarks.simulation."""

from statistics import median
from timeit import repeat

from tetris_trainer import Game
from tetris_trainer.board import Board
from tetris_trainer.engine import ActivePiece
from tetris_trainer.pieces import Tetromino


def representative_game():
    game = Game(42)
    heights = (2, 3, 2, 1, 0, 0, 1, 2, 3, 2)
    game.board = Board().with_cells({
        (x, y): Tetromino.J
        for x, height in enumerate(heights)
        for y in range(20 - height, 20)
    })
    game.active = ActivePiece(Tetromino.T)
    return game


def two_ply(game):
    """Exhaust all first/second placements; no ranking or search policy."""
    children = leaves = 0
    for placement in game.legal_placements():
        child = game.simulate_placement(placement)
        assert child.transition.accepted
        children += 1
        for choice in child.game.legal_placements():
            leaf = child.game.simulate_placement(choice)
            assert leaf.transition.accepted
            leaves += 1
    return children, leaves


def main():
    game = representative_game()
    before = game.snapshot()
    placement = game.legal_placements()[0]
    for label, operation, count in (
        ('clone', game.clone, 1000),
        ('legal_placements', game.legal_placements, 50),
        ('simulate_placement', lambda: game.simulate_placement(placement), 50),
    ):
        samples = repeat(operation, number=count, repeat=3)
        print(f'{label}: {median(samples) / count * 1000:.3f} ms '
              f'(median of 3 batches of {count})')
    sizes = []

    def expand():
        sizes.append(two_ply(game))

    samples = repeat(expand, number=1, repeat=3)
    print(f'two_ply: {median(samples) * 1000:.3f} ms '
          f'(median of 3 expansions; children/leaves={sizes[0]})')
    assert len(set(sizes)) == 1
    assert game.snapshot() == before


if __name__ == '__main__':
    main()
