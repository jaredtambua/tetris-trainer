# Agent guidance

## Project goal

Tetris Trainer will provide a human-playable Tetris implementation based on
verified TETR.IO mechanics, a high-performance headless reinforcement-learning
environment and agent, and a trainer that can load board states and recommend
moves. The repository is currently a scaffold: do not infer that a placeholder
module contains working game behavior.

## Non-negotiable architecture and mechanics principles

1. Maintain **one authoritative Tetris engine** shared by human gameplay, AI
   training, and the position trainer. Do not create subtly different rules
   implementations for individual consumers.
2. The engine must be usable completely headlessly. It must not require a
   renderer, windowing system, or human input layer.
3. Design the engine to become deterministic, seedable, fast, cloneable, and
   suitable for large-scale RL simulation.
4. Gravity is **intentionally omitted**. Pieces do not automatically fall as
   time passes.
5. Do not build opponent simulation or an opponent UI; neither is in scope.
6. The engine will calculate outgoing attack deterministically from the move
   and clear state.
7. Never guess TETR.IO mechanics. Cite a reliable source in the rules
   specification when implementing a mechanic. Record uncertain or unverified
   behavior as unresolved instead of implementing an assumption.
8. Never couple game logic to rendering or UI code. UI may consume engine state
   and issue actions through stable boundaries only.
9. Every implemented mechanic must have appropriate automated tests, including
   edge cases and deterministic behavior where relevant.

## Repository boundaries

- `src/tetris_trainer/engine/`: the sole authoritative game/rules engine.
- `src/tetris_trainer/env/`: headless RL-facing environment adapters.
- `src/tetris_trainer/agent/`: learning and inference agents.
- `src/tetris_trainer/trainer/`: board-loading and move-recommendation workflows.
- `tests/`: automated tests mirroring application boundaries.
- `docs/`: verified specifications and architectural decisions.

Before committing, run `make check`. Keep changes narrowly scoped, update the
rules specification when mechanics are verified, and keep source, tests, and
documentation consistent.
