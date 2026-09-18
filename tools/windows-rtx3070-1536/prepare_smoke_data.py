"""Measure every TRAIN sequence; select the nine longest complete records without truncation."""
import argparse
import json
import statistics
import sys
from common import ROOT, DATA, TRAIN, MODEL, SCRATCH, AccessGuard, read_json, write_json

SEED = 20260917
LIMIT = 1536
EXPECTED_TRAIN_ROWS = 8000
EXPECTED_MAX = 1421


def train_rows(path=TRAIN):
    if path.resolve() != TRAIN:
        raise PermissionError('Only the accepted TRAIN source is allowed')
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['split'] != 'train':
                raise ValueError('Non-TRAIN row')
            yield row


def tokenize_record(tokenizer, compiled, expected_json):
    assert compiled['completion'] == [{'role': 'assistant', 'content': expected_json}]
    assert '<think>' not in expected_json and '</think>' not in expected_json
    json.loads(expected_json)
    prompt = tokenizer.apply_chat_template(compiled['prompt'], tokenize=False,
                                           add_generation_prompt=True, enable_thinking=False)
    full = tokenizer.apply_chat_template(compiled['prompt'] + compiled['completion'], tokenize=False,
                                         add_generation_prompt=False, enable_thinking=False)
    if not full.startswith(prompt):
        raise ValueError('Non-thinking template does not preserve the exact prompt prefix')
    completion = full[len(prompt):]
    if not completion.startswith(expected_json) or '<think>' in completion or '</think>' in completion:
        raise ValueError('Unexpected thinking or changed JSON in supervision')
    prompt_ids = tokenizer(prompt, add_special_tokens=False)['input_ids']
    ids = tokenizer(full, add_special_tokens=False)['input_ids']
    if ids[:len(prompt_ids)] != prompt_ids:
        raise ValueError('Token boundary differs from text prefix')
    supervised = ids[len(prompt_ids):]
    if supervised.count(tokenizer.eos_token_id) != 1:
        raise ValueError('Exactly one supervised assistant EOS required')
    eos_index = supervised.index(tokenizer.eos_token_id)
    if tokenizer.decode(supervised[:eos_index]) != expected_json:
        raise ValueError('Canonical JSON not preserved byte-for-byte before EOS')
    if tokenizer.decode(supervised[eos_index+1:]).strip():
        raise ValueError('Only template whitespace may follow EOS')
    return dict(prompt=compiled['prompt'], completion=compiled['completion'], input_ids=ids,
                attention_mask=[1]*len(ids), completion_mask=[0]*len(prompt_ids)+[1]*len(supervised),
                labels=[-100]*len(prompt_ids)+supervised, prompt_length=len(prompt_ids),
                length=len(ids), json=expected_json, eos_index=len(prompt_ids)+eos_index)


def verify_labels(record, labels, tokenizer):
    values = labels.tolist() if hasattr(labels, 'tolist') else list(labels)
    n, p = record['length'], record['prompt_length']
    assert all(x == -100 for x in values[:p]), 'Prompt label leakage'
    assert values[p:n] == record['input_ids'][p:], 'Completion masked or changed'
    assert all(x == -100 for x in values[n:]), 'Padding contributes to loss'
    assert values[record['eos_index']] == tokenizer.eos_token_id
    target = tokenizer.decode(values[p:record['eos_index']])
    assert target == record['json'] and json.loads(target) == json.loads(record['json'])
    assert '<think>' not in target and '</think>' not in target


def prepare(limit):
    assert limit == LIMIT, 'Only the configured 1536 envelope is authorized'
    from transformers import AutoTokenizer
    sys.path.insert(0, str(DATA))
    from compile_sft import compile_row, canonical_completion
    registry = read_json(SCRATCH / 'train-contexts.json')
    assert all(v['split'] == 'train' for v in registry.values())
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    longest = []
    lengths = []
    measured = 0
    above_limit = 0
    for row in train_rows():
        if row['contextId'] not in registry:
            raise ValueError('Non-TRAIN context')
        compiled = compile_row(row, registry, checked=True)
        record = tokenize_record(tokenizer, compiled, canonical_completion(row['expected']))
        record.update(id=row['id'], intent=row['intent'], tags=row['criticalityTags'], split='train')
        measured += 1
        lengths.append(record['length'])
        if record['length'] > limit:
            above_limit += 1
        longest.append(record)
        longest.sort(key=lambda r: (-r['length'], r['id']))
        if len(longest) > 9:
            longest.pop()
    assert measured == EXPECTED_TRAIN_ROWS, f'Expected {EXPECTED_TRAIN_ROWS} TRAIN rows, measured {measured}'
    assert max(lengths) == EXPECTED_MAX, f'Accepted TRAIN maximum changed: {max(lengths)}'
    assert above_limit == 0, 'A complete TRAIN record exceeds the 1536 envelope; no truncation is permitted'
    assert len(longest) == 9 and len({r['id'] for r in longest}) == 9
    # The four globally longest records intentionally run in optimizer update #2,
    # where the 1024 campaign had the tighter boundary.
    step2 = longest[:4]
    step1 = longest[4:8]
    reload_row = longest[8]
    selected = step1 + step2
    assert min(r['length'] for r in step2) >= max(r['length'] for r in step1)
    selection = {
        'source_rows_measured': measured,
        'eligible_rows': measured - above_limit,
        'configured_max_length': limit,
        'observed_max_length': max(lengths),
        'rows_above_limit': above_limit,
        'truncated_rows': 0,
        'selected_ids': [r['id'] for r in selected],
        'optimizer_step_1_ids': [r['id'] for r in step1],
        'optimizer_step_2_ids': [r['id'] for r in step2],
        'reload_id': reload_row['id'],
        'selected_lengths': [r['length'] for r in selected],
        'optimizer_step_1_lengths': [r['length'] for r in step1],
        'optimizer_step_2_lengths': [r['length'] for r in step2],
        'reload_length': reload_row['length'],
        'top9_by_length': [{'rank': i+1, 'id': r['id'], 'length': r['length']} for i, r in enumerate(longest)],
        'all_length_min': min(lengths),
        'all_length_median': statistics.median(lengths),
        'all_length_max': max(lengths),
        'selection_algorithm': 'Tokenize all 8000 TRAIN records exactly; sort by (-length,id); ranks 5-8 step1, ranks 1-4 step2, rank9 reload; no truncation.'
    }
    data = {'max_length': limit, 'seed': SEED, 'source': TRAIN.relative_to(ROOT).as_posix(),
            'rows': selected, 'reload_row': reload_row, 'selection': selection}
    write_json(SCRATCH / f'data-{limit}.json', data)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-length', type=int, choices=[1536], default=1536)
    args = parser.parse_args()
    guard = AccessGuard('prepare-1536', tokenizer_only=True).install()
    try:
        result = prepare(args.max_length)
        print(json.dumps(result['selection'], ensure_ascii=False), flush=True)
    finally:
        write_json(SCRATCH / f'prepare-{args.max_length}-audit.json', guard.report())
