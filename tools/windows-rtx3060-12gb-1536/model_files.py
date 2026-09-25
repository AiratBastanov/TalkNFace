"""Local model first: strict TAR inspection, staging, unchanged per-file pins."""
import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import time
import uuid
from common import HERE, MODEL, SCRATCH, read_json, write_json, reject_reparse
from state import OperationLock, campaign_status

TRANSPORT_SHA256 = '30fab06f571f6b7f0b62342045bd6b10c2d65de2eda8caebc32e7baf56cfd697'
MODEL_BUDGET = 1800


def check_time(deadline):
    if time.monotonic() >= deadline:
        raise TimeoutError('Fixed model transfer/verification budget exhausted; staging preserved')


def bounded_hash(path, deadline):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        while block := f.read(8 * 2**20):
            check_time(deadline); digest.update(block)
    return digest.hexdigest()


def verify_model(folder=None, lock=None, complete=True, deadline=None):
    folder = Path(folder) if folder is not None else MODEL
    lock = lock or read_json(HERE / 'model-lock.json')
    deadline = deadline or time.monotonic() + 180
    results, missing = {}, []
    if folder.is_symlink() or folder.is_junction(): raise ValueError('Model reparse point refused')
    for name, pin in lock['files'].items():
        assert '/' not in name and '\\' not in name and name not in ('.', '..')
        path = folder / name
        if path.is_symlink() or path.is_junction(): raise ValueError('Model file link refused')
        if not path.is_file(): missing.append(name); continue
        actual = {'bytes': path.stat().st_size, 'sha256': bounded_hash(path, deadline)}
        if actual != pin:
            raise ValueError('MODEL_INTEGRITY_FAIL: ' + name + '; existing model preserved, no overwrite')
        results[name] = actual
        print('Model hash verified: ' + name, flush=True)
    if complete and missing: raise FileNotFoundError('Missing pinned model files: ' + ', '.join(missing))
    if not missing:
        config = read_json(folder / 'config.json'); index = read_json(folder / 'model.safetensors.index.json')
        assert config['model_type'] == 'qwen3' and config['hidden_size'] == 2560 and config['num_hidden_layers'] == 36
        assert set(index['weight_map'].values()) == {f'model-{i:05d}-of-00003.safetensors' for i in range(1, 4)}
        assert index['metadata']['total_size'] == 8044936192
        for name in ('tokenizer.json', 'tokenizer_config.json', 'vocab.json'):
            assert isinstance(read_json(folder / name), dict)
    return {'passed': not missing, 'repo_id': lock['repo_id'], 'revision': lock['revision'], 'files': results, 'missing': missing}


def inspect_archive(archive, lock):
    """Inspect every header before extraction. No extractall() or link following."""
    members, seen, roots = [], set(), set()
    for count, entry in enumerate(archive):
        if count > 128: raise ValueError('Too many TAR entries')
        name = entry.name; parts = PurePosixPath(name).parts
        if (not name or '\\' in name or ':' in name or name.startswith('/') or '..' in parts
                or any(p.rstrip(' .') != p for p in parts) or re.search(r'[\x00-\x1f]', name)):
            raise ValueError('Unsafe TAR path: ' + repr(name))
        normalized = '/'.join(p for p in parts if p != '.')
        if normalized.casefold() in seen: raise ValueError('Duplicate TAR entry')
        seen.add(normalized.casefold())
        if not (entry.isdir() or entry.isreg()) or entry.issym() or entry.islnk() or entry.sparse:
            raise ValueError('TAR links/special/sparse entries refused')
        # Inspect, but never extract, official ancillary files and HF metadata.
        relative = normalized
        for prefix in ('AlagModels/Qwen3-4B/', 'Qwen3-4B/'):
            if relative.startswith(prefix): relative = relative[len(prefix):]; break
        if entry.isdir():
            if normalized not in ('', 'Qwen3-4B', 'AlagModels', 'AlagModels/Qwen3-4B') and relative not in (
                    '.cache', '.cache/huggingface', '.cache/huggingface/download'):
                raise ValueError('Unexpected TAR directory')
        else:
            if relative in ('README.md','LICENSE','.gitattributes','.cache/huggingface/.gitignore'):
                if entry.size > 256*1024: raise ValueError('Oversized ancillary file')
                with archive.extractfile(entry) as stream: text = stream.read()
                if b'\0' in text or text.startswith((b'MZ',b'\x7fELF')): raise ValueError('Executable/binary ancillary payload')
                text.decode('utf-8-sig')
                continue
            if relative.startswith('.cache/huggingface/download/'):
                metadata = relative.removeprefix('.cache/huggingface/download/')
                base, dot, suffix = metadata.rpartition('.')
                if dot and base in lock['files'] and suffix in ('lock','metadata') and entry.size <= 4096:
                    continue
                raise ValueError('Unexpected HF cache payload')
            prefix, _, leaf = normalized.rpartition('/')
            if prefix not in ('', 'Qwen3-4B', 'AlagModels/Qwen3-4B') or leaf not in lock['files']:
                raise ValueError('Unexpected TAR payload (only pinned model files accepted)')
            if entry.size != lock['files'][leaf]['bytes']: raise ValueError('TAR file size differs from model-lock')
            roots.add(prefix); members.append((entry, leaf))
    if len(roots) != 1 or len(members) != len(lock['files']) or {n for _, n in members} != set(lock['files']):
        raise ValueError('TAR must contain exactly one complete pinned model')
    return members


def import_archive(path, stage, lock, deadline, expected=TRANSPORT_SHA256):
    path, stage = Path(path), Path(stage)
    actual = bounded_hash(path, deadline)
    if expected and actual.lower() != expected.lower(): raise ValueError('TAR transport SHA256 mismatch; archive unchanged')
    with tarfile.open(path, mode='r:') as archive:
        members = inspect_archive(archive, lock)
        stage.mkdir(exist_ok=False)
        for entry, name in members:
            check_time(deadline)
            with archive.extractfile(entry) as src, (stage / name).open('xb') as dst:
                count = 0
                while block := src.read(8 * 2**20):
                    check_time(deadline); dst.write(block); count += len(block)
                if count != entry.size: raise ValueError('Truncated TAR payload')
            print(f'TAR extracted {name}: {count} bytes', flush=True)
    verified = verify_model(stage, lock, deadline=deadline)
    return dict(verified, transport_sha256=actual, transport_checksum_checked=bool(expected))


def transport_checksum(path, explicit=None):
    if explicit:
        if not re.fullmatch(r'[0-9a-fA-F]{64}', explicit): raise ValueError('Invalid transport SHA256')
        return explicit.lower()
    sidecar = Path(str(path)+'.sha256')
    if sidecar.exists():
        if sidecar.stat().st_size > 1024: raise ValueError('Oversized checksum sidecar')
        line = sidecar.read_text(encoding='ascii').strip()
        match = re.fullmatch(r'([0-9a-fA-F]{64})  (.+)',line)
        if not match or match[2] != Path(path).name: raise ValueError('Invalid transport checksum sidecar')
        return match[1].lower()
    return TRANSPORT_SHA256


def ensure_model(archive=None, allow_download=False, expected=None):
    reject_reparse(MODEL)
    assert campaign_status() in ('fresh', 'retryable_precondition'), 'Campaign consumed; model is read-only'
    deadline = time.monotonic() + MODEL_BUDGET
    lock = read_json(HERE / 'model-lock.json')
    if MODEL.exists():
        result = verify_model(deadline=deadline)  # Never repair an unknown/partial published directory.
        result.update(downloaded=False, reused=True)
        write_json(SCRATCH / 'model-verification.json', result)
        return result
    if not archive and not allow_download:
        raise FileNotFoundError('ACTION REQUIRED: supply -ModelArchive with the original Qwen3-4B TAR, or explicitly choose -AllowModelDownload')
    if shutil.disk_usage(HERE).free < sum(p['bytes'] for p in lock['files'].values()) + 5 * 2**30:
        raise RuntimeError('Insufficient disk for isolated model staging')
    imports = SCRATCH / 'model-staging'; imports.mkdir(parents=True, exist_ok=True)
    stage = imports / uuid.uuid4().hex
    write_json(SCRATCH / 'model-transfer.json', {'stage': str(stage), 'owner': 'RTX3060 model transfer',
               'deadline_seconds': MODEL_BUDGET, 'mode': 'archive' if archive else 'explicit_download'})
    if archive:
        result = import_archive(archive, stage, lock, deadline, transport_checksum(archive,expected))
    else:
        os.environ['HF_HUB_DISABLE_IMPLICIT_TOKEN'] = '1'
        os.environ['HF_HUB_DISABLE_TELEMETRY'] = '1'
        os.environ['HF_HUB_DOWNLOAD_TIMEOUT'] = '30'
        os.environ['HF_HUB_ETAG_TIMEOUT'] = '15'
        os.environ['HF_HUB_DISABLE_XET'] = '1'
        from huggingface_hub import snapshot_download
        # Explicit fallback, no outer retry loop or TLS override; outer watchdog
        # covers native transport too. Partial downloads stay in owned staging.
        snapshot_download(repo_id=lock['repo_id'], revision=lock['revision'], local_dir=stage,
                          allow_patterns=list(lock['files']), token=False, max_workers=2,
                          cache_dir=SCRATCH / 'hf-download-cache')
        result = verify_model(stage, lock, deadline=deadline)
    check_time(deadline)
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    assert not MODEL.exists(), 'Model appeared concurrently; staging preserved'
    stage.rename(MODEL)  # Same-volume Windows rename refuses an existing destination.
    result.update(downloaded=not bool(archive), reused=False)
    write_json(SCRATCH / 'model-verification.json', result)
    return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('phase', choices=['ensure', 'verify'])
    p.add_argument('--archive'); p.add_argument('--allow-download', action='store_true')
    p.add_argument('--transport-sha256'); a = p.parse_args()
    with OperationLock():
        if a.phase == 'verify': write_json(SCRATCH / 'model-verification.json', verify_model())
        else: ensure_model(a.archive, a.allow_download, a.transport_sha256)
