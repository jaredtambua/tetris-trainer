# Placement and simulation performance

This bounded change preserves existing mechanics and decisions. No AI policy,
kick data, hold action space, or external rule status changes. The branch is
`perf/optimize-placement-simulation`, based on fetched `origin/main` at
`c185dd7b33fd6b172dffddfbd8c4fa6c1cabe6e6`. Local `main` remains unchanged at
`1619d0cef15229fb9b288fb341cb4bed996407df`.

## Reproducible workload

`python -m benchmarks.performance --output performance.json` runs uninstrumented
timings first, then separate cProfile and tracemalloc observations for each
operation. Saved [before](performance-before.json) and [after](performance-after.json)
reports use the same harness, runtime, and fixture: Python 3.13.0, Windows AMD64,
seed 42, active T, column heights `(2, 3, 2, 1, 0, 0, 1, 2, 3, 2)`.

Cold operations start from a fresh clone of a never-enumerated state; clone
overhead is included in both versions. Warm operations reuse an already
enumerated state. The full expansion starts cold and enumerates/simulates every
child and grandchild without scoring or ranking; it creates 34 children and 316
grandchildren in both versions. This is a benchmark workload, not new search
functionality. Timings are observations, not pass/fail thresholds.

## Profile before implementation

- One complete baseline decision called `legal_placements()` 35 times: one
  initial enumeration and one full rediscovery for each of 34 simulations.
  Enumeration accounted for 855.98 of 862.51 profiled milliseconds.
- The complete expansion called enumeration 385 times, with 6,405.94 of
  6,466.30 profiled milliseconds there. Only 35 distinct state graphs were
  necessary (root plus its 34 children).
- Fresh enumeration made 3,483 collision checks. Its 23.95 profiled milliseconds
  included 12.62 cumulative milliseconds in `_legal`, with `ActivePiece.cells`
  tuple construction, generators, movement/rotation candidates, and occupancy
  calls dominating. Cumulative times overlap; they must not be added together.
- Simulation after enumeration spent 24.66 of 24.84 profiled milliseconds
  rediscovering the graph, although its placement was already in a known set.

Profiling overhead makes these times larger than the uninstrumented latencies
below; compare profiled call counts and attribution rather than mixing timings.

## Two bounded optimizations

1. **One same-state reachable catalog per Game.** `legal_placements()` retains
   the immutable `(full_snapshot, ordered_placement_tuple)` it just computed.
   A subsequent call returns that tuple only if the current full snapshot is
   equal. Clones share the immutable metadata so simulations can validate
   against it; locking clears it. A mismatch causes fresh authoritative BFS.
   No global cache, transposition table, historical state collection, or custom
   AI engine is added. At most one catalog is held per Game; replacing it does
   not mutate a catalog shared with another clone.
2. **Avoid transient collision-coordinate tuples.** Authoritative `_legal()`
   iterates existing `CELLS` offsets and calls authoritative `Board.occupied()`
   directly. It preserves cell order and short-circuit rejection, including
   walls, floor, above-board positions, and blocked cells. No occupancy or kick
   rules are copied into another implementation. Absolute cells remain available
   for locking, rendering, and final-placement deduplication.

`apply_placement()` still checks type, originating full-state equality, and
membership in the authoritative reachable set. A forged/replaced pose does not
become valid just because it carries a genuine source snapshot. Full-state
guards cover direct public-field assignment as well as semantic actions,
queue consumption/refill, RNG draws, line count, hold, active pose, and game over.
The memo is derived implementation metadata and excluded from gameplay snapshots;
enumeration can populate it without changing future-affecting state. Equivalent
states can still exchange placements, matching existing value-based validation.

## Before/after benchmark

Medians from identical operations: three batches of 15 cold enumerations;
three batches of 50 warm enumerations/simulations; five complete cold decisions;
three complete cold expansions.

| Operation | Before (ms) | After (ms) | Speedup |
| --- | ---: | ---: | ---: |
| Fresh enumeration, including clone | 7.401 | 5.019 | 1.47× |
| Repeated enumeration of unchanged state | 7.663 | 0.013 | 610.89× |
| Simulate a placement after enumeration | 7.772 | 0.058 | 133.35× |
| Complete cold one-ply decision, 34 candidates | 276.556 | 7.427 | 37.24× |
| Complete cold two-ply expansion, 34 / 316 states | 2,189.585 | 152.198 | 14.39× |

The rounded warm latency is small, so its ratio is computed from raw JSON values.
It is catalog reuse, not a 610× faster fresh BFS. Benchmarks intentionally
distinguish these cases. Cold decision/expansion includes the initial BFS; it
does not hide that cost behind a warm root. Existing simulation and baseline
benchmark commands also label cold enumeration/decision appropriately.

## Memory and remaining costs

| Operation | Before traced peak (bytes) | After traced peak (bytes) |
| --- | ---: | ---: |
| Fresh enumeration | 260,092 | 118,460 |
| Simulation after enumeration | 260,092 | 28,692 |
| Complete cold decision | 323,016 | 118,460 |
| Complete cold expansion | 535,796 | 528,324 |

Fresh enumeration's profiled `ActivePiece.cells` calls fall from 3,551 to 68.
Removed temporary coordinate tuples/generators reduce allocation pressure; warm
validation avoids constructing entire visited sets and candidate graphs.
Tracemalloc peaks measure allocations during each operation and exclude objects
already present before tracing, including the warmed catalog. Retained-byte and
block counts in the JSON include allocator/free-list effects; they are not
cumulative counts of transient allocations or total lifetime heap usage.

The catalog retains one state snapshot and O(P) placements while a state is
enumerated; sharing avoids duplicating that catalog per simulation. The normal
lock clears it so future Game results do not unnecessarily retain parent boards.
There is a retained-memory tradeoff for long-lived enumerated games. The cold
two-ply peak is only about 1.4% smaller: this change substantially reduces work,
not the maximum footprint of that expansion.

Fresh BFS remains dominant when exploring distinct states: movement/rotation
candidate allocation, ordered kick attempts, collision checks, and visited-state
hashing. In the after-profile, the expansion still calls `legal_placements()`
385 times, but only 35 calls do BFS; the rest validate catalog reuse. Snapshot
construction/comparison and RNG copying remain visible costs of warm simulation.
No further optimization is justified in this bounded task.

## Correctness and review

Six regression tests cover catalog reuse, all future-affecting state invalidation,
forged unreachable choices, clone independence, collision equivalence, and exact
pre-change results. The fixture in `tests/data/placement_regressions.json` was
recorded before engine edits at the base revision above. It records ordered
placements, full gameplay/RNG-state digests for every simulation, and baseline
choices/scores across 13 empty/uneven/overhang/sealed/kick/line-clear scenarios.
It is regression evidence for the current engine, not external rules confirmation.

All 87 tests pass, including original reachability, recursive simulation,
headless agent, and visual adapter controls. Independent differential review
against the base revision checked 48 sequential states, 239 simulated children,
and 144 human actions; ordered placements, snapshots, scores, and decisions
matched. Independent full-suite and architecture/performance reviews passed.
Compilation and diff checks pass. No known unresolved correctness issues;
interactive visual playback was not manually rechecked, but the UI and policy
code are unchanged and their adapter tests pass.
