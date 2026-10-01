"""Authoritative board occupancy and line-clear operations."""

from __future__ import annotations

from dataclasses import dataclass

from .pieces import Tetromino


WIDTH = 10
HEIGHT = 20
Cell = Tetromino | None


@dataclass(frozen=True, slots=True)
class Board:
    rows: tuple[tuple[Cell, ...], ...] = tuple(
        tuple(None for _ in range(WIDTH)) for _ in range(HEIGHT)
    )

    def __post_init__(self) -> None:
        if len(self.rows) != HEIGHT or any(len(row) != WIDTH for row in self.rows):
            raise ValueError(f"board must be {WIDTH}x{HEIGHT}")

    def occupied(self, x: int, y: int) -> bool:
        """Return collision state; cells above the visible board remain legal."""
        return x < 0 or x >= WIDTH or y >= HEIGHT or (y >= 0 and self.rows[y][x] is not None)

    def lock(self, cells: tuple[tuple[int, int], ...], kind: Tetromino) -> "Board":
        if len(set(cells)) != 4 or any(self.occupied(x, y) or y < 0 for x, y in cells):
            raise ValueError("piece cannot be locked at these cells")
        rows = [list(row) for row in self.rows]
        for x, y in cells:
            rows[y][x] = kind
        return Board(tuple(tuple(row) for row in rows))

    def clear_lines(self) -> tuple["Board", int]:
        remaining = [row for row in self.rows if any(cell is None for cell in row)]
        cleared = HEIGHT - len(remaining)
        empty = [tuple(None for _ in range(WIDTH)) for _ in range(cleared)]
        return Board(tuple(empty + remaining)), cleared

    def with_cells(self, cells: dict[tuple[int, int], Tetromino]) -> "Board":
        """Convenience constructor used by scenario builders and tests."""
        rows = [list(row) for row in self.rows]
        for (x, y), kind in cells.items():
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                raise ValueError("cell outside board")
            rows[y][x] = kind
        return Board(tuple(tuple(row) for row in rows))
