import unittest

from tetris_trainer.board import Board, HEIGHT, WIDTH
from tetris_trainer.pieces import Tetromino


class BoardTests(unittest.TestCase):
    def test_single_line_clear_and_collapse(self):
        cells = {(x, HEIGHT - 1): Tetromino.I for x in range(WIDTH)}
        cells[(4, HEIGHT - 2)] = Tetromino.T
        board, count = Board().with_cells(cells).clear_lines()
        self.assertEqual(count, 1)
        self.assertEqual(board.rows[HEIGHT - 1][4], Tetromino.T)
        self.assertTrue(all(cell is None for cell in board.rows[0]))

    def test_multiple_line_clear(self):
        cells = {
            (x, y): Tetromino.Z
            for y in (HEIGHT - 1, HEIGHT - 2)
            for x in range(WIDTH)
        }
        cells[(2, HEIGHT - 3)] = Tetromino.J
        board, count = Board().with_cells(cells).clear_lines()
        self.assertEqual(count, 2)
        self.assertEqual(board.rows[HEIGHT - 1][2], Tetromino.J)
        self.assertTrue(all(cell is None for row in board.rows[:2] for cell in row))

    def test_lock_rejects_overlap(self):
        board = Board().with_cells({(1, 1): Tetromino.O})
        with self.assertRaises(ValueError):
            board.lock(((1, 1), (2, 1), (1, 2), (2, 2)), Tetromino.O)


if __name__ == "__main__":
    unittest.main()
