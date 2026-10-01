from collections import deque
from dataclasses import FrozenInstanceError, replace
import unittest

from tetris_trainer import Action, Game, Placement
from tetris_trainer.board import Board, WIDTH
from tetris_trainer.engine import ActivePiece
from tetris_trainer.pieces import Orientation, Tetromino


MANIPULATIONS = (
    Action.MOVE_LEFT, Action.MOVE_RIGHT, Action.SOFT_DROP,
    Action.ROTATE_CW, Action.ROTATE_CCW, Action.ROTATE_180,
)


def action_paths(game):
    """Independent traversal through the human-facing action API."""
    probe = Game(0)
    probe.board = game.board
    paths = {game.active: ()}
    pending = deque([game.active])
    while pending:
        state = pending.popleft()
        for action in MANIPULATIONS:
            probe.active = state
            if probe.apply(action).accepted and probe.active not in paths:
                paths[probe.active] = paths[state] + (action,)
                pending.append(probe.active)
    return paths


class PlacementTests(unittest.TestCase):
    def game(self, kind=Tetromino.T, cells=None, active=None):
        game = Game(42)
        game.active = active or ActivePiece(kind)
        game.board = Board().with_cells(cells or {})
        return game

    def assert_complete_and_reachable(self, game):
        before = game.snapshot()
        placements = game.legal_placements()
        self.assertEqual(game.snapshot(), before)
        paths = action_paths(game)
        expected = set()
        for state in paths:
            if all(y >= 0 for _, y in state.cells) and not game._legal(state.moved(dy=1)):
                expected.add(frozenset(state.cells))
        self.assertEqual({frozenset(p.cells) for p in placements}, expected)
        self.assertEqual(len(placements), len(expected))
        for placement in placements:
            state = ActivePiece(placement.kind, placement.orientation, placement.x, placement.y)
            self.assertIn(state, paths)
            self.assertTrue(game._legal(state))
            self.assertFalse(game._legal(state.moved(dy=1)))
        return placements, paths

    def test_empty_board_all_pieces_counts_and_reachability(self):
        counts = {Tetromino.O: 9, Tetromino.I: 17, Tetromino.S: 17, Tetromino.Z: 17}
        for kind in Tetromino:
            with self.subTest(kind=kind):
                game = self.game(kind)
                placements, _ = self.assert_complete_and_reachable(game)
                self.assertEqual(len(placements), counts.get(kind, 34))
                self.assertEqual(placements, game.legal_placements())
                self.assertEqual(placements, self.game(kind).legal_placements())

    def test_immutable(self):
        placement = self.game().legal_placements()[0]
        with self.assertRaises(FrozenInstanceError):
            placement.x = 4

    def test_sealed_cavity_excluded(self):
        game = self.game(Tetromino.O, {(x, 16): Tetromino.J for x in range(WIDTH)})
        hidden = ActivePiece(Tetromino.O, x=3, y=18)
        self.assertTrue(game._legal(hidden))
        placements, _ = self.assert_complete_and_reachable(game)
        self.assertNotIn(frozenset(hidden.cells), {frozenset(p.cells) for p in placements})
        forged = replace(placements[0], x=hidden.x, y=hidden.y, orientation=hidden.orientation)
        before = game.snapshot()
        self.assertFalse(game.apply_placement(forged).accepted)
        self.assertEqual(game.snapshot(), before)

    def test_lateral_entry_beneath_overhang(self):
        game = self.game(Tetromino.O, {(x, 16): Tetromino.J for x in range(4)})
        target = ActivePiece(Tetromino.O, x=0, y=18)
        placements, paths = self.assert_complete_and_reachable(game)
        self.assertIn(frozenset(target.cells), {frozenset(p.cells) for p in placements})
        probe = self.game(Tetromino.O, {(x, 16): Tetromino.J for x in range(4)},
                          ActivePiece(Tetromino.O, x=0))
        self.assertNotEqual(probe.ghost().cells, target.cells)
        self.assertIn(Action.MOVE_LEFT, paths[target])

    def test_floor_wall_and_180_kick_targets(self):
        for state, action in (
            (ActivePiece(Tetromino.T, x=3, y=18), Action.ROTATE_CW),
            (ActivePiece(Tetromino.T, x=3, y=18), Action.ROTATE_180),
            (ActivePiece(Tetromino.T, Orientation.RIGHT, x=-1, y=17), Action.ROTATE_CCW),
        ):
            with self.subTest(action=action):
                game = self.game(active=state)
                probe = self.game(active=state)
                self.assertTrue(probe.apply(action).accepted)
                self.assertNotEqual((probe.active.x, probe.active.y), (state.x, state.y))
                target = probe.ghost()
                placements, _ = self.assert_complete_and_reachable(game)
                self.assertIn(frozenset(target.cells), {frozenset(p.cells) for p in placements})

    def test_execution_matches_legal_inputs_for_every_overhang_placement(self):
        cells = {(x, 16): Tetromino.J for x in range(4)}
        game = self.game(cells=cells)
        placements, paths = self.assert_complete_and_reachable(game)
        for placement in placements:
            direct, manual = self.game(cells=cells), self.game(cells=cells)
            state = ActivePiece(placement.kind, placement.orientation, placement.x, placement.y)
            manual.apply_many(paths[state])
            expected = manual.apply(Action.HARD_DROP)
            self.assertEqual(direct.apply_placement(placement), expected)
            self.assertEqual(direct.snapshot(), manual.snapshot())

    def test_invalid_and_stale_rejected_atomically(self):
        game = self.game()
        placement = game.legal_placements()[0]
        for invalid in (None, Placement(Tetromino.T, Orientation.SPAWN, 0, 18),
                        replace(placement, x=100), replace(placement, y=0),
                        replace(placement, kind=Tetromino.I)):
            before = game.snapshot()
            self.assertFalse(game.apply_placement(invalid).accepted)
            self.assertEqual(game.snapshot(), before)
        game.apply(Action.MOVE_LEFT)
        before = game.snapshot()
        self.assertFalse(game.apply_placement(placement).accepted)
        self.assertEqual(game.snapshot(), before)

    def test_line_clear_and_hold_reset(self):
        cells = {(x, 19): Tetromino.J for x in range(WIDTH) if x not in (3, 4, 5, 6)}
        game = self.game(Tetromino.I, cells)
        game.hold_used = True
        target = frozenset((x, 19) for x in (3, 4, 5, 6))
        placement = next(p for p in game.legal_placements() if frozenset(p.cells) == target)
        result = game.apply_placement(placement)
        self.assertTrue(result.locked)
        self.assertEqual(result.lines_cleared, 1)
        self.assertEqual(game.total_lines, 1)
        self.assertFalse(game.hold_used)
        self.assertEqual(game.board, Board())

    def test_seeded_gameplay(self):
        first, second = Game(99), Game(99)
        for _ in range(15):
            left, right = first.legal_placements(), second.legal_placements()
            self.assertEqual(left, right)
            if not left:
                break
            self.assertEqual(first.apply_placement(left[0]), second.apply_placement(right[0]))
            self.assertEqual(first.snapshot(), second.snapshot())

    def test_dead_absent_colliding_and_topout_states(self):
        game = self.game(Tetromino.O, {(x, 2): Tetromino.J for x in range(WIDTH)})
        # Grounded above-visible cells cannot be locked by the existing engine.
        game.active = ActivePiece(Tetromino.O, y=-1)
        self.assertTrue(all(all(y >= 0 for _, y in p.cells) for p in game.legal_placements()))
        game.game_over = True
        self.assertEqual(game.legal_placements(), ())
        game.game_over = False
        game.active = None
        self.assertEqual(game.legal_placements(), ())
        game.active = ActivePiece(Tetromino.O, x=-10)
        self.assertEqual(game.legal_placements(), ())

    def test_above_board_start_terminates_without_ceiling(self):
        placements, _ = self.assert_complete_and_reachable(
            self.game(Tetromino.I, active=ActivePiece(Tetromino.I, y=-20)))
        self.assertEqual(len(placements), 17)


if __name__ == '__main__':
    unittest.main()
