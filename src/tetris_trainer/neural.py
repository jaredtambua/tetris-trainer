"""Optional PyTorch placement policy/value foundation; no gameplay or rewards."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Sequence

import torch
from torch import Tensor, nn

from .environment import (CONTRACT_VERSION, OBSERVATION_SIZE, PLACEMENT_SIZE, Observation,
                          PlacementAction, PlacementEnvironment)

TENSOR_VERSION = 2
CHECKPOINT_VERSION = 2


@dataclass(frozen=True)
class TensorBatch:
    states: Tensor
    candidates: Tensor
    mask: Tensor
    actions: tuple[tuple[PlacementAction, ...], ...]


def adapt_batch(samples: Sequence[tuple[Observation, Sequence[PlacementAction]]],
                *, device: str | torch.device = 'cpu') -> TensorBatch:
    """Copy public contract v2 rows; retain issued handles in exactly row order."""
    if not samples:
        raise ValueError('batch must contain at least one observation')
    actions = tuple(tuple(rows) for _, rows in samples)
    for observation, _ in samples:
        if len(observation) != OBSERVATION_SIZE:
            raise ValueError(f'expected environment v2 observation of length {OBSERVATION_SIZE}')
    states = torch.tensor([obs for obs, _ in samples], dtype=torch.float32, device=device)
    # Preserve the original prefix scaling; appended factual fields remain raw.
    states[:, [200, 204, 206, 207, 208, 209, 210]] /= 7
    states[:, 201] /= 3
    states[:, 202] /= 10
    states[:, 203] /= 20
    count = max(map(len, actions))
    candidates = torch.zeros((len(samples), count, PLACEMENT_SIZE), dtype=torch.float32, device=device)
    mask = torch.zeros((len(samples), count), dtype=torch.bool, device=device)
    for i, rows in enumerate(actions):
        if rows:
            candidates[i, :len(rows)] = torch.tensor([row.values for row in rows],
                                                    dtype=torch.float32, device=device)
            mask[i, :len(rows)] = True
    candidates /= torch.tensor([7, 3, 10, 20, 2], dtype=torch.float32, device=device)
    if not torch.isfinite(states).all() or not torch.isfinite(candidates).all():
        raise ValueError('tensor representation must be finite')
    return TensorBatch(states, candidates, mask, actions)


@dataclass(frozen=True)
class ModelConfig:
    hidden_size: int = 64

    def __post_init__(self):
        if type(self.hidden_size) is not int or self.hidden_size <= 0:
            raise ValueError('hidden_size must be a positive integer')


@dataclass(frozen=True)
class PolicyOutput:
    logits: Tensor
    values: Tensor


class PlacementPolicy(nn.Module):
    """Shared row scorer is permutation equivariant; value depends only on state."""
    def __init__(self, config: ModelConfig = ModelConfig()):
        super().__init__()
        self.config = config
        h = config.hidden_size
        self.encoder = nn.Sequential(nn.Linear(OBSERVATION_SIZE, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU())
        self.scorer = nn.Sequential(nn.Linear(h + PLACEMENT_SIZE, h), nn.ReLU(), nn.Linear(h, 1))
        self.value_head = nn.Linear(h, 1)

    def forward(self, states: Tensor, candidates: Tensor, mask: Tensor) -> PolicyOutput:
        if (states.ndim != 2 or states.shape[1] != OBSERVATION_SIZE or candidates.ndim != 3
                or candidates.shape[0] != states.shape[0] or candidates.shape[2] != PLACEMENT_SIZE
                or mask.shape != candidates.shape[:2] or mask.dtype != torch.bool):
            raise ValueError(f'expected states [B,{OBSERVATION_SIZE}], candidates [B,N,{PLACEMENT_SIZE}], bool mask [B,N]')
        embedding = self.encoder(states)
        expanded = embedding[:, None, :].expand(-1, candidates.shape[1], -1)
        logits = self.scorer(torch.cat((expanded, candidates), dim=-1)).squeeze(-1)
        return PolicyOutput(logits.masked_fill(~mask, -torch.inf),
                            self.value_head(embedding).squeeze(-1))


@dataclass(frozen=True)
class NeuralDecision:
    action: PlacementAction
    index: int
    logits: Tensor
    probabilities: Tensor
    log_probability: float
    value: float
    batch: TensorBatch


class NeuralAgent:
    def __init__(self, model: PlacementPolicy):
        self.model = model

    def decide(self, environment: PlacementEnvironment, *, stochastic: bool = False,
               generator: torch.Generator | None = None) -> NeuralDecision:
        device = next(self.model.parameters()).device
        batch = adapt_batch([(environment.observe(), environment.legal_actions())], device=device)
        if not batch.actions[0]:
            raise ValueError('cannot choose an action in a terminal environment')
        # No dropout/batch normalization: inference does not change model mode or buffers.
        with torch.no_grad():
            output = self.model(batch.states, batch.candidates, batch.mask)
            logits = output.logits[0]
            log_probs = torch.log_softmax(logits, dim=0)
            probabilities = log_probs.exp()
            index = int(torch.multinomial(probabilities, 1, generator=generator).item()
                        if stochastic else logits.argmax().item())
        return NeuralDecision(batch.actions[0][index], index, logits.detach().clone(),
                              probabilities.detach().clone(), float(log_probs[index]),
                              float(output.values[0]), batch)


@dataclass(frozen=True)
class RolloutStep:
    """Detached CPU snapshot; caller supplies reward and termination/truncation."""
    state: Tensor
    candidates: Tensor
    mask: Tensor
    selected_index: int
    log_probability: float
    value: float
    reward: float
    terminated: bool
    truncated: bool
    next_state: Tensor

    @classmethod
    def capture(cls, decision: NeuralDecision, *, reward: float, terminated: bool,
                next_observation: Observation, truncated: bool = False) -> RolloutStep:
        import math
        if not all(math.isfinite(x) for x in (reward, decision.log_probability, decision.value)):
            raise ValueError('rollout scalars must be finite')
        copy = lambda tensor: tensor.detach().cpu().clone()
        next_state = adapt_batch([(next_observation, ())]).states[0]
        return cls(copy(decision.batch.states[0]), copy(decision.batch.candidates[0]),
                   copy(decision.batch.mask[0]), decision.index, decision.log_probability,
                   decision.value, float(reward), bool(terminated), bool(truncated), next_state)


def save_checkpoint(model: PlacementPolicy, path: str | Path) -> None:
    torch.save({'format_version': CHECKPOINT_VERSION, 'tensor_version': TENSOR_VERSION,
                'environment_version': CONTRACT_VERSION, 'config': asdict(model.config),
                'state_dict': model.state_dict()}, path)


def load_checkpoint(path: str | Path, *, device: str | torch.device = 'cpu') -> PlacementPolicy:
    payload = torch.load(path, map_location=device, weights_only=True)
    if not isinstance(payload, dict):
        raise ValueError('invalid neural checkpoint: expected a dictionary')
    try:
        if (payload['format_version'] != CHECKPOINT_VERSION
                or payload['tensor_version'] != TENSOR_VERSION
                or payload['environment_version'] != CONTRACT_VERSION):
            raise ValueError('incompatible checkpoint version')
        model = PlacementPolicy(ModelConfig(**payload['config'])).to(device)
        model.load_state_dict(payload['state_dict'], strict=True)
    except (KeyError, TypeError, RuntimeError) as error:
        raise ValueError('invalid or incompatible neural checkpoint') from error
    return model


@dataclass(frozen=True)
class DemoResult:
    placements: int
    terminated: bool
    stop_reason: str
    observation: Observation


def run_headless(*, seed: int = 42, placement_limit: int = 20,
                 stochastic: bool = False) -> DemoResult:
    if type(placement_limit) is not int or placement_limit < 0:
        raise ValueError('placement_limit must be a nonnegative integer')
    # Isolate initialization RNG from the caller's global torch stream.
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = PlacementPolicy()
    generator = torch.Generator().manual_seed(seed)
    env = PlacementEnvironment(seed)
    agent = NeuralAgent(model)
    count = 0
    while count < placement_limit and not env.terminated:
        decision = agent.decide(env, stochastic=stochastic, generator=generator)
        env.step(decision.action)
        count += 1
    return DemoResult(count, env.terminated,
                      env.terminal_reason if env.terminated else 'limit', env.observe())


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='UNTRAINED neural headless architecture demo')
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--placements', type=int, default=20)
    parser.add_argument('--stochastic', action='store_true')
    args = parser.parse_args()
    result = run_headless(seed=args.seed, placement_limit=args.placements,
                          stochastic=args.stochastic)
    print(f'UNTRAINED: placements={result.placements}, terminated={result.terminated}, '
          f'stop_reason={result.stop_reason}')
