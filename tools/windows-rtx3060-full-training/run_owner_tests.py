"""Focused 180-second groups. Existing environment only; CPU and tokenizer, no Qwen load."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid
from full_common import HERE, ROOT, atomic
from supervisor import bounded


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--groups', nargs='+', default=['test_controls', 'test_resume', 'test_results', 'tokenizer'])
    a = p.parse_args()
    output = ROOT / '.tmp/qwen3-4b-full-training-owner-tests' / uuid.uuid4().hex
    output.mkdir(parents=True)
    rows = []
    for name in a.groups:
        if name not in ('test_controls', 'test_resume', 'test_results', 'tokenizer'):
            p.error('Unknown test group')
        print('OWNER TEST: {}; fixed watchdog=180s; output={}'.format(name, output), flush=True)
        if name == 'tokenizer':
            command = [sys.executable, '-B', '-u', str(HERE / 'owner_tokenizer_check.py')]
        else:
            command = [sys.executable, '-B', '-u', '-m', 'unittest', name, '-v']
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
                   CUDA_VISIBLE_DEVICES='-1')  # explicit owner-test isolation; never used by workflow.py
        started = time.monotonic()
        code, monitor = bounded(command, 180, output, name, env=env)
        text = (output / (name + '.log')).read_text(encoding='utf-8')
        counts = re.findall(r'Ran (\d+) tests?', text)
        record = {'group': name, 'returncode': code, 'tests': int(counts[-1]) if counts else None,
                  'seconds': time.monotonic() - started, 'watchdog_seconds': 180, 'passed': code == 0}
        if name == 'tokenizer' and code == 0:
            record['real_tokenizer'] = json.loads(text.strip().splitlines()[-1])
        rows.append(record)
        print(json.dumps(record), flush=True)
        if code:
            print(text[-9000:], flush=True)
    report = {'passed': all(r['passed'] for r in rows), 'groups': rows,
              'real_Qwen_model_loads': 0, 'real_Qwen_training_updates': 0, 'quality_evaluation_calls': 0,
              'production_CUDA_path': 'NOT_EXECUTED; shared engine/checkpoint workflow exercised with CPU fixtures',
              'real_Windows_PowerShell_51_and_process_controls': True}
    atomic(output / 'results.json', report, immutable=True)
    print('TEST RECEIPT: ' + str(output / 'results.json'), flush=True)
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    # Resolve unittest modules without PYTHONPATH or global environment changes.
    os.chdir(HERE)
    raise SystemExit(main())
