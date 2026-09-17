"""Local-only static/fixture validation. No CUDA calls, Qwen inference or training."""
import ast
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from common import ROOT, HERE, SCRATCH, MODEL, ADAPTER, FORBIDDEN, AccessGuard, read_json, write_json, sha256
from configuration import validate_config, ConfigurationError
from model_files import verify_model, download
from package_result import package, allowed, sanitize, process_active
from runner import reserve_campaign
from verdict import decide, PREFIX

VALIDATION = ROOT / '.tmp/rtx3070-handoff-preparation'


def fixture():
    step = {'loss': 2.0, 'gradients_finite': True, 'grad_scaler_skipped': False, 'memory': {'free_bytes': 512*2**20}}
    train = {'passed': True, 'actual_optimizer_steps': 2, 'steps': [copy.deepcopy(step) for _ in range(2)],
             'microbatches': [copy.deepcopy(step) for _ in range(8)], 'nan_inf': False,
             'adapter_structure': {'trainable_parameters': 2949120, 'A_tensors': 72, 'B_tensors': 72, 'target_counts': {'q_proj': 36, 'v_proj': 36}},
             'all_parameters_on_cuda': True, 'only_adapters_trainable': True, 'quantized_modules': 252, 'offload_verified': True,
             'after_training': {'peak_allocated_bytes': 6000*2**20, 'peak_reserved_bytes': 9000*2**20, 'total_bytes': 8192*2**20},
             'before_load': {'host_available_bytes': 20*2**30}, 'after_preparation': {'host_available_bytes': 18*2**30},
             'adapter_change': {'changed_tensors': 144}, 'adapter': {'files': {'adapter_model.safetensors': {'sha256': 'fixture-only'}}}}
    monitor = {'host_min_available_bytes': 16*2**30, 'pagefile_peak_delta_bytes': 0, 'returncode': 0,
               'worker_exited': True, 'gpu_samples': 100, 'stop_reason': None}
    reload = {'passed': True, 'logits_finite': True, 'adapter_tensors_equal': True}
    return train, monitor, reload


def psquote(value):
    return "'" + str(value).replace("'", "''") + "'"


def powershell(code, timeout=30):
    return subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
                           '[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);' + code],
                          capture_output=True, encoding='utf-8', errors='replace', timeout=timeout)


class HandoffTests(unittest.TestCase):
    def test_powershell_syntax_and_all_dry_runs_are_read_only(self):
        required = ['00-preflight.ps1', '01-setup-python-env.ps1', '02-download-and-verify-model.ps1',
                    '03-prepare-smoke.ps1', '04-run-targeted-memory-smoke.ps1', '05-package-result.ps1']
        for path in HERE.glob('*.ps1'):
            text = path.read_text(encoding='utf-8')
            self.assertIn('Set-StrictMode -Version Latest', text)
            self.assertIn("$ErrorActionPreference = 'Stop'", text)
            parsed = powershell('$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile(' + psquote(path) + ',[ref]$t,[ref]$e);if($e.Count){$e|Out-String|Write-Output;exit 1}')
            self.assertEqual(parsed.returncode, 0, parsed.stdout + parsed.stderr)
        with tempfile.TemporaryDirectory(dir=VALIDATION, prefix='portable space ') as temp:
            moved = Path(temp) / 'Проект друга'; tools = moved / 'tools/windows-rtx3070'; tools.mkdir(parents=True)
            for path in [*HERE.glob('*.ps1'), HERE / 'runtime-lock.json']:
                shutil.copyfile(path, tools / path.name)
            before = {p.relative_to(moved).as_posix(): sha256(p) for p in moved.rglob('*') if p.is_file()}
            for name in required:
                output = powershell('& ' + psquote(tools / name) + ' -DryRun')
                self.assertEqual(output.returncode, 0, output.stdout + output.stderr)
                self.assertIn('DRY RUN', output.stdout)
                self.assertIn(str(moved), output.stdout)
            after = {p.relative_to(moved).as_posix(): sha256(p) for p in moved.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            self.assertFalse((moved / '.venv-qlora-remote').exists())
            self.assertFalse((moved / '.tmp').exists())

    def test_native_process_quoting_spaces_and_nonzero(self):
        with tempfile.TemporaryDirectory(dir=VALIDATION, prefix='native quote ') as temp:
            root = Path(temp); helper = root / 'arguments with spaces.py'
            helper.write_text('import json,sys\nprint(json.dumps(sys.argv[1:]))\n', encoding='utf-8')
            args = ['a space', 'a"quote', 'trailing slash\\', 'кириллица']
            code = '. ' + psquote(HERE / 'Remote.Common.ps1') + ';$script:ScratchRoot=' + psquote(root / 'logs')
            code += ';Invoke-Bounded -Executable ' + psquote(sys.executable) + ' -Arguments @(' + ','.join(psquote(x) for x in ['-B', str(helper), *args]) + ') -Timeout 10 -Name test-native'
            process = powershell(code)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            log = next((root / 'logs').glob('*.stdout.log'))
            self.assertEqual(json.loads(log.read_text(encoding='utf-8')), args)
            helper.write_text('raise SystemExit(7)\n', encoding='utf-8')
            process = powershell(code.replace('test-native', 'test-nonzero'))
            self.assertNotEqual(process.returncode, 0)

    def test_native_watchdog_stops_only_its_child(self):
        with tempfile.TemporaryDirectory(dir=VALIDATION, prefix='watchdog ') as temp:
            root = Path(temp); helper = root / 'owned_child.py'
            helper.write_text('import os,time\nprint(os.getpid(),flush=True)\ntime.sleep(20)\n', encoding='utf-8')
            code = '. ' + psquote(HERE / 'Remote.Common.ps1') + ';$script:ScratchRoot=' + psquote(root / 'logs')
            code += ';Invoke-Bounded -Executable ' + psquote(sys.executable) + ' -Arguments @(' + ','.join(psquote(x) for x in ['-B', str(helper)]) + ') -Timeout 1 -Name test-watchdog'
            process = powershell(code, timeout=15)
            self.assertNotEqual(process.returncode, 0)
            pid = int(next((root / 'logs').glob('*.stdout.log')).read_text(encoding='utf-8').strip())
            self.assertFalse(process_active(pid))
            self.assertTrue(process_active(os.getpid()))

    def test_python_syntax_and_no_fixed_user_paths(self):
        for path in HERE.glob('*.py'): ast.parse(path.read_text(encoding='utf-8'))
        for path in HERE.iterdir():
            if path.is_file():
                text = path.read_text(encoding='utf-8')
                self.assertNotRegex(text, r'(?i)\b[A-Z]:[\\/]+Users[\\/]+[A-Za-z0-9_-]+')
        train = (HERE / 'train_smoke.py').read_text(encoding='utf-8')
        self.assertIn("choices=[1024]", train)
        self.assertNotIn('choices=[1024, 768]', train)
        self.assertIn("device_map={'': 0}", train)
        self.assertIn("campaign-started.json", train)

    def test_lock_covers_exact_historical_packages_with_binary_hashes(self):
        lock = read_json(HERE / 'runtime-lock.json')
        historical = read_json(ROOT / 'docs/gates/evidence/LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE.json')['environment']
        self.assertEqual(lock['packages'], historical['installed'])
        hashes = {w['name'].lower().replace('_', '-'): w['sha256'] for w in lock['historical_wheels']}
        parsed = {}
        for filename in ('requirements.txt', 'requirements-torch.txt'):
            text = (HERE / filename).read_text()
            self.assertIn('--only-binary=:all:', text)
            for line in text.splitlines():
                if not line or line.startswith(('#', '--')): continue
                package, digest = line.split(' --hash=sha256:')
                name, version = package.split('==')
                parsed[name] = version
                self.assertEqual(digest, hashes[name.lower().replace('_', '-')])
        self.assertEqual(parsed, lock['packages'])
        self.assertEqual(lock['torch_index'], 'https://download.pytorch.org/whl/cu126')
        self.assertEqual(lock['packages']['psutil'], '7.2.2')

    def test_frozen_architecture_selection_and_formula(self):
        decision = read_json(ROOT / 'docs/gates/evidence/LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION.json')
        spec = decision['next_experiment']; config = read_json(HERE / 'config.json')
        for key in ('lora', 'training', 'quantization', 'activation_offload'):
            self.assertEqual(config[key], spec['configuration'][key])
        self.assertEqual(config['lora']['target_modules'], ['q_proj', 'v_proj'])
        self.assertEqual(config['lora']['r'], 8)
        self.assertEqual(len(spec['same_historical_selection']['selected_ids']), 32)
        self.assertEqual(spec['optimizer_row_ids'], spec['same_historical_selection']['selected_ids'][:8])
        self.assertNotIn(spec['reload_row_id'], spec['optimizer_row_ids'])
        self.assertEqual(max(spec['same_historical_selection']['lengths']), 974)
        dims = decision['static_analysis']['module_dimensions']
        count = sum(8*dims[n]['count']*(dims[n]['in']+dims[n]['out']) for n in ('q_proj', 'v_proj'))
        self.assertEqual(count, 2949120)
        self.assertEqual(sum(dims[n]['count'] for n in ('q_proj', 'v_proj')), 72)
        with tempfile.TemporaryDirectory(dir=VALIDATION) as temp:
            scratch = Path(temp)
            write_json(scratch / 'spec-control.json', dict(spec, configuration=config))
            write_json(scratch / 'module-control.json', dims)
            with patch('configuration.SCRATCH', scratch): self.assertEqual(validate_config(), config)

    def test_real_model_hashes_without_model_load(self):
        result = verify_model()
        self.assertTrue(result['passed'])
        self.assertEqual(len(result['files']), 10)
        self.assertEqual(result['revision'], '1cfa9a7208912126459214e8b04321603b3df60c')
        write_json(VALIDATION / 'local-model-verification.json', result)

    def test_model_mismatch_fails_closed_before_download(self):
        with tempfile.TemporaryDirectory(dir=VALIDATION) as temp:
            folder = Path(temp); (folder / 'config.json').write_text('wrong')
            lock = read_json(HERE / 'model-lock.json')
            with self.assertRaises(ValueError): verify_model(folder, lock, complete=False)
            self.assertEqual((folder / 'config.json').read_text(), 'wrong')
        with tempfile.TemporaryDirectory(dir=VALIDATION) as temp:
            scratch = Path(temp); write_json(scratch / 'cuda-backend.json', {'passed': True})
            with patch('model_files.SCRATCH', scratch), patch('environment.capture'), patch('model_files.verify_model', return_value={'passed': True}) as verifier:
                download()
                verifier.assert_called_once_with(complete=False)
                self.assertFalse(read_json(scratch / 'model-verification.json')['downloaded'])

    def test_eval_and_historical_write_guards(self):
        guard = AccessGuard('unit')
        for path in (*FORBIDDEN, ROOT / 'AlagDatasets/raw.json', ROOT / 'ml/data/synthetic_ru/contexts.json'):
            with self.assertRaises(PermissionError): guard.check(path)
        for path in (MODEL / 'config.json', ROOT / 'docs/gates/LOCAL_QWEN_TARGETED_LORA_MEMORY_SMOKE.md', ROOT / 'ml/qlora_smoke/config.json'):
            with self.assertRaises(PermissionError): guard.check(path, True)
        guard.check(SCRATCH / 'safe.json', True); guard.check(ADAPTER / '1024/adapter_config.json', True)
        code = 'from common import *\ng=AccessGuard("fixture").install()\nfor p in FORBIDDEN:\n try:p.read_bytes()\n except PermissionError:pass\n else:raise AssertionError("exposure")\nassert not g.report()["evaluation_file_reads"]\n'
        # Redirect only this cheap negative-open subprocess scratch to a fixture.
        with tempfile.TemporaryDirectory(dir=VALIDATION) as temp:
            code = 'import common\nfrom pathlib import Path\ncommon.SCRATCH=Path(' + repr(temp) + ')\n' + code
            p = subprocess.run([sys.executable, '-B', '-c', code], cwd=HERE, capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode, 0, p.stderr)

    def test_one_campaign_marker_is_atomic_and_persistent(self):
        with tempfile.TemporaryDirectory(dir=VALIDATION) as temp:
            marker = Path(temp) / 'campaign-started.json'
            reserve_campaign(marker)
            with self.assertRaises(FileExistsError): reserve_campaign(marker)
            self.assertTrue(read_json(marker)['worker_may_start'])

    def test_supervisor_lifecycle_with_fixture_workers_only(self):
        import runner
        with tempfile.TemporaryDirectory(dir=VALIDATION, prefix='lifecycle fixture ') as temp:
            scratch = Path(temp); calls = []; train, monitor, reload = fixture()
            write_json(scratch / 'tests.json', {'passed': True, 'audit': {'denied': [], 'evaluation_file_reads': []}})
            write_json(scratch / 'prepared-ready.json', {'git': {'commit': 'fixture'}})
            def fake_worker(name, seconds, argv):
                calls.append((name, seconds, Path(argv[2]).name))
                if name.startswith('resources-'):
                    write_json(scratch / 'preflight.json', {'passed': True})
                elif name.startswith('training-'):
                    write_json(scratch / 'train-1024.json', dict(train, model_load_started=True))
                    write_json(scratch / (name+'-monitor.json'), monitor)
                elif name == 'reload':
                    write_json(scratch / 'reload-1024.json', reload)
                    write_json(scratch / 'reload-monitor.json', dict(monitor, returncode=0))
                else: raise AssertionError(name)
                return 0
            with patch('runner.SCRATCH', scratch), patch('runner.assert_ready'), patch('runner.capture'), patch('runner.verify_model'), \
                 patch('runner.protect_after', return_value={'passed': True}), patch('runner.supervise', side_effect=fake_worker), \
                 patch('runner.reserve_campaign', side_effect=lambda: reserve_campaign(scratch/'campaign-started.json')):
                self.assertTrue(runner.run_campaign())
                with self.assertRaises(AssertionError): runner.run_campaign()
            self.assertEqual([v[2] for v in calls], ['runtime_checks.py', 'train_smoke.py', 'verify_adapter.py'])
            self.assertEqual([v[1] for v in calls], [120, 1800, 600])
            result = read_json(scratch / 'outcome.json')
            self.assertEqual(result['verdict'], PREFIX+'PASS')
            self.assertEqual(result['training_campaigns'], 1)
            self.assertFalse((scratch/'supervisor-active.json').exists())

    def test_supervisor_resource_block_never_claims_a_campaign(self):
        import runner
        with tempfile.TemporaryDirectory(dir=VALIDATION, prefix='blocked fixture ') as temp:
            scratch = Path(temp); calls = []
            def blocked(name, seconds, argv):
                calls.append(Path(argv[2]).name)
                write_json(scratch / 'preflight.json', {'passed': False, 'gpu_environment_blocked': True, 'error': 'fixture occupancy'})
                return 1
            with patch('runner.SCRATCH', scratch), patch('runner.assert_ready'), patch('runner.capture'), patch('runner.supervise', side_effect=blocked):
                self.assertFalse(runner.run_campaign())
            self.assertEqual(calls, ['runtime_checks.py'])
            self.assertFalse((scratch / 'campaign-started.json').exists())
            self.assertEqual(read_json(scratch / 'outcome.json')['verdict'], PREFIX+'GPU_ENVIRONMENT_BLOCKED')

    def test_supervisor_integrity_failure_preserves_completed_fixture_metrics(self):
        import runner
        with tempfile.TemporaryDirectory(dir=VALIDATION, prefix='integrity fixture ') as temp:
            scratch = Path(temp); train, monitor, reload = fixture()
            def fake_worker(name, seconds, argv):
                if name.startswith('resources-'): write_json(scratch/'preflight.json', {'passed': True})
                elif name.startswith('training-'):
                    write_json(scratch/'train-1024.json', train); write_json(scratch/(name+'-monitor.json'), monitor)
                else:
                    write_json(scratch/'reload-1024.json', reload); write_json(scratch/'reload-monitor.json', monitor)
                return 0
            with patch('runner.SCRATCH', scratch), patch('runner.assert_ready'), patch('runner.capture'), patch('runner.verify_model'), \
                 patch('runner.protect_after', side_effect=[{'passed': True}, ValueError('MODEL_INTEGRITY_FAIL: fixture')]), \
                 patch('runner.supervise', side_effect=fake_worker), \
                 patch('runner.reserve_campaign', side_effect=lambda: reserve_campaign(scratch/'campaign-started.json')):
                self.assertFalse(runner.run_campaign())
            outcome = read_json(scratch/'outcome.json')
            self.assertEqual(outcome['verdict'], PREFIX+'MODEL_INTEGRITY_FAIL')
            self.assertEqual(outcome['training']['actual_optimizer_steps'], 2)
            self.assertTrue(outcome['reload']['passed'])
            self.assertTrue((scratch/'campaign-started.json').exists())

    def test_exact_remote_memory_boundaries_and_next_gate(self):
        train, monitor, reload = fixture()
        for free, verdict in ((512, 'PASS'), (511, 'PASS_TIGHT_MEMORY'), (256, 'PASS_TIGHT_MEMORY'), (255, 'MEMORY_FAIL'), (0, 'MEMORY_FAIL')):
            for boundary in (0, 1):
                t = copy.deepcopy(train); t['steps'][boundary]['memory']['free_bytes'] = free*2**20
                result = decide(t, monitor, reload, True, True, True)
                self.assertEqual(result['verdict'], PREFIX + verdict)
                self.assertEqual(result['next'], 'RTX3070_TARGETED_LORA_1536_ENVELOPE_SMOKE' if verdict.startswith('PASS') else 'QWEN3_4B_LARGER_GPU_TRAINING_ARCHITECTURE')
        t = copy.deepcopy(train); t['after_training']['peak_allocated_bytes'] = 8192*2**20
        self.assertEqual(decide(t, monitor, reload, True, True, True)['verdict'], PREFIX + 'MEMORY_FAIL')
        # Reserved > capacity is deliberately not treated as physical allocation.
        self.assertEqual(decide(train, monitor, reload, True, True, True)['verdict'], PREFIX + 'PASS')

    def test_correctness_host_pagefile_and_isolation_failures(self):
        train, monitor, reload = fixture()
        for field, value in [('passed', False), ('actual_optimizer_steps', 1), ('offload_verified', False), ('nan_inf', True)]:
            t = copy.deepcopy(train); t[field] = value
            self.assertEqual(decide(t, monitor, reload, True, True, True)['verdict'], PREFIX + 'FAIL')
        t = copy.deepcopy(train); t['steps'][0]['grad_scaler_skipped'] = True
        self.assertIn('no_skip', decide(t, monitor, reload, True, True, True)['failed_checks'])
        for m in (dict(monitor, host_min_available_bytes=6*2**30-1), dict(monitor, pagefile_peak_delta_bytes=256*2**20+1)):
            self.assertEqual(decide(train, m, reload, True, True, True)['verdict'], PREFIX + 'MEMORY_FAIL')
        self.assertEqual(decide(train, monitor, {'passed': False}, True, True, True)['verdict'], PREFIX + 'FAIL')
        self.assertEqual(decide(train, monitor, reload, False, True, True)['verdict'], PREFIX + 'FAIL')
        self.assertEqual(decide(train, monitor, reload, True, True, False)['verdict'], PREFIX + 'FAIL')

    def test_fixture_zip_allowlist_redaction_and_incomplete_failure(self):
        with tempfile.TemporaryDirectory(dir=VALIDATION, prefix='zip fixture ') as temp:
            root = Path(temp); scratch = root / 'scratch'; scratch.mkdir()
            train, monitor, reload = fixture()
            outcome = dict(decide(train, monitor, reload, True, True, True), fixture_only=True, training=train, monitor=monitor, reload=reload)
            write_json(scratch / 'outcome.json', outcome)
            write_json(scratch / 'package-integrity.json', {'versions': {'torch': '2.14.0+cu126'}, 'python': '3.12.10', 'mismatches': {'fixture': {'expected': '1.2.3', 'installed': '0.0.0'}}})
            write_json(scratch / 'model-verification.json', {'passed': True})
            forbidden = ['data-1024.json', 'train-contexts.json', 'train.jsonl', 'dev.jsonl', 'internal_test.jsonl', 'a01-a16.json',
                         'adapter_model.safetensors', 'model-00001-of-00003.safetensors', '.env', 'token']
            for name in forbidden: (scratch / name).write_text('EXCLUDED_FIXTURE_CONTENT', encoding='utf-8')
            secret = 'hf_' + 'A'*32
            (scratch / 'training-1.log').write_text('fixture ' + secret, encoding='utf-8')
            archive = package(scratch, root / 'output', root)
            with zipfile.ZipFile(archive) as z:
                all_bytes = b'\n'.join(z.read(n) for n in z.namelist())
                self.assertNotIn(secret.encode(), all_bytes)
                self.assertNotIn(b'EXCLUDED_FIXTURE_CONTENT', all_bytes)
                self.assertTrue(all(not any(n.endswith('/'+x) for x in forbidden) for n in z.namelist()))
                self.assertIn('BOUNDARY FREE 2:', z.read('RESULT.txt').decode())
                self.assertTrue(json.loads(z.read('evidence.json'))['fixture_only'])
                write_json(VALIDATION/'package-fixture-verification.json', {'fixture_only': True,
                           'members': z.namelist(), 'sha256': sha256(archive), 'excluded_content_absent': True,
                           'credentials_redacted': True, 'archive_crc_pass': z.testzip() is None})
            with self.assertRaises(FileExistsError): package(scratch, root / 'output', root)
            (scratch / 'outcome.json').unlink()
            write_json(scratch / 'last-phase-error.json', {'phase': '04', 'message': 'ACTION REQUIRED: close GPU-heavy applications and rerun script 04.'})
            archive2 = package(scratch, root / 'failure-output', root)
            with zipfile.ZipFile(archive2) as z:
                self.assertEqual(json.loads(z.read('evidence.json'))['verdict'], PREFIX + 'GPU_ENVIRONMENT_BLOCKED')
        with self.assertRaises(ValueError): sanitize({'input_ids': [1, 2]})
        self.assertFalse(allowed('data-1024.json'))
        self.assertFalse(allowed('../outcome.json'))

    def test_outputs_ignored_and_no_weight_files_tracked(self):
        paths = ['.venv-qlora-remote/pyvenv.cfg', '.tmp/rtx3070-targeted-smoke/data-1024.json',
                 'AlagModels/adapters/rtx3070-targeted-smoke/1024/adapter_model.safetensors',
                 'handoff-results/RTX3070_TARGETED_LORA_SMOKE_RESULT.zip']
        p = subprocess.run(['git', 'check-ignore', *paths], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(set(p.stdout.splitlines()), set(paths))
        tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
        self.assertFalse(any(p.startswith(('AlagModels/', 'AlagDatasets/', '.venv', '.tmp/', 'handoff-results/')) for p in tracked))


if __name__ == '__main__':
    VALIDATION.mkdir(parents=True, exist_ok=True)
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HandoffTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    write_json(VALIDATION / 'tests.json', {'passed': result.wasSuccessful(), 'tests': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'Qwen_loads': 0,
               'inference_calls': 0, 'training_campaigns': 0, 'package_installs': 0,
               'fixture_archives_only': True, 'remote_execution': False})
    raise SystemExit(0 if result.wasSuccessful() else 1)
