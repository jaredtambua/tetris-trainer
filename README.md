# tetris-trainer

Initial Python scaffold for a TETR.IO-inspired Tetris trainer and reinforcement
learning project. Gameplay, UI, and AI mechanics are intentionally not yet
implemented.

## Development

This project requires Python 3.11 or newer. Create an environment and install
the development tools:

```sh
python -m pip install -e '.[dev]'
```

Run every repository check with one command:

```sh
make check
```

That command checks formatting, linting, static types, and tests using Ruff,
Mypy, and pytest.
