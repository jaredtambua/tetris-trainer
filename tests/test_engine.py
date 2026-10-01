import time
import unittest

from tetris_trainer.board import Board, HEIGHT, WIDTH
from tetris_trainer.engine import Action, ActivePiece, Game
from tetris_trainer.pieces import Orientation, Tetromino


class MovementTests(unittest.TestCase):
    def test_legal_left_and_right(self):
        game = Game(1)
        start = game.active
        self.assertTrue(game.apply(Action.MOVE_LEFT).accepted)
        self.assertEqual(game.active.x, start.x - 1)
        self.assertTrue(game.apply(Action.MOVE_RIGHT).accepted)
        self.assertEqual(game.active, start)

    def test_wall_collision_leaves_state_unchanged(self):
        game = Game(1)
        while game.apply(Action.MOVE_LEFT).accepted:
            pass
        before = game.snapshot()
        self.assertFalse(game.apply(Action.MOVE_LEFT).accepted)
        self.assertEqual(game.snapshot(), before)

    def test_occupied_cell_collision(self):
        game = Game(1)
        game.active = ActivePiece(Tetromino.T)
        game.board = Board().with_cells({(6, 1): Tetromino.Z})
        before = game.active
        self.assertFalse(game.apply(Action.MOVE_RIGHT).accepted)
        self.assertEqual(game.active, before)

    def test_soft_drop_moves_exactly_one_row(self):
        game = Game(1)
        y = game.active.y
        result = game.apply(Action.SOFT_DROP)
        self.assertTrue(result.accepted)
        self.assertEqual(game.active.y, y + 1)
        self.assertFalse(result.locked)

    def test_blocked_soft_drop_does_not_lock(self):
        game = Game(1)
        game.active = ActivePiece(Tetromino.I, y=18)
        before_board = game.board
        result = game.apply(Action.SOFT_DROP)
        self.assertFalse(result.accepted)
        self.assertFalse(result.locked)
        self.assertEqual(game.active.y, 18)
        self.assertEqual(game.board, before_board)


class HardDropAndLockTests(unittest.TestCase):
    def test_hard_drop_lands_locks_and_spawns_next(self):
        game = Game(7)
        game.active = ActivePiece(Tetromino.T)
        expected_next = game.upcoming[0]
        result = game.apply(Action.HARD_DROP)
        self.assertTrue(result.accepted)
        self.assertTrue(result.locked)
        self.assertEqual(result.lines_cleared, 0)
        self.assertEqual(game.active.kind, expected_next)
        expected_cells = {(4, 18), (3, 19), (4, 19), (5, 19)}
        actual = {
            (x, y)
            for y, row in enumerate(game.board.rows)
            for x, cell in enumerate(row)
            if cell is Tetromino.T
        }
        self.assertEqual(actual, expected_cells)

    def test_lock_writes_exactly_four_without_overlap(self):
        game = Game(3)
        game.active = ActivePiece(Tetromino.O)
        game.apply(Action.HARD_DROP)
        occupied = [cell for row in game.board.rows for cell in row if cell is not None]
        self.assertEqual(len(occupied), 4)

    def test_hard_drop_is_deterministic(self):
        left, right = Game(99), Game(99)
        self.assertEqual(left.apply(Action.HARD_DROP), right.apply(Action.HARD_DROP))
        self.assertEqual(left.snapshot(), right.snapshot())

    def test_lock_clears_line_and_reports_count(self):
        game = Game(4)
        game.board = Board().with_cells(
            {(x, HEIGHT - 1): Tetromino.J for x in range(WIDTH) if x not in (3, 4, 5, 6)}
        )
        game.active = ActivePiece(Tetromino.I)
        result = game.apply(Action.HARD_DROP)
        self.assertEqual(result.lines_cleared, 1)
        self.assertEqual(game.total_lines, 1)

    def test_blocked_next_spawn_sets_game_over(self):
        game = Game(4)
        next_kind = game.upcoming[0]
        spawn_cells = ActivePiece(next_kind).cells
        visible_spawn_cells = {(x, y): Tetromino.Z for x, y in spawn_cells if y >= 0}
        game.board = game.board.with_cells(visible_spawn_cells)
        # Put the active piece safely at the floor without crossing the filled spawn area.
        game.active = ActivePiece(Tetromino.O, x=0, y=18)
        result = game.apply(Action.HARD_DROP)
        self.assertTrue(result.locked)
        self.assertTrue(result.game_over)
        self.assertTrue(game.game_over)


class RotationTests(unittest.TestCase):
    def new_t_game(self):
        game = Game(1)
        game.active = ActivePiece(Tetromino.T, x=3, y=5)
        return game

    def test_unobstructed_clockwise(self):
        game = self.new_t_game()
        self.assertTrue(game.apply(Action.ROTATE_CW).accepted)
        self.assertEqual(game.active.orientation, Orientation.RIGHT)

    def test_unobstructed_counterclockwise(self):
        game = self.new_t_game()
        self.assertTrue(game.apply(Action.ROTATE_CCW).accepted)
        self.assertEqual(game.active.orientation, Orientation.LEFT)

    def test_unobstructed_180(self):
        game = self.new_t_game()
        self.assertTrue(game.apply(Action.ROTATE_180).accepted)
        self.assertEqual(game.active.orientation, Orientation.REVERSE)

    def test_representative_wall_kick(self):
        game = Game(1)
        game.active = ActivePiece(Tetromino.T, Orientation.RIGHT, x=-1, y=4)
        self.assertTrue(game.apply(Action.ROTATE_CCW).accepted)
        self.assertEqual(game.active.orientation, Orientation.SPAWN)
        self.assertEqual(game.active.x, 0)

    def test_representative_floor_kick(self):
        game = Game(1)
        game.active = ActivePiece(Tetromino.T, Orientation.SPAWN, x=3, y=18)
        self.assertTrue(game.apply(Action.ROTATE_CW).accepted)
        self.assertEqual(game.active.orientation, Orientation.RIGHT)
        self.assertLess(game.active.y, 18)

    def test_fully_blocked_rotation_is_atomic(self):
        game = self.new_t_game()
        active_cells = set(game.active.cells)
        blockers = {
            (x, y): Tetromino.Z
            for y in range(2, 10)
            for x in range(WIDTH)
            if (x, y) not in active_cells
        }
        game.board = Board().with_cells(blockers)
        before = game.snapshot()
        self.assertFalse(game.apply(Action.ROTATE_CW).accepted)
        self.assertEqual(game.snapshot(), before)


class HoldTests(unittest.TestCase):
    def test_empty_hold_consumes_queue_and_resets_spawn(self):
        game = Game(13)
        outgoing, incoming = game.active.kind, game.upcoming[0]
        self.assertTrue(game.apply(Action.HOLD).accepted)
        self.assertEqual(game.hold_piece, outgoing)
        self.assertEqual(game.active, ActivePiece(incoming))

    def test_swap_with_occupied_hold(self):
        game = Game(13)
        game.hold_piece = Tetromino.T
        outgoing = game.active.kind
        game.active = ActivePiece(outgoing, Orientation.LEFT, x=1, y=8)
        self.assertTrue(game.apply(Action.HOLD).accepted)
        self.assertEqual(game.hold_piece, outgoing)
        self.assertEqual(game.active, ActivePiece(Tetromino.T))

    def test_second_hold_before_lock_rejected(self):
        game = Game(13)
        game.apply(Action.HOLD)
        before = game.snapshot()
        self.assertFalse(game.apply(Action.HOLD).accepted)
        self.assertEqual(game.snapshot(), before)

    def test_hold_available_again_after_lock(self):
        game = Game(13)
        game.apply(Action.HOLD)
        game.apply(Action.HARD_DROP)
        self.assertFalse(game.hold_used)
        self.assertTrue(game.apply(Action.HOLD).accepted)


class DeterminismAndNoGravityTests(unittest.TestCase):
    ACTIONS = (
        Action.MOVE_LEFT, Action.ROTATE_CW, Action.SOFT_DROP,
        Action.HARD_DROP, Action.HOLD, Action.ROTATE_180,
        Action.MOVE_RIGHT, Action.HARD_DROP,
    )

    def test_same_seed_and_actions_produce_identical_state(self):
        first, second = Game(2026), Game(2026)
        self.assertEqual(first.apply_many(self.ACTIONS), second.apply_many(self.ACTIONS))
        self.assertEqual(first.snapshot(), second.snapshot())

    def test_passage_of_time_cannot_change_state(self):
        game = Game(8)
        before = game.snapshot()
        time.sleep(0.01)
        self.assertEqual(game.snapshot(), before)

    def test_non_downward_transition_does_not_descend(self):
        game = Game(8)
        y = game.active.y
        game.apply(Action.MOVE_LEFT)
        self.assertEqual(game.active.y, y)


if __name__ == "__main__":
    unittest.main()
