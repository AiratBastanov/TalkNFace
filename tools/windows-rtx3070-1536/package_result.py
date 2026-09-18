"""Portable 1536 result ZIP; explicit text/JSON allowlist only, no model/data/adapter bytes."""
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from common import ROOT, SCRATCH, read_json, sha256

PREFIX = 'RTX3070_TARGETED_LORA_1536_ENVELOPE_SMOKE_'
RESULTS = ROOT / 'handoff-results'
EXACT = {'outcome.json', 'package-integrity.json', 'wheel-provenance.json', 'cuda-backend.json',
         'preflight.json', 'model-verification.json', 'frozen-controls.json', 'tests.json',
         'train-1536.json', 'reload-1536.json', 'prepare-1536-audit.json', 'last-phase-error.json',
         'campaign-started.json', 'baseline-1024-prerequisite.json', 'prepared-ready.json',
         'pip-version.txt', 'pip-freeze.txt', 'pip-check.txt'}
PATTERNS = [r'(prepare-data|cheap-checks|training-\d+|reload|resources-\d+|cuda-backend)-monitor\.json',
            r'(prepare-data|cheap-checks|training-\d+|reload|resources-\d+|cuda-backend)\.log',
            r'0[0-5]-(preflight|prepare|campaign|package)-\d+T\d+\.(stdout|stderr)\.log',
            r'gpu-preload-blocked-\d+\.json']
FORBIDDEN_CONTENT_KEYS = {'prompt', 'completion', 'input_ids', 'labels', 'messages', 'expected', 'public_context', 'json'}
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
            if key in FORBIDDEN_CONTENT_KEYS:
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
    outcome = optional(scratch, 'outcome.json'); last = optional(scratch, 'last-phase-error.json')
    if not outcome:
        outcome = {'verdict': PREFIX + 'RUNTIME_BLOCKED', 'reason': last.get('message', 'Workflow incomplete'),
                   'training_campaigns': 0, 'next': 'Resolve prerequisite; no training retry was consumed'}
    data = optional(scratch, 'data-1536.json'); selection = data.get('selection', {})
    records = [optional(scratch, 'prepare-1536-audit.json'), optional(scratch, 'tests.json'),
               outcome.get('training', {}), outcome.get('reload', {})]
    read_paths = set()
    for record in records:
        audit = record.get('audit', record); read_paths.update(audit.get('evaluation_file_reads', []))
    exposures = {name: int(path in read_paths) for name, path in {
        'DEV': 'ml/data/synthetic_ru/dev.jsonl', 'INTERNAL_TEST': 'ml/data/synthetic_ru/internal_test.jsonl',
        'tuning_eval': 'evals/local-qwen/dev-ru-v1.json', 'A01_A16': 'evals/local-qwen/a01-a16.json'}.items()}
    return {'schema_version': 1, 'generated_utc': datetime.now(timezone.utc).isoformat(), **outcome,
            'runtime': optional(scratch, 'package-integrity.json'), 'cuda_backend': optional(scratch, 'cuda-backend.json'),
            'model_hash_verification': optional(scratch, 'model-verification.json'),
            'baseline_1024': optional(scratch, 'baseline-1024-prerequisite.json'), 'selection': selection,
            'isolation': {'gradient_source': 'TRAIN only', **exposures,
                          'evidence_basis': 'Worker audit records; protected eval files are byte-hashed only by the separate supervisor'},
            'excluded': ['model weights', 'adapter weights', 'corpus rows', 'evaluation data', 'raw datasets', 'credentials', 'HF caches'],
            'REAL_APPLICATION_SMOKE': {'status': 'NOT_APPLICABLE_WITH_REASON', 'reason': 'Remote R&D infrastructure only; no application behavior change'},
            'full_training_started': outcome.get('full_training_started', False)}


def result_text(e):
    training=e.get('training',{}); monitor=e.get('monitor',{}); steps=training.get('steps',[]); after=training.get('after_training',{})
    selection=e.get('selection',{}); free=[s.get('memory',{}).get('free_bytes') for s in steps]
    def mib(v): return f'{v/2**20:.3f} MiB' if isinstance(v,(int,float)) else 'NOT MEASURED'
    lines=[f'VERDICT: {e["verdict"]}',
           f'CONFIGURED ENVELOPE: {selection.get("configured_max_length","NOT MEASURED")}',
           f'FULL TRAIN ROWS MEASURED: {selection.get("source_rows_measured","NOT MEASURED")}',
           f'OBSERVED TRAIN MAX: {selection.get("observed_max_length","NOT MEASURED")}',
           f'ROWS ABOVE 1536: {selection.get("rows_above_limit","NOT MEASURED")}',
           f'TRUNCATED ROWS: {selection.get("truncated_rows","NOT MEASURED")}',
           f'OPTIMIZER UPDATES: {training.get("actual_optimizer_steps",0)}',
           'LOSSES: '+json.dumps([s.get('loss') for s in steps]),
           'PEAK ALLOCATED: '+mib(after.get('peak_allocated_bytes')),
           'PEAK RESERVED: '+mib(after.get('peak_reserved_bytes')),
           'BOUNDARY FREE 1: '+(mib(free[0]) if len(free)>0 else 'NOT MEASURED'),
           'BOUNDARY FREE 2: '+(mib(free[1]) if len(free)>1 else 'NOT MEASURED'),
           'MIN HOST RAM: '+mib(monitor.get('host_min_available_bytes')),
           'PAGEFILE DELTA: '+mib(monitor.get('pagefile_peak_delta_bytes')),
           f'ADAPTER CHANGED: {training.get("adapter_change",{}).get("changed_tensors","NOT RUN")}',
           f'SAVE/RELOAD: save={bool(training.get("adapter"))}; reload={e.get("reload",{}).get("passed",False)}',
           f'FULL TRAINING PREPARATION AUTHORIZED: {e.get("full_training_preparation_authorized",False)}',
           f'NEXT: {e.get("next","Return result to project owner")}',
           'STOP - FULL QLORA TRAINING NOT STARTED.']
    if e.get('reason'): lines.insert(1,'REASON: '+e['reason'])
    return '\n'.join(lines)+'\n'


def process_active(pid):
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.GetExitCodeProcess.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        return ctypes.get_last_error() != 87
    try:
        code = wintypes.DWORD()
        return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
    finally:
        kernel.CloseHandle(handle)


def package(scratch=SCRATCH, output=RESULTS, root=ROOT):
    marker=scratch/'supervisor-active.json'
    if marker.exists() and process_active(read_json(marker)['pid']):
        raise RuntimeError('Supervisor is still active. Wait for script 04 to exit before packaging.')
    output.mkdir(parents=True,exist_ok=True)
    archive=output/'RTX3070_TARGETED_LORA_1536_ENVELOPE_RESULT.zip'
    if archive.exists(): raise FileExistsError('Keep the existing 1536 ZIP; never overwrite evidence')
    evidence=sanitize(evidence_for(scratch),root)
    payload={'RESULT.txt':scrub_text(result_text(evidence),root).encode('utf-8'),
             'evidence.json':(json.dumps(evidence,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode('utf-8')}
    for path in sorted(scratch.iterdir()) if scratch.exists() else []:
        if not path.is_file() or path.is_symlink() or not allowed(path.name): continue
        if path.stat().st_size>16*2**20: raise ValueError('Unexpectedly large diagnostic file: '+path.name)
        if path.suffix=='.json':
            value=read_json(path)
            # Training/data JSONs contain raw examples; package only a sanitized metadata projection.
            if path.name=='train-1536.json':
                value={k:v for k,v in value.items() if k not in ('microbatches',)}
                if 'selection' in value: value['selection']=value['selection']
            if path.name=='reload-1536.json': value={k:v for k,v in value.items() if k not in ('audit',)} | {'audit': value.get('audit',{})}
            contents=json.dumps(sanitize(value,root),ensure_ascii=False,indent=2,allow_nan=False)
        else:
            contents=scrub_text(path.read_text(encoding='utf-8',errors='replace'),root)
        payload['diagnostics/'+path.name]=contents.encode('utf-8')
    import hashlib
    manifest={name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in payload.items()}
    payload['archive-manifest.json']=json.dumps(manifest,indent=2).encode('utf-8')
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for name,data in payload.items(): z.writestr(name,data)
    with zipfile.ZipFile(archive) as checked:
        assert checked.testzip() is None and set(checked.namelist())==set(payload)
    print(str(archive)); print('SHA256: '+sha256(archive)); return archive


if __name__=='__main__': package()
