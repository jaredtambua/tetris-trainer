"""Regression cases captured from origin/main before hot-path changes."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import random
import unittest
from unittest.mock import patch

from benchmarks.simulation import representative_game
from tetris_trainer.baseline import BaselineAgent
from tetris_trainer.board import Board, HEIGHT, WIDTH
from tetris_trainer.engine import Action, ActivePiece, Game, Placement
from tetris_trainer.pieces import Orientation, Tetromino


def pose(piece):
    return [piece.kind.value, int(piece.orientation), piece.x, piece.y]


def state_digest(game):
    """Hash legacy gameplay state against the unchanged pre-versus fixture.

    New versus-state preservation is independently covered in test_versus.
    """
    state = {
        'board': [[cell.value if cell is not None else None for cell in row]
                  for row in game.board.rows],
        'active': pose(game.active) if game.active is not None else None,
        'hold': game.hold_piece.value if game.hold_piece is not None else None,
        'hold_used': game.hold_used, 'game_over': game.game_over,
        'total_lines': game.total_lines, 'randomizer': game.randomizer.snapshot(),
    }
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def scenarios():
    for kind in Tetromino:
        game = Game(42)
        game.active = ActivePiece(kind)
        yield f'empty_{kind.value}', game
    yield 'uneven', representative_game()
    for name, kind, cells, active in (
        ('overhang', Tetromino.O, {(x, 16): Tetromino.J for x in range(4)}, None),
        ('sealed', Tetromino.O, {(x, 16): Tetromino.J for x in range(WIDTH)}, None),
        ('floor_kicks', Tetromino.T, {}, ActivePiece(Tetromino.T, x=3, y=18)),
        ('wall_kicks', Tetromino.T, {}, ActivePiece(Tetromino.T, Orientation.RIGHT, -1, 17)),
        ('clear', Tetromino.I, {(x, 19): Tetromino.J for x in range(WIDTH)
                              if x not in (3, 4, 5, 6)}, None),
    ):
        game = Game(42)
        game.active = active or ActivePiece(kind)
        game.board = Board().with_cells(cells)
        game.hold_piece = Tetromino.Z
        game.hold_used = True
        game.total_lines = 4
        yield name, game


def capture_semantics():
    cases = {}
    for name, game in scenarios():
        # Preserve every legacy geometry/order/simulation assertion. New Spin
        # variants are independently checked by the history-aware reference
        # graph in test_versus; this historical fixture predates their metadata.
        by_geometry = {}
        for placement in game.legal_placements():
            by_geometry.setdefault(tuple(sorted(placement.cells)), placement)
        placements = tuple(by_geometry.values())
        decision = BaselineAgent().decide(game)
        cases[name] = {
            'placements': [pose(p) for p in placements],
            'simulations': [state_digest(game.simulate_placement(p)) for p in placements],
            'decision': [pose(decision.placement), decision.score] if decision else None,
        }
    return cases


class PlacementPerformanceTests(unittest.TestCase):
    def test_matches_preoptimization_order_results_and_baseline_choices(self):
        expected = json.loads((Path(__file__).parent / 'data/placement_regressions.json').read_text())
        self.assertEqual(capture_semantics(), expected)

    def test_warm_enumeration_and_simulation_reuse_reachability(self):
        game = representative_game()
        before = game.snapshot()
        placements = game.legal_placements()
        with patch.object(Game, '_rotation_result', side_effect=AssertionError('redundant BFS')):
            self.assertEqual(game.legal_placements(), placements)
            for choice in placements:
                first = game.simulate_placement(choice)
                second = game.simulate_placement(choice)
                self.assertEqual(first.snapshot(), second.snapshot())
        self.assertEqual(game.snapshot(), before)

    def test_every_future_affecting_field_invalidates_reuse_and_stale_choices(self):
        def change_rng(game):
            game.randomizer._rng.random()

        mutations = (
            lambda g: setattr(g, 'board', g.board.with_cells({(0, 19): Tetromino.Z})),
            lambda g: setattr(g, 'active', g.active.moved(dx=-1)),
            lambda g: setattr(g, 'active', None),
            lambda g: setattr(g, 'active', ActivePiece(Tetromino.T, x=-10)),
            lambda g: setattr(g, 'hold_piece', Tetromino.Z),
            lambda g: setattr(g, 'hold_used', True),
            lambda g: setattr(g, 'total_lines', 7),
            lambda g: setattr(g, 'game_over', True),
            lambda g: g.randomizer.pop(),
            lambda g: g.randomizer.peek(30),
            change_rng,
        )
        for index, mutation in enumerate(mutations):
            with self.subTest(field=index):
                game = representative_game()
                stale = game.legal_placements()[0]
                mutation(game)
                before = game.snapshot()
                self.assertFalse(game.apply_placement(stale).accepted)
                with self.assertRaises(ValueError):
                    game.simulate_placement(stale)
                self.assertEqual(game.snapshot(), before)
                fresh = game.clone()
                fresh._placement_cache = None
                self.assertEqual(game.legal_placements(), fresh.legal_placements())

    def test_forged_geometrically_valid_but_unreachable_choice_rejected_on_warm_cache(self):
        game = Game(42)
        game.active = ActivePiece(Tetromino.O)
        game.board = Board().with_cells({(x, 16): Tetromino.J for x in range(WIDTH)})
        placement = game.legal_placements()[0]
        forged = replace(placement, x=3, y=18)
        self.assertTrue(game._legal(ActivePiece(forged.kind, forged.orientation, forged.x, forged.y)))
        before = game.snapshot()
        self.assertFalse(game.apply_placement(forged).accepted)
        self.assertFalse(game.apply_placement(Placement(forged.kind, forged.orientation, forged.x, forged.y)).accepted)
        self.assertEqual(game.snapshot(), before)

    def test_clone_shared_metadata_is_immutable_and_refresh_is_independent(self):
        root = representative_game()
        root.legal_placements()
        clone = root.clone()
        memo = root._placement_cache
        self.assertIs(clone._placement_cache, memo)
        self.assertIsInstance(memo, tuple)
        self.assertIsInstance(memo[1], tuple)
        clone.apply(Action.MOVE_LEFT)
        clone.legal_placements()
        self.assertIs(root._placement_cache, memo)
        self.assertIsNot(clone._placement_cache, memo)
        self.assertNotEqual(root.snapshot(), clone.snapshot())

    def test_collision_semantics_match_cell_api_on_random_boards_and_boundary_poses(self):
        rng = random.Random(290)
        game = Game(0)
        for _ in range(5):
            game.board = Board().with_cells({(x, y): Tetromino.J
                                            for y in range(HEIGHT) for x in range(WIDTH)
                                            if rng.random() < .15})
            for kind in Tetromino:
                for orientation in Orientation:
                    for x, y in ((-3, -5), (-1, 0), (3, -2), (3, 0), (3, 8), (7, 18), (10, 20)):
                        piece = ActivePiece(kind, orientation, x, y)
                        expected = all(not game.board.occupied(cx, cy) for cx, cy in piece.cells)
                        self.assertEqual(game._legal(piece), expected)


if __name__ == '__main__':
    unittest.main()
