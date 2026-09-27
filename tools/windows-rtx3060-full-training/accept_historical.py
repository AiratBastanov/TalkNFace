"""Reproduce acceptance ONLY in the recorded packaging checkout, never at future HEAD."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from full_common import HERE, NO_WINDOW, pin, read, require


def accept(archive, checkout):
    baseline = read(HERE / 'accepted-baseline.json')
    require(pin(archive) == baseline['archive'], 'Not the exact final friend ZIP')
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=checkout, text=True, timeout=30, creationflags=NO_WINDOW).strip()
    require(git('rev-parse', 'HEAD') == baseline['packaging_commit'],
            'Use a separate checkout at recorded packaging commit; do not reset the working checkout')
    require(not git('status', '--porcelain'), 'Historical verification checkout must be clean')
    require(git('remote', 'get-url', 'origin') == baseline['origin'], 'Wrong origin')
    old = checkout / 'tools/windows-rtx3060-12gb-1536'
    for name, expected in baseline['strict_verifier']['files'].items():
        require(pin(old / name) == expected, 'Historical verifier version mismatch')
    proc = subprocess.run([sys.executable, '-B', str(old / 'verify_result.py'), str(archive.resolve())],
                          cwd=checkout, capture_output=True, encoding='utf-8', timeout=180, creationflags=NO_WINDOW)
    require(proc.returncode == 0, 'Historical strict verifier failed: ' + proc.stdout)
    result = json.loads(proc.stdout)
    require(result == baseline['strict_verifier']['result'], 'Historical acceptance changed')
    return {'archive': pin(archive), 'packaging_commit': baseline['packaging_commit'], 'result': result}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('archive', type=Path)
    p.add_argument('--checkout', required=True, type=Path)
    a = p.parse_args()
    print(json.dumps(accept(a.archive, a.checkout), indent=2))
