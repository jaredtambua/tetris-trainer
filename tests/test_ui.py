import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from tetris_trainer.engine import Action, Game
from tetris_trainer.ui import KEY_BINDINGS, RESTART_KEY, TetrisWindow


class UiAdapterSmokeTests(unittest.TestCase):
    def test_required_keys_map_to_semantic_actions(self):
        self.assertEqual(KEY_BINDINGS["Left"], Action.MOVE_LEFT)
        self.assertEqual(KEY_BINDINGS["Right"], Action.MOVE_RIGHT)
        self.assertEqual(KEY_BINDINGS["Down"], Action.SOFT_DROP)
        self.assertEqual(KEY_BINDINGS["space"], Action.HARD_DROP)
        self.assertEqual(KEY_BINDINGS["q"], Action.ROTATE_180)
        self.assertEqual(KEY_BINDINGS["w"], Action.ROTATE_CCW)
        self.assertEqual(KEY_BINDINGS["e"], Action.ROTATE_CW)
        self.assertEqual(KEY_BINDINGS["r"], Action.HOLD)
        self.assertTrue({"z", "x", "Up", "a", "c"}.isdisjoint(KEY_BINDINGS))

    def test_hold_key_dispatches_without_restarting(self):
        window = TetrisWindow.__new__(TetrisWindow)
        window.seed = 123
        window.game = Mock()
        window.draw = Mock()
        original_game = window.game
        for key in ("r", "R"):
            self.assertEqual(window._key(SimpleNamespace(keysym=key)), "break")
            self.assertIs(window.game, original_game)
        self.assertEqual(original_game.apply.call_args_list,
                         [unittest.mock.call(Action.HOLD)] * 2)

    def test_restart_key_restarts_with_same_seed(self):
        window = TetrisWindow.__new__(TetrisWindow)
        window.seed = 123
        window.game = Game(window.seed)
        window.game.apply(Action.HARD_DROP)
        window.draw = Mock()
        self.assertEqual(window._key(SimpleNamespace(keysym=RESTART_KEY)), "break")
        self.assertEqual(window.game.snapshot(), Game(window.seed).snapshot())



if __name__ == "__main__":
    unittest.main()
