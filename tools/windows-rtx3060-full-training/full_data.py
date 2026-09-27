"""Exactly one frozen TRAIN pass, using the accepted compiler and mask builder."""
import json
import os
import random
import sys
from full_common import DATA, MODEL, atomic, digest, legacy, pin, read, require


def shuffled_order(count, seed):
    indices = list(range(count))
    random.Random(seed).shuffle(indices)
    return indices


def validate_order(order, count=8000):
    require(len(order) == count and all(type(i) is int for i in order)
            and sorted(order) == list(range(count)), 'Missing/duplicate TRAIN positions')


def project_contexts(runtime):
    # Metadata-only projection before the worker guard. No holdout example file is opened.
    registry = {k: v for k, v in read(DATA / 'contexts.json').items() if v['split'] == 'train'}
    require(len(registry) == 140, 'TRAIN context count changed')
    # Insertion order inside publicContext.player is part of the accepted prompt bytes.
    # Sorting nested keys would silently change tokenization (including the 1421 maximum).
    atomic(runtime / 'train-contexts.json', registry, preserve_order=True)


def prepare_records(runtime, tokenizer):
    sys.path.insert(0, str(DATA))
    from compile_sft import compile_row, canonical_completion
    accepted = legacy('prepare_smoke_data')
    registry = read(runtime / 'train-contexts.json')
    require(all(v['split'] == 'train' for v in registry.values()), 'Non-TRAIN context')
    offsets, lengths, ids = [], [], set()
    path = runtime / 'train-tokens.jsonl'
    temporary = runtime / 'train-tokens.partial'
    with temporary.open('wb') as output, (DATA / 'train.jsonl').open(encoding='utf-8') as source:
        for line in source:
            row = json.loads(line)
            require(row['split'] == 'train' and row['id'] not in ids and row['contextId'] in registry,
                    'TRAIN split/context/unique-ID violation')
            ids.add(row['id'])
            record = accepted.tokenize_record(tokenizer, compile_row(row, registry, checked=True),
                                               canonical_completion(row['expected']))
            accepted.verify_labels(record, record['labels'], tokenizer)
            require(record['length'] <= 1536, 'Complete record exceeds 1536; truncation/filtering forbidden')
            offsets.append(output.tell())
            lengths.append(record['length'])
            keep = {k: record[k] for k in ('input_ids', 'labels', 'length', 'prompt_length', 'json', 'eos_index')}
            keep['id'] = row['id']
            output.write(json.dumps(keep, ensure_ascii=True, separators=(',', ':')).encode() + b'\n')
            if len(lengths) % 500 == 0:
                print('TRAIN tokenized {}/8000; max={}'.format(len(lengths), max(lengths)), flush=True)
        output.flush()
        os.fsync(output.fileno())
    require(len(lengths) == 8000 and max(lengths) == 1421, 'Accepted full TRAIN coverage changed')
    os.replace(temporary, path)
    order = shuffled_order(8000, 20260917)
    validate_order(order)
    atomic(runtime / 'order.json', order)
    atomic(runtime / 'offsets.json', offsets)
    summary = {'rows': 8000, 'minimum_length': min(lengths), 'maximum_length': max(lengths),
               'rows_above_1536': 0, 'truncated_rows': 0, 'prompt_masks_verified': 8000,
               'complete_json_and_eos_verified': 8000, 'order_sha256': digest(order),
               'files': {p: pin(runtime / p) for p in ('train-tokens.jsonl', 'order.json', 'offsets.json', 'train-contexts.json')}}
    atomic(runtime / 'data-summary.json', summary)
    return summary


class TrainRecords:
    def __init__(self, runtime, summary):
        for name, expected in summary['files'].items():
            require(pin(runtime / name) == expected, 'Prepared TRAIN file changed')
        self.order = read(runtime / 'order.json')
        validate_order(self.order)
        require(digest(self.order) == summary['order_sha256'], 'Data order changed')
        self.offsets = read(runtime / 'offsets.json')
        require(len(self.offsets) == 8000, 'Offset count changed')
        self.stream = (runtime / 'train-tokens.jsonl').open('rb')

    def __getitem__(self, cursor):
        self.stream.seek(self.offsets[self.order[cursor]])
        return json.loads(self.stream.readline())

    def close(self):
        self.stream.close()
