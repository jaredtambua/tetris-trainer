"""Thin Tk desktop renderer and keyboard adapter for the headless engine."""

from __future__ import annotations

import argparse
import tkinter as tk

from .board import HEIGHT, WIDTH
from .engine import Action, Game
from .pieces import CELLS, Orientation, Tetromino


KEY_BINDINGS: dict[str, Action] = {
    "Left": Action.MOVE_LEFT,
    "Right": Action.MOVE_RIGHT,
    "Down": Action.SOFT_DROP,
    "space": Action.HARD_DROP,
    "z": Action.ROTATE_CCW,
    "x": Action.ROTATE_CW,
    "Up": Action.ROTATE_CW,
    "a": Action.ROTATE_180,
    "c": Action.HOLD,
}

CONTROLS = (
    "←/→  Move",
    "↓  Soft drop (one row)",
    "Space  Hard drop",
    "Z / X / ↑  Rotate CCW / CW",
    "A  Rotate 180°",
    "C  Hold",
    "R  Restart",
)

COLORS = {
    Tetromino.I: "#31c7ef",
    Tetromino.J: "#5a65ad",
    Tetromino.L: "#ef7921",
    Tetromino.O: "#f7d308",
    Tetromino.S: "#42b642",
    Tetromino.T: "#ad4d9c",
    Tetromino.Z: "#ef3e3e",
}


class TetrisWindow:
    CELL = 28
    MARGIN = 18
    SIDE = 150

    def __init__(self, root: tk.Tk, seed: int = 0) -> None:
        self.root = root
        self.seed = seed
        self.game = Game(seed)
        width = self.MARGIN * 3 + self.SIDE * 2 + WIDTH * self.CELL
        height = self.MARGIN * 2 + HEIGHT * self.CELL
        self.canvas = tk.Canvas(root, width=width, height=height, bg="#16161d", highlightthickness=0)
        self.canvas.pack()
        root.title("Tetris Trainer — no gravity")
        root.resizable(False, False)
        root.bind("<KeyPress>", self._key)
        self.draw()

    @property
    def board_x(self) -> int:
        return self.MARGIN * 2 + self.SIDE

    def _key(self, event: tk.Event) -> str:
        key = event.keysym
        if key.lower() == "r":
            self.game = Game(self.seed)
        else:
            action = KEY_BINDINGS.get(key) or KEY_BINDINGS.get(key.lower())
            if action is None:
                return ""
            self.game.apply(action)
        self.draw()
        return "break"

    def _block(self, x: int, y: int, color: str, *, outline: str = "#09090d") -> None:
        left = self.board_x + x * self.CELL
        top = self.MARGIN + y * self.CELL
        self.canvas.create_rectangle(
            left + 1, top + 1, left + self.CELL - 1, top + self.CELL - 1,
            fill=color, outline=outline, width=1,
        )

    def _preview(self, kind: Tetromino | None, x: int, y: int, size: int = 18) -> None:
        if kind is None:
            self.canvas.create_text(x, y, text="—", fill="#777", anchor="nw", font=("TkDefaultFont", 16))
            return
        for dx, dy in CELLS[kind][Orientation.SPAWN]:
            self.canvas.create_rectangle(
                x + dx * size, y + dy * size, x + (dx + 1) * size - 2, y + (dy + 1) * size - 2,
                fill=COLORS[kind], outline="#09090d",
            )

    def draw(self) -> None:
        self.canvas.delete("all")
        bx, by = self.board_x, self.MARGIN
        self.canvas.create_rectangle(
            bx, by, bx + WIDTH * self.CELL, by + HEIGHT * self.CELL,
            fill="#20202a", outline="#a7a7b4", width=2,
        )
        for y in range(HEIGHT):
            for x in range(WIDTH):
                kind = self.game.board.rows[y][x]
                if kind is not None:
                    self._block(x, y, COLORS[kind])

        ghost = self.game.ghost()
        if ghost is not None and self.game.active is not None and ghost.cells != self.game.active.cells:
            for x, y in ghost.cells:
                if y >= 0:
                    self._block(x, y, "#383844", outline="#898995")
        if self.game.active is not None:
            for x, y in self.game.active.cells:
                if y >= 0:
                    self._block(x, y, COLORS[self.game.active.kind])

        self.canvas.create_text(self.MARGIN, self.MARGIN, text="HOLD", fill="white", anchor="nw", font=("TkDefaultFont", 12, "bold"))
        self._preview(self.game.hold_piece, self.MARGIN, self.MARGIN + 30)
        controls_y = 170
        self.canvas.create_text(
            self.MARGIN, controls_y, text="CONTROLS\n" + "\n".join(CONTROLS), fill="#d3d3dc",
            anchor="nw", justify="left", font=("TkDefaultFont", 9), width=self.SIDE,
        )

        right = bx + WIDTH * self.CELL + self.MARGIN
        self.canvas.create_text(right, self.MARGIN, text="NEXT", fill="white", anchor="nw", font=("TkDefaultFont", 12, "bold"))
        for index, kind in enumerate(self.game.upcoming):
            self._preview(kind, right, self.MARGIN + 30 + index * 92)
        self.canvas.create_text(right, 520, text=f"Lines: {self.game.total_lines}", fill="white", anchor="nw")

        if self.game.game_over:
            cx = bx + WIDTH * self.CELL / 2
            cy = by + HEIGHT * self.CELL / 2
            self.canvas.create_rectangle(cx - 125, cy - 50, cx + 125, cy + 50, fill="#101018", outline="#ef3e3e", width=2)
            self.canvas.create_text(cx, cy - 12, text="GAME OVER", fill="#ef3e3e", font=("TkDefaultFont", 20, "bold"))
            self.canvas.create_text(cx, cy + 22, text="Press R to restart", fill="white")


def main() -> None:
    parser = argparse.ArgumentParser(description="Play no-gravity Tetris Trainer")
    parser.add_argument("--seed", type=int, default=0, help="deterministic seven-bag seed")
    args = parser.parse_args()
    root = tk.Tk()
    TetrisWindow(root, args.seed)
    root.mainloop()


if __name__ == "__main__":
    main()
