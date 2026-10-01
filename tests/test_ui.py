import unittest

from tetris_trainer.engine import Action
from tetris_trainer.ui import KEY_BINDINGS


class UiAdapterSmokeTests(unittest.TestCase):
    def test_required_keys_map_to_semantic_actions(self):
        self.assertEqual(KEY_BINDINGS["Left"], Action.MOVE_LEFT)
        self.assertEqual(KEY_BINDINGS["Right"], Action.MOVE_RIGHT)
        self.assertEqual(KEY_BINDINGS["Down"], Action.SOFT_DROP)
        self.assertEqual(KEY_BINDINGS["space"], Action.HARD_DROP)
        self.assertEqual(KEY_BINDINGS["z"], Action.ROTATE_CCW)
        self.assertEqual(KEY_BINDINGS["x"], Action.ROTATE_CW)
        self.assertEqual(KEY_BINDINGS["Up"], Action.ROTATE_CW)
        self.assertEqual(KEY_BINDINGS["a"], Action.ROTATE_180)
        self.assertEqual(KEY_BINDINGS["c"], Action.HOLD)


if __name__ == "__main__":
    unittest.main()
