"""Supervisor: fresh bootstrap preparation, single campaign, fresh reload."""
import argparse
import os
import sys
import time
import traceback
import uuid
from common import ROOT, HERE, SCRATCH, ADAPTER, read_json, write_json, sha256
from control import assert_git_safe, project, protect_before, protect_after
from environment import capture
from model_files import verify_model
from monitor import run as supervise
from selection import validate_selection
from state import GATE, OperationLock, campaign_status, reserve_campaign, release_preload_failure
from verdict import PREFIX, decide


def optional(name):
    path = SCRATCH / name
    return read_json(path) if path.is_file() else {}


def command(name, *args):
    return [sys.executable, '-B', str(HERE / name), *args]


def assert_ready():
    ready = read_json(SCRATCH / 'prepared-ready.json')
    assert ready['passed'] is True and read_json(SCRATCH / 'tests.json')['passed'] is True
    assert ready['git']['commit'] == assert_git_safe()['commit'], 'Source changed after preparation'
    assert ready['configuration_sha256'] == sha256(HERE / 'config.json')
    for name, digest in ready['files'].items():
        assert sha256(SCRATCH / name) == digest, 'Prepared file changed: ' + name
    validate_selection(read_json(SCRATCH / 'data-1536.json')['selection'])


def prepare():
    assert campaign_status() in ('fresh', 'retryable_precondition'), 'Campaign consumed or ambiguous; package only'
    capture(); assert_git_safe()
    write_json(SCRATCH / 'model-verification.json', verify_model())
    if (SCRATCH / 'prepared-ready.json').exists():
        assert_ready(); protect_after()
        print('Validated preparation reused; no TRAIN measurement or model load repeated.', flush=True)
        return
    owner = SCRATCH / 'preparation-owner.json'
    if owner.exists():
        assert read_json(owner)['gate'] == GATE and read_json(owner)['commit'] == assert_git_safe()['commit']
    else:
        assert not (SCRATCH / 'data-1536.json').exists(), 'Unknown preparation data preserved'
        write_json(owner, {'gate': GATE, 'commit': assert_git_safe()['commit']})
    assert read_json(SCRATCH / 'cuda-backend.json')['passed'] is True
    project(); protect_before()
    # Unique non-training phase names preserve an interrupted preparation. Only
    # this positively identified phase may be remeasured on PrepareOnly retry.
    suffix = uuid.uuid4().hex
    for phase, budget, argv in [('prepare-data', 600, command('prepare_smoke_data.py', '--max-length', '1536')),
                                 ('cheap-checks', 180, command('cheap_checks.py'))]:
        if supervise(phase + '-' + suffix, budget, argv) != 0:
            raise RuntimeError(phase + ' failed; no Qwen weights loaded')
    protect_after()
    validate_selection(read_json(SCRATCH / 'data-1536.json')['selection'])
    names = ['data-1536.json', 'frozen-controls.json', 'module-control.json', 'train-contexts.json',
             'tests.json', 'prepare-1536-audit.json', 'integrity-before.json']
    write_json(SCRATCH / 'prepared-ready.json', {'passed': True, 'files': {n: sha256(SCRATCH / n) for n in names},
               'git': assert_git_safe(), 'configuration_sha256': sha256(HERE / 'config.json')})
    print('PREPARED: 8000/8000 complete TRAIN records; configured 1536; observed maximum 1421.', flush=True)
    print('Updates: [1396,1393,1391,1388], [1421,1408,1406,1402]; unused reload record 1387.', flush=True)


def isolation_ok(prepare_audit, tests, train, reload):
    try:
        records = [prepare_audit, tests['audit'], train['audit'], reload['audit']]
        return all(r['network_allowed'] is False and r['evaluation_file_reads'] == [] and r['denied'] == []
                   and isinstance(r['reads'], list) and isinstance(r['limitation'], str) for r in records)
    except (KeyError, TypeError):
        return False


def no_live_workers():
    import psutil
    for process in psutil.process_iter(['pid', 'cmdline']):
        if process.info['pid'] == os.getpid(): continue
        args = process.info['cmdline'] or []
        for name in ('train_smoke.py', 'verify_adapter.py'):
            if any(os.path.normcase(str(HERE / name)) == os.path.normcase(a) for a in args):
                raise RuntimeError('Live gate worker exists; no repeat is safe')


def record_precondition_failure():
    """Only called under the operation lock before reservation and worker spawn."""
    assert not (SCRATCH / 'campaign-started.json').exists()
    name = 'precondition-' + uuid.uuid4().hex + '.json'
    write_json(SCRATCH / name, {'verified_before_load': True, 'worker_exited': True,
                               'worker_started': False, 'model_load_started': False})
    write_json(SCRATCH / 'campaign-ledger.json', {'gate': GATE, 'status': 'precondition_failed',
               'model_load_started': False, 'release_record': name})


def run_campaign():
    status = campaign_status()
    if status == 'completed':
        verdict = read_json(SCRATCH / 'outcome.json')['verdict']
        print('Completed campaign: ' + verdict)
        return verdict in (PREFIX + 'PASS', PREFIX + 'PASS_TIGHT_MEMORY')
    assert status in ('fresh', 'retryable_precondition'), 'Executed/ambiguous attempt; package only'
    no_live_workers()
    stage = 'prerequisites'; reserved = False
    outcome = {'schema_version': 2, 'gate': GATE, 'training_campaigns': 0, 'verdict': PREFIX + 'RUNTIME_BLOCKED',
               'full_training_started': False, 'evaluation_started': False, 'local_quality_evaluation': False}
    try:
        assert_ready(); capture()
        name = 'resources-' + uuid.uuid4().hex
        code = supervise(name, 180, command('runtime_checks.py'))
        fresh = optional('preflight.json'); outcome['preflight'] = fresh
        outcome['resource_monitor'] = optional(name + '-monitor.json')
        if code != 0 or fresh.get('passed') is not True:
            record_precondition_failure()
            outcome['failed_checks'] = [k for k, v in fresh.get('hardware_checks', {}).items() if not v]
            outcome['reason'] = 'Fresh runtime precondition failed before reservation/model load'
            return False
        verify_model(); protect_after()
        stage = 'training'; reserve_campaign(); reserved = True
        outcome['training_campaigns'] = 1
        train_phase = 'training-' + uuid.uuid4().hex
        train_code = supervise(train_phase, 1800, command('train_smoke.py', '--max-length', '1536'))
        training = optional('train-1536.json'); monitoring = optional(train_phase + '-monitor.json')
        outcome.update(training=training, monitor=monitoring)
        if (training.get('precondition_failed') is True and training.get('model_load_started') is False
                and train_code != 0):
            release_preload_failure(training, monitoring)
            reserved = False
            outcome.update(training_campaigns=0, reason='Verified resource refusal before model load',
                           verdict=PREFIX + 'RUNTIME_BLOCKED')
            return False
        reloaded, reload_monitor = {}, {}
        if train_code == 0 and training.get('passed') is True and monitoring.get('worker_exited') is True and not monitoring.get('stop_reason'):
            stage = 'reload'
            reload_code = supervise('reload', 600, command('verify_adapter.py', '--max-length', '1536'))
            reloaded = optional('reload-1536.json'); reload_monitor = optional('reload-monitor.json')
            if reload_code != 0: reloaded['passed'] = False
        outcome.update(reload=reloaded, reload_monitor=reload_monitor)
        stage = 'integrity'; integrity = protect_after()
        tests = optional('tests.json'); audit = optional('prepare-1536-audit.json')
        isolated = isolation_ok(audit, tests, training, reloaded)
        decision = decide(training, monitoring, reloaded, integrity['passed'], tests.get('passed') is True, isolated,
                          reload_monitor=reload_monitor)
        outcome.update(decision, integrity=integrity, isolated=isolated)
        print(decision['verdict'], flush=True)
        return decision['verdict'] in (PREFIX + 'PASS', PREFIX + 'PASS_TIGHT_MEMORY')
    except Exception as error:
        if not reserved and stage == 'prerequisites': record_precondition_failure()
        outcome.update(verdict=PREFIX + ('RUNTIME_BLOCKED' if not reserved else 'FAIL'), failed_stage=stage,
                       error_type=type(error).__name__, error=traceback.format_exc())
        print(outcome['error'], flush=True)
        return False
    finally:
        outcome.update(completed_at_unix=time.time(), repository_commit=optional('prepared-ready.json').get('git', {}).get('commit'),
                       stop='Full training and a second executed memory campaign are not authorized.')
        write_json(SCRATCH / 'outcome.json', outcome)
        if reserved:
            ledger = read_json(SCRATCH / 'campaign-ledger.json')
            ledger.update(status='completed', model_load_started=(SCRATCH / 'model-load-started.json').exists())
            write_json(SCRATCH / 'campaign-ledger.json', ledger)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('phase', choices=['prepare', 'run']); a = parser.parse_args()
    with OperationLock():
        if a.phase == 'prepare': prepare()
        else: raise SystemExit(0 if run_campaign() else 1)
