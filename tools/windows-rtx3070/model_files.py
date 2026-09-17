"""Official public snapshot download; immutable file pins and safe resume."""
import argparse
import json
import shutil
import traceback
from common import HERE, MODEL, SCRATCH, read_json, write_json, sha256


def verify_model(folder=MODEL, lock=None, complete=True):
    lock = lock or read_json(HERE / 'model-lock.json')
    results = {}; missing = []
    for name, pin in lock['files'].items():
        assert '/' not in name and '\\' not in name and name not in ('.', '..'), 'Unsafe model-lock filename'
        path = folder / name
        if not path.is_file():
            missing.append(name); continue
        actual = {'bytes': path.stat().st_size, 'sha256': sha256(path)}
        if actual != pin:
            raise ValueError(f'MODEL_INTEGRITY_FAIL: {name} differs from the pinned original. Refusing overwrite/redownload. Contact the project owner.')
        results[name] = actual
    if complete and missing:
        raise FileNotFoundError('Missing pinned model files: ' + ', '.join(missing))
    if not missing:
        config = read_json(folder / 'config.json'); index = read_json(folder / 'model.safetensors.index.json')
        assert config['model_type'] == 'qwen3' and config['hidden_size'] == 2560 and config['num_hidden_layers'] == 36
        expected = {f'model-{i:05d}-of-00003.safetensors' for i in range(1, 4)}
        assert set(index['weight_map'].values()) == expected, 'Index must reference exactly the three pinned shards'
        assert index['metadata']['total_size'] == 8044936192
        for name in ('tokenizer.json', 'tokenizer_config.json', 'vocab.json'):
            assert isinstance(read_json(folder / name), dict)
    return {'passed': not missing, 'repo_id': lock['repo_id'], 'revision': lock['revision'], 'files': results, 'missing': missing}


def download():
    from environment import capture
    assert read_json(SCRATCH / 'cuda-backend.json')['passed'], 'Run script 01 successfully first'
    capture()
    lock = read_json(HERE / 'model-lock.json')
    result = verify_model(complete=False)
    if result['passed']:
        result['downloaded'] = False
        write_json(SCRATCH / 'model-verification.json', result)
        print('Existing model matches every pinned byte; no download.'); return
    import psutil
    assert psutil.virtual_memory().available >= 12 * 2**30, 'Need >=12 GiB available RAM'
    assert shutil.disk_usage(MODEL.parent if MODEL.parent.exists() else HERE).free >= 30 * 2**30, 'Need >=30 GiB free before model download'
    from huggingface_hub import snapshot_download
    # Public repo, immutable revision, no token or user credentials; allowlist excludes alternate formats.
    snapshot_download(repo_id=lock['repo_id'], revision=lock['revision'], local_dir=MODEL,
                      allow_patterns=list(lock['files']), token=False, max_workers=2,
                      cache_dir=SCRATCH / 'hf-download-cache')
    result = verify_model(); result['downloaded'] = True
    write_json(SCRATCH / 'model-verification.json', result)
    print('All three original shards, config, tokenizer files and index verified.')


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('phase', choices=['download', 'verify']); a = p.parse_args()
    try:
        if a.phase == 'download': download()
        else: write_json(SCRATCH / 'model-verification.json', verify_model())
    except Exception as error:
        write_json(SCRATCH / 'model-verification.json', {'passed': False, 'error_type': type(error).__name__, 'error': traceback.format_exc()})
        raise
