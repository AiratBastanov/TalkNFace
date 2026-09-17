"""Hash-locked binary installation into the private remote environment only."""
import argparse
import importlib.metadata
import os
import platform
import re
import struct
import subprocess
import sys
from urllib.parse import urlparse
from common import ROOT, HERE, SCRATCH, VENV, read_json, write_json


def normalized(name):
    return re.sub(r'[-_.]+', '-', name).lower()


def package_check():
    lock = read_json(HERE / 'runtime-lock.json')
    installed = {normalized(d.metadata['Name']): d.version for d in importlib.metadata.distributions()}
    expected = {normalized(k): v for k, v in lock['packages'].items()}
    mismatches = {k: {'expected': v, 'installed': installed.get(k)} for k, v in expected.items() if installed.get(k) != v}
    extra = sorted(set(installed) - set(expected))
    check = subprocess.run([sys.executable, '-B', '-m', 'pip', '--isolated', 'check'], capture_output=True, text=True, timeout=60)
    result = {'passed': platform.python_version() == lock['python'] and not mismatches and not extra and check.returncode == 0,
              'python': platform.python_version(), 'versions': installed, 'mismatches': mismatches,
              'unexpected_packages': extra, 'pip_check_returncode': check.returncode,
              'pip_check': check.stdout.strip(), 'pip_check_stderr': check.stderr.strip()}
    return result


def capture():
    result = package_check()
    for filename, args in [('pip-version.txt', ['--version']), ('pip-freeze.txt', ['freeze', '--all']), ('pip-check.txt', ['check'])]:
        p = subprocess.run([sys.executable, '-B', '-m', 'pip', '--isolated', *args], capture_output=True, text=True, timeout=60)
        (SCRATCH / filename).write_text(p.stdout + p.stderr, encoding='utf-8')
    write_json(SCRATCH / 'package-integrity.json', result)
    if not result['passed']:
        raise RuntimeError('Pinned environment mismatch or pip check failure. Do not replace versions; run script 05 and contact the project owner.')
    return result


def validate_reports():
    lock = read_json(HERE / 'runtime-lock.json')
    expected = {normalized(w['name']): w for w in lock['historical_wheels']}
    rows = []
    for phase in ('torch', 'packages'):
        report = read_json(SCRATCH / f'pip-{phase}-report.json')
        for item in report['install']:
            name = normalized(item['metadata']['name'])
            info = item['download_info']; url = info['url']; parsed = urlparse(url)
            if parsed.scheme != 'https' or parsed.hostname not in ('download.pytorch.org', 'download-r2.pytorch.org', 'files.pythonhosted.org'):
                raise RuntimeError('Unexpected package source; no non-official mirror is accepted')
            assert parsed.path.endswith('.whl'), 'Source distribution forbidden'
            actual = info['archive_info']['hashes']['sha256']
            assert name in expected and actual == expected[name]['sha256'], f'Wheel digest mismatch: {name}'
            assert item['metadata']['version'] == expected[name]['version']
            rows.append({'name': name, 'version': item['metadata']['version'], 'url': url, 'sha256': actual})
    write_json(SCRATCH / 'wheel-provenance.json', {'passed': True, 'wheels_installed_this_setup': rows,
               'note': 'Already matching ensurepip bootstrap packages may not appear in pip install reports; all package versions are checked separately.'})


def setup():
    assert platform.python_version() == '3.12.10' and struct.calcsize('P') == 8, 'Use Python 3.12.10 x64'
    assert os.name == 'nt', 'Windows only'
    SCRATCH.mkdir(parents=True, exist_ok=True)
    assert not (SCRATCH / 'campaign-started.json').exists(), 'Do not alter environment after a campaign'
    python = VENV / 'Scripts/python.exe'
    owned = SCRATCH / 'environment-created.json'
    if VENV.exists() and not owned.exists():
        raise RuntimeError('An unrecognized .venv-qlora-remote already exists. Keep it unchanged and contact the project owner.')
    if not VENV.exists():
        subprocess.run(['py', '-3.12', '-m', 'venv', str(VENV)], check=True, timeout=120)
        write_json(owned, {'created_by': 'tools/windows-rtx3070/01-setup-python-env.ps1', 'python': '3.12.10'})
    # A completed installation is verified, never automatically reinstalled.
    if (SCRATCH / 'environment-ready.json').exists():
        subprocess.run([str(python), '-B', str(HERE / 'environment.py'), 'check'], check=True, timeout=120)
        print('Existing verified private environment reused.')
        return
    lock = read_json(HERE / 'runtime-lock.json')
    for phase, requirements, index in [('torch', 'requirements-torch.txt', lock['torch_index']),
                                        ('packages', 'requirements.txt', lock['package_index'])]:
        command = [str(python), '-B', '-m', 'pip', '--isolated', '--disable-pip-version-check', 'install',
                   '--no-input', '--no-cache-dir', '--only-binary=:all:', '--require-hashes', '--no-deps',
                   '--timeout', '30', '--retries', '1', '--index-url', index,
                   '--report', str(SCRATCH / f'pip-{phase}-report.json'), '-r', str(HERE / requirements)]
        print(f'Installing exact binary wheel phase: {phase} ({index})', flush=True)
        subprocess.run(command, check=True)  # outer owned-process watchdog bounds setup to 1800 s
    validate_reports()
    subprocess.run([str(python), '-B', str(HERE / 'environment.py'), 'check'], check=True, timeout=120)
    write_json(SCRATCH / 'environment-ready.json', {'passed': True, 'python': lock['python'], 'packages': lock['packages']})


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('phase', choices=['setup', 'check']); a = p.parse_args()
    if a.phase == 'setup':
        setup()
    else:
        assert os.path.normcase(sys.prefix) == os.path.normcase(str(VENV)), 'Use the project remote venv'
        capture()
