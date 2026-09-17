"""Cheap boundary tests, including the real tokenizer and installed TRL collator."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from common import ROOT, HERE, DATA, MODEL, TRAIN, SCRATCH, ADAPTER, FORBIDDEN, AccessGuard, sha256, read_json
from integrity import compare
from prepare_smoke_data import select, train_rows, tokenize_record, verify_labels
from assess_result import assess


class BoundaryTests(unittest.TestCase):
    def test_successful_steps_cannot_hide_gpu_oversubscription(self):
        preflight = {'passed': True, 'cuda_device_total_bytes': 6144}
        training = {'passed': True, 'actual_optimizer_steps': 2, 'sequence_limit': 1024,
                    'nan_inf': False, 'after_training': {'peak_allocated_bytes': 6234}}
        verdict, failures = assess(preflight, training, {'passed': True}, [])
        self.assertTrue(verdict.endswith('_FAIL'))
        self.assertIn('capacity', failures[0])
        training['after_training']['peak_allocated_bytes'] = 5000
        verdict, failures = assess(preflight, training, {'passed': True}, [])
        self.assertTrue(verdict.endswith('_PASS'))
        self.assertEqual(failures, [])

    def test_train_only(self):
        for path in FORBIDDEN:
            with self.assertRaises(PermissionError):
                next(train_rows(path))
        first = next(train_rows())
        self.assertEqual(first['split'], 'train')

    def test_read_and_write_guard(self):
        guard = AccessGuard('unit')
        for path in (*FORBIDDEN, ROOT / 'AlagDatasets/raw/anything', ROOT / 'docs/gates/evidence/anything.json'):
            with self.assertRaises(PermissionError):
                guard.check(path)
        guard.check(TRAIN)
        for path in (TRAIN, MODEL / 'config.json', ROOT / 'packages/ai/src/prompt.ts'):
            with self.assertRaises(PermissionError):
                guard.check(path, True)
        guard.check(SCRATCH / 'output.json', True)
        guard.check(ADAPTER / 'adapter_model.safetensors', True)

    def test_installed_audit_hook_refuses_actual_open(self):
        code = ('from common import *\n'
                'g=AccessGuard("probe").install()\n'
                'for p in FORBIDDEN:\n'
                ' try: p.read_bytes()\n'
                ' except PermissionError: pass\n'
                ' else: raise AssertionError("leak")\n'
                'assert len(g.denied)==4\n')
        result = subprocess.run([sys.executable, '-B', '-c', code], cwd=HERE, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def fixture_rows(self):
        intents = ('offer', 'counter_offer', 'concession', 'argument', 'close_attempt', 'walk_away')
        return [dict(id=f'fixture-{i}', intent=intents[i % len(intents)],
                     tags=['ambiguity', 'negation', 'prompt_injection'], length=700+i) for i in range(400)]

    def test_deterministic_order_independent_selection(self):
        rows = self.fixture_rows()
        a, reload_a = select(rows, 1024)
        b, reload_b = select(list(reversed(rows)), 1024)
        self.assertEqual(a, b)
        self.assertEqual(reload_a, reload_b)
        self.assertNotIn(reload_a, a)
        self.assertEqual(len(a), 32)
        self.assertGreaterEqual(a[0]['length'], 900)

    def test_limit_exclusion_does_not_truncate(self):
        rows = self.fixture_rows()
        original = copy.deepcopy(rows)
        for limit in (1024, 768):
            chosen, unused = select(rows, limit)
            self.assertTrue(all(r['length'] <= limit for r in chosen + [unused]))
        self.assertEqual(rows, original)
        with self.assertRaises(ValueError):
            select([dict(id='too-long', intent='offer', tags=[], length=1025)], 1024)

    def test_ignored_output_and_environment(self):
        paths = ['.venv-qlora-smoke/Scripts/python.exe', '.tmp/qlora-smoke/data-1024.json',
                 'AlagModels/adapters/qlora-feasibility-smoke/adapter_model.safetensors', 'AlagDatasets/raw/example']
        result = subprocess.run(['git', 'check-ignore', *paths], cwd=ROOT, capture_output=True, text=True, check=True)
        self.assertEqual(set(result.stdout.splitlines()), set(paths))

    def test_hashes_detect_protected_drift(self):
        with tempfile.TemporaryDirectory(dir=SCRATCH) as directory:
            path = Path(directory) / 'protected-fixture'
            path.write_bytes(b'frozen')
            first = sha256(path)
            path.write_bytes(b'changed')
            self.assertNotEqual(first, sha256(path))
        before = {'files': {'frozen': {'sha256': first}}, 'baseline_environment_file_stats': {}}
        self.assertEqual(compare(before, before), [])
        after = copy.deepcopy(before)
        after['files']['frozen']['sha256'] = 'different'
        self.assertEqual(compare(before, after), ['frozen'])

    def test_runtime_configuration_and_official_optimizer(self):
        from transformers import Trainer
        from trl import SFTConfig
        config = read_json(HERE / 'config.json')
        args = SFTConfig(output_dir=str(SCRATCH / 'config-test'), **config['training'])
        self.assertTrue(args.completion_only_loss)
        self.assertFalse(args.bf16)
        self.assertEqual((args.max_steps, args.gradient_accumulation_steps), (2, 4))
        cls, kwargs = Trainer.get_optimizer_cls_and_kwargs(args)
        self.assertIn('bitsandbytes', cls.__module__)
        self.assertTrue(kwargs['is_paged'])
        self.assertEqual(kwargs['optim_bits'], 8)


class TokenizerMaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from transformers import AutoTokenizer
        sys.path.insert(0, str(DATA))
        from compile_sft import compile_row, canonical_completion
        cls.tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
        row = next(train_rows())
        cls.compiled = compile_row(row, read_json(DATA / 'contexts.json'), checked=True)
        cls.canonical = canonical_completion(row['expected'])
        cls.record = tokenize_record(cls.tokenizer, cls.compiled, cls.canonical)

    def test_existing_compiler_canonical_prompt_completion(self):
        self.assertEqual([m['role'] for m in self.compiled['prompt']], ['system', 'user'])
        user = json.loads(self.compiled['prompt'][1]['content'])
        self.assertEqual(set(user), {'context', 'utterance'})
        self.assertEqual(self.compiled['completion'][0]['content'], self.canonical)
        self.assertEqual(self.record['labels'][:self.record['prompt_length']], [-100]*self.record['prompt_length'])

    def test_real_trl_collator_completion_eos_and_padding(self):
        from trl.trainer.sft_trainer import DataCollatorForLanguageModeling
        collator = DataCollatorForLanguageModeling(pad_token_id=self.tokenizer.pad_token_id)
        feature = {k: self.record[k] for k in ('input_ids', 'labels')}
        batch = collator([feature])
        verify_labels(self.record, batch['labels'][0], self.tokenizer)
        # Verify real padding with unequal-length inputs as well.
        longer = {k: v + ([-100] if k == 'labels' else [self.tokenizer.pad_token_id]) for k, v in feature.items()}
        batch = collator([feature, longer])
        verify_labels(self.record, batch['labels'][0], self.tokenizer)

    def test_mask_verifier_rejects_leak_missing_completion_and_eos(self):
        labels = list(self.record['labels'])
        for index in (0, self.record['prompt_length'], self.record['eos_index']):
            bad = labels.copy()
            bad[index] = 0 if index == 0 else -100
            with self.assertRaises(AssertionError):
                verify_labels(self.record, bad, self.tokenizer)

    def test_no_thinking_supervision_or_partial_json(self):
        target = self.tokenizer.decode(self.record['input_ids'][self.record['prompt_length']:self.record['eos_index']])
        self.assertEqual(target, self.canonical)
        self.assertNotIn('<think>', target)
        bad = copy.deepcopy(self.compiled)
        bad['completion'][0]['content'] = '<think>reasoning</think>' + self.canonical
        with self.assertRaises(AssertionError):
            tokenize_record(self.tokenizer, bad, bad['completion'][0]['content'])
        with self.assertRaises(json.JSONDecodeError):
            bad['completion'][0]['content'] = self.canonical[:-1]
            tokenize_record(self.tokenizer, bad, self.canonical[:-1])


if __name__ == '__main__':
    from common import configure_offline
    configure_offline()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    unittest.main(verbosity=2)
