import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from full_common import HERE, LEGACY, ROOT, AccessGuard, Layout, OperationLock, config, read
from full_data import shuffled_order, validate_order, project_contexts
from supervisor import OwnedProcess, RollingLog, bounded
from workflow import dispatch, launch


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=ROOT / '.tmp', prefix='full-controls-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_exact_8000_reproducible_coverage_and_pins(self):
        order = shuffled_order(8000, 20260917)
        validate_order(order)
        self.assertEqual(order, shuffled_order(8000, 20260917))
        self.assertNotEqual(order, list(range(8000)))
        self.assertEqual(len([order[i:i+4] for i in range(0, len(order), 4)]), 2000)
        with self.assertRaises(ValueError):
            validate_order(order[:-1] + [order[0]])
        c, old = config(), read(LEGACY / 'config.json')
        for key in ('quantization', 'lora', 'activation_offload', 'host_memory'):
            self.assertEqual(c[key], old[key])
        self.assertEqual(c['hardware_admission'], old['remote_resources'])
        self.assertEqual((c['optimizer']['lr'], c['seed'], c['data_seed']), (0.0002, 20260917, 20260917))
        self.assertEqual(c['checkpoint']['every_successful_update'], 1)

    def test_guard_refuses_holdouts_smoke_writes_and_model_weights_during_preparation(self):
        layout = Layout('qwen3-4b-v1-guard')
        guard = AccessGuard(layout, tokenizer_only=True)
        for p in ('ml/data/synthetic_ru/dev.jsonl', 'ml/data/synthetic_ru/internal_test.jsonl',
                  'evals/local-qwen/dev-ru-v1.json', 'evals/local-qwen/a01-a16.json',
                  'AlagModels/Qwen3-4B/model-00001-of-00003.safetensors'):
            with self.assertRaises(PermissionError):
                guard.check(ROOT / p)
        with self.assertRaises(PermissionError):
            guard.check(ROOT / '.tmp/rtx3060-12gb-targeted-1536-smoke/anything', True)
        guard.check(ROOT / 'ml/data/synthetic_ru/train.jsonl')

    def test_context_projection_preserves_accepted_prompt_dictionary_order(self):
        from full_common import DATA
        project_contexts(self.root)
        projected = read(self.root / 'train-contexts.json')
        source = read(DATA / 'contexts.json')
        self.assertEqual(len(projected), 140)
        for key, row in projected.items():
            self.assertEqual(row['split'], 'train')
            self.assertEqual(json.dumps(row, ensure_ascii=False), json.dumps(source[key], ensure_ascii=False))

    def test_status_dry_run_and_prepare_package_dispatch_never_train(self):
        layout = Layout('qwen3-4b-v1-modes', self.root)
        with patch('workflow.Layout', return_value=layout), patch('workflow.launch', side_effect=AssertionError('training started')):
            for action in ('status', 'prepare', 'package', 'start', 'resume'):
                a = argparse.Namespace(action=action, run_id=layout.run_id, dry_run=True)
                self.assertEqual(dispatch(a), 0)
            self.assertFalse(layout.base.exists())
            a = argparse.Namespace(action='status', run_id=layout.run_id, dry_run=False)
            self.assertEqual(dispatch(a), 0)
            self.assertFalse(layout.base.exists())
            commands = []
            with patch('supervisor.bounded', side_effect=lambda cmd, *args, **kwargs: (commands.append(cmd) or 0, {})), \
                 patch('workflow.shutil.disk_usage', return_value=shutil._ntuple_diskusage(100, 0, 20 * 2**30)):
                for action in ('prepare', 'package'):
                    a.action = action
                    self.assertEqual(dispatch(a), 0)
            self.assertTrue(any('_prepare' in c for c in commands))
            self.assertTrue(any(str(HERE / 'results.py') in c for c in commands))
            self.assertFalse(any('train_full.py' in ' '.join(c) for c in commands))

    def test_concurrent_operation_rejected_and_stale_file_does_not_block(self):
        lock = self.root / 'operation.lock'
        with OperationLock(lock):
            code = 'import sys;sys.path.insert(0,sys.argv[1]);from pathlib import Path;from full_common import OperationLock\nwith OperationLock(Path(sys.argv[2])): pass'
            p = subprocess.run([sys.executable, '-B', '-c', code, str(HERE), str(lock)], capture_output=True, timeout=15)
            self.assertNotEqual(p.returncode, 0)
        with OperationLock(lock):
            pass

    def test_native_failure_and_watchdog_only_owned_process(self):
        code, _ = bounded([sys.executable, '-c', 'raise SystemExit(37)'], 5, self.root, 'native')
        self.assertEqual(code, 37)
        sentinel = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(15)'])
        try:
            start = time.monotonic()
            code, report = bounded([sys.executable, '-c', 'import time;time.sleep(30)'], 0.5, self.root, 'timeout')
            self.assertEqual(code, 124)
            self.assertLess(time.monotonic() - start, 8)
            self.assertIsNone(sentinel.poll())
            self.assertEqual(report['stop_reason'], 'WALL_CLOCK_TIMEOUT')
        finally:
            sentinel.terminate()
            sentinel.wait(timeout=5)

    def test_owned_job_also_bounds_descendants(self):
        import psutil
        pidfile = self.root / 'child-pid.txt'
        code = ('import subprocess,sys,time;from pathlib import Path;'
                'p=subprocess.Popen([sys.executable,"-c","import time;time.sleep(30)"]);'
                'Path(sys.argv[1]).write_text(str(p.pid));time.sleep(30)')
        result, _ = bounded([sys.executable, '-c', code, str(pidfile)], 1, self.root, 'tree')
        self.assertEqual(result, 124)
        child = int(pidfile.read_text())
        self.assertFalse(psutil.pid_exists(child))

    def test_windows_powershell51_cyrillic_spaces_native_code_and_launcher_rejection(self):
        destination = self.root / 'папка с пробелами'
        destination.mkdir()
        script = destination / 'RUN-FULL-TRAINING.ps1'
        shutil.copyfile(HERE / script.name, script)
        (destination / 'workflow.py').write_text('import sys\nassert sys.argv[1:]==["status","--run-id","qwen3-4b-v1"]\nraise SystemExit(37)\n', encoding='utf-8')
        base = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)]
        p = subprocess.run(base + ['-Action', 'Status', '-RunId', 'qwen3-4b-v1', '-PythonExe', sys.executable], capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 37, p.stderr)
        p = subprocess.run(base + ['-Action', 'Status', '-RunId', 'qwen3-4b-v1', '-PythonExe', 'py.exe'], capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 1)
        p = subprocess.run(base, capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 0)
        p = subprocess.run(base + ['-Action', 'Start', '-RunId', 'qwen3-4b-v1', '-DryRun'], capture_output=True, timeout=20)
        self.assertEqual(p.returncode, 0)

    def test_log_rotation_bounded(self):
        path = self.root / 'log.txt'
        log = RollingLog(path, limit=100)
        try:
            for i in range(20):
                log.write(b'x' * 60)
        finally:
            log.close()
        self.assertEqual(len(list(self.root.glob('log.txt*'))), 3)
        self.assertLessEqual(sum(p.stat().st_size for p in self.root.glob('log.txt*')), 300)


if __name__ == '__main__':
    unittest.main()
