"""Tetromino geometry in SRS bounding boxes.

Coordinates are (column, row), with rows increasing down the board.  Geometry is
simulation data; colours and preview layout deliberately live in the UI.
"""

from __future__ import annotations

from enum import Enum, IntEnum


class Tetromino(str, Enum):
    I = "I"
    J = "J"
    L = "L"
    O = "O"
    S = "S"
    T = "T"
    Z = "Z"


class Orientation(IntEnum):
    SPAWN = 0
    RIGHT = 1
    REVERSE = 2
    LEFT = 3


# Explicit states avoid floating-point rotation and make the SRS rotation centre
# unambiguous. I and O use their standard 4x4/offset SRS boxes.
CELLS: dict[Tetromino, tuple[tuple[tuple[int, int], ...], ...]] = {
    Tetromino.J: (
        ((0, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (1, 2)),
        ((0, 1), (1, 1), (2, 1), (2, 2)),
        ((1, 0), (1, 1), (0, 2), (1, 2)),
    ),
    Tetromino.L: (
        ((2, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (1, 1), (1, 2), (2, 2)),
        ((0, 1), (1, 1), (2, 1), (0, 2)),
        ((0, 0), (1, 0), (1, 1), (1, 2)),
    ),
    Tetromino.S: (
        ((1, 0), (2, 0), (0, 1), (1, 1)),
        ((1, 0), (1, 1), (2, 1), (2, 2)),
        ((1, 1), (2, 1), (0, 2), (1, 2)),
        ((0, 0), (0, 1), (1, 1), (1, 2)),
    ),
    Tetromino.T: (
        ((1, 0), (0, 1), (1, 1), (2, 1)),
        ((1, 0), (1, 1), (2, 1), (1, 2)),
        ((0, 1), (1, 1), (2, 1), (1, 2)),
        ((1, 0), (0, 1), (1, 1), (1, 2)),
    ),
    Tetromino.Z: (
        ((0, 0), (1, 0), (1, 1), (2, 1)),
        ((2, 0), (1, 1), (2, 1), (1, 2)),
        ((0, 1), (1, 1), (1, 2), (2, 2)),
        ((1, 0), (0, 1), (1, 1), (0, 2)),
    ),
    Tetromino.I: (
        ((0, 1), (1, 1), (2, 1), (3, 1)),
        ((2, 0), (2, 1), (2, 2), (2, 3)),
        ((0, 2), (1, 2), (2, 2), (3, 2)),
        ((1, 0), (1, 1), (1, 2), (1, 3)),
    ),
    Tetromino.O: (
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
        ((1, 0), (2, 0), (1, 1), (2, 1)),
    ),
}


ALL_TETROMINOES = tuple(Tetromino)
