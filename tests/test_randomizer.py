import unittest

from tetris_trainer.engine import BagRandomizer
from tetris_trainer.pieces import ALL_TETROMINOES


class BagTests(unittest.TestCase):
    def sequence(self, seed, count=21):
        bag = BagRandomizer(seed)
        return tuple(bag.pop() for _ in range(count))

    def test_every_complete_bag_has_each_piece_once(self):
        sequence = self.sequence(9)
        expected = set(ALL_TETROMINOES)
        for start in range(0, len(sequence), 7):
            self.assertEqual(set(sequence[start : start + 7]), expected)

    def test_same_seed_same_sequence(self):
        self.assertEqual(self.sequence(42), self.sequence(42))

    def test_different_seeds_can_differ(self):
        self.assertNotEqual(self.sequence(1), self.sequence(2))


if __name__ == "__main__":
    unittest.main()
