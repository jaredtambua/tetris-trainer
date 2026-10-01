from dataclasses import FrozenInstanceError
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from tetris_trainer.baseline import (
    BaselineAgent, BoardFeatures, extract_features, run_headless, score_features,
)
from tetris_trainer.board import Board, HEIGHT, WIDTH
from tetris_trainer.engine import ActivePiece, Game
from tetris_trainer.pieces import Tetromino


class FeatureTests(unittest.TestCase):
    def test_empty_board(self):
        self.assertEqual(extract_features(Board()), BoardFeatures(0, 0, 0, 0))

    def test_holes_height_bumpiness_and_line_metadata(self):
        board = Board().with_cells({(0, 17): Tetromino.T, (0, 19): Tetromino.T,
                                    (1, 18): Tetromino.J})
        features = extract_features(board, lines_cleared=2)
        self.assertEqual(features, BoardFeatures(2, 5, 3, 2))
        self.assertEqual(score_features(features), 2)
        self.assertEqual(features, extract_features(board, lines_cleared=2))
        with self.assertRaises(FrozenInstanceError):
            features.holes = 0

    def test_flat_surface(self):
        board = Board().with_cells({(x, HEIGHT - 1): Tetromino.I for x in range(WIDTH)})
        self.assertEqual(extract_features(board), BoardFeatures(0, WIDTH, 0, 0))

    def test_topmost_cell_and_all_empty_cells_below_are_holes(self):
        board = Board().with_cells({(0, 0): Tetromino.J})
        self.assertEqual(extract_features(board), BoardFeatures(HEIGHT - 1, HEIGHT, HEIGHT, 0))


class AgentTests(unittest.TestCase):
    def test_highest_score_and_every_placement_simulated_once(self):
        choices = (object(), object(), object())
        boards = (Board().with_cells({(0, 0): Tetromino.J}), Board(),
                  Board().with_cells({(0, 19): Tetromino.J}))
        game = Mock(spec=Game)
        game.total_lines = 5
        game.legal_placements.return_value = choices
        game.simulate_placement.side_effect = [
            SimpleNamespace(board=board, total_lines=5) for board in boards
        ]
        decision = BaselineAgent().decide(game)
        self.assertIs(decision.placement, choices[1])
        self.assertEqual(decision.score, 0)
        self.assertEqual(decision.features, BoardFeatures(0, 0, 0, 0))
        self.assertEqual(decision.placements_evaluated, 3)
        game.legal_placements.assert_called_once_with()
        self.assertEqual([call.args[0] for call in game.simulate_placement.call_args_list], list(choices))

    def test_deterministic_tie_breaking_keeps_first_legal_placement(self):
        game = Game(23)
        expected = game.legal_placements()[0]
        before = game.snapshot()
        with patch('tetris_trainer.baseline.score_features', return_value=0):
            for _ in range(2):
                self.assertEqual(BaselineAgent().decide(game).placement, expected)
        self.assertEqual(game.snapshot(), before)

    def test_deterministic_legal_choice_does_not_mutate_source(self):
        game = Game(42)
        before = game.snapshot()
        first, second = BaselineAgent().decide(game), BaselineAgent().decide(game)
        self.assertEqual(first, second)
        self.assertIn(first.placement, game.legal_placements())
        self.assertEqual(game.snapshot(), before)
        future = game.simulate_placement(first.placement)
        self.assertEqual(first.features, extract_features(future.board, future.total_lines - game.total_lines))
        self.assertEqual(first.score, score_features(first.features))
        with self.assertRaises(FrozenInstanceError):
            first.score = 10
        self.assertTrue(game.apply_placement(first.placement).accepted)

    def test_no_legal_choices_returns_none_without_simulating(self):
        game = Mock(spec=Game)
        game.legal_placements.return_value = ()
        self.assertIsNone(BaselineAgent().decide(game))
        game.simulate_placement.assert_not_called()

    def test_only_candidate_line_delta_is_scored(self):
        game = Game(42)
        game.total_lines = 10
        game.board = Board().with_cells({(x, 19): Tetromino.J for x in range(WIDTH)
                                        if x not in (3, 4, 5, 6)})
        game.active = ActivePiece(Tetromino.I)
        decision = BaselineAgent().decide(game)
        self.assertEqual(decision.features.lines_cleared, 1)
        self.assertEqual(decision.features.aggregate_height, 0)
        self.assertEqual(decision.score, 10)


class HeadlessTests(unittest.TestCase):
    def test_seeded_run_limit_and_reproduction(self):
        first, second = run_headless(42, 4), run_headless(42, 4)
        self.assertEqual(first.placements, 4)
        self.assertEqual(first.stop_reason, 'limit')
        self.assertEqual(first.game.snapshot(), second.game.snapshot())
        self.assertEqual(first.lines_cleared, first.game.total_lines)
        self.assertEqual(first.game_over, first.game.game_over)

    def test_zero_and_invalid_limits(self):
        summary = run_headless(11, 0)
        self.assertEqual(summary.placements, 0)
        self.assertEqual(summary.game.snapshot(), Game(11).snapshot())
        for limit in (-1, 1.5, True, '2', None):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                run_headless(0, limit)

    def test_no_moves_and_game_over_stop_reasons(self):
        with patch('tetris_trainer.baseline.BaselineAgent.decide', return_value=None):
            summary = run_headless(0, 10)
        self.assertEqual(summary.stop_reason, 'no_legal_placements')
        self.assertEqual(summary.placements, 0)
        self.assertFalse(summary.game_over)
        terminal = Game(0)
        terminal.game_over = True
        with patch('tetris_trainer.baseline.Game', return_value=terminal):
            summary = run_headless(0, 10)
        self.assertEqual(summary.stop_reason, 'game_over')
        self.assertEqual(summary.placements, 0)

    def test_import_and_execution_do_not_load_tk_or_ui(self):
        code = (
            'import sys; from tetris_trainer.baseline import run_headless; '
            'result = run_headless(0, 1); assert result.placements == 1; '
            'assert "tkinter" not in sys.modules; assert "tetris_trainer.ui" not in sys.modules'
        )
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
