"""Comparable cold/warm timings and profiles; no engine instrumentation.

python -m benchmarks.performance --output docs/performance-before.json
Run before and after implementation using the same fixture and this harness.
"""

import argparse
import cProfile
import gc
import json
from pathlib import Path
import platform
import pstats
from statistics import median
from timeit import repeat
import tracemalloc

from benchmarks.simulation import representative_game, two_ply
from tetris_trainer.baseline import BaselineAgent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    pristine = representative_game()
    warmed = pristine.clone()
    placement = warmed.legal_placements()[0]
    agent = BaselineAgent()
    operations = (
        ('cold_enumeration', lambda: pristine.clone().legal_placements(), 15, 3),
        ('warm_enumeration', warmed.legal_placements, 50, 3),
        ('simulation_after_enumeration', lambda: warmed.simulate_placement(placement), 50, 3),
        ('cold_one_ply', lambda: agent.decide(pristine.clone()), 1, 5),
        ('cold_two_ply', lambda: two_ply(pristine.clone()), 1, 3),
    )
    report = {
        'environment': {'python': platform.python_version(), 'system': platform.system(),
                        'machine': platform.machine()},
        'fixture': {'seed': 42, 'active': 'T', 'heights': [2, 3, 2, 1, 0, 0, 1, 2, 3, 2]},
        'expansion': two_ply(pristine.clone()),
        'operations': {},
    }
    for name, operation, count, repeats in operations:
        samples = repeat(operation, number=count, repeat=repeats)
        latency = median(samples) * 1000 / count
        print(f'{name}: {latency:.3f} ms', flush=True)
        profiler = cProfile.Profile()
        profiler.runcall(operation)
        stats = pstats.Stats(profiler)
        top = sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)[:12]
        profile = [
            {'function': f'{Path(key[0]).name}:{key[1]}:{key[2]}',
             'calls': value[1], 'self_ms': value[2] * 1000, 'cumulative_ms': value[3] * 1000}
            for key, value in top
        ]
        gc.collect()
        tracemalloc.start()
        result = operation()
        retained, peak = tracemalloc.get_traced_memory()
        allocation_blocks = sum(stat.count for stat in tracemalloc.take_snapshot().statistics('filename'))
        tracemalloc.stop()
        del result
        report['operations'][name] = {
            'median_ms': latency, 'batch_size': count, 'repeats': repeats,
            'profile': profile, 'traced_retained_bytes': retained,
            'traced_peak_bytes': peak, 'retained_allocation_blocks': allocation_blocks,
        }
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Report: {args.output}', flush=True)


if __name__ == '__main__':
    main()
