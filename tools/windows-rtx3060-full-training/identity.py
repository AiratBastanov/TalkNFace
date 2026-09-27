"""Typed identities. Packaging HEAD is never substituted for training HEAD."""
import platform
import sys
from full_common import (HERE, LEGACY, ROOT, MODEL, ORIGIN, config, digest, git,
                         legacy, pin, read, require, sha)

TRAINING_FILES = ('full_common.py', 'identity.py', 'full_data.py', 'checkpoints.py',
                  'engine.py', 'train_full.py', 'supervisor.py', 'workflow.py',
                  'RUN-FULL-TRAINING.ps1', 'candidate-v1.json', 'accepted-baseline.json')


def accepted_inputs(model_weights=True):
    baseline = read(HERE / 'accepted-baseline.json')
    for name, expected in baseline['legacy_dependency_pins'].items():
        require(pin(LEGACY / name) == expected, 'Accepted smoke dependency changed: ' + name)
    for name, expected in baseline['data_and_compiler_pins'].items():
        require(pin(ROOT / name) == expected, 'Accepted data/compiler changed: ' + name)
    for name, expected in baseline['model']['files'].items():
        if model_weights or not name.endswith('.safetensors'):
            require(pin(MODEL / name) == expected, 'Accepted model/tokenizer changed: ' + name)
    return baseline


def source_identity():
    require(git('remote', 'get-url', 'origin') == ORIGIN, 'Wrong authoritative origin')
    require(git('remote', 'get-url', '--push', 'origin') == ORIGIN, 'Wrong authoritative push origin')
    require(git('branch', '--show-current') == 'main', 'Training preparation requires main')
    require(not git('status', '--porcelain', '--untracked-files=all'), 'Clean checkout required')
    files = {str((HERE / n).relative_to(ROOT)).replace('\\', '/'): pin(HERE / n) for n in TRAINING_FILES}
    return {'kind': 'full_training_source', 'commit': git('rev-parse', 'HEAD'),
            'origin': ORIGIN, 'files': files, 'files_digest': digest(files)}


def check_source(saved):
    require(saved['kind'] == 'full_training_source' and saved['origin'] == ORIGIN, 'Wrong source type')
    require(digest(saved['files']) == saved['files_digest'], 'Source manifest changed')
    for name, expected in saved['files'].items():
        require(pin(ROOT / name) == expected, 'Training source differs from this run: ' + name)
    # Later documentation/packaging commits are allowed; load-bearing content is fixed.


def runtime_identity():
    require(sys.flags.optimize == 0, 'Optimized Python would disable accepted assertions')
    result = legacy('environment').package_check()
    require(result['passed'], 'Use the existing exact validated venv; no automatic installation')
    require(platform.system() == 'Windows' and platform.machine().lower() in ('amd64', 'x86_64'),
            'Validated Windows x64 runtime required')
    return {'kind': 'full_training_runtime', 'python': result['python'], 'bits': result['bits'],
            'packages': result['versions'], 'platform': platform.platform(),
            'runtime_lock_sha256': sha(LEGACY / 'runtime-lock.json')}


def prepared_identity(baseline, source, runtime, prepared):
    return {'accepted_historical_smoke': {'kind': baseline['kind'], 'archive': baseline['archive'],
                                        'training_source_commit': baseline['training_source_commit'],
                                        'packaging_commit': baseline['packaging_commit']},
            'training_source': source, 'runtime': runtime, 'model': baseline['model'],
            'data_and_compiler_pins': baseline['data_and_compiler_pins'],
            'configuration': config(), 'configuration_sha256': sha(HERE / 'candidate-v1.json'),
            'prepared': prepared}
