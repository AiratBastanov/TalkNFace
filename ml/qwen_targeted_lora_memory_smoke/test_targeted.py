"""Cheap configuration, masking, isolation and threshold checks; no 4B loading."""
import copy
import os
import subprocess
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from common import ROOT, HERE, SCRATCH, MODEL, DATA, TRAIN, ADAPTER, FORBIDDEN, AccessGuard, read_json, write_json, configure_offline, sha256
from configuration import ConfigurationError, validate_config, validate_adapter
from prepare_smoke_data import train_rows, verify_labels, prepare
from offload import inspect_runtime, prepare_with_offload
from monitor import host_sample, pagefiles, ram_stop, summarize, run
from preflight import fair_start
from assess import assess, PREFIX


def passing_fixture():
    step = {'loss': 2.0, 'gradients_finite': True, 'gradient_tensors': 144, 'gradient_norm': 1.0,
            'grad_scaler_skipped': False, 'memory': {'free_bytes': 512 * 2**20}}
    training = {'passed': True, 'adapter_structure': {'target_counts': {'q_proj': 36, 'v_proj': 36},
                'A_tensors': 72, 'B_tensors': 72, 'trainable_parameters': 2949120},
                'only_adapters_trainable': True, 'all_parameters_on_cuda': True, 'quantized_modules': 252,
                'offload_verified': True, 'actual_optimizer_steps': 2, 'steps': [copy.deepcopy(step) for _ in range(2)],
                'microbatches': [copy.deepcopy(step) for _ in range(8)], 'nan_inf': False,
                'after_training': {'peak_allocated_bytes': 5500 * 2**20, 'total_bytes': 6144 * 2**20},
                'before_load': {'host_available_bytes': 20 * 2**30}, 'after_preparation': {'host_available_bytes': 18 * 2**30},
                'adapter_change': {'changed_tensors': 144}, 'adapter': {'files': {'adapter_model.safetensors': {}, 'adapter_config.json': {}}},
                'no_unexplained_oversubscription': True}
    monitor = {'host_min_available_bytes': 16 * 2**30, 'pagefile_peak_delta_bytes': 0, 'returncode': 0,
               'stop_reason': None, 'worker_exited': True, 'gpu_samples': 100}
    reload = {'passed': True, 'adapter_tensors_equal': True, 'logits_finite': True}
    kwargs = {'integrity': True, 'tests': True, 'isolation': True, 'preflight': {'passed': True}}
    return training, monitor, reload, kwargs


class TargetedTests(unittest.TestCase):
    def test_exact_frozen_config_and_only_target_change(self):
        config = validate_config()
        history = read_json(SCRATCH / 'comparison-control.json')['training']['configuration']
        for key in ('training', 'quantization', 'activation_offload'):
            self.assertEqual(config[key], history[key])
        self.assertEqual(config['lora'], dict(history['lora'], target_modules=['q_proj', 'v_proj']))
        self.assertEqual(config['lora']['r'], 8)
        self.assertIsNone(config['retry_sequence_limit'])

    def test_meta_adapter_counts_and_wrong_rank_rejected(self):
        import torch
        from peft import LoraConfig, get_peft_model
        dims = read_json(SCRATCH / 'module-control.json')
        class Projections(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.layers = torch.nn.ModuleList()
                for _ in range(36):
                    layer = torch.nn.Module()
                    for target in ('q_proj', 'v_proj'):
                        layer.add_module(target, torch.nn.Linear(dims[target]['in'], dims[target]['out'], bias=False, device='meta'))
                    self.layers.append(layer)
        # Projection-only meta probe: no Qwen checkpoint, no forward, no optimizer.
        with torch.device('meta'):
            model = get_peft_model(Projections(), LoraConfig(r=8, lora_alpha=16, target_modules=['q_proj', 'v_proj']))
        result = validate_adapter(model)
        self.assertEqual(result['trainable_parameters'], 2949120)
        self.assertEqual((result['A_tensors'], result['B_tensors']), (72, 72))
        self.assertTrue(all(p.device.type == 'meta' for p in model.parameters()))
        write_json(SCRATCH / 'meta-adapter-proof.json', dict(result, base_checkpoint_loaded=False, forward=False))
        with torch.device('meta'):
            wrong = get_peft_model(Projections(), LoraConfig(r=4, target_modules=['q_proj', 'v_proj']))
        with self.assertRaises(ConfigurationError):
            validate_adapter(wrong)

    def test_installed_api_and_exact_offload_call(self):
        info = inspect_runtime()
        self.assertTrue(info['qwen3_supported'])
        self.assertFalse(info['nested_offload_kwarg_used'])
        def checkpoint_func():
            pass
        class Dummy:
            gradient_checkpointing = True
            _gradient_checkpointing_func = SimpleNamespace(func=checkpoint_func)
            def parameters(self): return iter(())
            def modules(self): return iter((self,))
            def gradient_checkpointing_enable(self, **kwargs): self.kwargs = kwargs
        dummy = Dummy()
        with patch('peft.prepare_model_for_kbit_training', return_value=dummy) as prepare_mock:
            self.assertIs(prepare_with_offload(dummy), dummy)
        prepare_mock.assert_called_once_with(dummy, use_gradient_checkpointing=False)
        self.assertEqual(dummy.kwargs, {'offload': True, 'every_n_layers': 1,
                                      'gradient_checkpointing_kwargs': {'use_reentrant': True}})
        write_json(SCRATCH / 'runtime-api.json', info)

    def test_frozen_order_lengths_and_all_completion_masks(self):
        from transformers import AutoTokenizer
        from trl.trainer.sft_trainer import DataCollatorForLanguageModeling
        data = read_json(SCRATCH / 'data-1024.json')
        spec = read_json(SCRATCH / 'spec-control.json')
        rows = data['rows']
        self.assertEqual([r['id'] for r in rows], spec['same_historical_selection']['selected_ids'])
        self.assertEqual([r['length'] for r in rows], spec['same_historical_selection']['lengths'])
        self.assertEqual([r['id'] for r in rows[:8]], spec['optimizer_row_ids'])
        self.assertEqual([r['length'] for r in rows[:8]], spec['optimizer_row_lengths'])
        self.assertEqual(data['reload_row']['id'], spec['reload_row_id'])
        self.assertNotIn(spec['reload_row_id'], [r['id'] for r in rows])
        tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
        collator = DataCollatorForLanguageModeling(pad_token_id=tokenizer.pad_token_id)
        for row in rows + [data['reload_row']]:
            self.assertEqual(row['split'], 'train')
            self.assertEqual(row['length'], len(row['input_ids']))
            self.assertLessEqual(row['length'], 1024)
            self.assertEqual(row['completion'], [{'role': 'assistant', 'content': row['json']}])
            batch = collator([{k: row[k] for k in ('input_ids', 'labels')}])
            verify_labels(row, batch['labels'][0], tokenizer)
        batch = collator([{k: r[k] for k in ('input_ids', 'labels')} for r in rows[:3]])
        for i, row in enumerate(rows[:3]): verify_labels(row, batch['labels'][i], tokenizer)
        bad = list(rows[0]['labels']); bad[0] = 1
        with self.assertRaises(AssertionError): verify_labels(rows[0], bad, tokenizer)
        bad = list(rows[0]['labels']); bad[rows[0]['eos_index']] = -100
        with self.assertRaises(AssertionError): verify_labels(rows[0], bad, tokenizer)
        with self.assertRaises(AssertionError): verify_labels(rows[0], rows[0]['labels'][:-10], tokenizer)
        with self.assertRaises(AssertionError): prepare(768)

    def test_train_only_guard_no_evaluation_opens(self):
        guard = AccessGuard('unit')
        for path in FORBIDDEN:
            with self.assertRaises(PermissionError): next(train_rows(path))
            with self.assertRaises(PermissionError): guard.check(path)
        for path in (DATA / 'contexts.json', ROOT / 'AlagDatasets/private.json',
                     ROOT / 'docs/gates/evidence/LOCAL_QWEN_QLORA_HOST_RAM_OFFLOAD_CORRECTION.json'):
            with self.assertRaises(PermissionError): guard.check(path)
        code = ('from common import *\ng=AccessGuard("negative-open-test").install()\n'
                'for p in FORBIDDEN:\n'
                ' try:p.read_bytes()\n'
                ' except PermissionError:pass\n'
                ' else:raise AssertionError("exposure")\n'
                'assert len(g.denied)==4 and not g.report()["evaluation_file_reads"]\n')
        process = subprocess.run([sys.executable, '-B', '-c', code], cwd=HERE, capture_output=True, text=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)

    def test_no_historical_overwrite_and_ignored_outputs(self):
        guard = AccessGuard('unit')
        for path in (MODEL / 'config.json', ROOT / 'ml/qlora_offload_smoke/config.json',
                     ROOT / 'AlagModels/adapters/qlora-offload-smoke/1024/adapter_model.safetensors',
                     ROOT / 'docs/gates/evidence/LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE.json'):
            with self.assertRaises(PermissionError): guard.check(path, True)
        guard.check(SCRATCH / 'unit.json', True)
        guard.check(ADAPTER / '1024/adapter_config.json', True)
        paths = ['.tmp/qwen-targeted-lora-memory-smoke/data-1024.json',
                 'AlagModels/adapters/qwen-targeted-lora-memory-smoke/1024/adapter_model.safetensors',
                 '.venv-qlora-smoke/pyvenv.cfg']
        p = subprocess.run(['git', 'check-ignore', *paths], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(set(p.stdout.splitlines()), set(paths))
        for name in ('monitor.py', 'offload.py'):
            self.assertEqual(sha256(HERE / name), sha256(ROOT / 'ml/qlora_offload_smoke' / name))

    def test_host_monitor_and_safety_floor(self):
        host = host_sample(); pf = pagefiles()
        self.assertGreater(host['total_bytes'], 30 * 2**30)
        self.assertTrue(pf['available'])
        self.assertFalse(ram_stop(6 * 2**30))
        self.assertTrue(ram_stop(6 * 2**30 - 1))
        samples = [{'time': t, 'host': {'total_bytes': 32, 'available_bytes': 20-t, 'swap_used_bytes': t},
                    'pagefile': {'available': True, 'used_bytes': t}, 'process': {'rss': t+1, 'peak_wset': t+2}}
                   for t in (0, 0.2)]
        summary = summarize(samples, [{'free_MiB': 400, 'used_MiB': 5700}])
        self.assertEqual(summary['requested_interval_seconds'], 0.2)
        self.assertEqual(summary['gpu_min_free_MiB'], 400)
        self.assertEqual(summary['host_min_available_bytes'], 19.8)
        real = host_sample(); high = dict(real, available_bytes=20*2**30); low = dict(real, available_bytes=5*2**30)
        name = f'unit-safety-{os.getpid()}'
        with patch('monitor.host_sample', side_effect=[high] + [low] * 100):
            code = run(name, 10, [sys.executable, '-B', '-c', 'import time;time.sleep(20)'])
        safety = read_json(SCRATCH / f'{name}-monitor.json')
        self.assertNotEqual(code, 0)
        self.assertEqual(safety['stop_reason'], 'HOST_RAM_PRESSURE')
        self.assertEqual(safety['unrelated_processes_terminated'], [])

    def test_fixed_fair_start_tolerance(self):
        historic = {'training': {'before_load': {'free_bytes': 5103*2**20}},
                    'monitor': {'gpu_initial': {'free_MiB': 5396}}}
        snapshot = {'torch': {'free_bytes': (5103-256)*2**20}, 'free_MiB': 5396-256}
        self.assertTrue(fair_start(snapshot, historic)['fair'])
        snapshot['free_MiB'] -= 1
        self.assertFalse(fair_start(snapshot, historic)['fair'])

    def test_verdict_boundary_256_and_margin_512(self):
        t, m, r, k = passing_fixture()
        self.assertEqual(assess(t, m, r, **k)['verdict'], PREFIX + 'MEMORY_SMOKE_PASS')
        for free, margin, passed in ((512, 'COMFORTABLE', True), (511, 'ACCEPTABLE', True),
                                     (256, 'ACCEPTABLE', True), (255, 'INSUFFICIENT', False), (0, 'INSUFFICIENT', False)):
            for boundary in (0, 1):
                test = copy.deepcopy(t); test['steps'][boundary]['memory']['free_bytes'] = free*2**20
                result = assess(test, m, r, **k)
                self.assertEqual(result['margin'], margin)
                self.assertEqual(result['verdict'].endswith('_PASS'), passed)
        test = copy.deepcopy(t); test['steps'][0]['memory']['free_bytes'] = 256*2**20 - 1
        self.assertIn('boundary_headroom', assess(test, m, r, **k)['failed_checks'])

    def test_correctness_and_capacity_cannot_be_overruled_by_completion(self):
        t, m, r, k = passing_fixture()
        changes = [('actual_optimizer_steps', 1), ('offload_verified', False), ('nan_inf', True),
                   ('cuda_oom', True), ('watchdog_expired', True), ('no_unexplained_oversubscription', False)]
        for field, value in changes:
            test = copy.deepcopy(t); test[field] = value
            self.assertTrue(assess(test, m, r, **k)['verdict'].endswith('_FAIL'))
        test = copy.deepcopy(t); test['after_training']['peak_allocated_bytes'] = 6144*2**20
        self.assertIn('allocated_fits', assess(test, m, r, **k)['failed_checks'])
        test = copy.deepcopy(t); test['steps'][0]['grad_scaler_skipped'] = True
        self.assertIn('no_skipped_update', assess(test, m, r, **k)['failed_checks'])
        self.assertIn('pagefile', assess(t, dict(m, pagefile_peak_delta_bytes=256*2**20+1), r, **k)['failed_checks'])
        self.assertNotIn('pagefile', assess(t, dict(m, pagefile_peak_delta_bytes=256*2**20), r, **k)['failed_checks'])
        self.assertIn('host_floor', assess(t, dict(m, host_min_available_bytes=6*2**30-1), r, **k)['failed_checks'])
        self.assertIn('fresh_reload', assess(t, m, {'passed': False}, **k)['failed_checks'])
        for flag in ('integrity', 'tests', 'isolation'):
            self.assertIn(flag, assess(t, m, r, **dict(k, **{flag: False}))['failed_checks'])
        blocked = dict(k, preflight={'blocker': PREFIX + 'GPU_ENVIRONMENT_BLOCKED'})
        self.assertEqual(assess({}, {}, {}, **blocked)['verdict'], PREFIX + 'GPU_ENVIRONMENT_BLOCKED')


if __name__ == '__main__':
    configure_offline()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TargetedTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    write_json(SCRATCH / 'tests.json', {'passed': result.wasSuccessful(), 'run': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'model_checkpoint_loads': 0,
               'training_campaigns': 0, 'evaluation_campaigns': 0})
    raise SystemExit(0 if result.wasSuccessful() else 1)
