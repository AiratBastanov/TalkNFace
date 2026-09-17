"""Run one gate-owned process tree with a fixed watchdog and retained logs."""
import argparse
import os
import subprocess
import time
import psutil
from common import ROOT, SCRATCH, write_json


def run(name, command, timeout):
    SCRATCH.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMP=str(SCRATCH), TEMP=str(SCRATCH),
               HF_HUB_OFFLINE='1', HF_DATASETS_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    start = time.monotonic()
    result = {'command': command, 'watchdog_seconds': timeout, 'killed_gate_owned_pids': []}
    with (SCRATCH / (name + '.log')).open('x', encoding='utf-8') as log:
        proc = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        result['launcher_pid'] = proc.pid
        try:
            result['returncode'] = proc.wait(timeout=timeout)
            result['watchdog_expired'] = False
        except subprocess.TimeoutExpired:
            owner = psutil.Process(proc.pid)
            children = owner.children(recursive=True)
            for child in reversed(children):
                try:
                    child.kill()
                    result['killed_gate_owned_pids'].append(child.pid)
                except psutil.NoSuchProcess:
                    pass
            owner.kill()
            result['killed_gate_owned_pids'].append(owner.pid)
            result['returncode'] = proc.wait(timeout=15)
            result['watchdog_expired'] = True
    result['wall_seconds'] = time.monotonic() - start
    result['unrelated_processes_terminated'] = []
    write_json(SCRATCH / (name + '-process.json'), result)
    print(result, flush=True)
    return 124 if result['watchdog_expired'] else result['returncode']


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('timeout', type=int)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    raise SystemExit(run(args.name, args.command, args.timeout))
