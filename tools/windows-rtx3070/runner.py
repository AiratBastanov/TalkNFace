"""Portable supervisor. Only the run phase can claim and launch one 4B campaign."""
import argparse
import json
import os
import sys
import time
import traceback
from common import ROOT, HERE, SCRATCH, ADAPTER, read_json, write_json, sha256
from control import assert_git_safe, project, protect_before, protect_after
from environment import capture
from model_files import verify_model
from monitor import run as supervise
from verdict import PREFIX, decide


def optional(name):
    path = SCRATCH / name
    return read_json(path) if path.exists() else {}


def command(name, *args):
    return [sys.executable, '-B', str(HERE / name), *args]


def prepare():
    assert not (SCRATCH / 'campaign-started.json').exists(), 'A campaign has already been claimed'
    capture(); assert_git_safe()
    assert read_json(SCRATCH / 'cuda-backend.json')['passed'], 'Complete script 01 first'
    assert read_json(SCRATCH / 'model-verification.json')['passed'], 'Complete script 02 first'
    verify_model()
    if (SCRATCH / 'prepared-ready.json').exists():
        assert_ready()
        print('Preparation already complete and unchanged; nothing rerun.'); return
    project(); protect_before()
    if supervise('prepare-data', 120, command('prepare_smoke_data.py')) != 0:
        raise RuntimeError('TRAIN preparation failed; do not edit the corpus. Package result and contact project owner.')
    if supervise('cheap-checks', 120, command('cheap_checks.py')) != 0:
        raise RuntimeError('Cheap checks failed. Do not proceed to training; package result.')
    names = ['data-1024.json', 'spec-control.json', 'selection-control.json', 'module-control.json', 'train-contexts.json', 'tests.json']
    write_json(SCRATCH / 'prepared-ready.json', {'passed': True, 'files': {n: sha256(SCRATCH / n) for n in names},
               'git': assert_git_safe(), 'configuration_sha256': sha256(HERE / 'config.json')})
    print('32 frozen TRAIN rows + unused reload row ready. No model loaded.')


def assert_ready():
    ready = read_json(SCRATCH / 'prepared-ready.json')
    assert ready['passed'] and read_json(SCRATCH / 'tests.json')['passed']
    assert ready['git']['commit'] == assert_git_safe()['commit'], 'Repository changed after preparation'
    assert ready['configuration_sha256'] == sha256(HERE / 'config.json')
    for name, digest in ready['files'].items():
        assert sha256(SCRATCH / name) == digest, f'Prepared file changed: {name}'


def reserve_campaign(path=SCRATCH / 'campaign-started.json'):
    # Exclusive creation survives worker crashes, restarts and another PowerShell window.
    with path.open('x', encoding='utf-8') as stream:
        json.dump({'gate': 'RTX3070_TARGETED_LORA_MEMORY_SMOKE', 'worker_may_start': True,
                   'sequence_limit': 1024, 'time_unix': time.time(), 'supervisor_pid': os.getpid()}, stream)


def isolation_ok(records):
    return all(not r.get('audit', {}).get('evaluation_file_reads') and not r.get('audit', {}).get('denied') for r in records)


def run_campaign():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    assert not (SCRATCH / 'campaign-started.json').exists(), 'Campaign already claimed. No second training run; use script 05.'
    # Separate invocation mutex does not consume the training allowance.
    mutex = SCRATCH / 'supervisor-active.json'
    with mutex.open('x', encoding='utf-8') as stream: json.dump({'pid': os.getpid()}, stream)
    stage = 'prerequisites'; outcome = {'training_campaigns': 0, 'verdict': PREFIX + 'FAIL'}
    try:
        assert_ready(); capture()
        stamp = str(time.time_ns())
        resource_phase = 'resources-' + stamp
        code = supervise(resource_phase, 120, command('runtime_checks.py'))
        fresh = optional('preflight.json')
        if code != 0 or not fresh.get('passed'):
            suffix = 'GPU_ENVIRONMENT_BLOCKED' if fresh.get('gpu_environment_blocked') else 'RUNTIME_BLOCKED'
            outcome.update(verdict=PREFIX + suffix, reason=fresh.get('error', 'Fresh resource/runtime precondition failed'), preflight=fresh)
            if suffix == 'GPU_ENVIRONMENT_BLOCKED': print('ACTION REQUIRED: close GPU-heavy applications and rerun script 04.')
            return False
        stage = 'model_integrity'; verify_model()
        # Source/model bytes must still match preparation before any load.
        protect_after()
        stage = 'training'; reserve_campaign()
        attempt = len(list(SCRATCH.glob('gpu-preload-blocked-*.json'))) + 1
        train_phase = f'training-{attempt}'
        supervise(train_phase, 1800, command('train_smoke.py'))
        training = optional('train-1024.json'); monitoring = optional(train_phase + '-monitor.json')
        outcome.update(training=training, monitor=monitoring)
        # A fresh external-occupancy race before any model load is a precondition
        # block, not a consumed training campaign. Preserve both records.
        if training.get('gpu_environment_blocked') and not training.get('model_load_started'):
            (SCRATCH / 'train-1024.json').rename(SCRATCH / f'gpu-preload-blocked-{attempt}.json')
            (SCRATCH / 'campaign-started.json').rename(SCRATCH / f'preload-reservation-{attempt}.json')
            outcome.update(verdict=PREFIX + 'GPU_ENVIRONMENT_BLOCKED', reason='External GPU occupancy changed before model load',
                           training=training, monitor=monitoring)
            print('ACTION REQUIRED: close GPU-heavy applications and rerun script 04.')
            return False
        outcome['training_campaigns'] = 1
        reloaded = {}; reload_monitor = {}
        if training.get('passed') and monitoring.get('worker_exited') and not monitoring.get('stop_reason'):
            stage = 'reload'
            supervise('reload', 600, command('verify_adapter.py'))
            reloaded = optional('reload-1024.json'); reload_monitor = optional('reload-monitor.json')
            if reload_monitor.get('returncode') != 0 or reload_monitor.get('stop_reason'):
                reloaded['passed'] = False
        outcome.update(reload=reloaded, reload_monitor=reload_monitor)
        stage = 'integrity'
        integrity = protect_after()
        audits = [optional('prepare-1024-audit.json'), optional('tests.json'), training, reloaded]
        prepare_audit = optional('prepare-1024-audit.json')
        isolated = isolation_ok(audits) and not prepare_audit.get('evaluation_file_reads') and not prepare_audit.get('denied')
        decision = decide(training, monitoring, reloaded, integrity['passed'], optional('tests.json').get('passed', False), isolated)
        outcome.update(decision, training=training, monitor=monitoring, reload=reloaded, reload_monitor=reload_monitor,
                       integrity=integrity, isolated=isolated, preflight=fresh)
        print(decision['verdict']); print('NEXT: ' + decision['next'])
        return decision['verdict'] in (PREFIX + 'PASS', PREFIX + 'PASS_TIGHT_MEMORY')
    except Exception as error:
        model_error = 'MODEL_INTEGRITY_FAIL' in str(error) or 'Missing pinned model files' in str(error)
        outcome.update(verdict=PREFIX + ('MODEL_INTEGRITY_FAIL' if model_error else
                                          'RUNTIME_BLOCKED' if stage == 'prerequisites' else 'FAIL'),
                       failed_stage=stage, error=traceback.format_exc())
        print(outcome['error'], flush=True)
        return False
    finally:
        outcome.update(full_training_started=False, evaluation_started=False, local_quality_evaluation=False,
                       completed_at_unix=time.time(),
                       repository_commit=optional('prepared-ready.json').get('git', {}).get('commit'),
                       stop='No further campaign or different configuration is authorized.')
        write_json(SCRATCH / 'outcome.json', outcome)
        mutex.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['prepare', 'run']); args = parser.parse_args()
    if args.phase == 'prepare': prepare()
    else: raise SystemExit(0 if run_campaign() else 1)
