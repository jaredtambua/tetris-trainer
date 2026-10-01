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

## Develop

```sh
make test
make check
```

The engine is usable without Tk or a display:

```python
from tetris_trainer import Action, Game

game = Game(seed=123)
game.apply(Action.MOVE_LEFT)
result = game.apply(Action.HARD_DROP)
```

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
