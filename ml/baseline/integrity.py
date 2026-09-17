"""Read-only integrity auditor. Dataset bytes are hashed here, never sent to inference."""
import argparse
import hashlib
import json
import math
import struct
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / 'docs/gates/evidence/AI_LOCAL_DATASET_MANIFEST.json'


def sha256(path):
    with open(path, 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot():
    acquisition = json.loads(MANIFEST.read_text(encoding='utf-8'))
    old = acquisition['model_verification']
    model = ROOT / 'AlagModels/Qwen3-4B'
    inventory = {p.relative_to(model).as_posix(): {'bytes': p.stat().st_size, 'mtime_ns': p.stat().st_mtime_ns}
                 for p in sorted(model.rglob('*')) if p.is_file()}
    assert inventory == old['file_inventory_before'], 'MODEL_STAT_DRIFT_FROM_ACQUISITION'
    small = []
    for item in old['small_file_hashes']:
        path = ROOT / item['path']
        digest = sha256(path)
        assert digest == item['sha256'] and path.stat().st_size == item['bytes'], item['path']
        small.append({'path': item['path'], 'bytes': path.stat().st_size, 'sha256': digest})
    index = json.loads((model / 'model.safetensors.index.json').read_text(encoding='utf-8'))
    seen, payload, shards = set(), 0, []
    for shard in old['shards']:
        path = model / shard['file']
        with path.open('rb') as stream:
            length = struct.unpack('<Q', stream.read(8))[0]
            assert length < 1_000_000
            header = json.loads(stream.read(length))
        offset = 0
        for name, spec in sorted(((k, v) for k, v in header.items() if k != '__metadata__'), key=lambda x: x[1]['data_offsets'][0]):
            start, end = spec['data_offsets']
            assert spec['dtype'] == 'BF16' and start == offset
            assert end - start == 2 * math.prod(spec['shape'])
            assert index['weight_map'][name] == shard['file'] and name not in seen
            offset = end
            seen.add(name)
        assert offset + 8 + length == path.stat().st_size == shard['bytes']
        digest = sha256(path)
        assert digest == shard['upstream_lfs_sha256_not_locally_recomputed'], 'SHARD_HASH_MISMATCH'
        shards.append({'file': shard['file'], 'bytes': path.stat().st_size, 'sha256': digest, 'header_valid': True})
        payload += offset
    assert seen == set(index['weight_map']) and payload == index['metadata']['total_size']
    config = json.loads((model / 'config.json').read_text(encoding='utf-8'))
    assert config == old['config'] and config['model_type'] == 'qwen3'
    raw = []
    for item in acquisition['raw_artifacts']:
        p = ROOT / item['relative_local_path']
        digest = sha256(p)
        assert digest == item['sha256'] and p.stat().st_size == item['bytes'], 'RAW_DATASET_HASH_DRIFT'
        raw.append({'path': item['relative_local_path'], 'bytes': p.stat().st_size, 'sha256': digest})
    application = []
    for item in acquisition['application_protection']['protected_application_hashes']:
        if item['path'] == '.gitignore':
            continue  # Sole authorized initial snapshot exclusion change.
        path = ROOT / item['path']
        digest = sha256(path)
        assert digest == item['after']['sha256'], 'PROTECTED_APPLICATION_DRIFT: ' + item['path']
        application.append({'path': item['path'], 'sha256': digest})
    return {'at_utc': datetime.now(timezone.utc).isoformat(), 'model_inventory': inventory,
            'small_files': small, 'shards': shards, 'tensor_count': len(seen),
            'raw_artifacts': raw, 'protected_application': application,
            'acquisition_match': True, 'model_full_shard_hashes_match_pinned_upstream': True,
            'dataset_access': 'hash-only in separate integrity process; no decoding or model exposure'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--compare')
    args = parser.parse_args()
    result = snapshot()
    if args.compare:
        before = json.loads(Path(args.compare).read_text(encoding='utf-8'))
        assert {k: v for k, v in result.items() if k != 'at_utc'} == {k: v for k, v in before.items() if k != 'at_utc'}
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    print(json.dumps({'integrity': 'PASS', 'model_shards': len(result['shards']), 'raw_artifacts': len(result['raw_artifacts']), 'protected_files': len(result['protected_application'])}))
