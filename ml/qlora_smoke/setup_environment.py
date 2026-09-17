"""Create a private venv; binary-only stable resolution, fixed core stack, 300s watchdog."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import venv
from common import ROOT, SCRATCH, write_json

PINS = ['torch==2.14.0+cu126', 'transformers==5.17.0', 'accelerate==1.15.0',
        'safetensors==0.8.0', 'tokenizers==0.23.2', 'bitsandbytes==0.50.2',
        'peft==0.21.0', 'trl==1.13.0', 'datasets==5.0.1', 'psutil==7.2.2']


def main():
    assert sys.version_info[:3] == (3, 12, 10)
    target = ROOT / '.venv-qlora-smoke'
    if target.exists():
        raise FileExistsError('Refusing to replace an existing environment')
    SCRATCH.mkdir(parents=True, exist_ok=True)
    metadata = {}
    for package in ('bitsandbytes', 'peft', 'trl', 'datasets'):
        version = next(pin.split('==')[1] for pin in PINS if pin.startswith(package + '=='))
        with urllib.request.urlopen(f'https://pypi.org/pypi/{package}/{version}/json', timeout=20) as response:
            # Read available chunks: some network intermediaries keep the
            # connection open after delivering a complete JSON document.
            payload = b''
            while True:
                chunk = response.read1(65536)
                if not chunk:
                    d = json.loads(payload)
                    break
                payload += chunk
                try:
                    d = json.loads(payload)
                    break
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
        metadata[package] = {'version': d['info']['version'], 'requires_python': d['info']['requires_python'],
                             'requires_dist': d['info']['requires_dist'], 'files': d['urls']}
        assert f'{package}=={d["info"]["version"]}' in PINS
        print(f'Verified official metadata: {package} {version}', flush=True)
    write_json(SCRATCH / 'package-metadata.json', metadata)
    venv.EnvBuilder(with_pip=True).create(target)
    python = target / 'Scripts/python.exe'
    command = [str(python), '-m', 'pip', 'install', '--only-binary=:all:', '--disable-pip-version-check',
               '--no-input', '--no-cache-dir', '--timeout', '30', '--retries', '1',
               '--index-url', 'https://pypi.org/simple', '--extra-index-url', 'https://download.pytorch.org/whl/cu126',
               '--report', str(SCRATCH / 'pip-report.json'), *PINS]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMP=str(SCRATCH), TEMP=str(SCRATCH))
    start = time.monotonic()
    with (SCRATCH / 'install.log').open('w', encoding='utf-8') as log:
        process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            code = process.wait(timeout=300)
        except subprocess.TimeoutExpired:
            import psutil
            owner = psutil.Process(process.pid)
            children = owner.children(recursive=True)
            for child in reversed(children):
                child.kill()
            owner.kill()
            process.wait(timeout=15)
            write_json(SCRATCH / 'install-result.json', {'timeout': True, 'seconds': time.monotonic()-start,
                       'killed_gate_owned_pids': [c.pid for c in children] + [process.pid]})
            raise
    write_json(SCRATCH / 'install-result.json', {'returncode': code, 'seconds': time.monotonic()-start, 'command': command})
    if code:
        raise RuntimeError('Binary dependency resolution/install failed; inspect install.log; do not replace core stack')
    subprocess.run([str(python), '-m', 'pip', 'check'], cwd=ROOT, check=True, env=env)
    print('Isolated binary-only environment installed', flush=True)


if __name__ == '__main__':
    main()
