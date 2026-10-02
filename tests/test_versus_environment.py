"""Factual v2 observation and authoritative transition-boundary probes."""
import unittest

from tetris_trainer.board import Board, GarbageCell
from tetris_trainer.engine import ActivePiece, GarbageEvent, Game, RotationHistory
from tetris_trainer.environment import (
    B2B_INDEX, BOARD_SLICE, COMBO_INDEX, GARBAGE_BOARD_SLICE,
    OBSERVATION_SIZE, PENDING_GARBAGE_SLICE, ROTATION_AMOUNT_INDEX,
    ROTATION_KICK_INDEX, ROTATION_SPIN_INDEX, PlacementEnvironment, encode_observation,
)
from tetris_trainer.pieces import Tetromino
from tetris_trainer.versus import Spin


class VersusEnvironmentTests(unittest.TestCase):
    def test_new_fields_are_exact_and_read_only(self):
        game = Game(42)
        game.board = Board().with_cells({(2, 19): GarbageCell.GARBAGE,
                                        (3, 19): Tetromino.T})
        game.combo = 7
        game.b2b = 3
        game.last_rotation = RotationHistory(1, 4, Spin.FULL)
        game.enqueue_garbage(GarbageEvent((0, 9), False))
        game.enqueue_garbage(GarbageEvent((4,), True))
        before = game.snapshot()
        values = encode_observation(game, terminated=False)
        self.assertEqual(len(values), OBSERVATION_SIZE)
        self.assertEqual(values[BOARD_SLICE][192:194], (1, 1))
        self.assertEqual(values[GARBAGE_BOARD_SLICE][192:194], (1, 0))
        self.assertEqual(values[COMBO_INDEX], 7)
        self.assertEqual(values[B2B_INDEX], 3)
        self.assertEqual(values[ROTATION_AMOUNT_INDEX], 1)
        self.assertEqual(values[ROTATION_KICK_INDEX], 4)
        self.assertEqual(values[ROTATION_SPIN_INDEX], 2)
        pending = values[PENDING_GARBAGE_SLICE]
        self.assertEqual(pending[:6], (1, 0, 10, 0, 5, 1))
        self.assertEqual(pending[6:], (0,) * 506)
        self.assertEqual(game.snapshot(), before)

    def test_bound_is_encoded_without_truncation(self):
        game = Game(42)
        holes = tuple(index % 10 for index in range(256))
        game.enqueue_garbage(GarbageEvent(holes))
        values = encode_observation(game, terminated=False)
        self.assertEqual(values[PENDING_GARBAGE_SLICE],
                         tuple(value for hole in holes for value in (hole + 1, 1)))
        before = game.snapshot()
        with self.assertRaises(ValueError):
            game.enqueue_garbage(GarbageEvent((0,)))
        self.assertEqual(game.snapshot(), before)

    def test_rotation_time_spin_is_observed_independently_of_pose_and_kick(self):
        game = Game(42)
        observations = []
        for spin in (Spin.NONE, Spin.MINI, Spin.FULL):
            game.last_rotation = RotationHistory(1, 0, spin)
            observations.append(encode_observation(game, terminated=False))
        self.assertEqual([obs[ROTATION_SPIN_INDEX] for obs in observations], [0, 1, 2])
        for observation in observations[1:]:
            self.assertEqual(observation[:ROTATION_SPIN_INDEX],
                             observations[0][:ROTATION_SPIN_INDEX])
            self.assertEqual(observation[ROTATION_SPIN_INDEX + 1:],
                             observations[0][ROTATION_SPIN_INDEX + 1:])

    def test_clear_event_matches_engine_and_source_is_isolated(self):
        game = Game(42)
        game.active = ActivePiece(Tetromino.I)
        game.board = Board().with_cells({(x, 19): GarbageCell.GARBAGE
                                        for x in range(10) if x not in (3, 4, 5, 6)})
        game.enqueue_garbage(GarbageEvent((2, 8), False))
        env = PlacementEnvironment.from_game(game)
        action = next(a for a in env.legal_actions() if a.values == (1, 0, 3, 18, 0))
        before = game.snapshot()
        expected = game.clone().apply_placement(action._placement)
        actual = env.step(action)
        self.assertIsNotNone(actual.facts.clear_event)
        self.assertEqual(actual.facts.clear_event, expected.clear_event)
        self.assertEqual(actual.facts.clear_event.garbage_lines_cleared, 1)
        self.assertEqual(game.snapshot(), before)


if __name__ == '__main__':
    unittest.main()
