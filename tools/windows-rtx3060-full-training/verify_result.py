"""Stdlib archive and training-completion verifier. Never a quality certificate."""
import argparse
import hashlib
import json
import math
import re
import struct
import zipfile
from full_common import (GATE, HERE, LEGACY, ROOT, ORIGIN, config, digest, read, require)


def exact(obj, names):
    require(isinstance(obj, dict) and set(obj) == set(names.split()), 'Unknown/missing evidence fields')


def hash_value(value, width=64):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{' + str(width) + '}', value) is not None, 'Invalid digest')


def file_pin(value):
    exact(value, 'bytes sha256')
    require(type(value['bytes']) is int and value['bytes'] >= 0, 'Invalid size')
    hash_value(value['sha256'])


def packaging(value):
    exact(value, 'kind version commit clean files')
    require(type(value['clean']) is bool, 'Packaging checkout state missing')
    require(value['kind'] == 'packaging_verifier' and value['version'] == 1, 'Wrong packaging identity')
    hash_value(value['commit'], 40)
    require(set(value['files']) == {'results.py', 'verify_result.py'}, 'Packaging source coverage')
    for v in value['files'].values():
        file_pin(v)


def validate_identity(value, fixture):
    exact(value, 'accepted_historical_smoke training_source runtime model data_and_compiler_pins configuration configuration_sha256 prepared')
    baseline = read(HERE / 'accepted-baseline.json')
    accepted = {'kind': baseline['kind'], 'archive': baseline['archive'],
                'training_source_commit': baseline['training_source_commit'], 'packaging_commit': baseline['packaging_commit']}
    require(value['accepted_historical_smoke'] == accepted, 'Accepted historical baseline changed')
    require(value['model'] == baseline['model'] and value['data_and_compiler_pins'] == baseline['data_and_compiler_pins'],
            'Base/tokenizer/data/compiler lock mismatch')
    source = value['training_source']
    exact(source, 'kind commit origin files files_digest')
    require(source['kind'] == 'full_training_source' and source['origin'] == ORIGIN, 'Wrong training source type')
    hash_value(source['commit'], 40)
    from identity import TRAINING_FILES
    require(set(source['files']) == {'tools/windows-rtx3060-full-training/' + n for n in TRAINING_FILES}, 'Source file coverage')
    for v in source['files'].values():
        file_pin(v)
    require(source['files_digest'] == digest(source['files']), 'Training source digest mismatch')
    hash_value(value['configuration_sha256'])
    runtime = value['runtime']
    if fixture:
        require(runtime == {'kind': 'cpu_fixture_runtime'}, 'Fixture runtime type')
        expected = dict(config(), rows=value['configuration']['rows'], microbatches=value['configuration']['microbatches'],
                        optimizer_updates=value['configuration']['optimizer_updates'])
        require(value['configuration'] == expected and expected['rows'] == expected['microbatches'] == expected['optimizer_updates'] * 4,
                'Invalid fixture configuration')
    else:
        require(value['configuration'] == config(), 'Frozen V1 configuration mismatch')
        exact(runtime, 'kind python bits packages platform runtime_lock_sha256')
        lock = read(LEGACY / 'runtime-lock.json')
        expected = {re.sub(r'[-_.]+', '-', k).lower(): v for k, v in lock['packages'].items()}
        require(runtime['kind'] == 'full_training_runtime' and runtime['packages'] == expected
                and runtime['python'] == lock['python'] and runtime['bits'] == 64, 'Runtime lock mismatch')
        require(re.fullmatch(r'Windows-[A-Za-z0-9_.-]{1,100}', runtime['platform']) is not None, 'Private/invalid platform string')
        hash_value(runtime['runtime_lock_sha256'])
    prepared = value['prepared']
    exact(prepared, 'rows minimum_length maximum_length rows_above_1536 truncated_rows prompt_masks_verified complete_json_and_eos_verified order_sha256 files')
    require(prepared['rows'] == value['configuration']['rows'] and prepared['truncated_rows'] == prepared['rows_above_1536'] == 0,
            'Incomplete coverage')
    require(prepared['prompt_masks_verified'] == prepared['complete_json_and_eos_verified'] == prepared['rows'], 'Incomplete masks')
    require(type(prepared['minimum_length']) is int and type(prepared['maximum_length']) is int
            and 0 < prepared['minimum_length'] <= prepared['maximum_length'] <= 1536, 'Length coverage mismatch')
    if not fixture:
        require(prepared['maximum_length'] == 1421, 'Accepted maximum changed')
    hash_value(prepared['order_sha256'])
    require(set(prepared['files']) == {'train-tokens.jsonl', 'order.json', 'offsets.json', 'train-contexts.json'}, 'Prepared file coverage')
    for v in prepared['files'].values():
        file_pin(v)


def validate_reference(r):
    exact(r, 'schema_version kind run_digest base_and_tokenizer configuration_sha256 final_checkpoint_manifest_sha256 adapter_files quality_evaluation resume_requires_local_optimizer_checkpoint')
    require(r['schema_version'] == 1 and r['kind'] == 'deployable_lora_reference'
            and r['base_and_tokenizer'] == read(HERE / 'accepted-baseline.json')['model'], 'Adapter reference identity')
    for k in ('run_digest', 'configuration_sha256', 'final_checkpoint_manifest_sha256'):
        hash_value(r[k])
    require(r['quality_evaluation'] == 'NOT_RUN' and r['resume_requires_local_optimizer_checkpoint'] is True, 'Unsupported quality/resume claim')
    require(set(r['adapter_files']) == {'adapter_config.json', 'adapter_model.safetensors'}, 'Unexpected adapter files')
    for v in r['adapter_files'].values():
        file_pin(v)


def validate_evidence(e):
    exact(e, 'schema_version kind gate run_id fixture_only run prepared_identity training_facts operational_diagnostics packaging quality_evaluation REAL_APPLICATION_SMOKE')
    require(e['schema_version'] == 1 and e['kind'] == 'sanitized_full_training_diagnostic' and e['gate'] == GATE, 'Evidence kind mismatch')
    require(re.fullmatch(r'qwen3-4b-v1(?:-[a-z0-9]{1,32})?', e['run_id']) is not None, 'Invalid run ID')
    require(type(e['fixture_only']) is bool and e['quality_evaluation'] == 'NOT_RUN', 'Unsupported quality claim')
    require(e['REAL_APPLICATION_SMOKE'] == {'status': 'NOT_APPLICABLE_WITH_REASON',
                'reason': 'training infrastructure only; application behavior unchanged'}, 'Application claim mismatch')
    packaging(e['packaging'])
    op = e['operational_diagnostics']
    exact(op, 'last_error_phase error_type native_returncode packaging_attempts')
    require(op['last_error_phase'] in (None, 'prepare', 'start', 'resume', 'package', 'finalize'), 'Private/unknown error phase')
    require(op['error_type'] is None or re.fullmatch(r'[A-Z][A-Za-z]{0,60}(?:Error|Exception|Failure)', op['error_type']) is not None,
            'Error text/paths cannot enter diagnostics')
    require(op['native_returncode'] is None or type(op['native_returncode']) is int, 'Native code type')
    require(op['packaging_attempts'] is None or type(op['packaging_attempts']) is int and op['packaging_attempts'] >= 0, 'Attempt count')
    if e['prepared_identity'] is not None:
        validate_identity(e['prepared_identity'], e['fixture_only'])
    if e['run'] is not None:
        r = e['run']
        exact(r, 'schema_version kind run_id nonce identity started_unix deadline_unix authorization')
        require(r['schema_version'] == 1 and r['kind'] == 'full_training_run' and r['run_id'] == e['run_id']
                and r['identity'] == e['prepared_identity'] and r['authorization'] == 'EXPLICIT_START', 'Run identity mismatch')
        hash_value(r['nonce'], 32)
        require(isinstance(r['started_unix'], (float, int)) and math.isfinite(r['started_unix'])
                and r['deadline_unix'] - r['started_unix'] == config()['timeouts_seconds']['full_run_wall_clock'], 'Run deadline changed')
    f = e['training_facts']
    if f is not None:
        require(e['run'] is not None, 'Missing completed run')
        exact(f, 'schema_version kind run_digest completed_updates completed_microbatches epochs skipped_updates final_checkpoint final_checkpoint_manifest_sha256 mean_record_loss elapsed_seconds checkpoint_history external_gpu_min_free_MiB external_host_min_available_bytes pagefile_max_attempt_growth_bytes adapter_reference quality_evaluation')
        total = e['run']['identity']['configuration']['optimizer_updates']
        require(f['schema_version'] == 1 and f['kind'] == 'completed_full_training_facts'
                and f['run_digest'] == digest(e['run']) and f['completed_updates'] == total
                and f['completed_microbatches'] == total * 4 and f['epochs'] == 1 and f['skipped_updates'] == 0,
                'Not a complete one-epoch run')
        require(f['final_checkpoint'] == 'step-{:04d}'.format(total), 'Final checkpoint mismatch')
        hash_value(f['final_checkpoint_manifest_sha256'])
        require(type(f['mean_record_loss']) in (float, int) and math.isfinite(f['mean_record_loss'])
                and f['mean_record_loss'] >= 0 and 0 <= f['elapsed_seconds'] <= 86400, 'Invalid loss/time measurement')
        exact(f['checkpoint_history'], 'committed_checkpoints checkpoint_history_sha256 minimum_cuda_boundary_free_bytes peak_torch_allocated_bytes peak_torch_reserved_bytes minimum_boundary_host_available_bytes')
        require(f['checkpoint_history']['committed_checkpoints'] == total + 1, 'Missing checkpoint history')
        hash_value(f['checkpoint_history']['checkpoint_history_sha256'])
        if not e['fixture_only']:
            require(type(f['external_gpu_min_free_MiB']) in (int, float) and f['external_gpu_min_free_MiB'] >= 0
                    and type(f['checkpoint_history']['minimum_cuda_boundary_free_bytes']) is int
                    and f['checkpoint_history']['minimum_cuda_boundary_free_bytes'] >= 268435456, 'Missing production memory evidence')
            require(type(f['external_host_min_available_bytes']) is int and f['external_host_min_available_bytes'] > 0
                    and type(f['pagefile_max_attempt_growth_bytes']) is int, 'Missing host/pagefile measurement')
            require(all(type(f['checkpoint_history'][k]) is int and f['checkpoint_history'][k] > 0
                        for k in ('peak_torch_allocated_bytes', 'peak_torch_reserved_bytes', 'minimum_boundary_host_available_bytes')),
                    'Missing PyTorch/boundary host measurements')
        validate_reference(f['adapter_reference'])
        require(f['adapter_reference']['run_digest'] == f['run_digest']
                and f['adapter_reference']['configuration_sha256'] == e['prepared_identity']['configuration_sha256']
                and f['adapter_reference']['final_checkpoint_manifest_sha256'] == f['final_checkpoint_manifest_sha256']
                and f['quality_evaluation'] == 'NOT_RUN', 'Fact/reference mismatch')
    return True


def unique_json(raw):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'Duplicate JSON key')
            result[k] = v
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: require(False, 'Nonfinite JSON'))


def verify(path):
    require(path.stat().st_size < 64 * 2**20, 'Archive too large')
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        require(len(names) == len(set(names)), 'Duplicate ZIP entry')
        diagnostic = set(names) == {'evidence.json', 'archive-manifest.json'}
        require(diagnostic or set(names) == {'adapter_config.json', 'adapter_model.safetensors', 'references.json',
                                            'provenance.json', 'archive-manifest.json'}, 'Unexpected archive files')
        require(sum(i.file_size for i in z.infolist()) < 64 * 2**20, 'Expanded archive too large')
        for i in z.infolist():
            require(not i.flag_bits & 1 and ((i.external_attr >> 16) & 0o170000) != 0o120000, 'Encrypted/linked member')
        require(z.testzip() is None, 'ZIP CRC failure')
        manifest = unique_json(z.read('archive-manifest.json'))
        require(set(manifest) == set(names) - {'archive-manifest.json'}, 'Archive manifest coverage')
        for name, expected in manifest.items():
            raw = z.read(name)
            require(expected == {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}, 'Archive hash mismatch')
        if diagnostic:
            e = unique_json(z.read('evidence.json'))
            validate_evidence(e)
            status = 'FIXTURE_ONLY' if e['fixture_only'] else 'COMPLETED_UNEVALUATED' if e['training_facts'] else 'NOT_COMPLETED'
        else:
            refs, provenance = unique_json(z.read('references.json')), unique_json(z.read('provenance.json'))
            validate_reference(refs)
            exact(provenance, 'fixture_only run_id packaging')
            require(type(provenance['fixture_only']) is bool and re.fullmatch(r'qwen3-4b-v1(?:-[a-z0-9]{1,32})?', provenance['run_id']), 'Adapter provenance')
            packaging(provenance['packaging'])
            for name, expected in refs['adapter_files'].items():
                require(manifest[name] == expected, 'Adapter reference hash mismatch')
            c = unique_json(z.read('adapter_config.json'))
            require(c['base_model_name_or_path'] == 'Qwen/Qwen3-4B' and c['revision'] == refs['base_and_tokenizer']['revision'], 'Wrong adapter base')
            if not provenance['fixture_only']:
                for k, v in config()['lora'].items():
                    require(sorted(c[k]) == sorted(v) if k == 'target_modules' else c[k] == v, 'LoRA config changed')
                raw = z.read('adapter_model.safetensors')
                n = struct.unpack('<Q', raw[:8])[0]
                require(0 < n < 1024 * 1024, 'Invalid safetensors header')
                header = unique_json(raw[8:8+n])
                tensors = {k: v for k, v in header.items() if k != '__metadata__'}
                require(len(tensors) == 144 and all('lora_' in k for k in tensors)
                        and sum(math.prod(t['shape']) for t in tensors.values()) == 2949120, 'Adapter tensor coverage')
            status = 'FIXTURE_ONLY' if provenance['fixture_only'] else 'ADAPTER_INTEGRITY_ONLY'
    return {'archive_integrity': 'PASS', 'training_completion': status, 'quality_evaluation': 'NOT_RUN'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('archive', type=__import__('pathlib').Path)
    a = p.parse_args()
    print(json.dumps(verify(a.archive), indent=2))
