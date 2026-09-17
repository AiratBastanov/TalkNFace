"""Recompute archived output metrics without a model call or label changes."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from scoring import metrics, score

ROOT = Path(__file__).resolve().parents[2]
INPUT_FILES = ['ml/baseline/system-prompt.txt', 'ml/baseline/config.json', 'ml/baseline/requirements.txt',
               'evals/local-qwen/a01-a16.json', 'evals/local-qwen/interpretation.schema.json']


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(run, output, maintenance):
    original = json.loads((run / 'result.json').read_text(encoding='utf-8'))
    assert original['exit_code'] == 0 and original['completed_generations'] == 48
    for path in INPUT_FILES:
        assert digest(ROOT / path) == original['frozen_hashes'][path], 'Frozen input changed: ' + path
    holdout = json.loads((ROOT / 'evals/local-qwen/a01-a16.json').read_text(encoding='utf-8'))
    cfg = json.loads((run / 'config.json').read_text(encoding='utf-8'))
    schema = json.loads((ROOT / 'evals/local-qwen/interpretation.schema.json').read_text(encoding='utf-8'))
    by_id = {c['id']: c for c in holdout['cases']}
    raw_file = run / 'generations.jsonl'
    before = digest(raw_file)
    rows = [json.loads(line) for line in raw_file.read_text(encoding='utf-8').splitlines()]
    assert [(r['case_id'], r['seed']) for r in rows] == [(c['id'], seed) for seed in cfg['seeds'] for c in holdout['cases']]
    scored = [{**r, **score(r['raw_model_output'], by_id[r['case_id']], schema)} for r in rows]
    changes = []
    for old, new in zip(original['per_case'], scored, strict=True):
        fields = {k: {'before': old.get(k), 'after': value} for k, value in new.items() if old.get(k) != value}
        if fields:
            changes.append({'case_id': new['case_id'], 'seed': new['seed'], 'fields': fields})
    result = {**original, 'per_case': scored, 'aggregate': metrics(scored, holdout['cases']),
              'per_seed': {str(seed): metrics([r for r in scored if r['seed'] == seed], holdout['cases']) for seed in cfg['seeds']}}
    assert before == digest(raw_file), 'Raw output mutation'
    result['postprocessing'] = {
        'at_utc': datetime.now(timezone.utc).isoformat(), 'raw_generations_sha256': before,
        'raw_generations_unchanged': True, 'model_calls': 0, 'frozen_inputs_unchanged': True,
        'scorer_sha256': digest(ROOT / 'ml/baseline/scoring.py'),
        'original_aggregate_metrics': original['aggregate'], 'per_case_scoring_changes': changes,
        'maintenance': json.loads(maintenance.read_text(encoding='utf-8')) if maintenance else None,
    }
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'generations': len(scored), 'changed_score_rows': len(changes), 'model_calls': 0, 'raw_unchanged': True}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--maintenance', type=Path)
    args = parser.parse_args()
    assert args.output.resolve().is_relative_to(ROOT / '.tmp')
    main(args.run, args.output, args.maintenance)
