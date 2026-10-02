# Versus foundation handoff

TASK: Implement the bounded, authoritative own-board versus-mechanics foundation.

SCOPE: Clear/Spin facts, combo/B2B/Surge attack, garbage identity, explicit pending
events, ordinary cancellation, capped insertion, deterministic simulation and
factual environment integration. No opponent, search, reward, training, network,
gravity, package restructuring, commit, push or PR.

Acceptance criteria: one authoritative engine; immutable factual results;
source-backed selected external rules; all future-affecting state in clone and
snapshot; full-snapshot catalog validation; atomic stale/forged rejection;
independent deterministic tests/review; complete checks and measured hot paths.

RULE RESEARCH: Official client retrieved 2026-10-02, engine version 19, SHA-256
and inspection selectors recorded in [VERSUS_MECHANICS.md](VERSUS_MECHANICS.md).
The ignored research copy is under artifacts/rules/. Official patch notes establish
the relevant changes; secondary descriptions were checked against current source.
Tests establish local implementation correctness, not independent external parity.

CONFIRMED RULES: Current TL attack/Mini tables, combo multiplier/minimum/DOWN
rounding, All Clear addition and B2B eligibility, charge/Surge total, garbage-clear
bonus, rotation-time All-Mini+ flags, fifth-kick upgrade including 180, hard-drop
flag retention, ordinary cancellation eligibility/order, cap-eight ready insertion
and clear blocking. See the evidence register for precise boundaries.

TO VERIFY / OMITTED RULES: Existing geometry/kick-table, spawn and exact top-out
parity remain unverified. Live activation/travel clocks, opener double cancellation,
Clutch Clear, Surge packet segmentation and alternate room profiles are omitted.

ARCHITECTURE: Game remains the sole mechanics orchestrator. Board retains one
immutable cell matrix with an enum garbage sentinel. versus.py contains immutable
values and pure attack arithmetic; environment/neural consume factual contracts.

VERSUS STATE ADDED: Combo and displayed B2B counters; immutable pending events;
rotation amount, ordered kick index and retained rotation-time Spin flag. Board
garbage identity lives in occupancy. All are cloned, snapshotted and simulated.

CLEAR / SPIN CLASSIFICATION: ClearEvent reports piece, original cleared rows,
Spin/Mini, All Clear, garbage rows removed and termination. Rotation witnesses
include instant hard-drop outcomes and distinct Spin results for equal cells.
Legacy canonical geometries retain their order; additional outcomes follow.

COMBO / B2B: Consecutive clear counter; no-clear combo reset/B2B preservation;
difficult continuation and All Clear increments; ordinary break and Surge release.
Surge charge is derived from the B2B counter, with no redundant mutable state.

ATTACK: Pure deterministic source-backed tables/formula, including universal Mini
values, All Clear outside combo multiplication and flat garbage-clear bonus.

GARBAGE REPRESENTATION: GarbageCell.GARBAGE occupies the existing Board cells.
Mixed full rows count once as garbage lines; insertion preserves identity and
reports visible occupancy overflow. No duplicate board or per-cell objects.

CANCELLATION / INSERTION: FIFO ordinary 1:1 cancellation includes unready damage;
partial events retain hole suffix/order. Excess attack is outgoing. On a non-clear,
scan ready events in order and insert at most eight rows, retaining unready packets
and capped suffixes. Supplied holes/readiness introduce no new random generator.

TRANSITION / ENVIRONMENT METADATA: Transition and environment facts expose the
same immutable ClearEvent. Environment contract v2 has 929 integers and five-value
placement descriptors including Spin ID. Neural tensor/checkpoint versions are 2;
old versions fail explicitly. Only necessary state/action input sizes changed.

FILES CHANGED:

- src/tetris_trainer/board.py: garbage sentinel, insertion and detailed clears.
- src/tetris_trainer/engine.py: authoritative state, history, resolution and witnesses.
- src/tetris_trainer/versus.py: immutable facts and pure attack calculation.
- src/tetris_trainer/environment.py and neural.py: mechanical contract v2 migration.
- src/tetris_trainer/ui.py and __init__.py: garbage rendering and public fact exports.
- tests/test_garbage_board.py, test_versus.py and test_versus_environment.py: new coverage.
- tests/test_environment.py, test_neural.py, test_packaging.py and
  test_placement_performance.py: contract/cache/legacy regression checks.
- AGENTS.md, README.md, docs/AI_ROADMAP.md, TETRIO_RULESET.md, RL_ENVIRONMENT.md,
  NEURAL_AGENT.md, VERSUS_MECHANICS.md and this handoff: architecture/evidence/contracts.

TESTS ADDED: Independent attack and counter fixtures; rotation-time flags versus
changed lock geometry; genuine quarter-turn/180 fifth-kick cases; human witness
replay; separate history-aware reachability graph; garbage identity/order/partial
cancellation/cap/overflow; simulation isolation; all new snapshot fields and stale
catalog handling; observation/descriptor distinction and old-checkpoint rejection.

VALIDATION: Editable .[ml] installed in repository .venv. Make is unavailable;
documented equivalent unittest discovery and compileall pass, including all neural
tests. 160 tests pass. git diff --check passes; conflict-marker scan finds none.
Simulation, baseline, performance, environment and neural benchmarks all run.
No generated research, training, build or checkpoint artifact is in the diff.

PERFORMANCE: Python 3.13.0, Windows AMD64, seed 42, active T, column heights
[2,3,2,1,0,0,1,2,3,2]. Same-session performance harness medians:

| Operation | Before | After |
| --- | ---: | ---: |
| Cold enumeration | 6.198 ms | 11.706 ms |
| Warm enumeration | 0.015 ms | 0.013 ms |
| Simulation after enumeration | 0.075 ms | 0.066 ms |
| Cold one-ply | 9.703 ms | 15.649 ms |
| Cold two-ply | 201.043 ms | 337.968 ms |

Branches increase from 34 children/316 leaves to 36/334 due to distinct Spin
outcomes. Cold traced peak increases 118,460 to 431,468 bytes; simulation peak
28,692 to 28,996 bytes. Rotation-time classification dominates added cold cost
(1,686 calls, 10.464 ms under profiling). Predecessor links replace copied BFS
paths and reconstruct witnesses only for final outcomes. Final simulation harness
reports clone 0.014 ms, cold 11.223 ms, warm 0.010 ms, simulation 0.059 ms and
two-ply 309.079 ms. These are workload evidence, not timing thresholds.

Environment observe is 0.026 ms. Neural CPU (torch 2.14.1+cpu, one benchmark
thread) adaptation is 0.126 ms, single forward 0.064 ms and prepared decision
0.307 ms. Raw profile reports remain ignored under artifacts/versus-{before,after}.json.

REGRESSIONS: Legacy geometry/order/board simulation and baseline-choice fixtures
pass without replacing the historical expected data. New Spin outcomes are checked
separately by exhaustive history-aware fixtures. Material cold throughput and
allocation regression remains, explicitly measured above; warm simulation is stable.

ASSUMPTIONS: Existing visible-board mechanics are preserved. The environment
supplies hole columns and readiness instead of live clocks. Pending capacity is
an explicit local 256-row limit so the fixed numerical contract never truncates.
Ordinary 1:1 cancellation excludes opening/margin modifiers.

UNRESOLVED: Full live TL/replay parity is outside this foundation for the listed
omissions and existing geometry/spawn/top-out gaps. Cold classification/witness
overhead is a measured future optimization concern. No pending correctness finding.

REVIEW NOTES: Independent testing/review covered all changed subsystems. Found and
fixed geometry-only neural candidate ambiguity by adding Spin ID; retained original
geometry ordering; updated warm-cache test to patch the actual rotation helper;
used independent graph and semantic replays to verify predecessor witnesses.
Final independent full suite, compilation and diff check pass. Performance review
explicitly reports the cold cost instead of introducing speculative caches/native code.

GIT STATUS: Current local main; all task-owned changes unstaged and uncommitted.
Initial tracked working tree was clean; no unrelated tracked changes were found.
No branch, commit, push, merge or pull request was created.

SUGGESTED COMMIT MESSAGE: feat: add authoritative versus and garbage mechanics

READY FOR HUMAN REVIEW: YES
