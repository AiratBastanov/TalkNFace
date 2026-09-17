"""Deterministic TRAIN-only coverage sample; complete sequences, never truncation."""
import argparse
from collections import Counter
import hashlib
import json
import statistics
import sys
from common import ROOT, DATA, TRAIN, MODEL, SCRATCH, AccessGuard, read_json, write_json

SEED = 20260917
CRITICAL = ('ambiguity', 'negation', 'prompt_injection')


def train_rows(path=TRAIN):
    if path.resolve() != TRAIN:
        raise PermissionError('Only the accepted TRAIN source is allowed')
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            row = json.loads(line)
            if row['split'] != 'train':
                raise ValueError('Non-TRAIN row')
            yield row


def order_key(row):
    return hashlib.sha256(f'{SEED}:{row["id"]}'.encode()).hexdigest()


def select(rows, limit, count=32):
    eligible = sorted((r for r in rows if r['length'] <= limit), key=order_key)
    selected = []
    def take(predicate):
        match = next((r for r in eligible if predicate(r) and r not in selected), None)
        if match is None:
            raise ValueError('Required coverage unavailable within complete-sequence limit')
        selected.append(match)
    # First microbatch always exercises the envelope; remaining choices are
    # seeded hash ordering, with no model outputs or holdout-derived heuristics.
    take(lambda r: r['length'] >= (900 if limit == 1024 else 700))
    # At 768 some complete intent/target combinations cannot fit at all.
    # Cover every eligible intent; never truncate or change targets to force it.
    for intent in sorted({r['intent'] for r in eligible}):
        take(lambda r, intent=intent: r['intent'] == intent)
    for tag in CRITICAL:
        if any(tag in r['tags'] for r in eligible) and not any(tag in r['tags'] for r in selected):
            take(lambda r, tag=tag: tag in r['tags'])
    for row in eligible:
        if len(selected) >= count:
            break
        if row not in selected:
            selected.append(row)
    if len(selected) != count:
        raise ValueError('Insufficient complete TRAIN examples')
    reload_row = next(r for r in eligible if r not in selected)
    return selected, reload_row


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
    from transformers import AutoTokenizer
    sys.path.insert(0, str(DATA))
    from compile_sft import compile_row, canonical_completion
    registry = read_json(SCRATCH / 'train-contexts.json')
    assert all(v['split']=='train' for v in registry.values())
    control = read_json(SCRATCH / 'selection-control.json')
    wanted = set(control['selected_ids'] + [control['reload_id']])
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    records = []
    for row in train_rows():
        if limit==1024 and row['id'] not in wanted:
            continue
        if row['contextId'] not in registry:
            raise ValueError('Non-TRAIN context')
        compiled = compile_row(row, registry, checked=True)
        record = tokenize_record(tokenizer, compiled, canonical_completion(row['expected']))
        record.update(id=row['id'], intent=row['intent'], tags=row['criticalityTags'], split='train')
        records.append(record)
    if limit==1024:
        by_id={r['id']:r for r in records}
        assert set(by_id)==wanted
        selected=[by_id[i] for i in control['selected_ids']]
        reload_row=by_id[control['reload_id']]
        assert [r['length'] for r in selected]==control['lengths']
        assert all(r['length']<=limit for r in selected+[reload_row])
    else:
        selected, reload_row = select(records, limit)
    lengths = [r['length'] for r in selected]
    data = {'max_length': limit, 'seed': SEED, 'source': TRAIN.relative_to(ROOT).as_posix(),
            'rows': selected, 'reload_row': reload_row,
            'selection': {'source_rows_measured': len(records), 'eligible_rows': sum(r['length'] <= limit for r in records),
                          'historical_ids_and_lengths_reused': limit==1024,
                          'unavailable_intents_within_limit': sorted({r['intent'] for r in records}-{r['intent'] for r in records if r['length']<=limit}),
                          'unavailable_critical_tags_within_limit': [t for t in CRITICAL if not any(t in r['tags'] and r['length']<=limit for r in records)],
                          'selected_ids': [r['id'] for r in selected], 'reload_id': reload_row['id'],
                          'lengths': lengths, 'min': min(lengths), 'max': max(lengths), 'median': statistics.median(lengths),
                          'intents': dict(Counter(r['intent'] for r in selected)),
                          'critical_tags': dict(Counter(t for r in selected for t in r['tags'])),
                          'truncated_rows': 0, 'selection_algorithm': '1024: exact historical IDs/order. 768: seeded SHA256 order; boundary first; every eligible intent and eligible critical tag; fill to 32'}}
    write_json(SCRATCH / f'data-{limit}.json', data)
    return data


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-length', type=int, choices=[1024, 768], default=1024)
    args = parser.parse_args()
    guard = AccessGuard('prepare', tokenizer_only=True).install()
    try:
        result = prepare(args.max_length)
        print(json.dumps(result['selection']), flush=True)
    finally:
        write_json(SCRATCH / f'prepare-{args.max_length}-audit.json', guard.report())
