# Rules status and evidence

This register separates the current project's behavior from verified TETR.IO
compatibility. Preserve working behavior unless a bounded task explicitly
changes it. A status describes evidence or project scope, not test pass/fail.

## Status vocabulary

- **CONFIRMED:** external TETR.IO behavior supported by attributable evidence.
  Record the source, applicable mode/version/date, a precise statement, and a
  testable compatibility case. Current code or tests alone are insufficient.
- **TO VERIFY:** external compatibility lacks sufficient recorded evidence.
  The implementation can remain a baseline without claiming parity.
- **INTENTIONALLY OMITTED:** excluded from current project scope; this does not
  imply the mechanic is absent from TETR.IO.
- **PROJECT-SPECIFIC:** an explicit local rule or architectural decision;
  external TETR.IO parity is not claimed.

## Current mechanic register

Keep the Status column in this table to exactly one of the four labels above.
The unittest document check validates required rows and this vocabulary.

| Mechanic | Status | Current implementation / evidence boundary |
| --- | --- | --- |
| Board dimensions / hidden rows | TO VERIFY | `board.py`: 10 columns, 20 stored visible rows; no stored hidden rows. Above-board cells are collision-free within horizontal bounds, with no upper ceiling. External dimensions/hidden-row parity needs evidence. |
| Tetromino geometry | TO VERIFY | `pieces.py`: explicit four orientations in SRS bounding boxes; O geometry is unchanged across orientations. No cited TETR.IO geometry verification is recorded. |
| SRS+ rotations and kicks | TO VERIFY | `engine.py` uses the ordered `data/srs_plus.json` tables for CW, CCW, and 180 rotations; y-up kick offsets are negated for board coordinates. O changes orientation without kicks. The JSON calls the tables verified, but gives no attributable source, version, or verification record. Preserve this data; external parity, especially 180 transitions and ordering, remains unverified in this register. |
| Spawn behavior | PROJECT-SPECIFIC | Normal orientation at bounding-box position (3, 0), including hold spawn. README identifies this as temporary; exact TETR.IO spawn rows/positions are TO VERIFY. |
| Top-out / game-over behavior | PROJECT-SPECIFIC | A colliding spawn ends the game. A lock attempt containing cells above row zero ends the game without partial board writes. A visible lock may end the game when the next spawn collides. Exact external top-out conditions are TO VERIFY. |
| Seven-bag randomizer | TO VERIFY | `BagRandomizer` shuffles complete seven-piece bags with an owned seeded Python RNG. Queue and RNG state are copied exactly for clones. Tests establish local bags and reproducibility; external RNG distribution/sequence parity is not established or promised. |
| Hold | TO VERIFY | Empty hold consumes the next piece; populated hold swaps. Spawn pose resets; one accepted hold per lock; successful lock re-enables hold. Existing tests establish local behavior, not external hold/top-out parity. |
| Soft drop | PROJECT-SPECIFIC | One semantic action moves down exactly one row if legal; blocked soft drop does not lock. There is no time-based descent. TETR.IO timing/rates are TO VERIFY and outside current scope. |
| Hard drop | TO VERIFY | Descends to the lowest position reachable vertically from the current pose, then uses authoritative lock/clear/spawn. External timing/top-out parity is unverified. |
| Line clearing | TO VERIFY | All complete visible rows are removed together; remaining rows retain order and empty rows are prepended. Total cleared lines accumulates. Tests confirm local single/multiple clears; no external compatibility source is recorded. |
| Gravity | INTENTIONALLY OMITTED | No tick/update-driven movement. Time passing cannot change engine state; inputs alone move pieces. |
| Lock delay | INTENTIONALLY OMITTED | No timer, automatic grounded locking, or reset counter. Hard drop or validated placement execution invokes locking. |
| Attack | CONFIRMED | Current-client attack constants, multiplier/max floor, additive All Clear and flat garbage-clear bonus implemented; see [versus evidence](VERSUS_MECHANICS.md). Full match timing/alternate profiles are excluded. |
| Garbage | PROJECT-SPECIFIC | Immutable cell tuples with a GarbageCell sentinel; explicit holes/readiness, FIFO ordinary 1:1 cancellation and cap-eight no-clear insertion. Current-client evidence confirms cancellation eligibility, cap and clear blocking; queue capacity, readiness and visible overflow are local boundaries. See [versus evidence](VERSUS_MECHANICS.md). |
| Combos | CONFIRMED | Consecutive clears increment; no-clear resets. Current client AnnounceLines uses multiplier plus logarithmic minimum and DOWN rounding. See [versus evidence](VERSUS_MECHANICS.md). |
| Back-to-back | CONFIRMED | Current TL charging profile: difficult clears and All Clears increment, ordinary clears break, no-clear preserves; displayed count four charges Surge. Aggregate Surge recorded, packet segmentation omitted. See [versus evidence](VERSUS_MECHANICS.md). |
| Spin detection / scoring | CONFIRMED | Current-client All-Mini+ classifications use authoritative rotations, stored rotation-time Spin flags, T corners/kick upgrade and immobile Mini fallback. Failed moves preserve flags; horizontal/soft-drop movement invalidates; hard drop preserves. Full geometry/kick-table parity remains TO VERIFY. See [versus evidence](VERSUS_MECHANICS.md). |
| Opponent simulation | INTENTIONALLY OMITTED | No opponent state or mechanics. |

Current INTENTIONALLY OMITTED statuses describe today's scope, not permanent
roadmap exclusions. Own-state versus mechanics now have a bounded foundation;
[AI_ROADMAP.md](AI_ROADMAP.md) keeps search and learning planned. Opponent
modelling remains outside the product goal; environment-injected garbage does
not require an opponent representation. No status changes or exact VS formulas
are introduced by the roadmap.

## Project decisions, separate from external rules

The following are PROJECT-SPECIFIC architecture and task-scope decisions:

- One authoritative engine supplies human input, placement execution, and
  simulation. Rendering and keyboard bindings do not define mechanics.
- Headless, deterministic, seedable operation is required. Python RNG cloning
  guarantees the same continuation within this engine/runtime; it does not
  promise TETR.IO seeds or cross-version serialized replay compatibility.
- AI decisions use immutable reachable final placements, distinguished by final
  occupied cells and Spin classification. BFS begins at the current pose and
  uses engine movement and
  rotations. Grounded above-board top-out attempts are excluded from placements.
- Hold is separate from the placement action space. Enumeration has stable
  ordering and does not mutate the source game. Stale/invalid choices are
  rejected safely against current state.
- Clones share immutable board/piece values and own separate RNG/queue state.
  `simulate_placement()` returns an independent Game; `simulate_placement_result()`
  additionally returns the authoritative Transition. Invalid direct simulation
  raises ValueError; the metadata API returns an unaccepted transition. Repeated
  and multi-ply simulation must leave ancestors unchanged.
- The separate one-ply baseline maximizes `-5 * holes - aggregate_height -
  bumpiness + 10 * lines_cleared`, with first-enumerated tie breaking. It uses
  authoritative isolated simulation without hold or future-piece lookahead.
  These are untuned AI preferences, not TETR.IO gameplay scoring or rules.
- UI watch mode schedules final placement decisions; this adds no engine gravity.
  The same agent works headlessly and does not mutate the source while deciding.
- No gravity, opponents or deeper search policy is
  introduced. The optional neural foundation supplies an untrained PyTorch
  policy/value model above the environment; it adds no reward objective or RL
  training algorithm. Future additions need separately scoped tasks.

## Evidence inventory and maintenance

Inspected local evidence: `README.md`, `board.py`, `pieces.py`, `engine.py`,
`data/srs_plus.json`, and the board/engine/randomizer/placement/simulation tests.
These establish implementation behavior and regression coverage. The JSON's
source description and README's compatibility wording are claims, not a
reproducible external verification record. Current versus facts have first-party
client evidence, dated and fingerprinted in
[VERSUS_MECHANICS.md](VERSUS_MECHANICS.md). This does not promote the older
geometry, spawn, kick-table or top-out claims to full external parity.

Research only a required uncertainty for an approved bounded task. Prefer
official TETR.IO documentation or inspectable authoritative behavior; record
reliable secondary evidence and its limitations explicitly when necessary.
Before promoting a row to CONFIRMED, add a source link or versioned artifact,
access/version context, confirmed statement, relevant mode, and compatibility
test/fixture reference. If evidence conflicts or applies to only one mode,
retain TO VERIFY for the unresolved portion rather than generalizing silently.
