"""Thin Tk desktop renderer and keyboard adapter for the headless engine."""

from __future__ import annotations

import argparse
import tkinter as tk

from .board import HEIGHT, WIDTH
from .baseline import BaselineAgent, Decision
from .engine import Action, Game
from .pieces import CELLS, Orientation, Tetromino


KEY_BINDINGS: dict[str, Action] = {
    "Left": Action.MOVE_LEFT,
    "Right": Action.MOVE_RIGHT,
    "Down": Action.SOFT_DROP,
    "space": Action.HARD_DROP,
    "q": Action.ROTATE_180,
    "w": Action.ROTATE_CCW,
    "e": Action.ROTATE_CW,
    "r": Action.HOLD,
}

RESTART_KEY = "F5"

CONTROLS = (
    "←/→  Move",
    "↓  Soft drop (one row)",
    "Space  Hard drop",
    "W / E  Rotate CCW / CW",
    "Q  Rotate 180°",
    "R  Hold",
    f"{RESTART_KEY}  Restart",
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

    def __init__(self, root: tk.Tk, seed: int = 0, *, ai: bool = False,
                 ai_interval_ms: int = 750) -> None:
        if ai_interval_ms <= 0:
            raise ValueError("AI interval must be positive")
        self.root = root
        self.seed = seed
        self.game = Game(seed)
        self.ai = ai
        self.ai_interval_ms = ai_interval_ms
        self.agent = BaselineAgent() if ai else None
        self.paused = False
        self.stopped = False
        self.closed = False
        self.decision: Decision | None = None
        self._timer: str | None = None
        width = self.MARGIN * 3 + self.SIDE * 2 + WIDTH * self.CELL
        height = self.MARGIN * 2 + HEIGHT * self.CELL
        self.canvas = tk.Canvas(root, width=width, height=height, bg="#16161d", highlightthickness=0)
        self.canvas.pack()
        root.title("Tetris Trainer — no gravity")
        root.resizable(False, False)
        root.bind("<KeyPress>", self._key)
        root.protocol("WM_DELETE_WINDOW", self._close)
        self.draw()
        self._schedule()

    def _cancel_timer(self) -> None:
        if self._timer is not None:
            self.root.after_cancel(self._timer)
            self._timer = None

    def _schedule(self) -> None:
        if (self.ai and not self.paused and not self.stopped and not self.closed
                and not self.game.game_over and self._timer is None):
            self._timer = self.root.after(self.ai_interval_ms, self._ai_step)

    def _ai_step(self) -> None:
        self._timer = None
        if self.closed or self.paused or self.stopped or self.game.game_over:
            return
        assert self.agent is not None
        self.decision = self.agent.decide(self.game)
        if self.decision is None:
            self.stopped = True
        else:
            transition = self.game.apply_placement(self.decision.placement)
            self.stopped = not transition.accepted
        self.draw()
        self._schedule()

    def _close(self) -> None:
        self.closed = True
        self._cancel_timer()
        self.root.destroy()

    @property
    def board_x(self) -> int:
        return self.MARGIN * 2 + self.SIDE

    def _key(self, event: tk.Event) -> str:
        key = event.keysym
        if key == RESTART_KEY:
            self._cancel_timer()
            self.game = Game(self.seed)
            self.paused = False
            self.stopped = False
            self.decision = None
            self._schedule()
        elif self.ai and key.lower() == "p":
            self.paused = not self.paused
            self._cancel_timer()
            self._schedule()
        elif self.ai and key == "Escape":
            self._close()
            return "break"
        elif self.ai:
            return "break"
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
            self.MARGIN, controls_y,
            text="CONTROLS\n" + "\n".join(
                ("P  Pause / resume", "F5  Restart", "Esc  Close") if self.ai else CONTROLS), fill="#d3d3dc",
            anchor="nw", justify="left", font=("TkDefaultFont", 9), width=self.SIDE,
        )
        if self.ai:
            state = ("Game over" if self.game.game_over else "Stopped" if self.stopped
                     else "Paused" if self.paused else "Playing")
            details = f"BASELINE AI\n{state}"
            if self.decision is not None:
                features = self.decision.features
                details += (f"\nScore: {self.decision.score:.3f}\nHoles: {features.holes}"
                            f"\nHeight: {features.aggregate_height}"
                            f"\nBumpiness: {features.bumpiness}"
                            f"\nCleared: {features.lines_cleared}"
                            f"\nCandidates: {self.decision.placements_evaluated}")
            self.canvas.create_text(
                self.MARGIN, 310, text=details, fill="#d3d3dc", anchor="nw",
                justify="left", font=("TkDefaultFont", 9), width=self.SIDE)

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
            self.canvas.create_text(cx, cy + 22, text=f"Press {RESTART_KEY} to restart", fill="white")


def main() -> None:
    parser = argparse.ArgumentParser(description="Play no-gravity Tetris Trainer")
    parser.add_argument("--seed", type=int, default=0, help="deterministic seven-bag seed")
    parser.add_argument("--ai", action="store_true", help="watch the one-ply baseline AI")
    parser.add_argument("--ai-interval-ms", type=int, default=750,
                        help="delay between AI placements in milliseconds (positive)")
    args = parser.parse_args()
    if args.ai_interval_ms <= 0:
        parser.error("--ai-interval-ms must be positive")
    root = tk.Tk()
    TetrisWindow(root, args.seed, ai=args.ai, ai_interval_ms=args.ai_interval_ms)
    root.mainloop()


if __name__ == "__main__":
    main()
