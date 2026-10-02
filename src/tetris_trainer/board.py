"""Authoritative board occupancy and line-clear operations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .pieces import Tetromino


WIDTH = 10
HEIGHT = 20
class GarbageCell(str, Enum):
    """Non-tetromino occupancy stored in the authoritative board rows."""

    GARBAGE = "G"


Cell = Tetromino | GarbageCell | None


@dataclass(frozen=True, slots=True)
class LineClearResult:
    board: "Board"
    cleared_rows: tuple[int, ...]
    garbage_lines: int

    @property
    def cleared_lines(self) -> int:
        return len(self.cleared_rows)


@dataclass(frozen=True, slots=True)
class Board:
    rows: tuple[tuple[Cell, ...], ...] = tuple(
        tuple(None for _ in range(WIDTH)) for _ in range(HEIGHT)
    )

    def __post_init__(self) -> None:
        if len(self.rows) != HEIGHT or any(len(row) != WIDTH for row in self.rows):
            raise ValueError(f"board must be {WIDTH}x{HEIGHT}")
        # Enforce deep immutability even when a scenario supplies list rows.
        # Game clones can then safely share every Board instance.
        object.__setattr__(self, "rows", tuple(tuple(row) for row in self.rows))

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
        result = self.clear_lines_result()
        return result.board, result.cleared_lines

    def clear_lines_result(self) -> LineClearResult:
        """Clear full rows, retaining their original indices and garbage facts."""
        cleared_rows = tuple(
            y for y, row in enumerate(self.rows) if all(cell is not None for cell in row)
        )
        remaining = [row for row in self.rows if any(cell is None for cell in row)]
        cleared = len(cleared_rows)
        empty = [tuple(None for _ in range(WIDTH)) for _ in range(cleared)]
        garbage_lines = sum(
            any(cell is GarbageCell.GARBAGE for cell in self.rows[y])
            for y in cleared_rows
        )
        return LineClearResult(Board(tuple(empty + remaining)), cleared_rows, garbage_lines)

    def insert_garbage(self, holes: tuple[int, ...]) -> tuple["Board", bool]:
        """Raise supplied rows in order, reporting occupied cells lost above view.

        Each supplied hole describes one new bottom row. This visible-board
        insertion boundary does not model hidden rows or garbage timing.
        """
        holes = tuple(holes)
        if any(type(hole) is not int or not 0 <= hole < WIDTH for hole in holes):
            raise ValueError(f"garbage holes must be integer columns in [0, {WIDTH})")
        if not holes:
            return self, False
        added = tuple(
            tuple(None if x == hole else GarbageCell.GARBAGE for x in range(WIDTH))
            for hole in holes
        )
        combined = self.rows + added
        discarded = combined[:-HEIGHT]
        overflow = any(cell is not None for row in discarded for cell in row)
        return Board(combined[-HEIGHT:]), overflow

    def with_cells(self, cells: dict[tuple[int, int], Tetromino | GarbageCell]) -> "Board":
        """Convenience constructor used by scenario builders and tests."""
        rows = [list(row) for row in self.rows]
        for (x, y), kind in cells.items():
            if not (0 <= x < WIDTH and 0 <= y < HEIGHT):
                raise ValueError("cell outside board")
            rows[y][x] = kind
        return Board(tuple(tuple(row) for row in rows))
