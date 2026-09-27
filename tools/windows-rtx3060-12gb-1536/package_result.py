"""Bounded diagnostics projection; no raw logs, rows, tokens, or weight payloads."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import zipfile
from urllib.parse import urlsplit
from common import HERE, ROOT, SCRATCH, read_json, sha256, reject_reparse
from state import GATE, OperationLock, process_active

ARCHIVE = 'RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip'
RESULTS = ROOT / 'handoff-results'
PRIVATE_KEYS = {'prompt','completion','input_ids','labels','messages','public_context','json','rows','reload_row'}
SECRET_KEYS = {'token','access_token','refresh_token','hf_token','api_key','client_secret',
               'authorization','password','secret','credentials','cookie'}
OMIT_KEYS = {'error','message','pip_check','pip_check_stderr'}  # arbitrary exception/log text is not portable evidence


URL = re.compile(r'(?i)\b[a-z][a-z0-9+.-]*://[^\s<>\"\']+')
TOKEN = re.compile(r'\b(?:hf_[A-Za-z0-9]+|gh[pousr]_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)')


def scrub_text(text, root=ROOT):
    # Parse URL spans before filesystem paths. Never expose userinfo, query or
    # fragment payloads, including username-only credentials and non-HTTP URLs.
    def url(value):
        try:
            parsed = urlsplit(value)
            if (parsed.scheme.lower() not in ('https', 'http') or not parsed.hostname
                    or not parsed.netloc.isascii() or any(c in parsed.netloc for c in '@%\\')
                    or parsed.query or parsed.fragment or TOKEN.search(value)):
                return '<redacted-url>'
            parsed.port  # Reject malformed ports too.
            return value
        except ValueError:
            return '<redacted-url>'

    def paths(value):
        value = value.replace(str(root), '<repository>').replace(root.as_posix(), '<repository>')
        # Boundary prevents matching the trailing letter of a scheme. UNC,
        # drive, home and absolute POSIX paths remain private (spaces included).
        return re.sub(r'(?<![\w:/\\])(?:[a-zA-Z]:[\\/]|\\\\|//|/|~[\\/])[^\r\n\"\'<>]*',
                      '<local-path>', value)

    pieces = []; cursor = 0
    for match in URL.finditer(text):
        pieces.extend((paths(text[cursor:match.start()]), url(match.group())))
        cursor = match.end()
    pieces.append(paths(text[cursor:]))
    text = ''.join(pieces)
    text = TOKEN.sub('<redacted-token>', text)
    text = re.sub(r'(?i)Bearer\s+(?!<redacted>)\S+', 'Bearer <redacted>', text)
    text = re.sub(r'(?i)\b(token|access_token|api_key|password|secret|authorization)\s*[:=]\s*(?!<redacted>)[^\s,;<>]+',
                  r'\1=<redacted>', text)
    return text


def legacy_scrub_text(text, root=ROOT):
    """Original lossy projection, ONLY for binding to the immutable old receipt.

    This intentionally reproduces the defect; never use it for new payloads or
    to infer/repair an origin. Actual Git identity is validated separately.
    """
    text = text.replace(str(root), '<repository>').replace(root.as_posix(), '<repository>')
    text = re.sub(r'(?i)[a-z]:[\\/][^\r\n\"\']*', '<local-path>', text)
    text = re.sub(r'hf_[A-Za-z0-9]+', '<redacted-token>', text)
    text = re.sub(r'(?i)Bearer\s+\S+', 'Bearer <redacted>', text)
    text = re.sub(r'(https?://)[^/\s:@]+:[^/\s@]+@', r'\1<redacted>@', text)
    text = re.sub(r'(https?://[^\s?\"\']+)\?[^\s\"\']+', r'\1?<redacted-query>', text)
    return text


# Frozen schema-2 traversal from training commit 1c270adba77545720fa33bcee0e24f7d6f46e55d.
# Keep these independent of modern privacy policy. Never emit this projection.
LEGACY_PRIVATE_KEYS = {'prompt','completion','input_ids','labels','messages','public_context','json','rows','reload_row'}
LEGACY_SECRET_KEYS = {'token','access_token','hf_token','authorization','password','secret','credentials'}
LEGACY_OMIT_KEYS = {'error','message','pip_check','pip_check_stderr'}


def legacy_sanitize(value, root=ROOT):
    """Exact historical traversal and scrub order, for immutable digest binding only."""
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in LEGACY_SECRET_KEYS: result[key] = '<redacted>'; continue
            if key in LEGACY_PRIVATE_KEYS: raise ValueError('Example content cannot enter a result: ' + key)
            if key in LEGACY_OMIT_KEYS: continue
            result[key] = legacy_sanitize(item, root)
        return result
    if isinstance(value, list): return [legacy_sanitize(v, root) for v in value]
    if isinstance(value, str): return legacy_scrub_text(value, root)
    return value


def sanitize(value, root=ROOT, *, scrubber=scrub_text):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in SECRET_KEYS: result[key] = '<redacted>'; continue
            if key in PRIVATE_KEYS: raise ValueError('Example content cannot enter a result: ' + key)
            if key in OMIT_KEYS: continue
            result[key] = sanitize(item, root, scrubber=scrubber)
        return result
    if isinstance(value, list): return [sanitize(v, root, scrubber=scrubber) for v in value]
    if isinstance(value, str): return scrubber(value, root)
    return value


def optional(scratch, name):
    path = scratch / name
    if not path.exists(): return None
    if path.is_symlink() or path.stat().st_size > 16*2**20: raise ValueError('Unbounded or linked diagnostic')
    return read_json(path)


def evidence_for(scratch=SCRATCH):
    outcome = optional(scratch, 'outcome.json')
    data = optional(scratch, 'data-1536.json')
    ready = optional(scratch, 'prepared-ready.json')
    error = optional(scratch, 'last-phase-error.json')
    return {'schema_version': 2, 'gate': GATE, 'fixture_only': False,
            'outcome': outcome, 'selection': data['selection'] if data else None,
            'prepared': ready, 'campaign': optional(scratch, 'campaign-ledger.json'),
            'campaign_reservation': optional(scratch, 'campaign-started.json'),
            'worker_entry': optional(scratch, 'worker-started.json'), 'model_load_entry': optional(scratch, 'model-load-started.json'),
            'runtime': optional(scratch, 'package-integrity.json'),
            'wheel_provenance': optional(scratch, 'wheel-provenance.json'),
            'cuda_backend': optional(scratch, 'cuda-backend.json'),
            'model_hash_verification': optional(scratch, 'model-verification.json'),
            'prepare_audit': optional(scratch, 'prepare-1536-audit.json'),
            'tests': optional(scratch, 'tests.json'), 'controls': optional(scratch, 'frozen-controls.json'),
            'last_error_phase': error['phase'] if error else None,
            'full_training_started': outcome['full_training_started'] if outcome else None,
            'REAL_APPLICATION_SMOKE': {'status':'NOT_APPLICABLE_WITH_REASON',
                'explanation':'Isolated training/handoff infrastructure; no application behavior changed'},
            'isolation_contract':'TRAIN only; Python audit hooks, not an OS sandbox. Supervisor hashes source/model/data bytes.',
            'excluded':['raw logs','model/adapter weights','dataset rows','prompts','token arrays','credentials','caches']}


def result_text(e):
    o = e['outcome']
    verdict = o['verdict'] if o else 'NOT_RUN_OR_INCOMPLETE'
    return ('REPORTED TRAINING VERDICT: ' + verdict + '\n'
            'Archive integrity and training acceptance are checked separately by verify_result.py.\n'
            'Configured maximum: 1536. Frozen observed TRAIN maximum: 1421 (not a 1536-token execution).\n'
            'Full training is not authorized by this handoff.\n')


def assert_workers_exited(scratch):
    paths = list(scratch.glob('*-worker.json'))
    marker = scratch / 'campaign-started.json'
    if marker.exists():
        if process_active(read_json(marker)['supervisor_pid']): raise RuntimeError('Campaign supervisor still active')
    for path in paths:
        if process_active(read_json(path)['pid']): raise RuntimeError('Recorded worker is still active or cannot be inspected')


def package(scratch=SCRATCH, output=RESULTS, root=ROOT):
    scratch, output = Path(scratch), Path(output)
    reject_reparse(output); reject_reparse(scratch)
    assert_workers_exited(scratch)
    raw = evidence_for(scratch)
    provenance = None
    if raw['campaign'] and raw['campaign'].get('status') == 'completed':
        from source_identity import certify_packaging
        # Certification binds the historical campaign diagnostic separately
        # from a later phase-05 failure, without changing any scratch record.
        raw, provenance = certify_packaging(raw, scratch, output, root)
    e = sanitize(raw, root)
    if provenance is not None:
        e.update(schema_version=3, source_provenance=provenance)
    payload = {'RESULT.txt': result_text(e).encode('utf-8'),
               'evidence.json': (json.dumps(e, ensure_ascii=True, indent=2, allow_nan=False)+'\n').encode('utf-8')}
    if any(len(data)>16*2**20 for data in payload.values()): raise ValueError('Diagnostic size limit exceeded')
    manifest = {n:{'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest()} for n,b in payload.items()}
    payload['archive-manifest.json'] = json.dumps(manifest, sort_keys=True, indent=2).encode('utf-8')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ARCHIVE
    from verify_result import inspect_zip
    if archive.exists():
        existing, _ = inspect_zip(archive)
        if existing == e:
            print('Existing identical result reused: ' + str(archive), flush=True)
            print('SHA256: ' + sha256(archive), flush=True)
            return archive
        history = scratch / 'packaged-history'; history.mkdir(parents=True, exist_ok=True)
        backup = history / (sha256(archive) + '.zip')
        reject_reparse(backup)
        if not backup.exists(): shutil.copy2(archive, backup)
        assert sha256(backup) == sha256(archive), 'Result backup verification failed'
        print('PRESERVED previous result: ' + str(backup) + '; SHA256: ' + sha256(backup), flush=True)
    temporary = scratch / ('result-' + __import__('uuid').uuid4().hex + '.zip')
    with zipfile.ZipFile(temporary, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for n,b in payload.items(): z.writestr(n,b)
    inspect_zip(temporary)
    temporary.replace(archive)
    print('RESULT: ' + str(archive), flush=True)
    print('SHA256: ' + sha256(archive), flush=True)
    return archive


def main():
    from verify_result import verify
    with OperationLock():
        archive = package()
        result = verify(archive)
        print(json.dumps(result, ensure_ascii=True, indent=2), flush=True)
    return 0 if result['certified_training_pass'] else 2


if __name__ == '__main__':
    raise SystemExit(main())
