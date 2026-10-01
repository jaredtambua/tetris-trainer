"""Measure the complete baseline decision: python -m benchmarks.baseline."""

import platform
from statistics import median
from timeit import repeat

from benchmarks.simulation import representative_game
from tetris_trainer.baseline import BaselineAgent, extract_features, score_features


def main():
    game = representative_game()
    pristine = game.clone()
    before = game.snapshot()
    agent = BaselineAgent()
    decision = agent.decide(game)
    print(f'Python {platform.python_version()} on {platform.system()} {platform.machine()}; '
          f'seed=42; active=T; placements evaluated={decision.placements_evaluated}')
    samples = repeat(lambda: agent.decide(pristine.clone()), number=1, repeat=5)
    print(f'cold one-ply decision: {median(samples) * 1000:.3f} ms (median of 5 decisions)')
    samples = repeat(lambda: score_features(extract_features(game.board)), number=1000, repeat=3)
    print(f'extract + score: {median(samples) * 1000 / 1000:.3f} ms '
          '(median of 3 batches of 1000)')
    assert game.snapshot() == before


if __name__ == '__main__':
    main()
