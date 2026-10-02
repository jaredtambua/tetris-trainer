"""Independent deterministic checks of the documented local versus profile.

These fixtures verify implementation contracts, not external TETR.IO parity.
"""
from dataclasses import FrozenInstanceError, replace
from collections import deque
import unittest

from tetris_trainer.board import Board, GarbageCell, HEIGHT, WIDTH
from tetris_trainer.engine import Action, ActivePiece, Game
from tetris_trainer.pieces import Orientation, Tetromino
from tetris_trainer.versus import GarbageEvent, RotationHistory, Spin, resolve_attack


def clear_fixture(lines=1, garbage=False, all_clear=False):
    game = Game(42)
    game.active = ActivePiece(Tetromino.I, Orientation.RIGHT, 2, 16)
    fill = GarbageCell.GARBAGE if garbage else Tetromino.J
    cells = {(x, y): fill for y in range(HEIGHT - lines, HEIGHT)
             for x in range(WIDTH) if x != 4}
    if not all_clear:
        cells[(0, 10)] = Tetromino.Z
    game.board = Board().with_cells(cells)
    return game


class AttackProfileTests(unittest.TestCase):
    def test_base_tables(self):
        tables = ((Tetromino.I, Spin.NONE, (0, 0, 1, 2, 4)),
                  (Tetromino.T, Spin.FULL, (0, 2, 4, 6, 10)),
                  (Tetromino.T, Spin.MINI, (0, 0, 1, 2, 4)),
                  (Tetromino.L, Spin.MINI, (0, 0, 1, 2, 4)))
        for piece, spin, table in tables:
            for lines, expected in enumerate(table):
                with self.subTest(piece=piece, spin=spin, lines=lines):
                    result = resolve_attack(piece, lines, spin, False, 0, -1, -1)
                    self.assertEqual(result.base, expected)
                    self.assertEqual(result.generated, expected)

    def test_combo_multiplier_and_zero_base_fallback(self):
        for before, expected in ((-1, 4), (0, 5), (1, 6), (3, 8)):
            self.assertEqual(resolve_attack(Tetromino.I, 4, Spin.NONE,
                                           False, 0, before, -1).generated, expected)
        for before, expected in ((-1, 0), (0, 0), (1, 1), (3, 1), (7, 2)):
            self.assertEqual(resolve_attack(Tetromino.I, 1, Spin.NONE,
                                           False, 0, before, -1).generated, expected)
        # Positive-base Double remains on the multiplicative branch at combo4.
        self.assertEqual(resolve_attack(Tetromino.I, 2, Spin.NONE,
                                       False, 0, 3, -1).generated, 2)
        self.assertEqual(resolve_attack(Tetromino.L, 2, Spin.MINI,
                                       False, 0, -1, -1).generated, 1)

    def test_b2b_charge_no_clear_and_break_surge(self):
        first = resolve_attack(Tetromino.I, 4, Spin.NONE, False, 0, -1, -1)
        self.assertEqual((first.b2b, first.generated), (0, 4))
        repeated = resolve_attack(Tetromino.I, 4, Spin.NONE, False, 0, -1, 0)
        self.assertEqual((repeated.b2b, repeated.generated), (1, 5))
        no_clear = resolve_attack(Tetromino.T, 0, Spin.FULL, False, 0, 8, 6)
        self.assertEqual((no_clear.combo, no_clear.b2b, no_clear.generated), (-1, 6, 0))
        for before, surge in ((3, 0), (4, 4), (9, 9)):
            result = resolve_attack(Tetromino.I, 1, Spin.NONE, False, 0, -1, before)
            self.assertEqual((result.b2b, result.surge, result.generated), (-1, surge, surge))

    def test_all_clear_and_garbage_bonus(self):
        ac = resolve_attack(Tetromino.I, 1, Spin.NONE, True, 0, -1, -1)
        self.assertEqual((ac.generated, ac.b2b), (5, 0))
        double_ac = resolve_attack(Tetromino.I, 2, Spin.NONE, True, 0, -1, -1)
        self.assertEqual((double_ac.generated, double_ac.b2b), (6, 0))
        charged_ac = resolve_attack(Tetromino.I, 2, Spin.NONE, True, 0, -1, 5)
        self.assertEqual((charged_ac.generated, charged_ac.b2b), (6, 6))
        for lines, spin, expected in ((1, Spin.NONE, 0), (4, Spin.NONE, 5),
                                      (1, Spin.FULL, 3), (1, Spin.MINI, 1)):
            result = resolve_attack(Tetromino.T, lines, spin, False, 2, -1, -1)
            self.assertEqual(result.generated, expected)


class VersusEngineTests(unittest.TestCase):
    def test_classification_combo_and_clear_row_facts(self):
        for lines, classification, attack in ((1, 'single', 0), (2, 'double', 1),
                                              (3, 'triple', 2), (4, 'quad', 4)):
            game = clear_fixture(lines)
            event = game.apply(Action.HARD_DROP).clear_event
            self.assertEqual(event.classification, classification)
            self.assertEqual(event.cleared_rows, tuple(range(20 - lines, 20)))
            self.assertEqual((event.combo_before, event.combo_after), (-1, 0))
            self.assertEqual(event.attack_generated, attack)
            self.assertFalse(event.all_clear)

    def test_garbage_clear_and_all_clear(self):
        game = clear_fixture(4, garbage=True, all_clear=True)
        event = game.apply(Action.HARD_DROP).clear_event
        self.assertEqual(event.garbage_lines_cleared, 4)
        self.assertEqual(event.attack_generated, 11)
        self.assertTrue(event.all_clear)
        self.assertEqual(game.board, Board())

    def test_no_clear_resets_combo_preserves_charge(self):
        game = Game(0)
        game.combo, game.b2b = 3, 5
        event = game.apply(Action.HARD_DROP).clear_event
        self.assertEqual(event.classification, 'none')
        self.assertEqual((game.combo, game.b2b), (-1, 5))
        self.assertEqual((event.attack_generated, event.surge_attack), (0, 0))

    def test_spin_geometry_history_front_and_fifth_kick(self):
        game = Game(0)
        piece = ActivePiece(Tetromino.T, x=3, y=17)
        corners = ((3, 17), (5, 17), (5, 19), (3, 19))
        for occupied, spin in (((0, 1, 3), Spin.FULL), ((0, 2, 3), Spin.MINI),
                               ((0, 3), Spin.NONE)):
            game.board = Board().with_cells({corners[i]: Tetromino.J for i in occupied})
            self.assertEqual(game._spin(piece, None), Spin.NONE)
            self.assertEqual(game._classify_spin(piece, 0), spin)
        game.board = Board().with_cells({corners[i]: Tetromino.J for i in (0, 2, 3)})
        self.assertEqual(game._classify_spin(piece, 4), Spin.FULL)
        self.assertEqual(game._spin(piece, RotationHistory(-1, 4, Spin.FULL)), Spin.FULL)
        self.assertEqual(game._spin(piece, RotationHistory(2, 4, Spin.FULL)), Spin.FULL)

    def test_full_and_mini_single_clear_lock_facts(self):
        for corners, history, spin, attack in (
                (((3, 17), (5, 17), (3, 19)), RotationHistory(1, 0, Spin.FULL), Spin.FULL, 2),
                (((3, 17), (3, 19), (5, 19)), RotationHistory(1, 0, Spin.MINI), Spin.MINI, 0),
                (((3, 17), (5, 17), (3, 19)), None, Spin.NONE, 0)):
            game = Game(42)
            game.active = ActivePiece(Tetromino.T, x=3, y=17)
            cells = {cell: Tetromino.J for cell in corners}
            cells.update({(x, 18): Tetromino.J for x in range(WIDTH)
                          if x not in (3, 4, 5)})
            game.board = Board().with_cells(cells)
            game.last_rotation = history
            self.assertEqual(game.ghost(), game.active)
            event = game.apply(Action.HARD_DROP).clear_event
            self.assertEqual((event.lines_cleared, event.spin, event.attack_generated),
                             (1, spin, attack))
            self.assertEqual(event.b2b_after, -1 if spin is Spin.NONE else 0)

    def test_rotation_history_clears_only_on_accepted_movement(self):
        game = Game(0)
        game.last_rotation = RotationHistory(1, 4)
        self.assertTrue(game.apply(Action.SOFT_DROP).accepted)
        self.assertIsNone(game.last_rotation)
        game.active = ActivePiece(Tetromino.T, x=0, y=18)
        game.last_rotation = RotationHistory(1, 0)
        self.assertFalse(game.apply(Action.SOFT_DROP).accepted)
        self.assertEqual(game.last_rotation, RotationHistory(1, 0))
        self.assertTrue(game.apply(Action.MOVE_RIGHT).accepted)
        self.assertIsNone(game.last_rotation)
        game.apply(Action.ROTATE_CW)
        game.apply(Action.HOLD)
        self.assertIsNone(game.last_rotation)

    def test_every_placement_witness_matches_human_actions(self):
        game = Game(12)
        game.active = ActivePiece(Tetromino.T)
        game.board = Board().with_cells({(3, 17): Tetromino.J, (5, 17): Tetromino.J,
                                        (3, 19): Tetromino.J})
        observed = set()
        for choice in game.legal_placements():
            human = game.clone()
            for action in choice._path:
                self.assertTrue(human.apply(action).accepted)
            actual = human.apply(Action.HARD_DROP)
            simulated = game.simulate_placement_result(choice)
            self.assertEqual(choice.spin, actual.clear_event.spin)
            observed.add(actual.clear_event.spin)
            self.assertEqual(actual, simulated.transition)
            self.assertEqual(human.snapshot(), simulated.game.snapshot())
        self.assertEqual(observed, {Spin.NONE, Spin.MINI, Spin.FULL})

    def test_non_t_immobility_mini_requires_rotation(self):
        game = Game(0)
        piece = ActivePiece(Tetromino.L, x=3, y=17)
        blockers = ((5, 16), (4, 17), (6, 17), (3, 19))
        game.board = Board().with_cells({cell: Tetromino.J for cell in blockers})
        self.assertTrue(game._legal(piece))
        self.assertEqual(game._spin(piece, None), Spin.NONE)
        self.assertEqual(game._classify_spin(piece, 0), Spin.MINI)
        game.board = Board().with_cells({cell: Tetromino.J for cell in blockers[:-1]})
        self.assertEqual(game._classify_spin(piece, 0), Spin.NONE)

    def test_positive_hard_drop_distance_preserves_rotation(self):
        game = Game(0)
        game.active = ActivePiece(Tetromino.T, Orientation.RIGHT, x=3, y=16)
        game.board = Board().with_cells({(3, 17): Tetromino.J,
                                        (3, 19): Tetromino.J, (5, 19): Tetromino.J})
        game.last_rotation = RotationHistory(1, 4, Spin.FULL)
        self.assertEqual(game.ghost().y, 17)
        event = game.apply(Action.HARD_DROP).clear_event
        self.assertEqual(event.spin, Spin.FULL)

    def test_real_ordered_fifth_kick_upgrades_mini_geometry(self):
        game = Game(0)
        game.active = ActivePiece(Tetromino.T)
        cells = ((0, 15), (1, 17), (2, 19), (3, 14), (4, 14), (4, 16),
                 (4, 17), (4, 18), (5, 19), (6, 15), (7, 19), (8, 16),
                 (8, 19), (9, 15), (9, 16), (9, 18))
        game.board = Board().with_cells({cell: Tetromino.J for cell in cells})
        choice = next(p for p in game.legal_placements()
                      if p.x == -1 and p.y == 17 and p.orientation == Orientation.RIGHT
                      and p._rotation == RotationHistory(1, 4, Spin.FULL))
        human = game.clone()
        for action in choice._path:
            self.assertTrue(human.apply(action).accepted)
        self.assertEqual(human.last_rotation, RotationHistory(1, 4, Spin.FULL))
        self.assertEqual(human._classify_spin(human.active, 0), Spin.MINI)
        self.assertEqual(human._spin(human.active, human.last_rotation), Spin.FULL)
        expected = game.simulate_placement_result(choice)
        self.assertEqual(human.apply(Action.HARD_DROP), expected.transition)

    def test_rotation_spin_retained_when_drop_changes_corner_geometry(self):
        game = Game(0)
        game.active = ActivePiece(Tetromino.T, x=3, y=16)
        game.board = Board().with_cells({(3, 16): Tetromino.J,
                                        (5, 16): Tetromino.J, (3, 18): Tetromino.J})
        self.assertTrue(game.apply(Action.ROTATE_CW).accepted)
        self.assertEqual(game.last_rotation.spin, Spin.MINI)
        self.assertEqual(game.ghost().y, 17)
        self.assertEqual(game._classify_spin(game.ghost(), 0), Spin.NONE)
        before = game.snapshot()
        choice = next(p for p in game.legal_placements()
                      if p.orientation == Orientation.RIGHT and p.x == 3
                      and p.y == 17 and p.spin is Spin.MINI)
        result = game.simulate_placement_result(choice)
        self.assertEqual(game.snapshot(), before)
        actual = game.apply(Action.HARD_DROP)
        self.assertEqual(actual.clear_event.spin, Spin.MINI)
        self.assertEqual(actual, result.transition)

    def test_real_180_fifth_kick_upgrades_t_mini(self):
        game = Game(0)
        game.active = ActivePiece(Tetromino.T, Orientation.LEFT, x=5, y=17)
        cells = ((0, 15), (0, 17), (1, 16), (1, 17), (2, 15), (2, 17),
                 (2, 18), (3, 14), (3, 15), (3, 18), (4, 17), (5, 15),
                 (5, 16), (5, 17), (7, 17), (7, 18), (9, 14), (9, 16), (9, 18))
        game.board = Board().with_cells({cell: Tetromino.J for cell in cells})
        self.assertTrue(game.apply(Action.ROTATE_180).accepted)
        self.assertEqual(game.active, ActivePiece(Tetromino.T, Orientation.RIGHT, 5, 15))
        self.assertEqual(game._classify_spin(game.active, 0), Spin.MINI)
        self.assertEqual(game.last_rotation, RotationHistory(2, 4, Spin.FULL))
        self.assertEqual(game.apply(Action.HARD_DROP).clear_event.spin, Spin.FULL)

    def test_failed_rotation_preserves_prior_rotation_history(self):
        game = Game(0)
        game.active = ActivePiece(Tetromino.T, x=3, y=10)
        game.board = Board().with_cells({(x, y): Tetromino.J
                                        for y in range(HEIGHT) for x in range(WIDTH)
                                        if (x, y) not in game.active.cells})
        game.last_rotation = RotationHistory(-1, 2)
        before = game.snapshot()
        self.assertFalse(game.apply(Action.ROTATE_CW).accepted)
        self.assertEqual(game.snapshot(), before)

    def test_board_garbage_identity_shift_and_mixed_clear(self):
        initial = Board().with_cells({(0, 19): Tetromino.Z})
        raised, overflow = initial.insert_garbage((2, 7))
        self.assertFalse(overflow)
        self.assertIs(raised.rows[17][0], Tetromino.Z)
        self.assertIsNone(raised.rows[18][2])
        self.assertIsNone(raised.rows[19][7])
        self.assertIs(raised.rows[18][0], GarbageCell.GARBAGE)
        full = raised.with_cells({(2, 18): Tetromino.I, (7, 19): Tetromino.I,
                                 **{(x, 16): Tetromino.J for x in range(WIDTH)}})
        result = full.clear_lines_result()
        self.assertEqual(result.cleared_rows, (16, 18, 19))
        self.assertEqual(result.garbage_lines, 2)
        self.assertIs(result.board.rows[19][0], Tetromino.Z)
        self.assertIs(initial.rows[19][0], Tetromino.Z)

    def test_board_inserting_more_than_visible_height_reports_overflow(self):
        board, overflow = Board().insert_garbage((0,) * 21)
        self.assertTrue(overflow)
        self.assertEqual(len(board.rows), HEIGHT)
        self.assertTrue(all(row[0] is None for row in board.rows))

    def test_forged_rotation_rejected_atomically(self):
        game = Game(0)
        choice = game.legal_placements()[0]
        before = game.snapshot()
        forged = replace(choice, _rotation=RotationHistory(1, 99))
        self.assertFalse(game.apply_placement(forged).accepted)
        self.assertEqual(game.snapshot(), before)

    def test_catalog_complete_against_history_aware_reference_graph(self):
        """Independent graph bookkeeping retains history at every visited pose."""
        fixtures = ({}, {(3, 17): Tetromino.J, (5, 17): Tetromino.J,
                         (3, 19): Tetromino.J},
                    {(x, y): Tetromino.J for x, y in ((0, 19), (1, 18), (2, 19),
                                                    (4, 17), (7, 19), (8, 18))})
        for kind in (Tetromino.T, Tetromino.L, Tetromino.I):
            for cells in fixtures:
                game = Game(42)
                game.active = ActivePiece(kind)
                game.board = Board().with_cells(cells)
                initial = (game.active, None)
                queue, seen, expected = deque([initial]), {initial}, set()
                while queue:
                    piece, history = queue.popleft()
                    lock = piece
                    while game._move_piece(lock, 0, 1) is not None:
                        lock = game._move_piece(lock, 0, 1)
                    if all(y >= 0 for _, y in lock.cells):
                        expected.add((tuple(sorted(lock.cells)), game._spin(lock, history)))
                    edges = [(game._move_piece(piece, dx, dy), None)
                             for dx, dy in ((-1, 0), (1, 0), (0, 1))]
                    for amount in (1, -1, 2):
                        rotated = game._rotation_result(piece, amount)
                        if rotated:
                            pose, witness = rotated
                            # Stored rotation classification survives hard drop;
                            # only that flag changes future outcome at a pose.
                            edges.append((pose, RotationHistory(1, 0, witness.spin)))
                    for edge in edges:
                        if edge[0] is not None and edge not in seen:
                            seen.add(edge)
                            queue.append(edge)
                actual = {(tuple(sorted(p.cells)), game._spin(
                    ActivePiece(p.kind, p.orientation, p.x, p.y), p._rotation))
                          for p in game.legal_placements()}
                for placement in game.legal_placements():
                    self.assertEqual(placement.spin, game._spin(ActivePiece(
                        placement.kind, placement.orientation, placement.x,
                        placement.y), placement._rotation))
                with self.subTest(kind=kind, cells=cells):
                    self.assertEqual(actual, expected)

    def test_cancel_fifo_partial_and_excess(self):
        for holes, expected_cancel, outgoing, remainder in (
                ((1, 2, 3, 4, 5, 6), 4, 0, (5, 6)), ((1, 2), 2, 2, ())):
            game = clear_fixture(4)
            game.enqueue_garbage(GarbageEvent(holes[:1], False))
            game.enqueue_garbage(GarbageEvent(holes[1:], True))
            event = game.apply(Action.HARD_DROP).clear_event
            self.assertEqual((event.cancelled, event.outgoing), (expected_cancel, outgoing))
            self.assertEqual(tuple(h for e in game.pending_garbage for h in e.holes), remainder)
            self.assertEqual(event.garbage_inserted, 0)

    def test_clear_stalls_ready_garbage_and_unready_does_not_block_ready(self):
        game = clear_fixture(1)
        game.enqueue_garbage(GarbageEvent((2,), False))
        game.enqueue_garbage(GarbageEvent((7,), True))
        event = game.apply(Action.HARD_DROP).clear_event
        self.assertEqual(event.garbage_inserted, 0)
        self.assertEqual(len(game.pending_garbage), 2)
        self.assertEqual(game.apply(Action.HARD_DROP).clear_event.garbage_inserted, 1)
        self.assertEqual(game.pending_garbage, (GarbageEvent((2,), False),))
        game.set_garbage_ready(0)
        event = game.apply(Action.HARD_DROP).clear_event
        self.assertEqual(event.garbage_inserted, 1)
        self.assertEqual(game.pending_garbage, ())
        self.assertIsNone(game.board.rows[-2][7])
        self.assertIsNone(game.board.rows[-1][2])

    def test_ready_events_insert_and_preserve_unready_events(self):
        game = Game(0)
        events = (GarbageEvent((1, 2)), GarbageEvent((3,), False), GarbageEvent((4,)))
        for event in events:
            game.enqueue_garbage(event)
        fact = game.apply(Action.HARD_DROP).clear_event
        self.assertEqual(fact.garbage_inserted, 3)
        self.assertEqual(game.pending_garbage, (events[1],))

    def test_insertion_cap_partially_consumes_event_and_preserves_order(self):
        game = Game(0)
        game.enqueue_garbage(GarbageEvent((9,), False))
        game.enqueue_garbage(GarbageEvent(tuple(range(9))))
        game.enqueue_garbage(GarbageEvent((7, 6)))
        event = game.apply(Action.HARD_DROP).clear_event
        self.assertEqual(event.garbage_inserted, 8)
        self.assertEqual(game.pending_garbage, (GarbageEvent((9,), False),
                                              GarbageEvent((8,)), GarbageEvent((7, 6))))
        for row, hole in zip(game.board.rows[-8:], range(8)):
            self.assertIsNone(row[hole])

    def test_garbage_overflow_and_spawn_topout_are_facts(self):
        game = Game(0)
        game.active = ActivePiece(Tetromino.O, x=0, y=18)
        game.board = Board().with_cells({(0, 0): Tetromino.Z})
        game.enqueue_garbage(GarbageEvent((4,)))
        event = game.apply(Action.HARD_DROP).clear_event
        self.assertTrue(event.game_over)
        self.assertTrue(game.game_over)
        self.assertEqual(event.garbage_inserted, 1)
        self.assertEqual(game.legal_placements(), ())

    def test_new_state_stales_choices_and_cache(self):
        mutations = (lambda g: setattr(g, 'combo', 1), lambda g: setattr(g, 'b2b', 4),
                     lambda g: setattr(g, 'last_rotation', RotationHistory(1, 0)),
                     lambda g: g.enqueue_garbage(GarbageEvent((2,))),
                     lambda g: g.set_garbage_ready(0))
        for mutate in mutations:
            game = Game(0)
            game.enqueue_garbage(GarbageEvent((1,), False))
            old = game.legal_placements()
            mutate(game)
            before = game.snapshot()
            self.assertFalse(game.apply_placement(old[0]).accepted)
            self.assertEqual(game.snapshot(), before)
            self.assertIsNot(game.legal_placements(), old)

    def test_clone_simulation_preserves_state_and_isolation(self):
        game = clear_fixture(4, garbage=True)
        game.combo, game.b2b = 2, 5
        game.enqueue_garbage(GarbageEvent((0, 1, 2, 3, 4, 5, 6), False))
        before = game.snapshot()
        clone = game.clone()
        self.assertEqual(clone.snapshot(), before)
        choice = next(p for p in game.legal_placements() if p.x == 2 and p.orientation == Orientation.RIGHT)
        one = game.simulate_placement_result(choice)
        two = game.simulate_placement_result(choice)
        self.assertEqual(one.transition, two.transition)
        self.assertEqual(one.game.snapshot(), two.game.snapshot())
        self.assertEqual(game.snapshot(), before)
        one.game.enqueue_garbage(GarbageEvent((9,)))
        self.assertEqual(game.snapshot(), before)
        self.assertNotEqual(one.game.snapshot(), two.game.snapshot())
        with self.assertRaises(FrozenInstanceError):
            two.transition.clear_event.outgoing = 99

    def test_explicit_events_are_deterministic_and_distinguishable(self):
        games = [Game(18) for _ in range(3)]
        for game, holes in zip(games, ((1, 2), (1, 2), (8, 9))):
            game.enqueue_garbage(GarbageEvent(holes))
            game.apply(Action.HARD_DROP)
        self.assertEqual(games[0].snapshot(), games[1].snapshot())
        self.assertNotEqual(games[0].board, games[2].board)
        self.assertEqual(games[0].randomizer.snapshot(), games[2].randomizer.snapshot())

    def test_event_validation_capacity_and_atomic_rejection(self):
        for holes in ((), (-1,), (10,), (True,), (1.0,), (0,) * 257):
            with self.assertRaises(ValueError):
                GarbageEvent(holes)
        game = Game(0)
        game.enqueue_garbage(GarbageEvent((0,) * 256))
        before = game.snapshot()
        with self.assertRaises(ValueError):
            game.enqueue_garbage(GarbageEvent((1,)))
        with self.assertRaises(ValueError):
            game.set_garbage_ready(True)
        self.assertEqual(game.snapshot(), before)
        mutable = [2, 3]
        event = GarbageEvent(mutable)
        mutable[0] = 9
        self.assertEqual(event.holes, (2, 3))


if __name__ == '__main__':
    unittest.main()
