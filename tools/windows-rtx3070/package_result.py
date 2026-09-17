"""Portable standard-library result ZIP; explicit metadata/log allowlist only."""
import json
import os
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from common import ROOT, SCRATCH, read_json, sha256

PREFIX = 'RTX3070_TARGETED_LORA_MEMORY_SMOKE_'
RESULTS = ROOT / 'handoff-results'
EXACT = {'outcome.json', 'package-integrity.json', 'wheel-provenance.json', 'cuda-backend.json',
         'preflight.json', 'model-verification.json', 'frozen-controls.json', 'tests.json',
         'train-1024.json', 'reload-1024.json', 'prepare-1024-audit.json', 'last-phase-error.json',
         'campaign-started.json', 'pip-version.txt', 'pip-freeze.txt', 'pip-check.txt'}
PATTERNS = [r'(prepare-data|cheap-checks|training-\d+|reload|resources-\d+)-monitor\.json',
            r'(prepare-data|cheap-checks|training-\d+|reload|resources-\d+)\.log',
            r'0[1-4]-(setup|cuda|model|prepare|campaign)-\d+T\d+\.(stdout|stderr)\.log',
            r'gpu-preload-blocked-\d+\.json']
FORBIDDEN_CONTENT_KEYS = {'prompt', 'completion', 'input_ids', 'labels', 'messages', 'expected', 'public_context'}
SECRET_KEYS = {'token', 'access_token', 'hf_token', 'authorization', 'password', 'secret', 'credentials'}


def allowed(name):
    return name in EXACT or any(re.fullmatch(p, name) for p in PATTERNS)


def scrub_text(text, root=ROOT):
    text = text.replace(str(root), '<repository>').replace(root.as_posix(), '<repository>')
    text = re.sub(r'(?i)[A-Z]:[\\/]Users[\\/][^\\/\s"\']+', '<user-profile>', text)
    text = re.sub(r'hf_[A-Za-z0-9]{12,}', '<redacted-token>', text)
    text = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/=-]+', r'\1<redacted>', text)
    text = re.sub(r'(https?://)[^/\s:@]+:[^/\s@]+@', r'\1<redacted>@', text)
    text = re.sub(r'(?i)([?&](?:token|access_token|signature|sig|key)=)[^&\s"\']+', r'\1<redacted>', text)
    text = re.sub(r'(https?://[^\s?"\']+)\?[^\s"\']+', r'\1?<redacted-query>', text)
    return text


def sanitize(value, root=ROOT):
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            if key.lower() in SECRET_KEYS: result[key] = '<redacted>'; continue
            if key in FORBIDDEN_CONTENT_KEYS and not (key == 'expected' and isinstance(item, str) and re.fullmatch(r'\d[\w.+-]*', item)):
                raise ValueError(f'Refusing to package example content field: {key}')
            result[key] = sanitize(item, root)
        return result
    if isinstance(value, list): return [sanitize(v, root) for v in value]
    if isinstance(value, str): return scrub_text(value, root)
    return value


def optional(scratch, name):
    path = scratch / name
    return read_json(path) if path.is_file() else {}


def evidence_for(scratch=SCRATCH):
    outcome = optional(scratch, 'outcome.json')
    last = optional(scratch, 'last-phase-error.json')
    model = optional(scratch, 'model-verification.json')
    runtime = optional(scratch, 'package-integrity.json')
    cuda = optional(scratch, 'cuda-backend.json')
    if not outcome:
        verdict = PREFIX + 'RUNTIME_BLOCKED'; reason = last.get('message', 'Workflow incomplete; no training result')
        if last.get('phase') == '04' and 'close GPU-heavy' in reason: verdict = PREFIX + 'GPU_ENVIRONMENT_BLOCKED'
        elif model and not model.get('passed') and ('MODEL_INTEGRITY_FAIL' in model.get('error', '') or model.get('error_type') == 'AssertionError'):
            verdict = PREFIX + 'MODEL_INTEGRITY_FAIL'
        outcome = {'verdict': verdict, 'reason': reason, 'training_campaigns': 0,
                   'next': 'Resolve the reported prerequisite; no automatic training or configuration retry'}
    elif outcome.get('training_campaigns', 0) == 0 and last.get('time_utc'):
        error_time = datetime.fromisoformat(last['time_utc'].replace('Z', '+00:00')).timestamp()
        if error_time > outcome.get('completed_at_unix', 0) and last.get('phase') == '04' and 'close GPU-heavy' in last.get('message', ''):
            outcome = dict(outcome, verdict=PREFIX+'GPU_ENVIRONMENT_BLOCKED', reason=last['message'])
    read_paths = set()
    records = [optional(scratch, 'prepare-1024-audit.json'), optional(scratch, 'tests.json'),
               outcome.get('training', {}), outcome.get('reload', {})]
    for record in records:
        audit = record.get('audit', record)
        read_paths.update(audit.get('evaluation_file_reads', []))
    exposures = {name: int(path in read_paths) for name, path in {
        'DEV': 'ml/data/synthetic_ru/dev.jsonl', 'INTERNAL_TEST': 'ml/data/synthetic_ru/internal_test.jsonl',
        'tuning_eval': 'evals/local-qwen/dev-ru-v1.json', 'A01_A16': 'evals/local-qwen/a01-a16.json'}.items()}
    return {'schema_version': 1, 'generated_utc': datetime.now(timezone.utc).isoformat(), **outcome,
            'runtime': runtime, 'cuda_backend': cuda, 'model_hash_verification': model,
            'selection': optional(scratch, 'frozen-controls.json'),
            'isolation': {'gradient_source': 'TRAIN only', **exposures,
                          'evidence_basis': 'Worker allowlist/audit records; protected eval files byte-hashed only by separate supervisor'},
            'excluded': ['model weights', 'adapter weights', 'corpus rows', 'evaluation data', 'raw datasets', 'credentials', 'HF caches'],
            'REAL_APPLICATION_SMOKE': {'status': 'NOT_APPLICABLE_WITH_REASON', 'reason': 'Remote R&D infrastructure only; no application behavior change'},
            'full_training_started': False}


def result_text(e):
    training = e.get('training', {}); monitor = e.get('monitor', {}); gpu = e.get('preflight', {}).get('gpu', {}) or e.get('cuda_backend', {}).get('gpu', {})
    steps = training.get('steps', []); after = training.get('after_training', {})
    def mib(value): return f'{value / 2**20:.3f} MiB' if isinstance(value, (int, float)) else 'NOT MEASURED'
    boundaries = [mib(s.get('memory', {}).get('free_bytes')) for s in steps]
    versions = e.get('runtime', {}).get('versions', {})
    runtime = 'Python ' + e.get('runtime', {}).get('python', 'NOT MEASURED') + '; ' + '; '.join(
        f'{name} {versions.get(name, "NOT MEASURED")}' for name in ('torch', 'transformers', 'bitsandbytes', 'peft', 'trl'))
    before_hash = 'PASS' if e.get('model_hash_verification', {}).get('passed') else 'NOT VERIFIED'
    after_hash = 'PASS' if e.get('integrity', {}).get('passed') and e.get('integrity', {}).get('model', {}).get('passed') else 'NOT VERIFIED'
    model_status = 'before=' + before_hash + '; after=' + (after_hash if e.get('training_campaigns', 0) else 'NOT RUN')
    lines = [f'VERDICT: {e["verdict"]}', f'GPU: {gpu.get("name", "NOT MEASURED")}',
             f'VRAM: physical {gpu.get("physical_MiB", "NOT MEASURED")} MiB; CUDA {mib(gpu.get("cuda_capacity_bytes"))}',
             f'CUDA: {gpu.get("cuda_runtime", "NOT MEASURED")}',
             'RUNTIME: ' + runtime,
             'MODEL HASH STATUS: ' + model_status,
             f'TRAINABLE PARAMETERS: {training.get("trainable_parameters", "2949120 expected; not trained")}',
             f'OPTIMIZER UPDATES: {training.get("actual_optimizer_steps", 0)}',
             'LOSSES: ' + json.dumps([s.get('loss') for s in steps]),
             'PEAK ALLOCATED: ' + mib(after.get('peak_allocated_bytes')),
             'PEAK RESERVED (not physical residency): ' + mib(after.get('peak_reserved_bytes')),
             'BOUNDARY FREE 1: ' + (boundaries[0] if len(boundaries) > 0 else 'NOT MEASURED'),
             'BOUNDARY FREE 2: ' + (boundaries[1] if len(boundaries) > 1 else 'NOT MEASURED'),
             'MIN HOST RAM: ' + mib(monitor.get('host_min_available_bytes')),
             'PAGEFILE DELTA: ' + mib(monitor.get('pagefile_peak_delta_bytes')),
             f'ADAPTER CHANGED: {training.get("adapter_change", {}).get("changed_tensors", "NOT RUN")}',
             f'SAVE/RELOAD: save={bool(training.get("adapter"))}; reload={e.get("reload", {}).get("passed", False)}',
             f'NEXT: {e.get("next", "Return result to the project owner; do not start another campaign")}',
             'LIMITATION: configured 1024; selected max 974, optimizer max 962. The 1421/1536 envelope is NOT proven.',
             'STOP - FULL QLORA TRAINING NOT STARTED.']
    if e.get('reason'): lines.insert(1, 'REASON: ' + e['reason'])
    return '\n'.join(lines) + '\n'


def process_active(pid):
    """Read-only Windows liveness check; permits packaging after a watchdog exit."""
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ctypes.get_last_error() != 87  # invalid PID = exited; uncertainty stays closed
    try:
        code = wintypes.DWORD()
        return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
    finally:
        kernel.CloseHandle(handle)


def package(scratch=SCRATCH, output=RESULTS, root=ROOT):
    marker = scratch / 'supervisor-active.json'
    if marker.exists() and process_active(read_json(marker)['pid']):
        raise RuntimeError('Supervisor is still active. Wait for script 04 to exit before packaging.')
    output.mkdir(parents=True, exist_ok=True)
    archive = output / 'RTX3070_TARGETED_LORA_SMOKE_RESULT.zip'
    if archive.exists(): raise FileExistsError('Keep the existing ZIP; rename it before packaging again')
    evidence = sanitize(evidence_for(scratch), root)
    if marker.exists():
        evidence['interrupted_supervisor'] = True
        evidence['verdict'] = PREFIX + 'FAIL'
        evidence['reason'] = 'Supervisor exited without finalizing; inspect logs. No retry authorized.'
    payload = {'RESULT.txt': scrub_text(result_text(evidence), root).encode('utf-8'),
               'evidence.json': (json.dumps(evidence, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')}
    for path in sorted(scratch.iterdir()) if scratch.exists() else []:
        if not path.is_file() or path.is_symlink() or not allowed(path.name): continue
        if path.stat().st_size > 16 * 2**20: raise ValueError('Unexpectedly large diagnostic file: ' + path.name)
        if path.suffix == '.json':
            contents = json.dumps(sanitize(read_json(path), root), ensure_ascii=False, indent=2, allow_nan=False)
        else:
            contents = scrub_text(path.read_text(encoding='utf-8', errors='replace'), root)
        payload['diagnostics/' + path.name] = contents.encode('utf-8')
    import hashlib
    manifest = {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for name, data in payload.items()}
    payload['archive-manifest.json'] = json.dumps(manifest, indent=2).encode('utf-8')
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as zipfile_out:
        for name, data in payload.items(): zipfile_out.writestr(name, data)
    with zipfile.ZipFile(archive) as checked:
        assert checked.testzip() is None
        assert set(checked.namelist()) == set(payload)
    print(str(archive)); print('SHA256: ' + sha256(archive))
    return archive


if __name__ == '__main__':
    package()
