"""Hash-only supervisor: protected bytes never enter a training process."""
import argparse
import subprocess
from common import ROOT, MODEL, SCRATCH, read_json, write_json, sha256


def capture():
    authority = read_json(ROOT / 'docs/gates/evidence/LOCAL_DATASET_DESIGN_AND_SYNTHETIC_RU.json')['integrity']
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')
    paths = [ROOT / p for p in tracked if p and not p.startswith('ml/qlora_smoke/') and 'LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE' not in p]
    paths += [p for p in MODEL.rglob('*') if p.is_file()]
    paths += [ROOT / x['path'] for x in authority['raw_artifacts']]
    hashes = {p.relative_to(ROOT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha256(p)} for p in paths}
    for row in authority['model_shards']:
        assert hashes['AlagModels/Qwen3-4B/' + row['file']]['sha256'] == row['sha256'], row['file']
    for row in authority['raw_artifacts'] + authority['model_small_files']:
        assert hashes[row['path']]['sha256'] == row['sha256'], row['path']
    manifest = read_json(ROOT / 'ml/data/synthetic_ru/manifest.json')
    for name, value in manifest['artifacts'].items():
        assert hashes[name]['sha256'] == value['sha256'], name
    assert hashes['evals/local-qwen/a01-a16.json']['sha256'] == manifest['holdout_sha256']
    baseline = {p.relative_to(ROOT / '.venv-ml').as_posix(): [p.stat().st_size, p.stat().st_mtime_ns]
                for p in (ROOT / '.venv-ml').rglob('*') if p.is_file()}
    return {'files': hashes, 'baseline_environment_file_stats': baseline,
            'pinned_model_raw_and_dataset_hashes_match': True,
            'role': 'Separate hash auditor; no JSON parsing of TRAIN/DEV/INTERNAL_TEST/A01-A16/tuning eval.'}


def compare(before, after):
    changed = [k for k, v in before['files'].items() if after['files'].get(k) != v]
    if before['baseline_environment_file_stats'] != after['baseline_environment_file_stats']:
        changed.append('.venv-ml file inventory/stats')
    return changed


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('phase', choices=['before', 'after'])
    args = parser.parse_args()
    result = capture()
    if args.phase == 'after':
        result['changed'] = compare(read_json(SCRATCH / 'integrity-before.json'), result)
        assert not result['changed'], result['changed']
    write_json(SCRATCH / f'integrity-{args.phase}.json', result)
    print(f'{args.phase}: {len(result["files"])} protected hashes verified; baseline file inventory recorded', flush=True)
