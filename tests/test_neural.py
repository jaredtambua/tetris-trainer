"""Independent contract and regression probes for the optional neural layer."""
import subprocess
import sys
import tempfile
from pathlib import Path
import unittest

try:
    import torch
except ImportError:
    torch = None

if torch is not None:
    from tetris_trainer.neural import (
        ModelConfig, NeuralAgent, PlacementPolicy, RolloutStep, adapt_batch,
        load_checkpoint, run_headless, save_checkpoint,
    )
from tetris_trainer.board import Board, WIDTH
from tetris_trainer.engine import ActivePiece, Game
from tetris_trainer.environment import PlacementEnvironment
from tetris_trainer.pieces import Tetromino


@unittest.skipIf(torch is None, 'optional ML dependency unavailable; install .[ml]')
class NeuralTests(unittest.TestCase):
    def setUp(self):
        torch.manual_seed(19)
        self.env = PlacementEnvironment(42)
        self.model = PlacementPolicy(ModelConfig(hidden_size=16))

    def batch(self):
        return adapt_batch([(self.env.observe(), self.env.legal_actions())])

    def test_encoding_exact_normalization_order_and_no_mutation(self):
        before = self.env._game.snapshot()
        actions = self.env.legal_actions()
        first, second = self.batch(), self.batch()
        self.assertEqual(first.states.shape, (1, 212))
        self.assertEqual(first.candidates.shape, (1, len(actions), 4))
        self.assertEqual(first.states.dtype, torch.float32)
        self.assertEqual(first.candidates.dtype, torch.float32)
        self.assertEqual(first.mask.dtype, torch.bool)
        self.assertTrue(first.mask.all())
        self.assertTrue(torch.equal(first.states, second.states))
        self.assertTrue(torch.equal(first.candidates, second.candidates))
        expected = torch.tensor(self.env.observe(), dtype=torch.float32)
        expected[[200, 204, 206, 207, 208, 209, 210]] /= 7
        expected[201:204] /= torch.tensor([3, 10, 20])
        torch.testing.assert_close(first.states[0], expected)
        for index, action in enumerate(actions):
            self.assertIs(first.actions[0][index], action)
            torch.testing.assert_close(first.candidates[0, index],
                torch.tensor(action.values) / torch.tensor([7, 3, 10, 20]))
        self.assertEqual(self.env._game.snapshot(), before)
        self.assertIs(self.env.legal_actions(), actions)

    def test_signed_coordinates_and_bad_observation(self):
        observation = list(self.env.observe())
        observation[202:204] = [-2, -5]
        batch = adapt_batch([(tuple(observation), ())])
        torch.testing.assert_close(batch.states[0, 202:204], torch.tensor([-.2, -.25]))
        for samples in ([], [((0,) * 211, ())]):
            with self.assertRaises(ValueError):
                adapt_batch(samples)

    def test_unequal_batches_padding_mask_and_terminal_value(self):
        actions = self.env.legal_actions()
        batch = adapt_batch([(self.env.observe(), actions[:1]),
                             (self.env.observe(), actions), (self.env.observe(), ())])
        self.assertGreater(len(actions), 20)
        self.assertEqual(batch.mask.sum(dim=1).tolist(), [1, len(actions), 0])
        self.assertTrue(torch.equal(batch.candidates[0, 1:], torch.zeros_like(batch.candidates[0, 1:])))
        output = self.model(batch.states, batch.candidates, batch.mask)
        self.assertEqual(output.logits.shape, batch.mask.shape)
        self.assertEqual(output.values.shape, (3,))
        self.assertTrue(torch.isfinite(output.values).all())
        self.assertTrue(torch.isneginf(output.logits[~batch.mask]).all())
        probabilities = output.logits[:2].softmax(dim=1)
        self.assertEqual(probabilities[0, 0].item(), 1.)
        self.assertEqual(probabilities[0, 1:].sum().item(), 0.)
        for _ in range(10):
            self.assertEqual(torch.multinomial(probabilities[0], 1).item(), 0)
        empty = adapt_batch([(self.env.observe(), ())])
        self.assertEqual(self.model(empty.states, empty.candidates, empty.mask).logits.shape, (1, 0))

    def test_candidate_permutation_and_padding_cannot_change_valid_scores(self):
        batch = self.batch()
        output = self.model(batch.states, batch.candidates, batch.mask)
        permutation = torch.arange(batch.candidates.shape[1] - 1, -1, -1)
        other = self.model(batch.states, batch.candidates[:, permutation], batch.mask[:, permutation])
        torch.testing.assert_close(other.logits, output.logits[:, permutation])
        torch.testing.assert_close(other.values, output.values)
        candidates = torch.cat([batch.candidates, torch.full((1, 7, 4), 1000.)], dim=1)
        mask = torch.cat([batch.mask, torch.zeros((1, 7), dtype=torch.bool)], dim=1)
        padded = self.model(batch.states, candidates, mask)
        torch.testing.assert_close(padded.logits[:, :-7], output.logits)
        torch.testing.assert_close(padded.values, output.values)
        self.assertEqual(padded.logits.softmax(dim=1)[0, -7:].sum().item(), 0.)

    def test_all_piece_representative_catalogs_and_largest_batch(self):
        samples = []
        for kind in Tetromino:
            game = Game(42)
            game.active = ActivePiece(kind)
            env = PlacementEnvironment.from_game(game)
            samples.append((env.observe(), env.legal_actions()))
        counts = [len(actions) for _, actions in samples]
        self.assertGreater(max(counts), min(counts))
        batch = adapt_batch(samples)
        self.assertEqual(batch.candidates.shape, (7, max(counts), 4))
        self.assertEqual(batch.mask.sum(dim=1).tolist(), counts)
        output = self.model(batch.states, batch.candidates, batch.mask)
        for row, count in enumerate(counts):
            self.assertEqual(torch.isfinite(output.logits[row]).sum().item(), count)
            single = adapt_batch([samples[row]])
            expected = self.model(single.states, single.candidates, single.mask)
            torch.testing.assert_close(output.logits[row, :count], expected.logits[0])

    def test_forward_is_trainable_and_rejects_wrong_shapes(self):
        batch = self.batch()
        output = self.model(batch.states, batch.candidates, batch.mask)
        (-output.logits.log_softmax(dim=1)[0, 0] + output.values.square().sum()).backward()
        for module in (self.model.encoder, self.model.scorer, self.model.value_head):
            self.assertTrue(any(p.grad is not None and p.grad.abs().sum() > 0 for p in module.parameters()))
        for parameter in self.model.parameters():
            self.assertIsNotNone(parameter.grad)
            self.assertTrue(torch.isfinite(parameter.grad).all())
        with self.assertRaises(ValueError):
            self.model(batch.states, batch.candidates, batch.mask.float())
        for value in (0, -1, True, 1.5):
            with self.assertRaises(ValueError):
                ModelConfig(value)

    def test_argmax_legal_correspondence_log_probability_and_immutability(self):
        before = self.env._game.snapshot()
        agent = NeuralAgent(self.model)
        decision = agent.decide(self.env)
        self.assertEqual(decision.index, int(decision.logits.argmax()))
        self.assertIs(decision.action, self.env.legal_actions()[decision.index])
        self.assertAlmostEqual(decision.probabilities.sum().item(), 1., places=6)
        self.assertAlmostEqual(decision.log_probability,
                               decision.logits.log_softmax(dim=0)[decision.index].item())
        self.assertFalse(decision.logits.requires_grad)
        self.assertEqual(self.env._game.snapshot(), before)
        self.env.step(decision.action)
        with self.assertRaises(ValueError):
            self.env.step(decision.action)

    def test_seeded_sampling_is_reproducible_and_legal(self):
        agent = NeuralAgent(self.model)
        first, second = torch.Generator().manual_seed(8), torch.Generator().manual_seed(8)
        sequence = [agent.decide(self.env, stochastic=True, generator=first).index for _ in range(20)]
        repeat = [agent.decide(self.env, stochastic=True, generator=second).index for _ in range(20)]
        self.assertEqual(sequence, repeat)
        self.assertTrue(all(0 <= i < len(self.env.legal_actions()) for i in sequence))

    def test_exact_argmax_tie_chooses_first_issued_row(self):
        with torch.no_grad():
            for parameter in self.model.parameters():
                parameter.zero_()
        decision = NeuralAgent(self.model).decide(self.env)
        self.assertEqual(decision.index, 0)
        self.assertIs(decision.action, self.env.legal_actions()[0])
        self.assertTrue(torch.equal(decision.logits, torch.zeros_like(decision.logits)))

    def test_terminal_agent_rejects_without_mutation(self):
        game = Game(42)
        game.board = Board().with_cells({(x, 1): Tetromino.J for x in range(WIDTH)})
        game.active = ActivePiece(Tetromino.O, y=-1)
        env = PlacementEnvironment.from_game(game)
        before = env._game.snapshot()
        with self.assertRaises(ValueError):
            NeuralAgent(self.model).decide(env)
        self.assertEqual(env._game.snapshot(), before)

    def test_checkpoint_reconstruction_equivalence_and_invalid_formats(self):
        batch = self.batch()
        expected = self.model(batch.states, batch.candidates, batch.mask)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'model.pt'
            save_checkpoint(self.model, path)
            restored = load_checkpoint(path)
            self.assertEqual(restored.config, self.model.config)
            actual = restored(batch.states, batch.candidates, batch.mask)
            torch.testing.assert_close(actual.logits, expected.logits, rtol=0, atol=0)
            torch.testing.assert_close(actual.values, expected.values, rtol=0, atol=0)
            payload = torch.load(path, weights_only=True)
            for key in ('format_version', 'tensor_version', 'environment_version'):
                broken = dict(payload, **{key: 999})
                torch.save(broken, path)
                with self.assertRaises(ValueError):
                    load_checkpoint(path)
            for broken in ({}, [], None, dict(payload, config={'hidden_size': 0}),
                           dict(payload, state_dict={})):
                torch.save(broken, path)
                with self.assertRaises(ValueError):
                    load_checkpoint(path)

    def test_rollout_retains_detached_snapshot_external_reward_and_boundary(self):
        decision = NeuralAgent(self.model).decide(self.env)
        transition = self.env.step(decision.action)
        record = RolloutStep.capture(decision, reward=-.25, terminated=transition.terminated,
                                     next_observation=transition.observation, truncated=True)
        expected = record.state.clone()
        candidates = record.candidates.clone()
        decision.batch.states.fill_(999)
        decision.batch.candidates.fill_(999)
        torch.testing.assert_close(record.state, expected)
        torch.testing.assert_close(record.candidates, candidates)
        self.assertEqual(record.state.device.type, 'cpu')
        self.assertFalse(record.state.requires_grad)
        self.assertEqual(record.selected_index, decision.index)
        self.assertEqual(record.reward, -.25)
        self.assertTrue(record.truncated)
        self.assertEqual(record.terminated, transition.terminated)
        torch.testing.assert_close(record.next_state,
                                  adapt_batch([(transition.observation, ())]).states[0])
        with self.assertRaises(ValueError):
            RolloutStep.capture(decision, reward=float('nan'), terminated=False,
                                next_observation=transition.observation)

    def test_bounded_demo_repeatability_and_global_rng_isolation(self):
        before = torch.random.get_rng_state().clone()
        first = run_headless(seed=3, placement_limit=5, stochastic=True)
        self.assertTrue(torch.equal(before, torch.random.get_rng_state()))
        self.assertEqual(first, run_headless(seed=3, placement_limit=5, stochastic=True))
        self.assertLessEqual(first.placements, 5)
        self.assertEqual(len(first.observation), 212)
        zero = run_headless(placement_limit=0)
        self.assertEqual((zero.placements, zero.stop_reason), (0, 'limit'))
        for value in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                run_headless(placement_limit=value)

    def test_headless_and_optional_dependency_boundaries(self):
        code = ('import sys; from tetris_trainer.environment import PlacementEnvironment; '
                'from tetris_trainer.baseline import BaselineAgent; '
                'assert "torch" not in sys.modules; '
                'from tetris_trainer.neural import run_headless; run_headless(placement_limit=1); '
                'assert "tkinter" not in sys.modules; assert "tetris_trainer.ui" not in sys.modules')
        result = subprocess.run([sys.executable, '-c', code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
