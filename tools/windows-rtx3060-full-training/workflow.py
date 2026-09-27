"""Explicit Prepare / Start / Resume / Status / Package / Cancel. Default is help."""
import argparse
import json
import os
import shutil
import sys
import time
import uuid
from full_common import (HERE, MODEL, ROOT, AccessGuard, Layout, OperationLock, atomic, config, digest,
                         no_links, offline, operational_error, pin, read, require)


def status(layout):
    def optional(name):
        return read(layout.runtime / name) if (layout.runtime / name).exists() else None
    run, completed = optional('run.json'), optional('completed.json')
    return {'run_id': layout.run_id, 'prepared': optional('prepared.json') is not None,
            'started': run is not None, 'completed': completed is not None,
            'progress': optional('progress.json'), 'phase': optional('phase.json'),
            'latest_checkpoint': read(layout.checkpoints / 'LATEST.json') if (layout.checkpoints / 'LATEST.json').exists() else None,
            'operational_diagnostics': optional('operations.json'),
            'quality_evaluation': 'NOT_RUN', 'deadline_unix': run['deadline_unix'] if run else None}


def worker_prepare(layout):
    from identity import accepted_inputs, runtime_identity, source_identity, prepared_identity
    from full_data import project_contexts, prepare_records
    require(not (layout.runtime / 'run.json').exists(), 'Run already started; use Status/Resume')
    baseline = accepted_inputs()
    runtime, source = runtime_identity(), source_identity()
    if (layout.runtime / 'prepared.json').exists():
        from identity import check_source
        from full_data import TrainRecords
        saved = read(layout.runtime / 'prepared.json')['identity']
        check_source(saved['training_source'])
        require(saved['runtime'] == runtime, 'Prepared runtime mismatch')
        TrainRecords(layout.runtime, saved['prepared']).close()
        return
    project_contexts(layout.runtime)
    AccessGuard(layout, tokenizer_only=True).install()
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    summary = prepare_records(layout.runtime, tokenizer)
    identity = prepared_identity(baseline, source, runtime, summary)
    atomic(layout.runtime / 'prepared.json', {'identity': identity}, immutable=True)
    print('PREPARED: 8000 TRAIN rows, complete JSON/EOS, no model weight load/inference/training', flush=True)


def worker_admit(layout):
    from identity import accepted_inputs, check_source, runtime_identity
    from full_data import TrainRecords
    saved = read(layout.runtime / 'prepared.json')['identity']
    check_source(saved['training_source'])
    accepted_inputs()
    require(saved['runtime'] == runtime_identity(), 'Runtime differs from prepared run')
    require(saved['configuration'] == config(), 'Training configuration changed')
    TrainRecords(layout.runtime, saved['prepared']).close()


def environment(layout):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1',
               HF_HUB_OFFLINE='1', HF_DATASETS_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               TMP=str(layout.runtime), TEMP=str(layout.runtime))
    for k in ('PYTHONPATH', 'PYTHONHOME', 'PYTHONOPTIMIZE'):
        env.pop(k, None)
    return env


def launch(layout, action, authorization=None, checkpoint=None):
    from supervisor import bounded
    from checkpoints import Store
    from results import finalize
    c = config()
    require(shutil.disk_usage(layout.runtime).free >= c['disk']['required_free_bytes'], 'Need 10 GiB free on run volume')
    if action == 'start':
        require(authorization == layout.run_id, 'Start requires --authorize-new-run exactly matching RunId')
        require(not (layout.runtime / 'run.json').exists() and not layout.checkpoints.exists()
                and not layout.adapter.exists(), 'Existing run requires explicit Resume; never Start again')
    else:
        require(authorization is None, 'Resume is continuation, not a new-run authorization')
        require((layout.runtime / 'run.json').exists(), 'Cannot resume an unrelated/unstarted run')
        run = read(layout.runtime / 'run.json')
        require(run['identity'] == read(layout.runtime / 'prepared.json')['identity'], 'Prepared/run identity mismatch')
        Store(layout, run).select(checkpoint)
        require(not (layout.runtime / 'completed.json').exists(), 'Run is completed; use Package')
        if checkpoint == 'step-2000':
            finalize(layout)  # crash after final checkpoint: finish evidence offline, no model execution
            return 0
        require(time.time() < run['deadline_unix'], 'Fixed run wall-clock budget exhausted; no automatic extension')
    attempt = uuid.uuid4().hex
    env = environment(layout)
    # Model hashing/runtime checks are a separate finite phase, never part of a microbatch.
    code, unused = bounded([sys.executable, '-B', '-u', str(HERE / 'workflow.py'), '_admit', '--run-id', layout.run_id],
                          c['timeouts_seconds']['admission'], layout.runtime, 'admission-' + attempt, env=env)
    if code:
        operational_error(layout, action, 'NativeFailure', code)
        return code
    if action == 'start':
        now = time.time()
        run = {'schema_version': 1, 'kind': 'full_training_run', 'run_id': layout.run_id, 'nonce': uuid.uuid4().hex,
               'identity': read(layout.runtime / 'prepared.json')['identity'], 'started_unix': now,
               'deadline_unix': now + c['timeouts_seconds']['full_run_wall_clock'], 'authorization': 'EXPLICIT_START'}
        atomic(layout.runtime / 'run.json', run, immutable=True)
    else:
        run = read(layout.runtime / 'run.json')
    cancel = layout.runtime / 'cancel.json'
    if cancel.exists():
        # Preserve cancellation evidence; explicit Resume alone clears the operational request.
        cancel.rename(layout.runtime / ('cancel-' + attempt + '.json'))
    token = uuid.uuid4().hex
    atomic(layout.runtime / 'worker-lease.json', {'token': token, 'parent_pid': os.getpid(), 'attempt': attempt})
    env['QWEN_FULL_WORKER_TOKEN'] = token
    atomic(layout.runtime / 'phase.json', {'phase': 'admission', 'started_unix': time.time()})
    command = [sys.executable, '-B', '-u', str(HERE / 'train_full.py'), '--run-id', layout.run_id]
    if action == 'resume':
        command += ['--resume', checkpoint]
    code, monitor = bounded(command, c['timeouts_seconds']['full_run_wall_clock'], layout.runtime,
                            'train-' + attempt, env=env, training=True, deadline=run['deadline_unix'])
    if code:
        operational_error(layout, action, 'NativeFailure', code)
        return code
    finalize(layout)
    print('FULL_TRAINING_COMPLETED_UNEVALUATED: one TRAIN epoch only; quality evaluation NOT RUN', flush=True)
    return 0


def dispatch(a):
    if a.action is None:
        return 0
    layout = Layout(a.run_id)
    if a.dry_run:
        print(json.dumps({'dry_run': True, 'action': a.action, 'run_id': a.run_id, 'runtime': str(layout.runtime),
                          'checkpoints': str(layout.checkpoints), 'adapter': str(layout.adapter),
                          'results': str(layout.results), 'model_execution': False}, indent=2))
        return 0
    if a.action == 'status':
        print(json.dumps(status(layout), indent=2))
        return 0
    if a.action == 'cancel':
        require((layout.runtime / 'run.json').exists(), 'No started run')
        atomic(layout.runtime / 'cancel.json', {'reason': 'EXPLICIT_CANCEL', 'unix': time.time()})
        print('Cancellation requested; verified checkpoints retained. Use explicit Resume later.')
        return 0
    if a.action == '_prepare':
        worker_prepare(layout)
        return 0
    if a.action == '_admit':
        worker_admit(layout)
        return 0
    with OperationLock(layout.base / 'operation.lock'):
        layout.runtime.mkdir(parents=True, exist_ok=True)
        for path in layout.base.rglob('*'):
            no_links(path)
        from supervisor import bounded
        if a.action == 'prepare':
            require(not (layout.runtime / 'run.json').exists(), 'Prepare cannot overwrite a started run')
            require(shutil.disk_usage(layout.runtime).free >= config()['disk']['required_free_bytes'], 'Need 10 GiB free')
            label = 'prepare-' + uuid.uuid4().hex
            code, unused = bounded([sys.executable, '-B', '-u', str(HERE / 'workflow.py'), '_prepare', '--run-id', a.run_id],
                                   config()['timeouts_seconds']['prepare'], layout.runtime, label, env=environment(layout))
        elif a.action in ('start', 'resume'):
            with OperationLock(ROOT / '.tmp/qwen3-4b-full-training/gpu-operation.lock'):
                return launch(layout, a.action, a.authorize_new_run, a.checkpoint)
        elif a.action == 'package':
            code, unused = bounded([sys.executable, '-B', '-u', str(HERE / 'results.py'), '--run-id', a.run_id],
                                   config()['timeouts_seconds']['package'], layout.runtime,
                                   'package-' + uuid.uuid4().hex, env=environment(layout))
            print('Result directory: ' + str(layout.results), flush=True)
        else:
            raise ValueError('Unknown action')
        if code:
            operational_error(layout, a.action, 'NativeFailure', code)
        return code


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', nargs='?', choices=('prepare', 'start', 'resume', 'status', 'package', 'cancel', '_prepare', '_admit'))
    p.add_argument('--run-id')
    p.add_argument('--authorize-new-run')
    p.add_argument('--checkpoint')
    p.add_argument('--dry-run', action='store_true')
    a = p.parse_args()
    if a.action is None:
        p.print_help()
        return 0
    if not a.run_id:
        p.error('--run-id is required')
    try:
        return dispatch(a)
    except Exception as error:
        print('{}: {}'.format(type(error).__name__, error), file=sys.stderr, flush=True)
        # Local operational errors contain type/code only, never copied into run facts.
        if a.action in ('prepare', 'start', 'resume', 'package'):
            layout = Layout(a.run_id)
            if layout.runtime.exists():
                operational_error(layout, a.action, type(error).__name__, 1)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
