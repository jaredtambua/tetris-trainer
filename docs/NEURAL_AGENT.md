# Neural placement foundation v2

This is an **UNTRAINED** policy/value model and data boundary, not a trained AI.
Install with `python -m pip install -e ".[ml]"`. PyTorch >=2.6,<3 is optional;
engine, environment, baseline and human UI imports do not import it. ML tests
require this extra (and skip explicitly when unavailable). The neural layer owns
no mechanics; environment contract v2 and engine rule statuses remain authoritative.

The [AI roadmap](AI_ROADMAP.md) owns the planned learning/search direction.
This foundation scores current-state placement descriptors and estimates V(s);
it does not simulate resulting afterstates as neural inputs, perform deep search,
or implement search supervision or RL fine-tuning. The planned afterstate model
is a future bounded task, not a description of this implementation.

## Tensor contract

`adapt_batch([(observation, issued_actions), ...], device='cpu')` copies public
environment data into `TensorBatch`. It never steps or edits the environment.
The batch must be nonempty; rows may have zero candidates for terminal values.

| Field | Shape | Dtype / meaning |
| --- | --- | --- |
| states | (B,929) | float32, same layout as environment v2 |
| candidates | (B,Nmax,5) | float32: piece, orientation, x, y, spin |
| mask | (B,Nmax) | bool, true for valid rows |
| actions | B tuples | original issued handles in supplied row order |

Board occupancy and binary flags stay 0/1. State piece IDs (active, hold,
five previews) divide by 7; active orientation divides by 3; active x by 10
and y by 20. Candidate rows divide by (7,3,10,20,2). These are scaled scalar
categorical IDs, not heuristic features or one-hot vectors. Signed coordinates
retain their sign and are not clipped: x rightward, y downward, bounding-box
origin, following the engine. Ordinary gameplay fits float32; arbitrary enormous
imported Python-int coordinates are not a lossless serialization contract.
Absent IDs remain zero. Tensor schema version is 2. Appended v2 garbage masks,
chain counters, rotation history and pending garbage fields remain raw float32
values. Version 1 observations and checkpoints are rejected; no migration or
trained-model compatibility is claimed.

Five-value descriptors include the authoritative spin class, distinguishing
lock outcomes with equal pose. Spin IDs are 0 none, 1 mini, 2 full.
Row positions are never neural inputs. Normal
callers pass `env.legal_actions()` unchanged, preserving engine order. The
adapter also preserves any supplied permutation; `batch.actions[b][i]` maps
output row i to its original handle. Handles expire on reset/step and cannot
be saved/reconstructed as executable actions. The environment validates them.

Padding is zero at the right end of each row. Nmax is the largest count in the
batch, without a global action-space ceiling. Explicit masks replace padded
logits with negative infinity. Softmax on a row with at least one valid candidate
assigns padding exactly zero probability. **Do not construct a categorical
distribution for an all-masked terminal row**: softmax there is undefined.
Terminal-only batches may have shape (B,0,5); value inference still works.
Training callers must filter terminal rows from policy losses/distributions.
The model does not pool candidates or infer state values from padding/counts.

## Model and inference

`PlacementPolicy(ModelConfig(hidden_size=64))` is an ordinary trainable
`torch.nn.Module`. A 929→64→64 ReLU MLP encodes state. Each candidate is
concatenated with the same state embedding and passed through a shared
69→64→1 ReLU scorer. A separate 64→1 linear head estimates V(s).
`forward(states, candidates, mask)` returns `PolicyOutput(logits, values)`
with shapes (B,Nmax) and (B,). Valid logits retain gradients; no algorithm,
loss, reward, handcrafted evaluation, or policy-position embedding is present.
Candidate permutations permute policy scores while leaving values unchanged.
This small architecture is a replaceable starting point, not a tuned choice.
Forward inputs must be finite float32 tensors on the model device, with a bool
mask on that device; the adapter supplies these dtypes. Device/dtype mismatches
use PyTorch's ordinary errors.

`NeuralAgent(model).decide(env, stochastic=False, generator=None)` returns a
`NeuralDecision` with issued action, row index, detached logits/probabilities,
selected-action log probability, value, and input batch. Argmax breaks exact
ties by first supplied row. Stochastic mode samples the categorical probabilities
using `torch.multinomial`; supply a seeded `torch.Generator` on the model's
device for reproducibility within the same runtime/device. CPU is sufficient.
Inference uses no gradients and does not change model mode, environment or RNG
except the supplied sampling stream (or torch's default stream if omitted).
There is no dropout or batch normalization. Selection rejects terminal states.
Only the caller invokes `env.step(decision.action)`.

## Rollout and checkpoint plumbing

`RolloutStep.capture(decision, reward=..., terminated=...,
next_observation=..., truncated=False)` retains detached cloned CPU state,
candidate rows, validity mask, selected row, behavior log probability, value,
external reward, next state, and separate termination/truncation flags.
Next state permits a future learner to bootstrap a time-limit boundary with its
own chosen policy. Caller owns temporal alignment, external reward meaning and
episode boundaries. Tensors are independent copies but remain mutable tensors;
do not mutate stored records. Executable handles and autograd graphs are not
retained in records. No returns, advantages, replay or optimizer is implemented.

`save_checkpoint(model,path)` stores a dictionary with format version 2,
tensor version 2, environment version 2, model config and state_dict.
`load_checkpoint(path,device='cpu')` reconstructs the architecture and strictly
loads parameters with `weights_only=True`. Version/schema/parameter mismatch
fails clearly. Checkpoints contain no optimizer/RNG/rollout/experiment state.
Use trusted local files; this is a small model format, not full training resume.

## Headless demonstration

```sh
python -m tetris_trainer.neural --seed 42 --placements 20
python -m tetris_trainer.neural --seed 42 --placements 20 --stochastic
python -m benchmarks.neural
```

`run_headless(seed=42, placement_limit=20, stochastic=False)` initializes a
seeded untrained model with isolated torch initialization RNG, owns a seeded
environment, selects issued actions and steps authoritatively until terminal
or the nonnegative integer limit. Zero placements is supported. `DemoResult`
reports placement count, final observation, termination and stop reason.
This bounded inference loop measures architecture, not AI quality. Visual UI
integration is deferred: the existing UI's Game/baseline interface differs
from the environment-handle boundary; baseline/human playback stays intact.

## Historical v1 CPU performance observations

Python 3.13.0, Windows AMD64, torch 2.9.1+cpu, one torch intra-op thread;
median of three batches, warmed tensor runtime. No CUDA measured or required.
Uneven-column seed-42 active-T fixture: 34 candidates. Batch16 uses empty-board
seeds 0–15 with counts 9–34. Generation begins from an uncached source Game.

| Operation | ms |
| --- | ---: |
| Cold environment preparation including candidate generation | 5.209 |
| Single adaptation | 0.102 |
| Batch16 adaptation | 0.497 |
| Single forward, no gradients | 0.072 |
| Batch16 forward, no gradients | 0.134 |
| Prepared complete decision, excluding transition | 0.258 |
| Decision including cold environment preparation | 5.528 |

Prepared action retrieval rounds to 0.000 ms; it performs no search. Generation
timing includes cloning/environment setup, which is required to prepare actions.
Single/adapt/forward/decision batches are 100 calls; cold preparation is 20;
getter is 1,000. Benchmark sets one thread only in its process; library does not
change caller thread settings. Tiny MLP thread overhead and machine configuration
can affect timings. These are observations, not thresholds or training estimates.
Existing simulation: cold/warm enumeration 5.040/0.011 ms, clone 0.014 ms,
simulation 0.049 ms, two-ply 140.622 ms (34 children, 316 leaves).

## Deferred decisions and limitations

The roadmap sets the qualitative versus objective and search-supervised path;
exact reward implementation and RL fine-tuning algorithm (including whether PPO
is used) remain undecided. Advantage/return calculation, truncation
policy, optimizer, architecture tuning, categorical embeddings, recurrent memory,
learned hold and hardware choice are future tasks. Preview-limited environment
observations remain partially observable. No model-quality claims follow from
untrained inference. Tensor conversion performs small allocations per decision;
measure actual training workloads before adding optimization infrastructure.
Stochastic reproducibility across PyTorch versions/devices is not promised.
See [RL_ENVIRONMENT.md](RL_ENVIRONMENT.md) and
[TETRIO_RULESET.md](TETRIO_RULESET.md) for current contracts/rule uncertainty.
