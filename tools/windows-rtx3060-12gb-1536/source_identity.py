"""Stdlib-only certification of the immutable, completed RTX3060 campaign.

No worker imports, model reads, dataset interpretation or evidence-file writes.
Git blobs are hashed as bytes; model identity uses the campaign's frozen pins.
The exact correction allowlist deliberately excludes every training entrypoint,
shared helper, model/data/config/lock, selection, monitor and verdict policy.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import urlsplit

from common import ROOT, sha256, reject_reparse

ORIGIN = 'https://github.com/AiratBastanov/TalkNFace.git'
TRAINING_COMMIT = '1c270adba77545720fa33bcee0e24f7d6f46e55d'
ORIGINAL_ZIP_SHA256 = '07d2abfc00d188a469b1a18e6bc370c7040aa0e7a22f091ffc553ecff68e2cbf'
ORIGINAL_EVIDENCE_SHA256 = 'e8a2314894204b10ddadc5372fea4d34887f66842c9a8cd8413e9269c8d12906'
# Independently verified from the immutable result plus the hash-pinned remote
# raw supplement. Both digests use campaign_payload(): no provenance, schema 2.
# Modern redaction is lossy; an archive cannot be projected back to raw input.
SANITIZED_EVIDENCE_SHA256 = 'd5ba0e4a5ab44d76b957abfa92e4795eb61ddee3594e37288dd6a712c737ecd7'
TOOL = 'tools/windows-rtx3060-12gb-1536/'
DECISION = 'docs/gates/evidence/LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION.json'
ALLOWED_CORRECTION_PATHS = frozenset(TOOL + name for name in (
    'package_result.py', 'verify_result.py', 'source_identity.py',
    'test_source_identity.py', 'test_workflow_result.py', 'run_owner_tests.py',
    'README.md', 'START_HERE_RU.md',
)) | frozenset((
    'docs/gates/RTX3060_SOURCE_IDENTITY_CERTIFICATION_CORRECTION.md',
    'docs/gates/evidence/RTX3060_SOURCE_IDENTITY_CERTIFICATION_CORRECTION.json',
))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def commit_id(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{40}', value) is not None,
            'Malformed source commit')
    return value


@dataclass(frozen=True)
class GitIdentity:
    commit: str
    origin: str
    clean: bool

    @classmethod
    def parse(cls, value):
        require(type(value) is dict and {'commit', 'origin', 'clean'} <= value.keys()
                and not value.keys() - {'commit', 'origin', 'clean', 'ignored_paths'},
                'Missing/malformed Git identity')
        commit_id(value['commit'])
        require(type(value['origin']) is str, 'Malformed origin')
        u = urlsplit(value['origin'])
        require(u.scheme == 'https' and u.netloc == 'github.com' and u.username is None
                and u.password is None and not u.query and not u.fragment
                and value['origin'] == ORIGIN, 'Unexpected or authenticated origin')
        require(value['clean'] is True, 'Source tree was not clean')
        return cls(value['commit'], value['origin'], value['clean'])


class Git:
    def __init__(self, root):
        self.root = Path(root)

    def raw(self, *args, input=None):
        return subprocess.check_output(
            ['git', '--no-replace-objects', '-C', str(self.root), *args], input=input,
            timeout=30, env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'))

    def text(self, *args):
        return self.raw(*args).decode('utf-8').rstrip('\r\n')

    def identity(self):
        require(self.text('branch', '--show-current') == 'main', 'Expected branch main')
        require(not self.raw('status', '--porcelain=v1', '--untracked-files=all'),
                'Certification checkout must be clean')
        value = {'commit': self.text('rev-parse', 'HEAD'),
                 'origin': self.text('remote', 'get-url', 'origin'), 'clean': True}
        GitIdentity.parse(value)
        require(self.text('remote', 'get-url', '--push', 'origin') == ORIGIN, 'Unexpected push origin')
        return value

    def tree(self, commit):
        commit_id(commit)
        tree = {}
        for entry in self.raw('ls-tree', '-rlz', commit).split(b'\0')[:-1]:
            meta, raw_name = entry.split(b'\t', 1)
            mode, kind, oid, size = meta.decode('ascii').split()
            name = raw_name.decode('utf-8')
            require(mode in ('100644', '100755') and kind == 'blob', 'Non-regular Git source')
            require(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                    and '\\' not in name and name not in tree, 'Unsafe Git path')
            tree[name] = {'mode': mode, 'object': oid, 'bytes': int(size)}
        require(tree and sum(v['bytes'] for v in tree.values()) <= 128 * 2**20,
                'Unbounded/empty source tree')
        return tree

    def blobs(self, tree):
        # One bounded Git operation, never one subprocess per file or model IO.
        raw = self.raw('cat-file', '--batch', input=''.join(
            v['object'] + '\n' for v in tree.values()).encode('ascii'))
        cursor = 0; result = {}
        for name, entry in tree.items():
            end = raw.index(b'\n', cursor)
            oid, kind, size = raw[cursor:end].decode('ascii').split()
            require(oid == entry['object'] and kind == 'blob' and int(size) == entry['bytes'],
                    'Git blob identity mismatch')
            cursor = end + 1
            result[name] = raw[cursor:cursor + int(size)]
            cursor += int(size)
            require(raw[cursor:cursor+1] == b'\n', 'Truncated Git blob')
            cursor += 1
        require(cursor == len(raw), 'Unexpected Git batch bytes')
        return result


def tooling_proof(git, training_commit, packaging_commit):
    """Check EVERY intermediate commit, rejecting even reverted training edits."""
    commit_id(training_commit); commit_id(packaging_commit)
    git.raw('merge-base', '--is-ancestor', training_commit, packaging_commit)
    base = git.tree(training_commit)
    commits = []
    previous = training_commit
    for commit in git.text('rev-list', '--reverse', training_commit + '..' + packaging_commit).splitlines():
        parents = git.text('rev-list', '--parents', '-n', '1', commit).split()
        require(parents == [commit, previous], 'Correction must be a linear descendant without merges')
        changed = git.raw('diff-tree', '--no-commit-id', '--name-only', '--no-renames', '-r', '-z',
                          previous, commit).decode('utf-8').split('\0')[:-1]
        require(set(changed) <= ALLOWED_CORRECTION_PATHS,
                'Load-bearing/non-allowlisted source changed in correction history')
        commits.append({'commit': commit, 'parent': previous, 'changed_paths': sorted(changed)})
        previous = commit
    current = git.tree(packaging_commit)
    protected = {k: v for k, v in base.items() if k not in ALLOWED_CORRECTION_PATHS}
    require(protected == {k: v for k, v in current.items() if k not in ALLOWED_CORRECTION_PATHS},
            'Protected source/config/data tree changed')
    return {'training_source_commit': training_commit, 'packaging_commit': packaging_commit,
            'training_tree_sha256': digest(base), 'protected_tree_sha256': digest(protected),
            'protected_paths': len(protected), 'load_bearing_changes': [],
            'allowed_correction_paths': sorted(ALLOWED_CORRECTION_PATHS), 'commits': commits}


def historical_snapshot(e, git):
    """Verify the full historical snapshot against historical Git, not HEAD."""
    o = e['outcome']; integrity = o['integrity']
    require(o['repository_commit'] == TRAINING_COMMIT, 'Unexpected training commit')
    require(integrity['passed'] is True and integrity['before'] == integrity['after'],
            'Contradictory before/after integrity')
    blobs = git.blobs(git.tree(TRAINING_COMMIT))
    model = json.loads(blobs[TOOL + 'model-lock.json'])
    expected = {name: pin(raw) for name, raw in blobs.items()}
    expected.update({'AlagModels/Qwen3-4B/' + name: value for name, value in model['files'].items()})
    require(integrity['before'] == expected, 'Historical source/model coverage or hash mismatch')
    require(integrity['model']['files'] == model['files'], 'Contradictory model pins')
    require(e['controls']['configuration'] == json.loads(blobs[TOOL + 'config.json']), 'Configuration mismatch')
    require(e['controls']['decision_sha256'] == pin(blobs[DECISION])['sha256'], 'Decision mismatch')
    require(e['prepared']['configuration_sha256'] == pin(blobs[TOOL + 'config.json'])['sha256'],
            'Prepared configuration mismatch')
    return expected


def campaign_payload(e):
    """Compare the campaign independently of packaging schema/provenance."""
    original = {k: v for k, v in e.items() if k != 'source_provenance'}
    original['schema_version'] = 2
    return original


def legacy_digest(e, root=ROOT):
    """Apply the frozen schema-2 sanitizer to raw records, never modern output."""
    from package_result import legacy_sanitize
    return digest(legacy_sanitize(campaign_payload(e), root))


def sanitized_digest(e, root=ROOT):
    from package_result import sanitize
    return digest(sanitize(campaign_payload(e), root))


def verify_checkout(git, commit):
    """Compare actual contents too, including files hidden by index flags.

    Git's explicit text=auto/eol=lf policy permits CRLF worktrees. Accept only
    that conversion for index-classified LF text, never arbitrary clean/smudge
    filters, binary normalization or normalization of the historical snapshot.
    """
    text_lf = set()
    for row in git.raw('ls-files', '--eol', '-z').split(b'\0')[:-1]:
        metadata, name = row.split(b'\t', 1)
        fields = metadata.decode('ascii').split()
        if fields[0] == 'i/lf' and fields[2:] == ['attr/text=auto', 'eol=lf']:
            text_lf.add(name.decode('utf-8'))
    normalized = []
    for name, expected in git.blobs(git.tree(commit)).items():
        path = git.root / name
        reject_reparse(path)
        max_size = len(expected) + (expected.count(b'\n') if name in text_lf else 0)
        require(len(expected) <= path.stat().st_size <= max_size, 'Checkout size mismatch: ' + name)
        actual = path.read_bytes()
        if actual == expected:
            continue
        require(name in text_lf and actual.replace(b'\r\n', b'\n') == expected,
                'Current checkout contents differ from Git: ' + name)
        normalized.append(name)
    return normalized


def collect_provenance(e, root=ROOT):
    """Bind raw records to both projections; bind published schema 3 directly.

    The modern campaign pin was derived/reviewed against real remote raw bytes
    and the original legacy pin, not inferred by reversing redacted URLs.
    """
    ready = GitIdentity.parse(e['prepared']['git'])
    after = GitIdentity.parse(e['outcome']['integrity']['git'])
    require(ready == after and ready.commit == e['outcome']['repository_commit'] == TRAINING_COMMIT,
            'Contradictory/historically wrong source identity')
    git = Git(root)
    current = git.identity()
    historical_snapshot(e, git)
    proof = tooling_proof(git, ready.commit, current['commit'])
    # status alone does not catch assume-unchanged/skip-worktree.
    verify_checkout(git, current['commit'])
    if e['schema_version'] == 2:
        require(legacy_digest(e, root) == ORIGINAL_EVIDENCE_SHA256,
                'Completed campaign differs from the immutable original result')
        require(sanitized_digest(e, root) == SANITIZED_EVIDENCE_SHA256,
                'Completed campaign differs from the verified sanitized result')
    else:
        require(e['schema_version'] == 3, 'Unexpected evidence schema')
        require(digest(campaign_payload(e)) == SANITIZED_EVIDENCE_SHA256,
                'Published campaign differs from the verified sanitized result')
    require(current == git.identity(), 'Git state changed during certification')
    return {'schema_version': 2, 'training_source_commit': ready.commit,
            'packaging_git': current, 'tooling_only_proof': proof,
            'original_result_zip_sha256': ORIGINAL_ZIP_SHA256,
            'original_evidence_sha256': ORIGINAL_EVIDENCE_SHA256,
            'sanitized_evidence_sha256': SANITIZED_EVIDENCE_SHA256,
            'gpu_campaign_rerun': False, 'full_training_started': False}


def source_identity(e, root=ROOT):
    proof = collect_provenance(e, root)
    if e['schema_version'] == 3:
        require(e['source_provenance'] == proof, 'Missing/contradictory certification provenance')
    else:
        require(e['schema_version'] == 2 and proof['packaging_git']['commit'] == TRAINING_COMMIT,
                'Historical schema cannot certify a later packaging commit')
    return True


def certify_packaging(e, scratch, output, root=ROOT):
    """Read original raw records and old ZIP. Never repair historical identity."""
    from package_result import ARCHIVE
    from verify_result import inspect_zip
    from common import read_json
    candidates = [Path(output) / ARCHIVE, Path(scratch) / 'packaged-history' / (ORIGINAL_ZIP_SHA256 + '.zip')]
    original = next((p for p in candidates if p.is_file() and sha256(p) == ORIGINAL_ZIP_SHA256), None)
    require(original is not None, 'Original result ZIP missing or SHA256 mismatch; preserve evidence')
    reject_reparse(original)
    old, _ = inspect_zip(original)
    require(digest(old) == ORIGINAL_EVIDENCE_SHA256 and legacy_digest(e, root) == digest(old),
            'Raw completed evidence contradicts the original result')
    # These pins were captured before phase 04, and are unchanged in the old ZIP.
    for name, expected in e['prepared']['files'].items():
        require(name in {'data-1536.json', 'frozen-controls.json', 'module-control.json',
                         'train-contexts.json', 'tests.json', 'prepare-1536-audit.json', 'integrity-before.json'},
                'Unknown prepared artifact')
        path = Path(scratch) / name
        reject_reparse(path)
        require(sha256(path) == expected, 'Prepared artifact changed: ' + name)
    before = read_json(Path(scratch) / 'integrity-before.json')
    require(GitIdentity.parse(before['git']) == GitIdentity.parse(e['prepared']['git']),
            'Raw pre-campaign Git identity contradicts preparation')
    require(before['files'] == e['outcome']['integrity']['before'], 'Raw integrity snapshot changed')
    return collect_provenance(e, root)
