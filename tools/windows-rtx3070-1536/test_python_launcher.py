"""Launcher correction regressions: stdlib/PowerShell fixtures only, no ML setup."""
import ast
from contextlib import contextmanager
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import environment
from common import ROOT, HERE, read_json, write_json

VALIDATION = ROOT / '.tmp/rtx3070-python-launcher-correction'


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def powershell(code):
    return subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command',
                           '[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);' + code],
                          capture_output=True, encoding='utf-8', errors='replace', timeout=30)


def common():
    return '. ' + quote(HERE / 'Remote.Common.ps1') + ';'


@contextmanager
def venv_fixture():
    with tempfile.TemporaryDirectory(dir=VALIDATION, prefix='venv fixture ') as temp:
        root = Path(temp).resolve()
        assert root.is_relative_to(VALIDATION.resolve())
        scratch = root / '.tmp/fixture'; scratch.mkdir(parents=True)
        venv = root / '.venv-qlora-remote'
        with patch.multiple(environment, ROOT=root, SCRATCH=scratch, VENV=venv):
            yield root, scratch, venv


def fake_venv(command, **kwargs):
    if command[:3] != [sys.executable, '-m', 'venv']:
        raise AssertionError('Unexpected subprocess, including possible package installation: ' + repr(command))
    venv = Path(command[3]); (venv / 'Scripts').mkdir(exist_ok=True)
    (venv / 'Scripts/python.exe').write_text('FIXTURE ONLY: never executed', encoding='utf-8')
    (venv / 'pyvenv.cfg').write_text('version = 3.12.10\n', encoding='utf-8')
    return subprocess.CompletedProcess(command, 0)


class LauncherTests(unittest.TestCase):
    def test_launcher_and_interpreter_version_and_venv_command_matrix(self):
        launcher = r'C:\Windows\py.exe'
        interpreters = [r'C:\Users\Булат\AppData\Local\Programs\Python\Python312\python.exe',
                        r'C:\Program Files\Python 3.12\python.exe']
        for executable, mode in [(launcher, 'Launcher'), *[(p, 'Interpreter') for p in interpreters]]:
            for arguments in (['--version'], ['-m', 'venv', r'D:\Проект друга\repo space\.venv-qlora-remote']):
                code = common() + '$c=Get-PythonInvocation -Mode ' + mode + ' -Executable ' + quote(executable)
                code += ' -Arguments @(' + ','.join(quote(a) for a in arguments) + ');'
                code += '@{executable=$c.Executable;arguments=$c.Arguments;raw=(ConvertTo-NativeArguments @c)}|ConvertTo-Json -Compress'
                result = powershell(code)
                self.assertEqual(result.returncode, 0, result.stderr)
                actual = json.loads(result.stdout)
                self.assertEqual(actual['executable'], executable)
                self.assertEqual(actual['arguments'], (['-3.12'] if mode == 'Launcher' else []) + arguments)
                if mode == 'Launcher':
                    self.assertTrue(actual['raw'].startswith('-3.12 '))
                    self.assertNotIn('"-3.12"', actual['raw'])
                else:
                    self.assertNotIn('-3.12', actual['arguments'])

    def test_interpreter_rejects_every_launcher_selector(self):
        for selector in ('-3', '-3.12', '-V:PythonCore/3.12'):
            result = powershell(common() + 'ConvertTo-NativeArguments -Executable ' + quote(sys.executable)
                                + ' -Arguments @(' + quote(selector) + ',\'--version\')')
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Never pass a launcher selector', result.stderr)

    def test_exact_version_and_bitness_fail_closed(self):
        for version, bits, valid in [('3.12.10', 64, True), ('3.12.9', 64, False),
                                     ('3.12.11', 64, False), ('3.13.0', 64, False), ('3.12.10', 32, False)]:
            code = common() + 'Assert-FrozenPythonIdentity ([pscustomobject]@{version=' + quote(version)
            code += ';bits=' + str(bits) + ';executable=' + quote(sys.executable) + '})'
            result = powershell(code)
            self.assertEqual(result.returncode == 0, valid, result.stdout + result.stderr)

    def test_resolve_system_launcher_to_cyrillic_interpreter_once(self):
        interpreter = r'C:\Users\Булат\AppData\Local\Programs\Python\Python312\python.exe'
        identity = json.dumps({'executable': interpreter, 'version': '3.12.10', 'bits': 64})
        code = common() + '$script:calls=@();'
        code += 'function Test-Path { param($LiteralPath,$PathType) return $LiteralPath -ceq ' + quote(interpreter) + ' };'
        code += 'function Invoke-PythonProbe { param($Executable,$Arguments) $script:calls+=@{executable=$Executable;arguments=@($Arguments)};'
        code += 'if($Arguments.Count -eq 1 -and $Arguments[0] -eq \'--version\'){return \'Python 3.12.10\'};return ' + quote(identity) + ' };'
        code += '$resolved=Resolve-FrozenPython -LauncherPath ' + quote(r'C:\Windows\py.exe') + ';'
        code += '@{resolved=$resolved;calls=$script:calls}|ConvertTo-Json -Depth 6 -Compress'
        result = powershell(code)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        actual = json.loads(result.stdout.splitlines()[-1])
        self.assertEqual(actual['resolved'], interpreter)
        self.assertEqual(len(actual['calls']), 3)
        self.assertEqual(actual['calls'][0]['arguments'][0], '-3.12')
        self.assertEqual(actual['calls'][1]['arguments'], ['--version'])
        for call in actual['calls'][1:]:
            self.assertEqual(call['executable'], interpreter)
            self.assertNotIn('-3.12', call['arguments'])

    def test_powershell_51_real_interpreter_quoting_without_selector(self):
        with tempfile.TemporaryDirectory(dir=VALIDATION, prefix='quote ') as temp:
            folder = Path(temp) / 'Булат space'; folder.mkdir()
            script = folder / 'проверка args.py'
            script.write_text('import sys,json\nprint(json.dumps(sys.argv[1:]))\n', encoding='utf-8')
            args = ['кириллица space', 'a"quote', 'trailing\\']
            code = common() + 'if($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){throw \'Expected PS 5.1\'};'
            code += '$script:ScratchRoot=' + quote(folder / 'logs') + ';'
            code += 'Invoke-Bounded -Executable ' + quote(sys.executable) + ' -Arguments @('
            code += ','.join(quote(v) for v in ['-B', str(script), *args]) + ') -Timeout 10 -Name quoting'
            result = powershell(code)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            log = next((folder / 'logs').glob('*.stdout.log'))
            self.assertEqual(json.loads(log.read_text(encoding='utf-8')), args)

    def test_real_interpreter_version_probe(self):
        result = powershell(common() + 'Invoke-PythonProbe -Executable ' + quote(sys.executable) + " -Arguments @('--version')")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'Python 3.12.10')

    def test_script_01_passes_only_resolved_interpreter_to_setup(self):
        with tempfile.TemporaryDirectory(dir=VALIDATION, prefix='script 01 ') as temp:
            root = Path(temp); tool = root / 'tools/windows-rtx3070'; tool.mkdir(parents=True)
            (tool / '01-setup-python-env.ps1').write_bytes((HERE / '01-setup-python-env.ps1').read_bytes())
            # Replace external/resource actions only, leaving the actual script
            # control flow intact. No CUDA operation or environment installation.
            helper = (HERE / 'Remote.Common.ps1').read_text(encoding='utf-8')
            helper += '\nfunction Test-Resources { param($DiskGiB) return @{} }\n'
            helper += 'function Resolve-FrozenPython { return ' + quote(sys.executable) + ' }\n'
            helper += 'function Require-RemotePython {}\n$script:calls=@()\n'
            helper += 'function Invoke-Bounded { param($Executable,$Arguments,$Timeout,$Name)\n'
            helper += '$script:calls+=@{executable=$Executable;arguments=@($Arguments);name=$Name};\n'
            helper += '$script:calls|ConvertTo-Json -Depth 5|Set-Content -Encoding UTF8 -LiteralPath ' + quote(root/'calls.json') + '\n}\n'
            (tool / 'Remote.Common.ps1').write_text(helper, encoding='utf-8')
            result = powershell('& ' + quote(tool / '01-setup-python-env.ps1'))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            calls = json.loads((root/'calls.json').read_text(encoding='utf-8-sig'))
            self.assertEqual(calls[0]['executable'], sys.executable)
            self.assertEqual(calls[0]['arguments'], ['-B', str(tool/'environment.py'), 'setup'])
            self.assertEqual(calls[1]['name'], '01-cuda')  # fixture dispatch, never executed
            self.assertTrue(all('-3.12' not in call['arguments'] for call in calls))

    def test_new_venv_command_uses_validated_interpreter_never_launcher(self):
        with venv_fixture() as (_, scratch, venv), patch('environment.subprocess.run', side_effect=fake_venv) as run:
            self.assertFalse(environment.prepare_private_venv())
            run.assert_called_once_with([sys.executable, '-m', 'venv', str(venv)], check=True, timeout=120)
            owned = read_json(scratch / 'environment-created.json')
            self.assertFalse(owned['package_installation_started'])
            self.assertEqual(owned['stage'], 'venv_ready')
            self.assertNotIn('-3.12', run.call_args.args[0])

    def test_owned_preinstall_failure_resumes_without_deletion(self):
        with venv_fixture() as (_, scratch, venv):
            with patch('environment.subprocess.run', side_effect=RuntimeError('fixture pre-install interruption')):
                with self.assertRaises(RuntimeError): environment.prepare_private_venv()
            before = read_json(venv / environment.OWNER_FILE)
            with patch('environment.subprocess.run', side_effect=fake_venv) as run:
                self.assertFalse(environment.prepare_private_venv())
                self.assertEqual(run.call_count, 1)
            self.assertEqual(read_json(venv / environment.OWNER_FILE), before)
            self.assertFalse(read_json(scratch / 'environment-created.json')['package_installation_started'])

    def test_unowned_partial_and_unknown_files_are_preserved(self):
        with venv_fixture() as (_, scratch, venv), patch('environment.subprocess.run') as run:
            venv.mkdir(); marker = venv / 'user-content.txt'; marker.write_text('keep me', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'Nothing deleted'): environment.prepare_private_venv()
            self.assertEqual(marker.read_text(), 'keep me'); run.assert_not_called()
        with venv_fixture() as (_, scratch, venv):
            with patch('environment.subprocess.run', side_effect=RuntimeError('fixture')):
                with self.assertRaises(RuntimeError): environment.prepare_private_venv()
            (venv / 'unrelated.txt').write_text('keep', encoding='utf-8')
            with patch('environment.subprocess.run') as run:
                with self.assertRaisesRegex(RuntimeError, 'Unexpected contents'): environment.prepare_private_venv()
                run.assert_not_called()
            self.assertEqual((venv / 'unrelated.txt').read_text(), 'keep')

    def test_ownership_mismatch_and_package_install_started_refuse_recovery(self):
        for change in ({'nonce': 'wrong'}, {'package_installation_started': True}, {'stage': 'package_installation'}):
            with venv_fixture() as (_, scratch, venv):
                with patch('environment.subprocess.run', side_effect=RuntimeError('fixture')):
                    with self.assertRaises(RuntimeError): environment.prepare_private_venv()
                owned_path = scratch / 'environment-created.json'; owned = read_json(owned_path)
                owned.update(change); write_json(owned_path, owned)
                with patch('environment.subprocess.run') as run:
                    with self.assertRaises(RuntimeError): environment.prepare_private_venv()
                    run.assert_not_called()
                self.assertTrue(venv.is_dir())

    def test_completed_legacy_environment_reuses_check_without_install(self):
        with venv_fixture() as (_, scratch, venv):
            venv.mkdir(); fake_venv([sys.executable, '-m', 'venv', str(venv)])
            write_json(scratch / 'environment-created.json', {'created_by': environment.OWNER, 'python': '3.12.10'})
            lock = read_json(HERE / 'runtime-lock.json')
            write_json(scratch / 'environment-ready.json', {'passed': True, 'python': lock['python'], 'packages': lock['packages']})
            with patch('environment.subprocess.run') as run:
                environment.setup()
                run.assert_called_once_with([str(venv / 'Scripts/python.exe'), '-B', str(HERE / 'environment.py'), 'check'], check=True, timeout=120)

    def test_reused_environment_checks_bitness_as_well_as_exact_versions(self):
        lock = read_json(HERE / 'runtime-lock.json')
        packages = [SimpleNamespace(metadata={'Name': name}, version=version) for name, version in lock['packages'].items()]
        for bits in (64, 32):
            with patch('environment.importlib.metadata.distributions', return_value=packages), \
                 patch('environment.struct.calcsize', return_value=bits//8), \
                 patch('environment.subprocess.run', return_value=subprocess.CompletedProcess([], 0, stdout='fixture', stderr='')):
                checked = environment.package_check()
                self.assertEqual(checked['bits'], bits)
                self.assertEqual(checked['passed'], bits == 64)

    def test_recovery_refuses_wrong_path_and_package_evidence(self):
        with venv_fixture() as (root, scratch, venv), patch('environment.VENV', root/'unrelated'), patch('environment.subprocess.run') as run:
            with self.assertRaisesRegex(RuntimeError, 'Unsafe venv path'): environment.prepare_private_venv()
            run.assert_not_called()
            self.assertFalse((root/'unrelated').exists())
        with venv_fixture() as (_, scratch, venv):
            with patch('environment.subprocess.run', side_effect=RuntimeError('fixture')):
                with self.assertRaises(RuntimeError): environment.prepare_private_venv()
            write_json(scratch/'pip-torch-report.json', {'fixture': True})
            with patch('environment.subprocess.run') as run:
                with self.assertRaisesRegex(RuntimeError, 'Package-install evidence'): environment.prepare_private_venv()
                run.assert_not_called()
            self.assertTrue(venv.is_dir())

    def test_changed_scripts_syntax_and_bootstrap_paths(self):
        for filename in ('Remote.Common.ps1', '01-setup-python-env.ps1', '05-package-result.ps1'):
            code = '$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('
            code += quote(HERE / filename) + ',[ref]$t,[ref]$e);if($e.Count){$e|Out-String|Write-Output;exit 1}'
            result = powershell(code); self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        source = (HERE / '01-setup-python-env.ps1').read_text(encoding='utf-8')
        self.assertIn('$resolvedPython = Resolve-FrozenPython', source)
        self.assertNotIn("@('-3.12'", source)
        ast.parse((HERE / 'environment.py').read_text(encoding='utf-8'))


if __name__ == '__main__':
    VALIDATION.mkdir(parents=True, exist_ok=True)
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(LauncherTests))
    write_json(VALIDATION / 'tests.json', {'passed': result.wasSuccessful(), 'tests': result.testsRun,
               'failures': len(result.failures), 'errors': len(result.errors), 'real_ML_environments_created': 0,
               'packages_installed': 0, 'Qwen_loads': 0, 'training': 0, 'evaluation': 0, 'fixtures_only': True})
    raise SystemExit(0 if result.wasSuccessful() else 1)
