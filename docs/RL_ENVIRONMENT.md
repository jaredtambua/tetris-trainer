# Placement environment contract v1

`tetris_trainer.environment.PlacementEnvironment` is a headless, framework-free
boundary around the authoritative Game. It owns its game; no Game reference,
rendering, heuristic features, reward policy, or learning algorithm is part of
the observation contract. All existing project rules apply unchanged; see
[TETRIO_RULESET.md](TETRIO_RULESET.md). No TO VERIFY behavior is resolved here.

```python
from tetris_trainer.environment import PlacementEnvironment

env = PlacementEnvironment(seed=42)  # initialized and ready
observation = env.reset(seed=42)     # explicit reset is also supported
candidates = env.legal_actions()
# A future policy may score rows [candidate.values for candidate in candidates].
# This example selects row zero only to illustrate the API, not a policy.
if candidates:
    transition = env.step(candidates[0])
    next_observation = transition.observation
    next_candidates = env.legal_actions()
    facts = transition.facts
```

## Numerical observation

`observe()` and `reset()` return an immutable Python `tuple[int, ...]` of length
**212**. There are no Python objects or Game internals inside the vector. The
module exports `CONTRACT_VERSION = 1`, layout slices, `OBSERVATION_SIZE`,
`BOARD_SHAPE`, `QUEUE_LENGTH`, and a read-only `PIECE_IDS` mapping.

| Indices | Shape / contents | Encoding |
| --- | --- | --- |
| 0:200 | Board flattened from (20, 10) | 0 empty, 1 occupied; piece colors/types are omitted |
| 200:204 | Active (piece, orientation, x, y) | Piece ID, orientation 0–3, signed bounding-box coordinates |
| 204:206 | Hold (piece, available) | Piece ID and 0/1 availability flag |
| 206:211 | Next five pieces | Piece IDs in next-to-spawn order |
| 211 | Episode terminated | 0 continuing, 1 terminated |

Piece IDs are explicit: **0 absent; 1 I; 2 J; 3 L; 4 O; 5 S; 6 T; 7 Z**.
Orientations are the existing SPAWN=0, RIGHT=1, REVERSE=2, LEFT=3. An absent
active piece encodes `(0, 0, 0, 0)`; ID zero disambiguates absence from a real
spawn pose. Empty hold is zero. The hold flag is one only when an active piece
exists, hold has not been used, and neither engine nor environment is terminal;
it describes potential hold eligibility, not an available action in v1.

Board indexing is `flat[y * 10 + x]`: x increases right; y increases downward
from the top visible row (0) to the floor row (19). No hidden rows are stored in
the board vector. Active pose can have negative x/y according to engine geometry.
Pose coordinates are bounding-box origins, not an occupied-cell corner.

The representation contains exact integer values, without normalization or
one-hot encoding. A later tensor adapter can use signed int32 for ordinary
engine states (int64 if imported scenario coordinates exceed int32), and can
cast/encode categorical fields or convert to floating-point at the model boundary.
Do not use an unsigned dtype for the entire vector because coordinates can be
negative. Python ints have no fixed storage dtype; no array/tensor dependency is
required here. Layout changes require a new contract version.

Normal gameplay maintains at least five queued pieces. For imported scenarios
with a shorter queue, missing slots are padded with zero; observing never refills
the queue or consumes RNG. Queued pieces beyond five, the hidden bag contents,
and RNG state remain private. Thus this is a preview-limited observation, not a
claim of full Markov-state visibility. Total lines and step count are available
as transition facts rather than handcrafted input features.

## Variable placement actions

`legal_actions()` returns an immutable ordered tuple of frozen `PlacementAction`
objects. Each exposes:

- `index`: its current policy row, from 0 through N-1;
- `values`: a four-int row `(piece_id, orientation, x, y)`.

Stacking those rows gives shape **(N, 4)**, with the same integer encodings as
the active pose. N varies because the current board/pose changes which final
locks are reachable. Rows correspond exactly to `Game.legal_placements()` in
engine order, with its deduplication by occupied cells. No unreachable poses
are inserted to create a fixed action space. No keyboard actions are exposed.

A policy can score N rows and submit `env.step(candidates[selected_index])`.
`step(0)` is intentionally rejected: a raw integer cannot carry stale-state
protection. Use only the issued object, not a reconstructed/copy/serialized
descriptor. Private fields bind that handle to its engine Placement and this
specific environment decision. Actions expire after every successful step or
reset, even a reset with the same seed. Cross-instance and replaced/forged
objects are rejected. Candidate equality describes numerical rows; equality
alone does not confer permission to execute in another environment.

The environment prepares candidates on reset and after a successful step.
Repeated observation/action getters perform no gameplay mutation, queue refill,
or reachability search. `from_game(game)` clones an existing engine scenario;
subsequent source/environment mutations are independent. Direct editing of
private environment state is unsupported. Reset/step are single-threaded calls;
there is no concurrency or process-sharing contract for handles.

## Step, termination, and reward boundary

`step(action)` validates the current issued handle and then invokes authoritative
`Game.apply_placement()`, retaining its full-state/reachability validation.
Normal locking, line clearing, hold reset, RNG/queue advancement, and next-piece
spawn occur in that one engine. There is no teleportation or mechanics adapter.

Invalid, stale, foreign, or terminal actions raise `ValueError` without changing
gameplay state, current candidates, or step count. A successful step returns a
frozen `StepResult` with:

- `observation`: the next 212-int vector;
- `terminated`: whether this placement-only episode has ended;
- `facts`: frozen `TransitionFacts` containing `placed` (the chosen four-int
  row), `locked`, `lines_cleared` for this step, `total_lines`, engine `game_over`,
  `terminal_reason`, and episode `step_count` (one-based after stepping).

Termination is engine game over **or** absence of visible legal lock placements.
`terminal_reason` is `game_over`, `no_legal_placements`, or `None`. The latter
terminal condition can occur in an imported above-board scenario without the
engine's game-over flag; the environment does not change that flag or invent an
engine top-out rule. Terminal candidates are empty; reset begins a new episode.
There is no built-in placement limit, truncation policy, or training loop.

No `reward` field or default heuristic is supplied. A future reward function
consumes facts and the previous/next observations in a separate component. It
can use authoritative cleared lines, termination reason, total lines, chosen
piece/pose, and observed board changes. This task neither defines weights nor
adds attack, spin, combo, or B2B facts that the engine does not implement.

## Hold extension

Hold state and eligibility are already observed. V1 actions operate solely on
the current active piece. A future bounded extension can add a tagged action
kind (placement versus hold) with decision-scoped handles, or compare placements
on an authoritative held-game branch. It can reuse reset/step/facts boundaries
and existing engine hold behavior, versioning any changed row schema. V1 does
not execute hold or rank held-piece alternatives.

## Validation and performance

`tests/test_environment.py` checks shape/coordinates/encodings, deterministic
reset and action order, correspondence to engine placements, authoritative step
equivalence, stale/invalid rejection, termination, instance isolation, and
subprocess operation without Tk. It checks observing a short queue has no refill
side effect. The complete existing suite remains required.

Run `python -m benchmarks.environment` for reset/observe/step timings. Reset
includes candidate enumeration. Timed steps start from identical seed-42 games,
execute row zero, validate through the engine, and enumerate next-state candidates;
initial environment preparation is outside the timed region. Each operation
uses a median of three batches (20 resets/steps or 1,000 observations). This is
an overhead check, not a performance target or justification for optimization.

Local Python 3.13.0 / Windows AMD64 measurements with 34 initial candidates:
reset 8.544 ms (117.0/s), step 14.250 ms (70.2/s), and observe 0.016 ms
(approximately 64,405/s). Throughput ratios use unrounded timings. Enumeration
and authoritative reachability validation dominate; the numerical encoding adds
little overhead. Results are machine/state-dependent and are not test thresholds.

This branch was created from fetched `origin/main` at `c185dd7`; the separate
performance commit `debbdb6` was not on origin/main and is not imported here.
The current engine therefore re-enumerates during placement validation. Future
integration of engine optimizations needs no environment contract redesign.
