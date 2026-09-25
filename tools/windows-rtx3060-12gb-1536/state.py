"""OS-held operation lock and conservative, durable campaign admission (stdlib)."""
import argparse
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import time
import uuid
from common import SCRATCH, ADAPTER, read_json, write_json, reject_reparse

GATE = 'RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_SMOKE'


def process_active(pid):
    if not isinstance(pid, int) or pid <= 0:
        return True  # corrupt identity is ambiguous
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ctypes.get_last_error() != 87  # access denied is NOT proof of exit
    try:
        code = wintypes.DWORD()
        return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
    finally:
        kernel.CloseHandle(handle)


class OperationLock:
    """Released by the OS on process exit; the persistent file is never deleted."""
    def __init__(self, scratch=SCRATCH):
        self.scratch = Path(scratch)

    def __enter__(self):
        import msvcrt
        reject_reparse(self.scratch)
        self.scratch.mkdir(parents=True, exist_ok=True)
        self.stream = (self.scratch / 'operation.lock').open('a+b')
        self.stream.seek(0)
        try:
            msvcrt.locking(self.stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self.stream.close()
            raise RuntimeError('Another gate operation owns the lock; nothing started') from None
        return self

    def __exit__(self, *args):
        import msvcrt
        self.stream.seek(0)
        msvcrt.locking(self.stream.fileno(), msvcrt.LK_UNLCK, 1)
        self.stream.close()


def campaign_status(scratch=SCRATCH, adapter=ADAPTER, active=process_active):
    scratch, adapter = Path(scratch), Path(adapter)
    # A missing campaign marker is never sufficient permission to start.
    for path in scratch.glob('*-worker.json'):
        if active(read_json(path)['pid']):
            return 'active_or_ambiguous'
    ledger_path = scratch / 'campaign-ledger.json'
    marker = scratch / 'campaign-started.json'
    # train-contexts.json belongs to read-only TRAIN preparation, not a campaign.
    traces = [*scratch.glob('train-[0-9]*.json'), *scratch.glob('training-*.log'),
              *scratch.glob('model-load-*.json'), *scratch.glob('worker-started*.json')]
    if ledger_path.exists():
        ledger = read_json(ledger_path)
        if ledger['gate'] != GATE:
            return 'active_or_ambiguous'
        if ledger['status'] == 'completed' and marker.is_file() and (scratch / 'outcome.json').is_file():
            reservation = read_json(marker)
            if reservation['gate'] == GATE and reservation['nonce'] == ledger['nonce']:
                return 'completed'
            return 'active_or_ambiguous'
        if ledger['status'] == 'precondition_failed' and ledger['model_load_started'] is False:
            released = read_json(scratch / ledger['release_record'])
            if (released['verified_before_load'] is True and released['worker_exited'] is True
                    and not marker.exists() and not traces and not any(adapter.glob('**/*'))):
                return 'retryable_precondition'
        return 'active_or_ambiguous'
    if marker.exists() or traces or any(adapter.glob('**/*')) or (scratch / 'outcome.json').exists():
        return 'active_or_ambiguous'
    return 'fresh'


def reserve_campaign(scratch=SCRATCH, adapter=ADAPTER):
    assert campaign_status(scratch, adapter) in ('fresh', 'retryable_precondition'), 'Campaign consumed or ambiguous; package only'
    nonce = uuid.uuid4().hex
    record = dict(gate=GATE, worker_may_start=True, sequence_limit=1536, nonce=nonce,
                  time_unix=time.time(), supervisor_pid=os.getpid(), model_load_started=False, status='reserved')
    # Ledger first: interruption between these writes remains fail-closed.
    write_json(Path(scratch) / 'campaign-ledger.json', record)
    with (Path(scratch) / 'campaign-started.json').open('x', encoding='utf-8') as f:
        json.dump(record, f)
        f.flush(); os.fsync(f.fileno())
    return record


def release_preload_failure(train, monitor, scratch=SCRATCH):
    """Only a positively observed worker precondition refusal permits a retry."""
    scratch = Path(scratch)
    assert train['model_load_started'] is False and (train.get('precondition_failed') is True or train.get('gpu_environment_blocked') is True)
    assert monitor['worker_exited'] is True and monitor['returncode'] != 0 and monitor['stop_reason'] is None
    assert not process_active(monitor['worker_pid']) and not process_active(monitor['launcher_pid'])
    assert not (scratch / 'model-load-started.json').exists()
    marker = read_json(scratch / 'campaign-started.json')
    history = scratch / 'preload-refusals' / marker['nonce']
    history.mkdir(parents=True, exist_ok=False)
    # Preserve every attempted-worker artifact and never delete a campaign marker.
    for path in list(scratch.iterdir()):
        if (path.name in ('campaign-started.json', 'train-1536.json', 'worker-started.json')
                or path.name.startswith('training-')):
            path.rename(history / path.name)
    record = {'verified_before_load': True, 'worker_exited': True, 'model_load_started': False,
              'nonce': marker['nonce'], 'monitor': monitor}
    write_json(history / 'release.json', record)
    write_json(scratch / 'campaign-ledger.json', dict(gate=GATE, status='precondition_failed',
               model_load_started=False, release_record=(history / 'release.json').relative_to(scratch).as_posix()))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['status'])
    parser.parse_args()
    print(campaign_status())
