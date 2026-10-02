# Development workflow

[AGENTS.md](../AGENTS.md) is the authoritative instruction set.
[TETRIO_RULESET.md](TETRIO_RULESET.md) tracks evidence and local decisions.
[AI_ROADMAP.md](AI_ROADMAP.md) owns future AI direction; consult it when scoping
AI work. Its planned phases do not authorize implementation or change current
contracts/rule statuses. Keep current behavior separate from roadmap intent.
Start from the current checkout and preserve the source layout by default;
structural changes require explicit authorization in the bounded task. Preserve
engine/UI boundaries, placement system, and simulation infrastructure.

## Substantial-feature lifecycle

Plan → Resolve required rule uncertainty → Implement bounded change → Test →
Independent review → Performance review when relevant → Validate → Handoff

1. **Plan:** inspect current code, tests, tooling, git status, and previous
   handoff UNRESOLVED. Define the outcome, affected modules, applicable rule
   statuses, uncertainties, acceptance criteria, tests, and exclusions. Avoid
   speculative redesign and unrelated cleanup.
2. **Resolve required rule uncertainty:** involve a rules/research agent only
   when a task depends on uncertain external mechanics. Record sources and
   distinguish confirmation from assumptions. Convert confirmed behavior into
   testable statements. Preserve current local semantics when parity is not
   required; do not guess a required TO VERIFY rule or research the whole game.
3. **Implement bounded change:** give implementers clear file ownership. Reuse
   authoritative mechanics, update appropriate tests, and document assumptions.
   Update snapshots, cloning, and deterministic tests together if state changes.
4. **Test independently:** ask an agent other than the implementer to probe
   happy paths, boundaries, regressions, invariants, determinism, stale/invalid
   states, and applicable verified compatibility cases. Passing tests of local
   behavior do not establish external rule parity.
5. **Review independently:** a reviewer reads the actual diff and acceptance
   criteria, checking specification alignment, duplicate rules, drift, coupling,
   aliasing/mutation, nondeterminism, edge cases, complexity, and performance
   regressions. Report concrete findings with file references and severity.
   Resolve findings and recheck changed areas before claiming completion.
6. **Review performance when relevant:** for placement, simulation, cloning,
   search, or other hot-path changes, independently inspect headless behavior,
   determinism, allocations, fork cost, enumeration throughput, and bottlenecks.
   Use representative lightweight benchmarks and document machine/runtime and
   workload. Do not add caches, native code, multiprocessing, or RL frameworks
   merely because future training may be large.
7. **Validate:** run the complete existing suite and repository checks below
   on the integrated result. Retain every existing validation step. Rerun checks
   affected by fixes; distinguish skipped/unavailable checks from passed checks.
8. **Handoff:** use the standard fields below with assumptions, unresolved
   issues, and independent review results. Receiving agents read UNRESOLVED and
   applicable rule statuses before continuing.

## Scale roles to the task

Roles are conceptual responsibilities, not six mandatory agents per edit.
A coordinator can plan and implement; another agent can independently test and
review, and perform performance review if applicable. Rules research is
conditional. Use read-only reviewers to avoid concurrent edits to the same
files; coordinate implementation ownership and integrate before final checks.
Review responsibility remains independent from the implementation it verifies.

Substantial changes include new APIs, engine behavior/state, placement or
simulation changes, and repository-wide workflow/validation policy. Use
independent testing/review agents for these when tools are available. If tools
are unavailable, report pending independent review and do not label the task
fully done until that responsibility is satisfied. Small typo fixes, isolated
formatting edits, and straightforward documentation corrections can use a single
agent and proportional checks. No user approval ceremony is added for routine
implementation, tests, or review within the authorized task.

## Definition of Done

For substantial work, all of these must hold:

- Scope, acceptance criteria, exclusions, and required tests were defined.
- Required rules are sufficiently specified; required TO VERIFY behavior was
  not silently guessed. Applicable project-specific assumptions are explicit.
- Implementation stayed within scope and preserved the current architecture.
- Appropriate tests were added/updated, and the complete existing suite passes.
- Repository validation passes without weakening existing checks.
- Independent review occurred; findings were resolved or explicitly reported.
- Performance-sensitive AI/simulation work received lightweight performance
  review with relevant measurements or a justified measurement limitation.
- Documentation was updated for changed behavior/architecture.
- Assumptions and unresolved issues are explicitly included in the handoff.

## Validation commands

Activate the repository `.venv` and install the editable package before running
commands below: `python -m pip install -e ".[ml]"` includes neural coverage.
See README for PowerShell setup. The src layout makes imports depend on a
correct installation rather than an incidental root-level source directory.

`make check` retains `make test` (unittest discovery) and compileall. Workflow
document validation lives in `tests/test_workflow_documents.py` and therefore
runs through the existing discovery command; no Make target or runtime package
is replaced. The check requires all three instruction documents, the full
mechanic register, and valid rule-status vocabulary.

```sh
make check
git diff --check
```

When Make is unavailable, run its exact existing steps, then the diff check:

```sh
python -m unittest discover -s tests -v
python -m compileall -q src/tetris_trainer tests benchmarks
git diff --check
```

For a targeted workflow check, use
`python -m unittest discover -s tests -p test_workflow_documents.py -v`.
For relevant hot-path changes, additionally use
`python -m benchmarks.simulation`; compilation of benchmark/tool files can be
added as an appropriate task check without dropping the existing source/tests.
Timing results are evidence, not machine-dependent pass/fail thresholds.

## Standard handoff

Keep entries concise; use `None` or `Not applicable` for empty sections.

```text
TASK: requested outcome
SCOPE: included work and exclusions
FILES CHANGED: task-owned paths and purpose; distinguish existing changes
RULES USED: statuses, evidence references, project-specific decisions
TESTS ADDED: coverage added or updated
VALIDATION: commands, outcomes, skipped checks, relevant benchmark results
ASSUMPTIONS: explicit assumptions
UNRESOLVED: remaining issues, pending verification/review, blockers
REVIEW NOTES: independent findings and their resolution
```

Do not turn outstanding compatibility questions into implementation instructions
without first checking scope and evidence. Preserve uncommitted earlier work;
do not claim it as a change made by the current task.
