"""Measure environment overhead: python -m benchmarks.environment."""

from statistics import median
from time import perf_counter
from timeit import repeat
import platform

from tetris_trainer.environment import PlacementEnvironment


def main():
    env = PlacementEnvironment(42)
    print(f'Python {platform.python_version()} on {platform.system()} {platform.machine()}; '
          f'seed=42; initial candidates={len(env.legal_actions())}')
    for label, operation, count in (
        ('reset including candidate enumeration', lambda: env.reset(42), 20),
        ('observe', env.observe, 1000),
    ):
        samples = repeat(operation, number=count, repeat=3)
        latency = median(samples) * 1000 / count
        print(f'{label}: {latency:.3f} ms; {1000 / latency:.1f}/s '
              f'(median of 3 batches of {count})')
    samples = []
    for _ in range(3):
        # Preparation is outside the timed region. Each step starts at the same
        # seeded state, executes row zero, and enumerates the next candidates.
        environments = [PlacementEnvironment(42) for _ in range(20)]
        start = perf_counter()
        for candidate_env in environments:
            candidate_env.step(candidate_env.legal_actions()[0])
        samples.append((perf_counter() - start) / len(environments))
    seconds = median(samples)
    print(f'step including authoritative validation and next enumeration: '
          f'{seconds * 1000:.3f} ms; {1 / seconds:.1f}/s (median of 3 batches of 20)')


if __name__ == '__main__':
    main()
