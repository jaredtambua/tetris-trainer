"""CPU architectural overhead, independent of untrained gameplay quality."""
import platform
from statistics import median
from timeit import repeat

import torch

from benchmarks.simulation import representative_game
from tetris_trainer.environment import PlacementEnvironment
from tetris_trainer.neural import NeuralAgent, PlacementPolicy, adapt_batch


def main():
    # Explicit benchmark-only thread setting avoids tiny-MLP oversubscription.
    torch.set_num_threads(1)
    torch.manual_seed(42)
    game = representative_game()
    env = PlacementEnvironment.from_game(game)
    sample = (env.observe(), env.legal_actions())
    single = adapt_batch([sample])
    environments = [PlacementEnvironment(seed) for seed in range(16)]
    samples = [(e.observe(), e.legal_actions()) for e in environments]
    batch = adapt_batch(samples)
    model = PlacementPolicy().eval()
    agent = NeuralAgent(model)
    def forward(tensors):
        with torch.no_grad():
            return model(tensors.states, tensors.candidates, tensors.mask)
    operations = (
        ('candidate_generation_cold', lambda: PlacementEnvironment.from_game(game), 20),
        ('candidate_getter_prepared', env.legal_actions, 1000),
        ('adapt_single', lambda: adapt_batch([sample]), 100),
        ('adapt_batch16', lambda: adapt_batch(samples), 100),
        ('forward_single', lambda: forward(single), 100),
        ('forward_batch16', lambda: forward(batch), 100),
        ('decision_prepared', lambda: agent.decide(env), 100),
        ('decision_with_generation', lambda: agent.decide(PlacementEnvironment.from_game(game)), 20),
    )
    print(f'CPU: Python {platform.python_version()}, {platform.system()} {platform.machine()}, '
          f'torch {torch.__version__}, threads={torch.get_num_threads()}, seed=42')
    print(f'Uneven-column active-T fixture; candidates={len(sample[1])}; '
          f'batch16 counts={[len(s[1]) for s in samples]}')
    for label, operation, count in operations:
        operation()  # warm model/runtime; generation still begins from uncached root
        ms = median(repeat(operation, number=count, repeat=3)) * 1000 / count
        print(f'{label}: {ms:.3f} ms (median of 3 x {count})')


if __name__ == '__main__':
    main()
