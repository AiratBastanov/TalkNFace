"""Separate byte-hash auditor and TRAIN-only control materializer; no model calls."""
import argparse
import hashlib
import json
import subprocess
from common import ROOT, HERE, MODEL, DATA, SCRATCH, read_json, write_json, sha256

HISTORY = ROOT / 'docs/gates/evidence/LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE.json'
PINS = ['328a91d3122359d5547f9d79521205bc0a46e1f79a792dfe650e99fc2d651223',
        '6cd087b316306a68c562436b5492edbcf6e16c6dba3a1308279caa5a58e21ca5',
        'e4bf436957184f4eeb86a80e9db394503f1f56446b2e6b7edeac5b81470f4ca1']


def historical_projection(data):
    assert data['verdict'] == 'LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE_FAIL'
    train = data['training']
    assert train['actual_optimizer_steps'] == 2
    return {'selection': train['selection'], 'configuration': train['configuration'],
            'peak_allocated_bytes': train['after_training']['peak_allocated_bytes'],
            'peak_reserved_bytes': train['after_training']['peak_reserved_bytes'],
            'process_peak_bytes': train['cleanup']['memory_before_exit']['peak_working_set_bytes'],
            'step_seconds': [s['seconds'] for s in train['steps']], 'evidence_sha256': sha256(HISTORY)}


def capture(paths):
    files = {name: {'bytes': (ROOT/name).stat().st_size, 'sha256': sha256(ROOT/name)} for name in paths}
    for i, pinned in enumerate(PINS, 1):
        assert files[f'AlagModels/Qwen3-4B/model-{i:05d}-of-00003.safetensors']['sha256'] == pinned
    environments = {}
    for name in ('.venv-ml', '.venv-qlora-smoke'):
        stats = {p.relative_to(ROOT/name).as_posix(): [p.stat().st_size, p.stat().st_mtime_ns]
                 for p in (ROOT/name).rglob('*') if p.is_file()}
        environments[name] = {'files': len(stats), 'stats_sha256': hashlib.sha256(json.dumps(stats,sort_keys=True).encode()).hexdigest()}
    return {'files': files, 'environments': environments}


def before():
    historical = read_json(HISTORY)
    paths = set(historical['integrity']['files'])
    paths.update(p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode().split('\0') if p)
    for folder in (MODEL, ROOT/'AlagModels/adapters/qlora-feasibility-smoke'):
        paths.update(p.relative_to(ROOT).as_posix() for p in folder.rglob('*') if p.is_file())
    snapshot = capture(sorted(paths))
    for name, item in historical['integrity']['files'].items():
        assert snapshot['files'][name] == item['after'], name
    write_json(SCRATCH/'integrity-before.json', snapshot)
    projection = historical_projection(historical)
    write_json(SCRATCH/'historical-comparison.json', projection)
    write_json(SCRATCH/'selection-control.json', projection['selection'])
    registry = {k:v for k,v in read_json(DATA/'contexts.json').items() if v['split']=='train'}
    assert len(registry)==140
    write_json(SCRATCH/'train-contexts.json', registry)
    print(f'{len(paths)} protected hashes verified; TRAIN-only registry and historical IDs projected')


def after():
    initial = read_json(SCRATCH/'integrity-before.json')
    final = capture(initial['files'])
    final['changed'] = [p for p,v in initial['files'].items() if final['files'][p]!=v]
    final['environment_changed'] = initial['environments'] != final['environments']
    write_json(SCRATCH/'integrity-after.json', final)
    assert not final['changed'] and not final['environment_changed']
    print(f'{len(final["files"])} protected hashes and both environments unchanged')


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('phase',choices=['before','after']); args=p.parse_args()
    (before if args.phase=='before' else after)()
