import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import torch
from checkpoints import Store, verify_checkpoint, state_payload
from engine import Cancelled, run_epoch
from full_common import ROOT, atomic, read
from test_support import TinyEngine, setup, equal_tree


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / '.tmp', prefix='full-fixture-')
        self.addCleanup(self.tmp.cleanup)

    def test_interrupted_partial_group_matches_continuous_including_rng_optimizer_scaler(self):
        a, ra, rows = setup(Path(self.tmp.name) / 'continuous')
        reference = TinyEngine()
        expected = run_epoch(reference, a, ra, rows)
        final_state = state_payload(reference, rows.order)
        b, rb, rb_rows = setup(Path(self.tmp.name) / 'resumed')
        interrupted = TinyEngine()
        def cancel():
            p = b.runtime / 'inflight.json'
            return p.exists() and read(p)['cursor'] == 4 and read(p)['microbatches_finished'] == 2
        with self.assertRaises(Cancelled):
            run_epoch(interrupted, b, rb, rb_rows, stopped=cancel)
        self.assertEqual(read(b.checkpoints / 'LATEST.json')['checkpoint'], 'step-0001')
        resumed = TinyEngine()  # consumes RNG; restore must overwrite all used generators
        actual = run_epoch(resumed, b, rb, rb_rows, resume='step-0001')
        self.assertEqual(expected['loss_sum'], actual['loss_sum'])
        self.assertTrue(equal_tree(reference.model.state_dict(), resumed.model.state_dict()))
        self.assertTrue(equal_tree(final_state, state_payload(resumed, rows.order)))
        replay = read(b.runtime / 'resume-replay.json')
        self.assertEqual(replay['uncommitted_group_discarded']['microbatches_finished'], 2)
        self.assertEqual(replay['replay_positions'], [4, 5, 6, 7])
        self.assertEqual(len(Store(b, rb).committed()), 2)
        self.assertFalse(torch.cuda.is_initialized())

    def test_truncated_corrupt_mismatched_and_unrelated_checkpoints(self):
        layout, run, rows = setup(self.tmp.name, updates=1)
        run_epoch(TinyEngine(), layout, run, rows)
        p = layout.checkpoints / 'step-0001'
        for section in ('model', 'runtime', 'configuration', 'data_and_compiler_pins'):
            changed = copy.deepcopy(run)
            changed['identity'][section] = {}
            with self.assertRaises(ValueError):
                verify_checkpoint(p, changed)
        changed = dict(run, nonce='b' * 32)
        with self.assertRaises(ValueError):
            verify_checkpoint(p, changed)
        state = p / 'state.pt'
        original = state.read_bytes()
        for bad in (original[:100], b'x' + original[1:]):
            state.write_bytes(bad)
            with self.assertRaises(ValueError):
                verify_checkpoint(p, run)
        state.write_bytes(original)
        self.assertEqual(verify_checkpoint(p, run)['cursor'], 4)

    def test_failed_save_is_not_resume_target(self):
        layout, run, rows = setup(self.tmp.name, updates=1)
        engine = TinyEngine()
        with self.assertRaises(Cancelled):
            run_epoch(engine, layout, run, rows, stopped=lambda: True)
        store = Store(layout, run)
        initial = read(layout.checkpoints / 'LATEST.json')
        progress = read(layout.checkpoints / 'step-0000/progress.json')
        def broken(stage):
            (stage / 'state.pt').write_bytes(b'partial')
            raise OSError('simulated disk interruption')
        with self.assertRaises(OSError):
            store.save(progress, broken, lambda p: None)
        self.assertEqual(read(layout.checkpoints / 'LATEST.json'), initial)
        self.assertEqual(store.select('step-0000')[1]['cursor'], 0)
        self.assertTrue(list(layout.checkpoints.glob('.incomplete-*')))
        run_epoch(TinyEngine(), layout, run, rows, resume='step-0000')
        with self.assertRaises(ValueError):
            store.select('step-0000')
        with self.assertRaises(ValueError):
            run_epoch(TinyEngine(), layout, run, rows)

    def test_amp_skip_is_failure_not_completed_update(self):
        layout, run, rows = setup(self.tmp.name, updates=1)
        engine = TinyEngine()
        with patch.object(engine.scaler, 'step', lambda optimizer: None), self.assertRaisesRegex(ValueError, 'AMP_SKIPPED'):
            run_epoch(engine, layout, run, rows)
        self.assertEqual(read(layout.checkpoints / 'LATEST.json')['checkpoint'], 'step-0000')
        self.assertFalse((layout.runtime / 'commits/step-0001.json').exists())

    def test_fresh_adapter_and_checkpoint_are_distinct_from_smoke(self):
        layout, run, rows = setup(self.tmp.name)
        self.assertNotIn('targeted-1536-smoke', str(layout.base))
        self.assertNotIn('targeted-1536-smoke', str(layout.adapter))
        engine = TinyEngine()
        self.assertEqual(torch.count_nonzero(engine.model.lora_B).item(), 0)
        with self.assertRaises(Cancelled):
            run_epoch(engine, layout, run, rows, stopped=lambda: True)
        self.assertEqual(verify_checkpoint(layout.checkpoints / 'step-0000', run)['optimizer_step'], 0)

    def test_explicit_start_resume_and_expired_budget_fail_before_model_worker(self):
        import shutil
        from workflow import launch
        layout, run, rows = setup(self.tmp.name, updates=1)
        with patch('workflow.shutil.disk_usage', return_value=shutil._ntuple_diskusage(100, 0, 20 * 2**30)), \
             patch('supervisor.bounded', side_effect=AssertionError('Must not start worker')):
            with self.assertRaisesRegex(ValueError, 'requires --authorize'):
                launch(layout, 'start')
            with self.assertRaisesRegex(ValueError, 'Existing run'):
                launch(layout, 'start', authorization=layout.run_id)
            with self.assertRaisesRegex(ValueError, 'Explicit checkpoint'):
                launch(layout, 'resume')
            with self.assertRaises(Cancelled):
                run_epoch(TinyEngine(), layout, run, rows, stopped=lambda: True)
            with patch('workflow.time.time', return_value=run['deadline_unix'] + 1):
                with self.assertRaisesRegex(ValueError, 'wall-clock budget exhausted'):
                    launch(layout, 'resume', checkpoint='step-0000')


if __name__ == '__main__':
    unittest.main()
