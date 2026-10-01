from dataclasses import replace
import unittest
from unittest.mock import patch

from tetris_trainer import Action, Game, SimulationResult
from tetris_trainer.board import Board, WIDTH
from tetris_trainer.engine import ActivePiece
from tetris_trainer.pieces import Orientation, Tetromino


class SimulationTests(unittest.TestCase):
    def test_direct_api_returns_game_and_supports_recursive_simulation(self):
        root = Game(101)
        before = root.snapshot()
        placement = root.legal_placements()[0]
        child = root.simulate_placement(placement)
        twin = root.simulate_placement(placement)
        self.assertIsInstance(child, Game)
        self.assertIsNot(child, root)
        self.assertEqual(child.snapshot(), twin.snapshot())
        real = root.clone()
        self.assertTrue(real.apply_placement(placement).accepted)
        self.assertEqual(child.snapshot(), real.snapshot())
        parent_before = child.snapshot()
        for choice in child.legal_placements():
            grandchild = child.simulate_placement(choice)
            repeated = twin.simulate_placement(choice)
            self.assertIsInstance(grandchild, Game)
            self.assertEqual(grandchild.snapshot(), repeated.snapshot())
            self.assertIsNot(grandchild.randomizer, child.randomizer)
            self.assertEqual(child.snapshot(), parent_before)
            self.assertEqual(root.snapshot(), before)
        child.apply(Action.HOLD)
        self.assertEqual(twin.snapshot(), parent_before)
        self.assertEqual(root.snapshot(), before)

    def test_direct_api_rejects_stale_invalid_and_terminal_choices(self):
        root = Game(7)
        stale = root.legal_placements()[0]
        root.apply(Action.MOVE_LEFT)
        current = root.legal_placements()[0]
        for invalid in (stale, None, replace(current, x=99)):
            before = root.snapshot()
            with self.assertRaises(ValueError):
                root.simulate_placement(invalid)
            self.assertEqual(root.snapshot(), before)
        root.game_over = True
        before = root.snapshot()
        with self.assertRaises(ValueError):
            root.simulate_placement(current)
        self.assertEqual(root.snapshot(), before)

    def test_direct_api_line_clear_matches_metadata_and_real_execution(self):
        root = Game(42)
        root.active = ActivePiece(Tetromino.I)
        root.hold_used = True
        root.board = Board().with_cells({
            (x, 19): Tetromino.J for x in range(WIDTH) if x not in (3, 4, 5, 6)
        })
        before = root.snapshot()
        placement = next(p for p in root.legal_placements()
                         if set(p.cells) == {(x, 19) for x in (3, 4, 5, 6)})
        child = root.simulate_placement(placement)
        metadata = root.simulate_placement_result(placement)
        self.assertEqual(child.snapshot(), metadata.game.snapshot())
        self.assertEqual(child.total_lines, 1)
        self.assertEqual(child.board, Board())
        self.assertFalse(child.hold_used)
        self.assertEqual(root.snapshot(), before)

    def test_mutable_board_input_is_normalized_before_clone_sharing(self):
        rows = [[None] * WIDTH for _ in range(20)]
        root = Game(3)
        root.board = Board(rows)
        clone = root.clone()
        before = root.snapshot()
        rows[19][0] = Tetromino.Z
        rows[0] = [Tetromino.J] * WIDTH
        self.assertEqual(root.snapshot(), before)
        self.assertEqual(clone.snapshot(), before)
        self.assertIsInstance(root.board.rows, tuple)
        self.assertTrue(all(isinstance(row, tuple) for row in root.board.rows))
        clone.board = clone.board.with_cells({(0, 19): Tetromino.Z})
        self.assertEqual(root.snapshot(), before)

    def test_clone_preserves_all_fields_without_initialization(self):
        game = Game(123)
        game.apply(Action.HOLD)
        game.apply(Action.ROTATE_180)
        game.apply(Action.SOFT_DROP)
        game.total_lines = 7
        game.board = Board().with_cells({(0, 19): Tetromino.Z})
        before = game.snapshot()
        with patch.object(Game, '__init__', side_effect=AssertionError('must not spawn')):
            clone = game.clone()
        self.assertEqual(clone.snapshot(), before)
        self.assertEqual(game.snapshot(), before)
        self.assertEqual(vars(clone).keys(), vars(game).keys())
        self.assertIs(clone.board, game.board)
        self.assertIs(clone.active, game.active)
        self.assertIsNot(clone.randomizer, game.randomizer)
        self.assertIsNot(clone.randomizer._rng, game.randomizer._rng)
        self.assertIsNot(clone.randomizer._pieces, game.randomizer._pieces)

    def test_mutations_are_independent_in_both_directions(self):
        for mutate_clone in (False, True):
            with self.subTest(mutate_clone=mutate_clone):
                root = Game(42)
                clone = root.clone()
                changed, untouched = (clone, root) if mutate_clone else (root, clone)
                before = untouched.snapshot()
                changed.apply_many((Action.HOLD, Action.ROTATE_CW, Action.HARD_DROP))
                changed.board = changed.board.with_cells({(0, 19): Tetromino.Z})
                changed.total_lines += 1
                changed.randomizer.peek(50)
                self.assertEqual(untouched.snapshot(), before)
                self.assertNotEqual(changed.snapshot(), before)

    def test_randomizer_exact_stream_and_independence_across_many_bags(self):
        root = Game(314)
        for _ in range(3):
            root.randomizer.pop()
        before = root.snapshot()
        first, second = root.clone(), root.clone()
        self.assertEqual(first.randomizer.peek(31), second.randomizer.peek(31))
        for _ in range(100):
            self.assertEqual(first.randomizer.pop(), second.randomizer.pop())
            self.assertEqual(first.randomizer.snapshot(), second.randomizer.snapshot())
        self.assertEqual(root.snapshot(), before)
        reference = root.clone()
        self.assertEqual([root.randomizer.pop() for _ in range(100)],
                         [reference.randomizer.pop() for _ in range(100)])

    def test_clones_follow_identical_human_actions(self):
        first = Game(11).clone()
        second = first.clone()
        actions = (Action.HOLD, Action.ROTATE_180, Action.MOVE_LEFT,
                   Action.SOFT_DROP, Action.HARD_DROP, Action.HOLD, Action.HARD_DROP)
        self.assertEqual(first.apply_many(actions), second.apply_many(actions))
        self.assertEqual(first.snapshot(), second.snapshot())

    def test_game_over_and_absent_active_preserved(self):
        for active in (None, ActivePiece(Tetromino.T, Orientation.LEFT, -1, 3)):
            root = Game(0)
            root.active = active
            root.game_over = True
            clone = root.clone()
            self.assertEqual(clone.snapshot(), root.snapshot())
            self.assertEqual(clone.legal_placements(), ())
            self.assertFalse(clone.apply(Action.HOLD).accepted)

    def test_every_simulation_matches_authoritative_execution(self):
        root = Game(42)
        root.board = Board().with_cells({(x, 16): Tetromino.J for x in range(4)})
        root.active = ActivePiece(Tetromino.T)
        before = root.snapshot()
        next_kind = root.upcoming[0]
        for placement in root.legal_placements():
            real = root.clone()
            expected = real.apply_placement(placement)
            result = root.simulate_placement_result(placement)
            self.assertIsInstance(result, SimulationResult)
            self.assertEqual(result.transition, expected)
            self.assertEqual(result.game.snapshot(), real.snapshot())
            self.assertEqual(result.game.active, ActivePiece(next_kind))
            self.assertEqual(root.snapshot(), before)

    def test_simulation_uses_authoritative_placement_path(self):
        root = Game(2)
        placement = root.legal_placements()[0]
        original = Game.apply_placement
        with patch.object(Game, 'apply_placement', autospec=True,
                          side_effect=original) as execute:
            result = root.simulate_placement_result(placement)
        execute.assert_called_once_with(result.game, placement)
        self.assertIsNot(result.game, root)

    def test_line_clear_hold_reset_and_queue_refill(self):
        root = Game(42)
        root.active = ActivePiece(Tetromino.I)
        root.hold_piece = Tetromino.T
        root.hold_used = True
        root.total_lines = 3
        root.board = Board().with_cells({
            (x, 19): Tetromino.J for x in range(WIDTH) if x not in (3, 4, 5, 6)
        })
        # Force the next lock to refill the queue from the preserved RNG.
        while len(root.randomizer._pieces) > 1:
            root.randomizer._pieces.pop()
        before = root.snapshot()
        expected_next = root.randomizer._pieces[0]
        placement = next(p for p in root.legal_placements()
                         if set(p.cells) == {(x, 19) for x in (3, 4, 5, 6)})
        result = root.simulate_placement_result(placement)
        self.assertEqual(result.transition.lines_cleared, 1)
        self.assertEqual(result.game.total_lines, 4)
        self.assertEqual(result.game.board, Board())
        self.assertEqual(result.game.active, ActivePiece(expected_next))
        self.assertEqual(result.game.hold_piece, Tetromino.T)
        self.assertFalse(result.game.hold_used)
        self.assertGreaterEqual(len(result.game.upcoming), Game.PREVIEW_COUNT)
        self.assertEqual(root.snapshot(), before)
        real = root.clone()
        self.assertEqual(real.apply_placement(placement), result.transition)
        self.assertEqual(real.snapshot(), result.game.snapshot())

    def test_next_spawn_topout_is_simulated(self):
        root = Game(9)
        root.board = Board().with_cells({cell: Tetromino.Z
                                        for cell in ActivePiece(root.upcoming[0]).cells})
        root.active = ActivePiece(Tetromino.O, x=0, y=18)
        before = root.snapshot()
        result = root.simulate_placement_result(root.legal_placements()[0])
        self.assertTrue(result.transition.locked)
        self.assertTrue(result.transition.game_over)
        self.assertTrue(result.game.game_over)
        self.assertEqual(result.game.legal_placements(), ())
        self.assertEqual(root.snapshot(), before)

    def test_stale_and_invalid_simulation_returns_unchanged_independent_clone(self):
        root = Game(7)
        placement = root.legal_placements()[0]
        root.apply(Action.MOVE_LEFT)
        for invalid in (placement, None, replace(root.legal_placements()[0], x=99)):
            before = root.snapshot()
            result = root.simulate_placement_result(invalid)
            self.assertFalse(result.transition.accepted)
            self.assertEqual(result.game.snapshot(), before)
            self.assertEqual(root.snapshot(), before)
            result.game.apply(Action.HOLD)
            self.assertEqual(root.snapshot(), before)

    def test_repeated_and_two_ply_simulations_are_deterministic(self):
        root = Game(101)
        before = root.snapshot()
        placement = root.legal_placements()[0]
        first, second = root.simulate_placement_result(placement), root.simulate_placement_result(placement)
        self.assertEqual(first.transition, second.transition)
        self.assertEqual(first.game.snapshot(), second.game.snapshot())
        parent_before = first.game.snapshot()
        next_placements = first.game.legal_placements()
        self.assertTrue(next_placements)
        for choice in next_placements:
            left = first.game.simulate_placement_result(choice)
            right = second.game.simulate_placement_result(choice)
            self.assertEqual(left.transition, right.transition)
            self.assertEqual(left.game.snapshot(), right.game.snapshot())
            self.assertEqual(first.game.snapshot(), parent_before)
            self.assertEqual(root.snapshot(), before)
        first.game.apply(Action.HOLD)
        self.assertEqual(second.game.snapshot(), parent_before)
        self.assertEqual(root.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
