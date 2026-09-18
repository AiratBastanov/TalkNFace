"""Portable supervisor for one isolated 1536/full-TRAIN-envelope campaign."""
import argparse
import json
import os
import sys
import time
import traceback
from common import ROOT, HERE, SCRATCH, read_json, write_json, sha256
from control import assert_git_safe, project, protect_before, protect_after
from environment import capture
from model_files import verify_model
from monitor import run as supervise
from verdict import PREFIX, decide

BASE_SCRATCH = ROOT / '.tmp/rtx3070-targeted-smoke'
BASE_RESULT = ROOT / 'handoff-results/RTX3070_TARGETED_LORA_SMOKE_RESULT.zip'
BASE_RESULT_SHA256 = '82d727d431ecbb91585d53961442eeab2f544c5f74b19f5572cea30dd1389fb9'


def optional(name):
    path = SCRATCH / name
    return read_json(path) if path.exists() else {}


def command(name, *args):
    return [sys.executable, '-B', str(HERE / name), *args]


def verify_baseline():
    assert BASE_RESULT.is_file(), 'Successful 1024 result ZIP is missing'
    assert sha256(BASE_RESULT) == BASE_RESULT_SHA256, 'Successful 1024 result ZIP hash changed'
    outcome_path = BASE_SCRATCH / 'outcome.json'
    assert outcome_path.is_file(), 'Successful 1024 outcome evidence is missing'
    outcome = read_json(outcome_path)
    assert outcome.get('verdict') == 'RTX3070_TARGETED_LORA_MEMORY_SMOKE_PASS', '1024 baseline was not a full PASS'
    assert outcome.get('training_campaigns') == 1
    assert outcome.get('training', {}).get('actual_optimizer_steps') == 2
    assert outcome.get('reload', {}).get('passed') is True
    record = {'passed': True, 'result_zip_sha256': BASE_RESULT_SHA256,
              'verdict': outcome['verdict'], 'optimizer_updates': 2, 'reload': True}
    write_json(SCRATCH / 'baseline-1024-prerequisite.json', record)
    return record


def prepare():
    assert not (SCRATCH / 'campaign-started.json').exists(), 'A 1536 campaign has already been claimed'
    capture(); assert_git_safe(); verify_baseline()
    write_json(SCRATCH / 'model-verification.json', verify_model())
    if (SCRATCH / 'prepared-ready.json').exists():
        assert_ready(); print('1536 preparation already complete and unchanged; nothing rerun.'); return
    if not optional('cuda-backend.json').get('passed'):
        if supervise('cuda-backend', 120, command('runtime_checks.py', '--backend')) != 0:
            raise RuntimeError('CUDA/NF4 backend recheck failed; no Qwen model was loaded.')
    assert read_json(SCRATCH / 'cuda-backend.json')['passed']
    project(); protect_before()
    if supervise('prepare-data', 600, command('prepare_smoke_data.py', '--max-length', '1536')) != 0:
        raise RuntimeError('Full TRAIN envelope measurement failed; do not edit the corpus or truncate records.')
    if supervise('cheap-checks', 180, command('cheap_checks.py')) != 0:
        raise RuntimeError('1536 cheap checks failed. Do not proceed to training.')
    names = ['data-1536.json', 'frozen-controls.json', 'module-control.json', 'train-contexts.json', 'tests.json',
             'cuda-backend.json', 'model-verification.json', 'baseline-1024-prerequisite.json']
    write_json(SCRATCH / 'prepared-ready.json', {'passed': True, 'files': {n: sha256(SCRATCH / n) for n in names},
               'git': assert_git_safe(), 'configuration_sha256': sha256(HERE / 'config.json')})
    selection = read_json(SCRATCH / 'data-1536.json')['selection']
    print('1536 preparation PASS: measured all 8000 TRAIN rows; observed max 1421; no truncation.')
    print(json.dumps({'step1_lengths': selection['optimizer_step_1_lengths'],
                      'step2_lengths': selection['optimizer_step_2_lengths'],
                      'reload_length': selection['reload_length']}, ensure_ascii=False))


def assert_ready():
    ready = read_json(SCRATCH / 'prepared-ready.json')
    assert ready['passed'] and read_json(SCRATCH / 'tests.json')['passed']
    assert ready['git']['commit'] == assert_git_safe()['commit'], 'Repository changed after 1536 preparation'
    assert ready['configuration_sha256'] == sha256(HERE / 'config.json')
    for name, digest in ready['files'].items():
        assert sha256(SCRATCH / name) == digest, f'Prepared file changed: {name}'
    verify_baseline()


def reserve_campaign(path=SCRATCH / 'campaign-started.json'):
    with path.open('x', encoding='utf-8') as stream:
        json.dump({'gate': 'RTX3070_TARGETED_LORA_1536_ENVELOPE_SMOKE', 'worker_may_start': True,
                   'sequence_limit': 1536, 'time_unix': time.time(), 'supervisor_pid': os.getpid()}, stream)


def isolation_ok(records):
    return all(not r.get('audit', {}).get('evaluation_file_reads') and not r.get('audit', {}).get('denied') for r in records)


def run_campaign():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    assert not (SCRATCH / 'campaign-started.json').exists(), '1536 campaign already claimed. No second training run; package the result.'
    mutex = SCRATCH / 'supervisor-active.json'
    with mutex.open('x', encoding='utf-8') as stream: json.dump({'pid': os.getpid()}, stream)
    stage = 'prerequisites'; outcome = {'training_campaigns': 0, 'verdict': PREFIX + 'FAIL'}
    try:
        assert_ready(); capture(); verify_baseline()
        stamp = str(time.time_ns()); resource_phase = 'resources-' + stamp
        code = supervise(resource_phase, 120, command('runtime_checks.py'))
        fresh = optional('preflight.json')
        if code != 0 or not fresh.get('passed'):
            suffix = 'GPU_ENVIRONMENT_BLOCKED' if fresh.get('gpu_environment_blocked') else 'RUNTIME_BLOCKED'
            outcome.update(verdict=PREFIX + suffix, reason=fresh.get('error', 'Fresh resource/runtime precondition failed'), preflight=fresh)
            if suffix == 'GPU_ENVIRONMENT_BLOCKED': print('ACTION REQUIRED: close GPU-heavy applications; no training campaign was consumed.')
            return False
        stage = 'model_integrity'; verify_model(); protect_after()
        stage = 'training'; reserve_campaign()
        attempt = len(list(SCRATCH.glob('gpu-preload-blocked-*.json'))) + 1
        train_phase = f'training-{attempt}'
        supervise(train_phase, 1800, command('train_smoke.py', '--max-length', '1536'))
        training = optional('train-1536.json'); monitoring = optional(train_phase + '-monitor.json')
        outcome.update(training=training, monitor=monitoring)
        if training.get('gpu_environment_blocked') and not training.get('model_load_started'):
            (SCRATCH / 'train-1536.json').rename(SCRATCH / f'gpu-preload-blocked-{attempt}.json')
            (SCRATCH / 'campaign-started.json').rename(SCRATCH / f'preload-reservation-{attempt}.json')
            outcome.update(verdict=PREFIX + 'GPU_ENVIRONMENT_BLOCKED', reason='External GPU occupancy changed before model load',
                           training=training, monitor=monitoring)
            print('ACTION REQUIRED: close GPU-heavy applications; no model load occurred and no training campaign was consumed.')
            return False
        outcome['training_campaigns'] = 1
        reloaded = {}; reload_monitor = {}
        if training.get('passed') and monitoring.get('worker_exited') and not monitoring.get('stop_reason'):
            stage = 'reload'; supervise('reload', 600, command('verify_adapter.py', '--max-length', '1536'))
            reloaded = optional('reload-1536.json'); reload_monitor = optional('reload-monitor.json')
            if reload_monitor.get('returncode') != 0 or reload_monitor.get('stop_reason'):
                reloaded['passed'] = False
        outcome.update(reload=reloaded, reload_monitor=reload_monitor)
        stage = 'integrity'; integrity = protect_after()
        audits = [optional('prepare-1536-audit.json'), optional('tests.json'), training, reloaded]
        prepare_audit = optional('prepare-1536-audit.json')
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
        print(outcome['error'], flush=True); return False
    finally:
        outcome.update(full_training_started=False, evaluation_started=False, local_quality_evaluation=False,
                       completed_at_unix=time.time(), repository_commit=optional('prepared-ready.json').get('git', {}).get('commit'),
                       stop='No second 1536 campaign or full training is authorized by this gate.')
        write_json(SCRATCH / 'outcome.json', outcome); mutex.unlink(missing_ok=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['prepare', 'run']); args = parser.parse_args()
    if args.phase == 'prepare': prepare()
    else: raise SystemExit(0 if run_campaign() else 1)
