# Tetris Trainer

A minimal keyboard-playable Tetris vertical slice with a deterministic,
headless engine. **There is deliberately no gravity:** a piece stays in place
until an input moves it.

## Play

Python 3.11+ with Tk support is the only requirement. From the repository root:

```sh
make play
```

For a repeatable piece sequence, use `python -m tetris_trainer --seed 123`.

| Key | Action |
| --- | --- |
| Left / Right | Move horizontally |
| Down | Soft drop exactly one row |
| Space | Hard drop and lock |
| W | Rotate counter-clockwise |
| E | Rotate clockwise |
| Q | Rotate 180 degrees |
| R | Hold / swap |
| F5 | Restart with the same seed |

The window shows the 10×20 board, active and ghost pieces, hold, five upcoming
pieces, cleared-line count, and game-over state.

## Watch the baseline AI

```sh
python -m tetris_trainer --ai --seed 42
```

The same headless `BaselineAgent` chooses and applies final placements through
the existing engine and renderer. The default pause between decisions is 750 ms;
set `--ai-interval-ms 1200` for a slower pace. **P** pauses/resumes, **F5** restarts
with the same seed, and **Escape** closes. Movement/hold keys are ignored only
in AI mode; launching without `--ai` retains the human controls above. There is
no gravity or path animation. The left panel shows the latest decision's score,
features, and number of placements evaluated. Decisions run synchronously, so
Tk waits while a complete decision is computed; the interval is additional to
that computation time.

## Interpretable one-ply baseline

`tetris_trainer/baseline.py` owns feature extraction and decision logic. Neither
`Game` nor `Board` contains AI scores. For every legal placement the agent uses
`Game.simulate_placement()`, measures the resulting **post-clear** board, and
maximizes this deliberately simple, untuned integer formula:

```text
score = -5 * holes - aggregate_height - bumpiness + 10 * lines_cleared
```

- A hole is an empty visible cell below at least one occupied cell in its column.
  Every such cell counts, even if lateral access is possible.
- Column height is the distance from its highest occupied cell to the floor;
  an empty column has height zero. Aggregate height sums these heights.
- Bumpiness is the sum of absolute height differences between adjacent columns,
  without adding imaginary boundary columns.
- Lines cleared is the candidate's simulated total-line-count delta, provided by
  authoritative execution. Feature extraction does not implement line clearing.

Named constants define the four weights. Equal scores keep the first placement
in the engine's deterministic enumeration order. A frozen `Decision` exposes
`placement`, `score`, `features`, and `placements_evaluated`; no legal placements
returns `None`. Decisions do not mutate the supplied game or use keyboard inputs.

Run and inspect the same agent without importing Tk:

```python
from tetris_trainer import Game
from tetris_trainer.baseline import BaselineAgent, run_headless

game = Game(seed=42)
decision = BaselineAgent().decide(game)
if decision is not None:
    print(decision.score, decision.features)
    game.apply_placement(decision.placement)

summary = run_headless(seed=42, placement_limit=100)
print(summary.placements, summary.lines_cleared, summary.game_over, summary.stop_reason)
final_game = summary.game
```

`run_headless()` owns its seeded game and runs until the nonnegative integer
placement limit, game over, or no visible legal locks. `stop_reason` distinguishes
`limit`, `game_over`, and `no_legal_placements`; no locks can occur without the
engine's game-over flag under current top-out semantics. A zero limit returns
the initial state. The summary includes the independent final game for inspection.

This is a reference/debugging baseline for the AI pipeline, not the final learned
agent. It has no hold, queue-aware search, or depth beyond one. Terminal results
receive the same four-feature score, with no extra survival heuristic. Thus it
can choose a placement whose next spawn ends the game. Untuned weights and local
features cannot anticipate future traps. Learned policies and faster simulation
remain separate bounded work.

Benchmark a complete decision with `python -m benchmarks.baseline`. It uses the
same uneven-column, seed-42 active-T fixture as the simulation benchmark, reports
placements evaluated, and separately times extraction/scoring. Each timed
decision starts from a fresh clone without cached enumeration. Fresh BFS,
collision checks, and piece allocations dominate, while feature extraction is
small. Simulation safely reuses the same-state reachable-placement catalog.
Before hot-path optimization, on Python 3.13.0 / Windows AMD64, the median of five decisions
was 277.934 ms for 34 candidates; extraction plus scoring averaged 0.007 ms
per call (median of three 1,000-call batches). Timings depend on the machine
and board and are observations, not test thresholds.

## Develop

```sh
make test
make check
```

Future development follows [AGENTS.md](AGENTS.md) and the
[development workflow](docs/DEVELOPMENT_WORKFLOW.md). Consult the
[rules-status register](docs/TETRIO_RULESET.md) before changing mechanics;
implementation coverage alone does not confirm TETR.IO compatibility.
`make check` includes checks for these documents and their rule-status table.

The engine is usable without Tk or a display:

```python
from tetris_trainer import Action, Game

game = Game(seed=123)
game.apply(Action.MOVE_LEFT)
result = game.apply(Action.HARD_DROP)
```

The headless placement API enumerates final locks for the current active piece:

```python
placements = game.legal_placements()
if placements:
    result = game.apply_placement(placements[0])
```

`Placement` is an immutable value with `kind`, `orientation`, `x`, `y`, and
derived `cells`. It also retains a private originating-state snapshot. Applying
a stale, manually constructed, or currently unreachable placement returns an
unaccepted `Transition` without changing the game. Enumerate again after any
state change; hold remains a separate action. Choices from an identical seeded
game state can also be applied, since validation binds to state values.

Enumeration uses breadth-first search from the current active state through
left, right, down, clockwise, counter-clockwise, and 180-degree rotation. Both
human actions and search call the same engine movement/rotation helpers, which
use the existing collision rules and ordered SRS+ kicks. Visited states retain
`(kind, orientation, x, y)` because equal geometry can have different rotation
transitions. Grounded visible states are deduplicated by their sorted occupied
cells; fixed traversal order selects a representative and results are sorted by
orientation, x, and y. No paths are exposed. Execution validates reachable membership and
uses the existing engine lock, clear, queue, hold-reset, and top-out behavior.
Above-board lock attempts that would top out without writing cells are excluded.

For V reachable states, E manipulation edges, and P unique placements, search
costs O(V + E + P log P) time and O(V + P) space. There are six attempted edges
per state and a fixed number of kicks, so exploration is effectively O(V).
The current SRS+ tables cannot repeatedly climb above an empty board: wall-only
rotations choose horizontal kicks before vertical kicks. This makes exploration
finite without adding a gameplay ceiling; unusually high starting states add
extra rows to explore. Changes to kick data should revisit this property.

A pre-optimization 100-call empty-board T measurement averaged approximately 8.4 ms per
enumeration (34 placements; machine-dependent). Collision checks, candidate
allocation, and repeated exploration during placement validation are the main
hotspots. This is a useful correctness baseline for simulated games, but high
volume training will need representative throughput profiling before choosing
further optimizations. The engine now keeps one immutable reachable-placement
catalog per Game, guarded by the entire gameplay snapshot. Clones share this
derived metadata; a state mismatch triggers fresh enumeration and locking
releases it. Stale/invalid choices still require source equality and reachable
membership. No global cache, transposition table, or runtime dependency is added.

## Independent simulation

```python
branch = game.clone()
placements = game.legal_placements()
if placements:
    child = game.simulate_placement(placements[0])
    next_choices = child.legal_placements()
    if next_choices:
        grandchild = child.simulate_placement(next_choices[0])
```

`clone()` copies every current future-affecting engine field without running
game initialization or consuming a piece. Immutable board and active-piece
values are shared safely; each clone owns a separate randomizer, `random.Random`
instance, and queue deque. RNG `getstate()`/`setstate()` preserves the stream
exactly, including future bags, rather than restarting from a seed. Hold,
availability, total lines, game-over state, and the entire queued stream are
preserved. Identical state values allow root placements to execute on clones.
Board construction normalizes supplied rows to tuples, so mutable scenario
inputs cannot introduce aliasing into shared boards.

`simulate_placement()` returns an independent resulting `Game` directly and
raises `ValueError` for an invalid or stale choice without changing the source.
The prior metadata-returning API is now named `simulate_placement_result()`;
callers that need `.game` and `.transition` should use that method. It returns a
frozen `SimulationResult` containing an independent mutable `game` and immutable
`transition`. It calls the ordinary
`apply_placement()` path on that clone, including validation, locking, line
clearing, and next-piece preparation. The requested placement identifies the
placed piece; the resulting game exposes board, active piece, queue, and all
other state for inspection. An invalid or stale choice returns an unaccepted
transition and an unchanged independent clone through the metadata API.
Neither successful nor rejected simulation changes the source. The returned
game supports the same APIs for
further simulation. No evaluation or search policy is included.

Run `python -m benchmarks.simulation` for repeatable infrastructure benchmarks.
The fixture uses seed 42, an active T, and solid uneven columns of heights
`(2, 3, 2, 1, 0, 0, 1, 2, 3, 2)`. Local Python 3.13.0 on Windows AMD64
pre-optimization measurements (median of three
batches, machine-dependent) were:

| Operation | Time | Batch size |
| --- | ---: | ---: |
| Clone | 0.014 ms | 1,000 |
| Legal placement enumeration | 7.573 ms | 50 |
| Simulate one existing placement | 7.372 ms | 50 |
| Full two-ply expansion | 3,423.204 ms | 1 |

Each expansion enumerates and simulates all 34 children and 316 grandchildren.
It discards the resulting states after counting them, without evaluating or
ranking them. These measurements preceded bounded reuse of same-state
reachability results; current before/after evidence is linked below.
Immutable board sharing avoids matrix deep copies. Clone cost is O(Q + R)
for queue length Q and fixed-size RNG state R; simulation adds the existing
reachability and lock/clear costs. This is a baseline for correct branching,
but substantial lookahead workloads need profiling before further optimization.
When adding future engine state, update both `clone()` and `snapshot()`.

## Placement/simulation performance

See [the measured optimization report](docs/PLACEMENT_PERFORMANCE.md) for profiles,
before/after timings, allocation observations, and validation. Run
`python -m benchmarks.performance --output performance.json` to repeat the full
timing/profile/memory harness. It distinguishes fresh BFS from warm catalog
reuse and measures complete one-/two-ply workloads without changing AI policy.

## First-version rules boundary

Rotation reads the machine-readable TETR.IO-compatible SRS+ kick data in
`tetris_trainer/data/srs_plus.json`; the UI has no independent movement,
collision, rotation, locking, or line-clear implementation.

The repository supplied for this integration contained no prior rules or
workflow documents beyond an empty placeholder. Spawn and top-out therefore
use an explicitly **project-specific temporary rule**: pieces spawn in their
normal orientation at `(3, 0)`, and a blocked spawn or a lock with cells above
the visible matrix ends the game. Exact TETR.IO spawn-row and top-out parity is
deferred until an authoritative source is available. This does not alter board
collision or SRS+ rotation correctness.

Rendering is optional, actions are semantic and programmatic, RNG state is
simulation-owned and seedable, snapshots contain all future-affecting state,
and UI events never enter engine data. These boundaries keep the vertical slice
suitable for a later lightweight RL adapter without adding an RL dependency.
