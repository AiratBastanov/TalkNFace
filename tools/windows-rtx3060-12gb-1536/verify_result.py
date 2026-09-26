"""Portable independent ZIP + training-evidence verifier. Stdlib only, offline."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile
from common import ROOT, HERE, read_json, sha256
from state import GATE
from verdict import PREFIX, decide, audit_ok
from policy import hardware_checks
from selection import validate_selection
from source_identity import source_identity


def unique_json(raw):
    def pairs(items):
        result = {}
        for k,v in items:
            if k in result: raise ValueError('Duplicate JSON key: ' + k)
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda v: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def inspect_zip(path):
    if Path(path).stat().st_size > 32*2**20: raise ValueError('Oversized result ZIP')
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)): raise ValueError('Duplicate ZIP entry')
        if set(names) != {'RESULT.txt','evidence.json','archive-manifest.json'}: raise ValueError('Unexpected/missing ZIP entries')
        for info in z.infolist():
            if info.file_size > 16*2**20 or info.flag_bits & 1 or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError('Unbounded/encrypted/linked ZIP entry')
        if z.testzip() is not None: raise ValueError('ZIP CRC failure')
        manifest = unique_json(z.read('archive-manifest.json'))
        if set(manifest) != set(names)-{'archive-manifest.json'}: raise ValueError('Manifest coverage mismatch')
        for name, pin in manifest.items():
            data = z.read(name)
            if set(pin) != {'bytes','sha256'} or pin != {'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}:
                raise ValueError('Manifest hash/size mismatch')
        evidence = unique_json(z.read('evidence.json'))
        from package_result import result_text
        if z.read('RESULT.txt').decode('utf-8') != result_text(evidence): raise ValueError('RESULT.txt contradicts evidence')
    return evidence, manifest


def verify_evidence(e, source_check=source_identity):
    required = {'schema_version','gate','fixture_only','outcome','selection','prepared','campaign','runtime',
                'campaign_reservation','worker_entry','model_load_entry',
                'wheel_provenance','cuda_backend','model_hash_verification','prepare_audit','tests','controls',
                'last_error_phase','full_training_started','REAL_APPLICATION_SMOKE','isolation_contract','excluded'}
    if e.get('schema_version') == 3: required.add('source_provenance')
    if set(e) != required or e['schema_version'] not in (2, 3) or e['gate'] != GATE:
        raise ValueError('Missing/unknown evidence schema or gate')
    from package_result import sanitize
    assert sanitize(e) == e, 'Unsanitized/private diagnostic payload'
    o = e['outcome']
    if o is None:
        return {'archive_integrity':'PASS','training_gate':'NOT_RUN_OR_INCOMPLETE','certified_training_pass':False,
                'failed_checks':['training evidence absent']}
    failed = []
    def check(name, fn):
        try:
            if fn() is not True: failed.append(name)
        except (KeyError, AssertionError, TypeError, ValueError, OSError, subprocess.SubprocessError): failed.append(name)
    check('full_training_not_started', lambda: e['full_training_started'] is False and o['full_training_started'] is False)
    check('campaign', lambda: e['campaign']['status'] == 'completed' and e['campaign']['model_load_started'] is True
          and e['campaign']['nonce'] == e['campaign_reservation']['nonce'] == e['worker_entry']['nonce']
          and e['campaign_reservation']['gate'] == GATE and e['campaign_reservation']['worker_may_start'] is True
          and e['model_load_entry']['started'] is True and e['model_load_entry']['pid'] == e['worker_entry']['pid'] == o['training']['worker_pid']
          and o['training_campaigns'] == 1 and o['evaluation_started'] is False and o['local_quality_evaluation'] is False)
    check('source_identity', lambda: source_check(e))
    check('selection_consistency', lambda: validate_selection(e['selection']) and e['selection'] == o['training']['selection'])
    check('model_lock', lambda: e['model_hash_verification']['passed'] is True
          and e['model_hash_verification']['repo_id'] == read_json(HERE/'model-lock.json')['repo_id']
          and e['model_hash_verification']['files'] == read_json(HERE/'model-lock.json')['files']
          and e['model_hash_verification']['revision'] == read_json(HERE/'model-lock.json')['revision']
          and o['integrity']['model']['files'] == e['model_hash_verification']['files'])
    check('runtime_lock', lambda: e['runtime']['passed'] is True and e['runtime']['python'] == read_json(HERE/'runtime-lock.json')['python']
          and e['runtime']['bits'] == 64 and e['runtime']['pip_check_returncode'] == 0
          and e['runtime']['mismatches'] == {} and e['runtime']['unexpected_packages'] == []
          and e['runtime']['versions'] == {__import__('re').sub(r'[-_.]+','-',k).lower():v for k,v in read_json(HERE/'runtime-lock.json')['packages'].items()})
    check('hardware_preflight', lambda: o['preflight']['passed'] is True and all(hardware_checks(o['preflight']['gpu']).values()))
    check('tiny_NF4', lambda: e['cuda_backend']['passed'] is True and e['cuda_backend']['Qwen_model_loaded'] is False
          and all(hardware_checks(e['cuda_backend']['gpu'], training=False).values())
          and all(e['cuda_backend']['nf4'][k] is True for k in ('executed_on_cuda','double_quant','finite_output'))
          and e['cuda_backend']['nf4']['compute_dtype'] == 'float16' and e['cuda_backend']['nf4']['backward'] is False)
    check('isolation', lambda: audit_ok(e['prepare_audit']) and audit_ok(e['tests']['audit']) and o['isolated'] is True)
    try:
        recomputed = decide(o['training'],o['monitor'],o['reload'],o['integrity']['passed'],e['tests']['passed'],o['isolated'],o['reload_monitor'])
        failed += ['training.'+k for k in recomputed['failed_checks']]
        if any(o[k] != recomputed[k] for k in ('verdict','checks','failed_checks','minimum_boundary_free_bytes')):
            failed.append('contradictory_reported_verdict')
    except (KeyError,TypeError,ValueError):
        failed.append('required_training_fields')
    check('no_application_change_claim', lambda: e['REAL_APPLICATION_SMOKE']['status'] == 'NOT_APPLICABLE_WITH_REASON')
    if e['fixture_only'] is not False: failed.append('fixture_is_not_hardware_evidence')
    certified = not failed and o['verdict'] in (PREFIX+'PASS', PREFIX+'PASS_TIGHT_MEMORY')
    return {'archive_integrity':'PASS', 'training_gate':o['verdict'] if certified else 'NOT_CERTIFIED',
            'certified_training_pass':certified,'failed_checks':failed}


def verify(path):
    e, _ = inspect_zip(path)
    return verify_evidence(e)


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('archive',type=Path); p.add_argument('--archive-only',action='store_true'); a=p.parse_args()
    if a.archive_only:
        inspect_zip(a.archive); result={'archive_integrity':'PASS','training_gate':'NOT_CHECKED','certified_training_pass':False}
    else: result=verify(a.archive)
    print(json.dumps(result,ensure_ascii=True,indent=2))
    raise SystemExit(0 if a.archive_only or result['certified_training_pass'] else 2)
