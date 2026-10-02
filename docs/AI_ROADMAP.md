# AI roadmap

This is the source of truth for the forward-looking AI plan. Phase A records
the current bounded foundation; the remaining phases are design intent, not
implemented functionality. Changes require later bounded tasks; this roadmap
does not authorize implementation.

## Product objective and own-state model

Build a very strong TETR.IO-oriented decision system as a **single-agent
optimization problem**. It reasons about its own board, current piece, preview
queue and hold, and eventually combo/B2B, pending garbage, garbage on its board,
and other self-state required by selected versus mechanics. It does not observe,
classify, predict or model an opponent. Do not describe the target as
opponent-aware unless a future explicitly authorized task changes this goal.

The environment may inject garbage directly; knowing who produced it is not
required. The loop is own state → best placement → environment evolution,
possibly garbage arrival → new own state → choose again. Future scenarios may
include clean garbage, messy garbage/cheese, bursts, varying pending amounts and
timing patterns. A garbage generator or scenario distribution supplies these
conditions without an opponent neural model.

## Existing foundation and action abstraction

Today the repository has one authoritative headless engine, reachable-placement
enumeration, deterministic isolated simulation, an untuned one-ply BaselineAgent,
measured placement/simulation optimizations, framework-free environment contract
v2, and an optional **UNTRAINED** neural policy/value foundation with inference,
detached rollout records and versioned local checkpoints. See
[RL_ENVIRONMENT.md](RL_ENVIRONMENT.md) and [NEURAL_AGENT.md](NEURAL_AGENT.md).
The own-board versus foundation now supplies garbage identity, supplied-hole
pending events/insertion, cancellation, clear/Spin facts, combo/B2B and attack.
See [VERSUS_MECHANICS.md](VERSUS_MECHANICS.md) for verified rules and local
boundaries; this is not full live Tetra League parity. There is no beam-search
teacher, afterstate learner, search distillation, reward calculation or RL trainer.

Strategic actions remain reachable **final legal placements**, not learned
keyboard sequences. Human controls use semantic actions. The same authoritative
engine owns movement, collision, rotation, ordered SRS+ kicks, reachability,
locking, line clearing, randomization and simulation. Hold remains separate
from the current placement action space; learned integration is deferred.

## Planned phases

The preferred architecture combines exact authoritative simulation,
reachable-placement generation, deep planning, learned policy/value evaluation,
and later RL fine-tuning. Strong practical play is the goal; pure PPO from
scratch is not the current direction. The user's design direction takes
inspiration from publicly visible MochBot/Fusion approaches, while keeping our
own implementation and architecture. This is a design reference, not a verified
claim about those systems' internals or an external rules source.

### A — Authoritative versus mechanics foundation (implemented with boundaries)

The bounded own-board foundation is implemented; its selected rules and omitted
live timing/opening behavior are recorded in [TETRIO_RULESET.md](TETRIO_RULESET.md).
Remaining external parity gaps require later bounded tasks before claiming a
complete Tetra League simulator. No garbage scenario generator is implemented.

### B — Strong offline search teacher

Beam search is the preferred search family: the bounded preview queue provides
known future pieces, transitions over that queue are deterministic under known
environment conditions, actions are complete reachable placements, and exact
isolated simulation already exists. Future pieces beyond the preview and unknown
garbage arrivals must not be treated as known. The offline teacher may be much
slower than the eventual runtime agent; it generates high-quality learning targets.

### C — Afterstate-oriented policy/value learning

Evaluate the actual result of each candidate: current state → placement →
authoritative simulation → resulting afterstate → neural evaluation. Learn which
resulting states/placements are promising. The current model instead encodes the
current 929-value observation and scores five-value placement descriptors with a
shared scorer; its value head evaluates current state. It does not simulate
candidate afterstates as neural inputs. The final afterstate architecture is
undecided and requires a separately scoped change.

### D — Search supervision / distillation

Use the expensive search oracle to supervise a cheaper policy/value model.
Likely targets are a soft distribution over placements derived from root search
scores and a value target derived from search evaluation. Target construction,
calibration and training are not implemented or finalized.

### E — Neural-guided runtime search

Use learned policy/value guidance inside shallower, faster beam search:
own state → legal placements → limited search with neural guidance → best
placement. The final agent need not choose an immediate move from a single
network forward pass. Runtime budget remains a future decision.

### F — Later RL fine-tuning

After search-supervised pretraining works, RL may fine-tune the model toward
long-term performance in garbage-containing environments. PPO is one possible
actor-critic method, **not a selected algorithm**. RL is not the foundation of
the whole system; the exact fine-tuning method remains unresolved.

## Versus-oriented objective direction

Aim for TETR.IO-style versus performance rather than generic single-player
survival. The desired VS-style concept involves useful attack, garbage/downstack
clearing, efficiency and speed. This is qualitative product intent, not an exact
TETR.IO VS formula or confirmed attack table.

The approximate core strategic reward direction is **attack produced + garbage
cleared** over play, with terminal/top-out consequences and delayed future value
handled by the learning system. Exact definitions, weights and normalization are
undecided. Separate strategic decision quality from external execution speed:
complete-placement decisions must not accidentally reward inference latency or
keyboard execution. Any efficiency/speed treatment needs an explicit later design.

The baseline's holes, bumpiness and aggregate-height weights are debugging
heuristics, not the final learning objective. Useful board structure should be
learned through future versus returns. Ordinary line clears are not automatically
attack. Current environment facts now supply the bounded profile's versus signals.
Before any exact VS formula or attack table becomes normative, verify a current
authoritative source and record its mode/version, evidence and rule status.
No external mechanic is promoted to CONFIRMED here.

## Explicitly deferred decisions

Later bounded tasks and experiments must decide:

- Exact RL fine-tuning algorithm, final PPO selection if any, and hyperparameters.
- Exact afterstate neural architecture and learned hold action integration.
- Beam width/depth and final inference-time search budget.
- Curriculum and garbage-generation distribution.
- Exact top-out penalty, discount factor and advantage estimation.
- Search-policy temperature and exact VS-derived reward normalization.
- Whether human replay imitation will be included.

This roadmap adds no mechanics, reward implementation, optimizer, training loop,
dataset, search implementation or neural refactor. Existing behavior and external
compatibility uncertainties remain authoritative as documented in the contracts
and rule register.
