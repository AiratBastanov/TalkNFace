"""Hash-locked binary installation into the private remote environment only."""
import argparse
import importlib.metadata
import os
import platform
import re
import struct
import subprocess
import sys
import uuid
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
    result = {'passed': platform.python_version() == lock['python'] and struct.calcsize('P') == 8 and not mismatches and not extra and check.returncode == 0,
              'python': platform.python_version(), 'bits': struct.calcsize('P') * 8, 'versions': installed, 'mismatches': mismatches,
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


OWNER = 'tools/windows-rtx3070/01-setup-python-env.ps1'
OWNER_FILE = '.rtx3070-handoff-owner.json'


def prepare_private_venv():
    """Resume only our positively identified pre-install bootstrap; never delete.

    The old implementation wrote ownership only after venv creation, so an old
    unmarked partial directory cannot safely be attributed to this gate.
    """
    target = ROOT / '.venv-qlora-remote'
    if VENV != target or VENV.parent.resolve() != ROOT.resolve() or VENV.is_symlink() or VENV.is_junction():
        raise RuntimeError('Unsafe venv path or reparse point; no directory will be changed.')
    owned_path = SCRATCH / 'environment-created.json'
    ready_path = SCRATCH / 'environment-ready.json'
    owned = read_json(owned_path) if owned_path.exists() else {}
    recognized = owned.get('created_by') == OWNER and owned.get('python') == '3.12.10'
    python = VENV / 'Scripts/python.exe'
    if ready_path.exists():
        ready = read_json(ready_path); lock = read_json(HERE / 'runtime-lock.json')
        if not (VENV.is_dir() and python.is_file() and recognized and ready.get('passed')
                and ready.get('python') == lock['python'] and ready.get('packages') == lock['packages']):
            raise RuntimeError('Completed-environment ownership or identity is inconsistent. Preserve it and send script 05 diagnostics.')
        return True  # setup() verifies all installed versions; never reinstalls.
    if VENV.exists():
        anchor = VENV / OWNER_FILE
        if not (VENV.is_dir() and recognized and owned.get('nonce') and anchor.is_file()
                and read_json(anchor) == {'owner': OWNER, 'nonce': owned['nonce']}
                and owned.get('path') == str(VENV.resolve())
                and owned.get('stage') in ('creating_venv', 'venv_ready')
                and owned.get('package_installation_started') is False):
            raise RuntimeError('Unrecognized or post-install incomplete .venv-qlora-remote. Nothing deleted or reinstalled. '
                               'Keep the directory, run script 05, and ask the project owner to review it; do not delete it blindly.')
        if any(SCRATCH.glob('pip-*-report.json')) or (SCRATCH / 'wheel-provenance.json').exists():
            raise RuntimeError('Package-install evidence exists; automatic pre-install recovery refused. Keep files and send script 05 diagnostics.')
        # Do not follow junctions or overwrite unrelated contents on recovery.
        allowed_top = {'Scripts', 'Lib', 'Include', 'pyvenv.cfg', OWNER_FILE}
        for path in VENV.rglob('*'):
            if path.is_symlink() or path.is_junction() or path.relative_to(VENV).parts[0] not in allowed_top:
                raise RuntimeError('Unexpected contents/reparse point in incomplete environment; preserve it for review.')
        site = VENV / 'Lib/site-packages'
        if site.exists() and any(p.name not in ('pip', 'pip-25.0.1.dist-info') for p in site.iterdir()):
            raise RuntimeError('Non-bootstrap packages found; automatic recovery refused before touching files.')
    else:
        if owned or any(SCRATCH.glob('pip-*-report.json')):
            raise RuntimeError('Stale environment/install markers exist without the venv. Preserve evidence and contact the project owner.')
        VENV.mkdir()  # exclusive creation; never adopt an arbitrary user folder
        owned = {'created_by': OWNER, 'python': '3.12.10', 'path': str(VENV.resolve()),
                 'nonce': uuid.uuid4().hex, 'stage': 'creating_venv', 'package_installation_started': False}
        write_json(VENV / OWNER_FILE, {'owner': OWNER, 'nonce': owned['nonce']})
        write_json(owned_path, owned)
    if owned['stage'] == 'creating_venv':
        # sys.executable is the exact interpreter resolved/validated by script 01.
        # No launcher selector, --clear, directory deletion or package installation.
        subprocess.run([sys.executable, '-m', 'venv', str(VENV)], check=True, timeout=120)
        if not python.is_file() or not (VENV / 'pyvenv.cfg').is_file():
            raise RuntimeError('venv creation did not produce the expected interpreter/config; preserve bootstrap evidence.')
        owned['stage'] = 'venv_ready'
        write_json(owned_path, owned)
    if not python.is_file() or not (VENV / 'pyvenv.cfg').is_file():
        raise RuntimeError('Owned environment is missing its interpreter/config; preserve it for review.')
    return False


def setup():
    assert platform.python_version() == '3.12.10' and struct.calcsize('P') == 8, 'Use Python 3.12.10 x64'
    assert os.name == 'nt', 'Windows only'
    SCRATCH.mkdir(parents=True, exist_ok=True)
    assert not (SCRATCH / 'campaign-started.json').exists(), 'Do not alter environment after a campaign'
    python = VENV / 'Scripts/python.exe'
    # A completed installation is verified, never automatically reinstalled.
    if prepare_private_venv():
        subprocess.run([str(python), '-B', str(HERE / 'environment.py'), 'check'], check=True, timeout=120)
        print('Existing verified private environment reused.')
        return
    lock = read_json(HERE / 'runtime-lock.json')
    owned_path = SCRATCH / 'environment-created.json'
    owned = read_json(owned_path)
    owned.update(stage='package_installation', package_installation_started=True)
    write_json(owned_path, owned)  # a later failure must never trigger bootstrap recovery
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
