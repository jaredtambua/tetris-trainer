from dataclasses import FrozenInstanceError, replace
import subprocess
import sys
import unittest
from unittest.mock import patch

from tetris_trainer.board import Board, HEIGHT, WIDTH
from tetris_trainer.engine import Action, ActivePiece, Game
from tetris_trainer.environment import (
    ACTIVE_SLICE, BOARD_SHAPE, BOARD_SLICE, CONTRACT_VERSION, HOLD_SLICE,
    OBSERVATION_SIZE, PIECE_IDS, QUEUE_LENGTH, QUEUE_SLICE, SPIN_IDS, TERMINATED_INDEX,
    PlacementEnvironment, encode_observation,
)
from tetris_trainer.pieces import Orientation, Tetromino


class ObservationTests(unittest.TestCase):
    def test_exact_shape_layout_and_numerical_types(self):
        env = PlacementEnvironment(42)
        values = env.observe()
        self.assertEqual(CONTRACT_VERSION, 2)
        self.assertEqual(BOARD_SHAPE, (20, 10))
        self.assertEqual(OBSERVATION_SIZE, 929)
        self.assertEqual(len(values), 929)
        self.assertIsInstance(values, tuple)
        self.assertTrue(all(type(value) is int for value in values))
        self.assertEqual(values[BOARD_SLICE], (0,) * 200)
        self.assertEqual(ACTIVE_SLICE, slice(200, 204))
        self.assertEqual(HOLD_SLICE, slice(204, 206))
        self.assertEqual(QUEUE_SLICE, slice(206, 211))
        self.assertEqual(QUEUE_LENGTH, 5)
        self.assertEqual(TERMINATED_INDEX, 211)
        self.assertEqual(values[TERMINATED_INDEX], 0)
        with self.assertRaises(TypeError):
            values[0] = 1

    def test_board_mapping_is_row_major_and_occupancy_only(self):
        game = Game(0)
        occupied = {(2, 7): Tetromino.Z, (9, 19): Tetromino.J, (0, 0): Tetromino.O}
        game.board = Board().with_cells(occupied)
        values = PlacementEnvironment.from_game(game).observe()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                self.assertEqual(values[y * WIDTH + x], int((x, y) in occupied))

    def test_piece_ids_pose_hold_and_queue(self):
        expected_ids = dict(zip(Tetromino, (1, 2, 3, 4, 5, 6, 7)))
        self.assertEqual(PIECE_IDS, {None: 0, **expected_ids})
        for kind, kind_id in expected_ids.items():
            with self.subTest(kind=kind):
                game = Game(42)
                game.active = ActivePiece(kind, Orientation.LEFT, 1, 7)
                game.hold_piece = kind
                values = PlacementEnvironment.from_game(game).observe()
                self.assertEqual(values[ACTIVE_SLICE], (kind_id, 3, 1, 7))
                self.assertEqual(values[HOLD_SLICE], (kind_id, 1))
                self.assertEqual(values[QUEUE_SLICE], tuple(expected_ids[p] for p in game.upcoming))
                game.hold_used = True
                self.assertEqual(encode_observation(game, terminated=False)[HOLD_SLICE], (kind_id, 0))

    def test_absent_piece_empty_hold_padding_and_signed_pose(self):
        game = Game(42)
        game.active = ActivePiece(Tetromino.I, Orientation.RIGHT, -2, -5)
        values = encode_observation(game, terminated=False)
        self.assertEqual(values[ACTIVE_SLICE], (1, 1, -2, -5))
        game.active = None
        game.randomizer._pieces.clear()
        before = game.snapshot()
        values = encode_observation(game, terminated=True)
        self.assertEqual(values[ACTIVE_SLICE], (0, 0, 0, 0))
        self.assertEqual(values[HOLD_SLICE], (0, 0))
        self.assertEqual(values[QUEUE_SLICE], (0,) * 5)
        self.assertEqual(values[TERMINATED_INDEX], 1)
        self.assertEqual(game.snapshot(), before)

    def test_observe_and_action_reads_do_not_mutate_state_or_refill_queue(self):
        game = Game(42)
        game.randomizer._pieces.clear()
        source_before = game.snapshot()
        env = PlacementEnvironment.from_game(game)
        before = env._game.snapshot()
        actions = env.legal_actions()
        with patch.object(env._game.randomizer, 'peek', side_effect=AssertionError('preview refill')):
            for _ in range(3):
                self.assertEqual(env.observe()[QUEUE_SLICE], (0,) * 5)
                self.assertIs(env.legal_actions(), actions)
        self.assertEqual(env._game.snapshot(), before)
        self.assertEqual(game.snapshot(), source_before)


class ActionAndTransitionTests(unittest.TestCase):
    def test_candidate_correspondence_order_and_immutability(self):
        game = Game(42)
        env = PlacementEnvironment.from_game(game)
        candidates = env.legal_actions()
        self.assertTrue(candidates)
        placements = game.legal_placements()
        for index, (candidate, placement) in enumerate(zip(candidates, placements)):
            self.assertEqual(candidate.index, index)
            self.assertEqual(candidate.values, (PIECE_IDS[placement.kind], int(placement.orientation),
                                                placement.x, placement.y, SPIN_IDS[placement.spin]))
            self.assertEqual(candidate._placement, placement)
        self.assertEqual(len(candidates), len(placements))
        self.assertEqual(candidates, PlacementEnvironment(42).legal_actions())
        with self.assertRaises(FrozenInstanceError):
            candidates[0].index = 1

    def test_valid_step_matches_authoritative_execution_and_next_observation(self):
        game = Game(42)
        env = PlacementEnvironment.from_game(game)
        candidate = env.legal_actions()[0]
        with patch.object(Game, 'apply_placement', autospec=True,
                          side_effect=Game.apply_placement) as execute:
            result = env.step(candidate)
        execute.assert_called_once_with(env._game, candidate._placement)
        expected_transition = game.apply_placement(candidate._placement)
        self.assertEqual(env._game.snapshot(), game.snapshot())
        self.assertEqual(result.observation, env.observe())
        self.assertEqual(result.facts.placed, candidate.values)
        self.assertEqual(result.facts.locked, expected_transition.locked)
        self.assertEqual(result.facts.lines_cleared, expected_transition.lines_cleared)
        self.assertEqual(result.facts.game_over, expected_transition.game_over)
        self.assertEqual(result.facts.step_count, 1)
        self.assertFalse(result.terminated)
        self.assertIsNone(result.facts.terminal_reason)
        self.assertFalse(hasattr(result, 'reward'))

    def test_rejects_raw_indices_foreign_modified_and_stale_candidates_atomically(self):
        env = PlacementEnvironment(42)
        candidate = env.legal_actions()[0]
        foreign = PlacementEnvironment(42).legal_actions()[0]
        invalid = (None, 0, True, 0.0, candidate.values, foreign,
                   replace(candidate, index=-1), replace(candidate, index=True),
                   replace(candidate, index=0.0), replace(candidate, values=(1, 0, 99, 99, 0)),
                   replace(candidate))
        for action in invalid:
            before = env._game.snapshot()
            actions = env.legal_actions()
            with self.subTest(action=action), self.assertRaises(ValueError):
                env.step(action)
            self.assertEqual(env._game.snapshot(), before)
            self.assertIs(env.legal_actions(), actions)
        env.step(candidate)
        before = env._game.snapshot()
        with self.assertRaises(ValueError):
            env.step(candidate)
        self.assertEqual(env._game.snapshot(), before)

    def test_reset_same_seed_reproduces_observation_and_invalidates_old_handles(self):
        env = PlacementEnvironment(23)
        observation = env.observe()
        old = env.legal_actions()[0]
        self.assertEqual(env.reset(23), observation)
        self.assertEqual(old.values, env.legal_actions()[0].values)
        with self.assertRaises(ValueError):
            env.step(old)
        result = env.step(env.legal_actions()[0])
        self.assertEqual(result.facts.step_count, 1)

    def test_authoritative_state_guard_rejects_internally_stale_placement(self):
        env = PlacementEnvironment(42)
        action = env.legal_actions()[0]
        env._game.apply(Action.MOVE_LEFT)
        before = env._game.snapshot()
        with self.assertRaises(ValueError):
            env.step(action)
        self.assertEqual(env._game.snapshot(), before)

    def test_line_clear_facts_and_hold_preservation(self):
        game = Game(42)
        game.active = ActivePiece(Tetromino.I)
        game.hold_piece = Tetromino.Z
        game.hold_used = True
        game.total_lines = 7
        game.board = Board().with_cells({(x, 19): Tetromino.J for x in range(WIDTH)
                                        if x not in (3, 4, 5, 6)})
        env = PlacementEnvironment.from_game(game)
        action = next(a for a in env.legal_actions() if a.values == (1, 0, 3, 18, 0))
        before = game.snapshot()
        result = env.step(action)
        self.assertEqual(result.facts.lines_cleared, 1)
        self.assertEqual(result.facts.total_lines, 8)
        self.assertEqual(result.observation[BOARD_SLICE], (0,) * 200)
        self.assertEqual(result.observation[HOLD_SLICE], (7, 1))
        self.assertEqual(game.snapshot(), before)

    def test_terminal_next_spawn_and_no_actions_after_termination(self):
        game = Game(9)
        game.board = Board().with_cells({cell: Tetromino.Z for cell in ActivePiece(game.upcoming[0]).cells})
        game.active = ActivePiece(Tetromino.O, x=0, y=18)
        env = PlacementEnvironment.from_game(game)
        result = env.step(env.legal_actions()[0])
        self.assertTrue(result.terminated)
        self.assertTrue(result.facts.game_over)
        self.assertTrue(result.facts.locked)
        self.assertEqual(result.facts.terminal_reason, 'game_over')
        self.assertEqual(result.observation[TERMINATED_INDEX], 1)
        self.assertEqual(result.observation[HOLD_SLICE][1], 0)
        self.assertEqual(env.legal_actions(), ())
        with self.assertRaises(ValueError):
            env.step(None)

    def test_no_visible_lock_terminates_without_changing_engine_game_over(self):
        game = Game(42)
        game.board = Board().with_cells({(x, 1): Tetromino.J for x in range(WIDTH)})
        game.active = ActivePiece(Tetromino.O, y=-1)
        before = game.snapshot()
        env = PlacementEnvironment.from_game(game)
        self.assertTrue(env.terminated)
        self.assertFalse(env._game.game_over)
        self.assertEqual(env.terminal_reason, 'no_legal_placements')
        self.assertEqual(env.observe()[TERMINATED_INDEX], 1)
        self.assertEqual(env.legal_actions(), ())
        self.assertEqual(game.snapshot(), before)

    def test_seeded_steps_are_reproducible_and_instances_are_isolated(self):
        first, second = PlacementEnvironment(99), PlacementEnvironment(99)
        self.assertEqual(first.observe(), second.observe())
        self.assertIsNot(first._game.randomizer, second._game.randomizer)
        self.assertIsNot(first._game.randomizer._rng, second._game.randomizer._rng)
        for _ in range(5):
            self.assertEqual(first.legal_actions(), second.legal_actions())
            if first.terminated:
                break
            self.assertEqual(first.step(first.legal_actions()[0]), second.step(second.legal_actions()[0]))
        before = second._game.snapshot()
        first.reset(18)
        self.assertEqual(second._game.snapshot(), before)

    def test_from_game_clones_mutable_state_and_source_changes_are_isolated(self):
        source = Game(42)
        env = PlacementEnvironment.from_game(source)
        before = env._game.snapshot()
        source.apply(Action.HOLD)
        source.randomizer.peek(50)
        self.assertEqual(env._game.snapshot(), before)
        self.assertIsNot(env._game.randomizer._pieces, source.randomizer._pieces)

    def test_environment_runs_without_tk_or_ui_imports(self):
        code = (
            'import sys; from tetris_trainer.environment import PlacementEnvironment; '
            'env=PlacementEnvironment(42); env.step(env.legal_actions()[0]); '
            'assert "tkinter" not in sys.modules; assert "tetris_trainer.ui" not in sys.modules'
        )
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
