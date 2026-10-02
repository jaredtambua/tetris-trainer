import unittest
from dataclasses import FrozenInstanceError

from tetris_trainer.board import Board, GarbageCell, HEIGHT, WIDTH
from tetris_trainer.pieces import Tetromino


class GarbageBoardTests(unittest.TestCase):
    def test_insertion_shifts_existing_cells_and_preserves_source(self):
        source = Board().with_cells({(4, HEIGHT - 1): Tetromino.T})
        board, overflow = source.insert_garbage((2, 7))
        self.assertFalse(overflow)
        self.assertIs(board.rows[HEIGHT - 3][4], Tetromino.T)
        self.assertIs(source.rows[HEIGHT - 1][4], Tetromino.T)
        for y, hole in ((HEIGHT - 2, 2), (HEIGHT - 1, 7)):
            self.assertIsNone(board.rows[y][hole])
            for x in range(WIDTH):
                self.assertEqual(board.occupied(x, y), x != hole)
                if x != hole:
                    self.assertIs(board.rows[y][x], GarbageCell.GARBAGE)

    def test_no_rows_returns_original_board(self):
        source = Board()
        board, overflow = source.insert_garbage(())
        self.assertIs(board, source)
        self.assertFalse(overflow)

    def test_overflow_detects_only_discarded_occupied_rows(self):
        source = Board().with_cells({(3, 1): Tetromino.I})
        self.assertFalse(source.insert_garbage((0,))[1])
        self.assertTrue(source.insert_garbage((0, 0))[1])
        self.assertFalse(Board().insert_garbage((0,) * HEIGHT)[1])
        board, overflow = Board().insert_garbage((0,) * HEIGHT + (9,))
        self.assertTrue(overflow)
        self.assertEqual(len(board.rows), HEIGHT)
        self.assertIsNone(board.rows[-1][9])

    def test_hole_validation(self):
        for hole in (-1, WIDTH, True, 1.0, "1", None):
            with self.subTest(hole=hole), self.assertRaises(ValueError):
                Board().insert_garbage((hole,))

    def test_line_clear_reports_original_indices_and_mixed_garbage_rows(self):
        source, _ = Board().insert_garbage((3, 4))
        source = source.with_cells({
            (3, HEIGHT - 2): Tetromino.T,
            (4, HEIGHT - 1): Tetromino.I,
            **{(x, 5): Tetromino.J for x in range(WIDTH)},
            (2, 4): Tetromino.O,
        })
        result = source.clear_lines_result()
        self.assertEqual(result.cleared_rows, (5, HEIGHT - 2, HEIGHT - 1))
        self.assertEqual(result.cleared_lines, 3)
        self.assertEqual(result.garbage_lines, 2)
        self.assertIs(result.board.rows[7][2], Tetromino.O)
        self.assertEqual(source.clear_lines(), (result.board, 3))
        self.assertIs(source.rows[-1][0], GarbageCell.GARBAGE)
        with self.assertRaises(FrozenInstanceError):
            result.garbage_lines = 0

    def test_incomplete_garbage_rows_do_not_clear(self):
        board, _ = Board().insert_garbage((0,))
        result = board.clear_lines_result()
        self.assertEqual(result.board, board)
        self.assertEqual(result.cleared_rows, ())
        self.assertEqual(result.garbage_lines, 0)


if __name__ == "__main__":
    unittest.main()
