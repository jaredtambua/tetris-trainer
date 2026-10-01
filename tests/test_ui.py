import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tetris_trainer.engine import Action, Game
from tetris_trainer.ui import KEY_BINDINGS, RESTART_KEY, TetrisWindow, main


class UiAdapterSmokeTests(unittest.TestCase):
    def make_window(self, *, ai=False):
        root = Mock()
        root.after.return_value = "timer"
        with patch("tetris_trainer.ui.tk.Canvas"):
            return TetrisWindow(root, 123, ai=ai)

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
        window = self.make_window()
        window.game = Mock()
        window.draw = Mock()
        original_game = window.game
        for key in ("r", "R"):
            self.assertEqual(window._key(SimpleNamespace(keysym=key)), "break")
            self.assertIs(window.game, original_game)
        self.assertEqual(original_game.apply.call_args_list,
                         [unittest.mock.call(Action.HOLD)] * 2)

    def test_restart_key_restarts_with_same_seed(self):
        window = self.make_window()
        window.game.apply(Action.HARD_DROP)
        window.draw = Mock()
        self.assertEqual(window._key(SimpleNamespace(keysym=RESTART_KEY)), "break")
        self.assertEqual(window.game.snapshot(), Game(window.seed).snapshot())

    def test_ai_uses_shared_agent_and_authoritative_placement(self):
        from tetris_trainer.baseline import BaselineAgent
        window = self.make_window(ai=True)
        self.assertIsInstance(window.agent, BaselineAgent)
        placement = window.game.legal_placements()[0]
        expected = window.game.simulate_placement(placement)
        window.agent = Mock()
        window.agent.decide.return_value = SimpleNamespace(placement=placement)
        window.draw = Mock()
        window._ai_step()
        window.agent.decide.assert_called_once_with(window.game)
        self.assertEqual(window.game.snapshot(), expected.snapshot())
        self.assertEqual(window.root.after.call_count, 2)

    def test_ai_pause_resume_restart_and_close_manage_timers(self):
        window = self.make_window(ai=True)
        window._key(SimpleNamespace(keysym="p"))
        self.assertTrue(window.paused)
        window.root.after_cancel.assert_called_once_with("timer")
        window._key(SimpleNamespace(keysym="P"))
        self.assertFalse(window.paused)
        window.game.apply(Action.HARD_DROP)
        window._key(SimpleNamespace(keysym=RESTART_KEY))
        self.assertEqual(window.game.snapshot(), Game(123).snapshot())
        self.assertIsNone(window.decision)
        window._key(SimpleNamespace(keysym="Escape"))
        window.root.destroy.assert_called_once()
        self.assertTrue(window.closed)
        self.assertIsNone(window._timer)

    def test_ai_ignores_human_moves_and_stops_on_no_choice(self):
        window = self.make_window(ai=True)
        original = window.game.snapshot()
        for key in KEY_BINDINGS:
            window._key(SimpleNamespace(keysym=key))
        self.assertEqual(window.game.snapshot(), original)
        window.agent = Mock()
        window.agent.decide.return_value = None
        window._ai_step()
        self.assertTrue(window.stopped)
        self.assertIsNone(window._timer)
        self.assertEqual(window.root.after.call_count, 1)

    def test_ai_step_after_pause_or_game_over_cannot_decide(self):
        window = self.make_window(ai=True)
        window.agent = Mock()
        window.paused = True
        window._ai_step()
        window.paused = False
        window.game.game_over = True
        window._ai_step()
        window.agent.decide.assert_not_called()

    def test_nonpositive_ai_interval_rejected(self):
        for interval in (0, -1):
            with self.assertRaises(ValueError):
                TetrisWindow(Mock(), ai_interval_ms=interval)

    def test_cli_ai_flag_passes_seed_and_interval_to_window(self):
        with (patch("sys.argv", ["tetris_trainer", "--ai", "--seed", "12",
                                "--ai-interval-ms", "900"]),
              patch("tetris_trainer.ui.tk.Tk") as root,
              patch("tetris_trainer.ui.TetrisWindow") as window):
            main()
        window.assert_called_once_with(root.return_value, 12, ai=True, ai_interval_ms=900)
        root.return_value.mainloop.assert_called_once()

    def test_cli_rejects_nonpositive_interval_before_creating_tk(self):
        with (patch("sys.argv", ["tetris_trainer", "--ai-interval-ms", "0"]),
              patch("tetris_trainer.ui.tk.Tk") as root,
              patch("sys.stderr")):
            with self.assertRaises(SystemExit) as exit_error:
                main()
        self.assertEqual(exit_error.exception.code, 2)
        root.assert_not_called()



if __name__ == "__main__":
    unittest.main()
