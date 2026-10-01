# Development instructions

These are the authoritative repository instructions for agents working on the
current Tetris-trainer. Inspect the current checkout before changing it. Preserve
existing work, including uncommitted changes; do not restore an older branch's
architecture, restructure the source tree, or introduce placeholder packages.

## Existing architecture

- `tetris_trainer/engine.py` owns `Game`, semantic `Action` handling, immutable
  `ActivePiece`, `Transition`, `Placement`, and `SimulationResult` values, the
  seedable `BagRandomizer`, placement reachability, cloning, and simulation.
- `tetris_trainer/board.py` owns immutable `Board` occupancy, locking, and line
  clearing. `pieces.py` owns tetromino geometry and orientations. These modules
  form one authoritative engine, not competing rules implementations.
- `data/srs_plus.json` supplies the existing ordered rotation kick tables.
- `ui.py` renders and maps keys to semantic engine actions; `__main__.py` is the
  desktop entry point. Headless consumers import the engine without Tk.
- `baseline.py` owns four-feature extraction, the deterministic one-ply
  `BaselineAgent`, structured decisions, and bounded headless runs. UI AI mode
  uses that same agent and authoritative placement execution; it owns no score
  or search rules. This is an untuned reference baseline, not the final learned AI.
- `tests/` covers boards, actions, randomization, UI bindings, reachable
  placements, and independent deterministic simulation. `benchmarks/simulation.py`
  measures branching infrastructure without evaluating placements.
  `benchmarks/baseline.py` measures complete one-ply decisions and feature cost.
<<<<<<< HEAD
  `benchmarks/performance.py` separates cold/warm enumeration and captures
  comparable profiles and allocation peaks; see `docs/PLACEMENT_PERFORMANCE.md`.
=======
- `environment.py` owns the framework-free numerical observation, variable
  placement-action handles, and factual episode transitions. It delegates all
  mechanics to Game; no reward weights, learned hold actions, or training
  algorithm live in this boundary. See `docs/RL_ENVIRONMENT.md` for contract v1
  and `benchmarks/environment.py` for basic reset/step overhead measurements.
>>>>>>> 08606dc (feat: add RL-ready placement environment)

## Non-negotiable principles

- Maintain ONE authoritative game engine. Human gameplay, AI/search, simulation,
  and future trainer features must reuse it. Never duplicate collision,
  movement, rotation/kicks, locking, line clearing, randomization, or other
  authoritative mechanics in decision or simulation layers.
- Keep mechanics independent of rendering/UI. Keep AI decisions independent of
  input bindings; semantic actions remain available for human input adapters.
- Preserve deterministic, seedable, headless operation. Gravity is intentionally
  absent unless project requirements explicitly change.
- AI/search decisions use reachable legal final placements rather than keyboard
  sequences. Reachability must use the same movement and ordered SRS+ rotation
  behavior as normal engine actions. Hold remains a separate decision until a
  bounded task explicitly changes that action space.
- Hypothetical simulation must not mutate its source/root game. Share immutable
  values safely and independently copy mutable RNG/queues. Preserve all
  future-affecting state, and update `clone()`, `snapshot()`, and determinism
  tests together when adding state.
- The engine's one-entry reachable-placement catalog is derived immutable
  metadata, shared safely with clones and excluded from gameplay snapshots.
  Reuse requires full snapshot equality; source/membership validation must remain.
  Do not replace that guard with action-only invalidation or trust placement
  provenance alone. Report cold versus warm timings when touching this path.
- Prefer bounded tasks and minimal compatible edits over speculative rewrites.
  Preserve working human controls and existing project-specific behavior unless
  the requested scope explicitly changes them.
- Never silently guess uncertain TETR.IO mechanics. Implementation tests alone
  do not confirm external compatibility. Consult [rule statuses](docs/TETRIO_RULESET.md)
  and resolve only uncertainty required by the task.
- Do not add AI features, scoring, RL frameworks, native extensions,
  multiprocessing, caches, or speculative optimization outside requested scope.

## Proportional multi-agent workflow

Follow [the development workflow](docs/DEVELOPMENT_WORKFLOW.md). For substantial
changes, use independent testing and code-review agents when agent tools are
available. The implementer must not be the sole verifier of their own work.
Roles are responsibilities, not a requirement to launch six agents. Planning
and implementation may share an agent; an independent agent may test and review.
Small documentation, formatting, and other trivial edits can use one agent with
targeted checks. If independent agent tools are unavailable, record review as
pending in UNRESOLVED; implementation may proceed, but do not claim substantial
work meets the Definition of Done until independent review is completed.

- **Planning / architecture:** inspect current files and instructions; define
  scope, affected modules, uncertainties, acceptance criteria, required tests,
  and explicit exclusions before implementation.
- **Rules / research:** use only when a required behavior depends on uncertain
  TETR.IO mechanics. Consult authoritative/reliable sources; record evidence,
  version/mode where relevant, assumptions, and testable confirmed statements.
  Report gaps instead of guessing; do not research unrelated mechanics.
- **Implementation:** implement the bounded change through existing engine
  behavior, add/update appropriate tests, avoid unrelated refactoring, and
  document unavoidable assumptions.
- **Testing:** independently probe happy paths, boundaries, regressions,
  invariants, deterministic reproduction, stale/invalid handling, and relevant
  verified compatibility cases. Tests of current behavior are not external
  verification evidence.
- **Independent review:** inspect the actual diff against scope and criteria for
  duplicated mechanics, architecture drift, coupling, mutation/aliasing,
  nondeterminism, edge cases, complexity, and obvious performance regressions.
- **AI / performance review:** apply when simulation, placements, cloning,
  search, or other hot paths change. Review headless suitability, deterministic
  simulation, fork cost, allocations, enumeration throughput, and obvious future
  search/training bottlenecks. Use lightweight relevant measurements; do not
  introduce optimization infrastructure without evidence.

Assign clear file ownership to concurrent implementers. Reviewers should read
without editing overlapping files. The coordinating agent integrates findings,
fixes issues, reruns relevant checks, and reports any remaining gaps. Use the
current checkout for this workflow; create isolated worktrees only when needed
under the applicable user instructions. Do not create sidebar chats just to
perform review subtasks.

## Definition of Done

A substantial task is complete only when:

1. Scope, acceptance criteria, exclusions, and required tests are defined.
2. Required rules are sufficiently specified; no required `TO VERIFY` behavior
   was silently guessed. Existing project-specific semantics can be preserved
   without researching external parity when the task does not depend on it.
3. Implementation stays within scope and preserves the architecture above.
4. Appropriate tests are added/updated; the complete suite and repository
   validation pass, without removing or weakening existing checks.
5. Substantial changes receive independent review, findings are resolved or
   explicitly reported, and performance-sensitive changes receive lightweight
   AI/performance review.
6. Documentation reflects changed behavior/architecture, and assumptions and
   unresolved issues are explicitly reported in the handoff.

## Validation and handoff

Run `make check` and `git diff --check` before handing off substantial work.
`make check` runs all unittest tests (including workflow-document validation)
and compiles the current source/tests. If Make is unavailable, use the exact
equivalent commands documented in the workflow. Hot-path changes should run
`python -m benchmarks.simulation` when relevant, reporting fixture, environment,
and timings rather than imposing machine-dependent timing thresholds.

Use this concise handoff; mark empty sections `None` or `Not applicable`:

```text
TASK: requested outcome
SCOPE: boundaries and exclusions
FILES CHANGED: paths and purpose
RULES USED: statuses, evidence, and relevant project decisions
TESTS ADDED: new/updated coverage
VALIDATION: commands and outcomes, including performance when applicable
ASSUMPTIONS: explicit assumptions
UNRESOLVED: remaining issues, blockers, or pending verification
REVIEW NOTES: independent reviewer findings and resolution
```

Receiving agents must read UNRESOLVED and the applicable rule statuses before
continuing. Report existing unrelated changes separately from task-owned edits.
