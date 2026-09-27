"""Runtime -> immutable facts -> diagnostic / adapter archives. No ML imports."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import time
import uuid
import zipfile
from full_common import (GATE, HERE, LEGACY, Layout, atomic, canonical, config, digest,
                         git, operational_error, pin, read, require, sha)
from checkpoints import Store, verify_checkpoint

VERSION = 1


def packaging_identity():
    return {'kind': 'packaging_verifier', 'version': VERSION, 'commit': git('rev-parse', 'HEAD'),
            'clean': not bool(git('status', '--porcelain', '--', 'tools/windows-rtx3060-full-training/results.py',
                                 'tools/windows-rtx3060-full-training/verify_result.py')),
            'files': {n: pin(HERE / n) for n in ('results.py', 'verify_result.py')}}


def journal_summary(layout, run, total):
    receipts = []
    cuda_free = []
    torch_allocated, torch_reserved, host_available = [], [], []
    for step in range(total + 1):
        row = read(layout.runtime / 'commits' / ('step-{:04d}.json'.format(step)))
        require(row['run_digest'] == digest(run) and row['optimizer_step'] == step
                and row['cursor'] == step * 4 and row['skipped_updates'] == 0, 'Committed coverage mismatch')
        receipts.append({'step': step, 'manifest_sha256': row['manifest_sha256']})
        if 'free_bytes' in row['measurements']:
            cuda_free.append(row['measurements']['free_bytes'])
            torch_allocated.append(row['measurements']['peak_allocated_bytes'])
            torch_reserved.append(row['measurements']['peak_reserved_bytes'])
            host_available.append(row['measurements']['host_available_bytes'])
    return {'committed_checkpoints': len(receipts), 'checkpoint_history_sha256': digest(receipts),
            'minimum_cuda_boundary_free_bytes': min(cuda_free) if cuda_free else None,
            'peak_torch_allocated_bytes': max(torch_allocated) if torch_allocated else None,
            'peak_torch_reserved_bytes': max(torch_reserved) if torch_reserved else None,
            'minimum_boundary_host_available_bytes': min(host_available) if host_available else None}


def finalize(layout):
    run = read(layout.runtime / 'run.json')
    total = run['identity']['configuration']['optimizer_updates']
    store = Store(layout, run)
    path, progress = store.select('step-{:04d}'.format(total))
    summary = journal_summary(layout, run, total)
    reference = {'schema_version': 1, 'kind': 'deployable_lora_reference',
                 'run_digest': digest(run), 'base_and_tokenizer': run['identity']['model'],
                 'configuration_sha256': run['identity']['configuration_sha256'],
                 'final_checkpoint_manifest_sha256': sha(path / 'manifest.json'),
                 'adapter_files': {n: pin(path / 'adapter' / n) for n in ('adapter_config.json', 'adapter_model.safetensors')},
                 'quality_evaluation': 'NOT_RUN', 'resume_requires_local_optimizer_checkpoint': True}
    if not layout.adapter.exists():
        stage = layout.base / ('.adapter-incomplete-' + uuid.uuid4().hex)
        stage.mkdir()
        for name, expected in reference['adapter_files'].items():
            shutil.copyfile(path / 'adapter' / name, stage / name)
            require(pin(stage / name) == expected, 'Adapter export copy corrupt')
        atomic(stage / 'references.json', reference, immutable=True)
        stage.rename(layout.adapter)
    require(read(layout.adapter / 'references.json') == reference, 'Existing adapter export differs')
    for name, expected in reference['adapter_files'].items():
        require(pin(layout.adapter / name) == expected, 'Adapter export changed')
    monitors = [read(p) for p in sorted(layout.runtime.glob('train-*-monitor.json'))]
    external = [r['external_gpu_min_free_MiB'] for r in monitors if r.get('external_gpu_min_free_MiB') is not None]
    hosts = [r['host_min_available_bytes'] for r in monitors if r.get('host_min_available_bytes') is not None]
    paging = [r['pagefile_peak_bytes'] - r['pagefile_initial_bytes'] for r in monitors
              if r.get('pagefile_peak_bytes') is not None and r.get('pagefile_initial_bytes') is not None]
    facts = {'schema_version': 1, 'kind': 'completed_full_training_facts', 'run_digest': digest(run),
             'completed_updates': total, 'completed_microbatches': total * 4, 'epochs': 1, 'skipped_updates': 0,
             'final_checkpoint': path.name, 'final_checkpoint_manifest_sha256': sha(path / 'manifest.json'),
             'mean_record_loss': progress['loss_sum'] / (total * 4), 'elapsed_seconds': progress['elapsed_seconds'],
             'checkpoint_history': summary, 'external_gpu_min_free_MiB': min(external) if external else None,
             'external_host_min_available_bytes': min(hosts) if hosts else None,
             'pagefile_max_attempt_growth_bytes': max(paging) if paging else None,
             'adapter_reference': reference, 'quality_evaluation': 'NOT_RUN'}
    destination = layout.runtime / 'completed.json'
    if destination.exists():
        # Re-finalization after an operational error preserves the original measurements.
        saved = read(destination)
        seal = layout.runtime / 'completed-seal.json'
        if not seal.exists():
            require(saved == facts, 'Unsealed completed facts do not match verified runtime evidence')
            atomic(seal, pin(destination), immutable=True)
        require(read(layout.runtime / 'completed-seal.json') == pin(destination), 'Completed facts corrupted')
        require(saved['final_checkpoint_manifest_sha256'] == facts['final_checkpoint_manifest_sha256']
                and saved['checkpoint_history'] == summary and saved['adapter_reference'] == reference,
                'Completed facts/checkpoint mismatch')
        return saved
    atomic(destination, facts, immutable=True)
    atomic(layout.runtime / 'completed-seal.json', pin(destination), immutable=True)
    return facts


def collect(layout, pack_identity=None):
    prepared = read(layout.runtime / 'prepared.json') if (layout.runtime / 'prepared.json').exists() else None
    run = read(layout.runtime / 'run.json') if (layout.runtime / 'run.json').exists() else None
    completed = layout.runtime / 'completed.json'
    facts = None
    if completed.exists():
        require(read(layout.runtime / 'completed-seal.json') == pin(completed), 'Immutable completed evidence changed')
        facts = read(completed)
        require(facts['run_digest'] == digest(run), 'Run identity changed')
        path = layout.checkpoints / facts['final_checkpoint']
        verify_checkpoint(path, run)
        require(sha(path / 'manifest.json') == facts['final_checkpoint_manifest_sha256'], 'Final checkpoint changed')
        require(journal_summary(layout, run, facts['completed_updates']) == facts['checkpoint_history'], 'Journal changed')
    ops = read(layout.runtime / 'operations.json') if (layout.runtime / 'operations.json').exists() else {}
    # Only these enumerated operational values may enter diagnostics; never exception text/paths.
    operational = {k: ops.get(k) for k in ('last_error_phase', 'error_type', 'native_returncode', 'packaging_attempts')}
    identity = run['identity'] if run else prepared['identity'] if prepared else None
    fixture = bool(identity and identity['runtime']['kind'] == 'cpu_fixture_runtime')
    evidence = {'schema_version': 1, 'kind': 'sanitized_full_training_diagnostic', 'gate': GATE,
                'run_id': layout.run_id, 'fixture_only': fixture, 'run': run, 'prepared_identity': identity,
                'training_facts': facts, 'operational_diagnostics': operational,
                'packaging': pack_identity or packaging_identity(), 'quality_evaluation': 'NOT_RUN',
                'REAL_APPLICATION_SMOKE': {'status': 'NOT_APPLICABLE_WITH_REASON',
                                           'reason': 'training infrastructure only; application behavior unchanged'}}
    from verify_result import validate_evidence
    validate_evidence(evidence)
    return evidence


def write_archive(target, payload, verifier):
    require(not target.exists(), 'Existing archive must not be replaced')
    stage = target.with_name(target.name + '.incomplete-' + uuid.uuid4().hex)
    manifest = {n: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()} for n, data in payload.items()}
    with zipfile.ZipFile(stage, 'x', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in payload.items():
            z.writestr(name, data)
        z.writestr('archive-manifest.json', canonical(manifest))
    with stage.open('rb+') as stream:
        import os
        os.fsync(stream.fileno())
    verifier(stage)
    stage.rename(target)
    return target


def package(layout, pack_identity=None):
    from verify_result import verify
    layout.results.mkdir(parents=True, exist_ok=True)
    op = layout.runtime / 'operations.json'
    old = read(op) if op.exists() else {}
    atomic(op, dict(old, packaging_attempts=old.get('packaging_attempts', 0) + 1))
    attempt = uuid.uuid4().hex
    try:
        evidence = collect(layout, pack_identity)
        diag = write_archive(layout.results / ('diagnostic-' + attempt + '.zip'),
                             {'evidence.json': canonical(evidence)}, verify)
        adapter = None
        if evidence['training_facts'] is not None:
            refs = read(layout.adapter / 'references.json')
            require(refs == evidence['training_facts']['adapter_reference'], 'Adapter reference mismatch')
            payload = {'references.json': canonical(refs),
                       'provenance.json': canonical({'fixture_only': evidence['fixture_only'], 'run_id': layout.run_id,
                                                     'packaging': evidence['packaging']})}
            for name, expected in refs['adapter_files'].items():
                require(pin(layout.adapter / name) == expected, 'Adapter payload changed')
                payload[name] = (layout.adapter / name).read_bytes()
            adapter = write_archive(layout.results / ('adapter-' + attempt + '.zip'), payload, verify)
        receipt = {'attempt': attempt, 'diagnostic': pin(diag), 'adapter': pin(adapter) if adapter else None,
                   'completed_facts_sha256': sha(layout.runtime / 'completed.json') if evidence['training_facts'] else None,
                   'packaging': evidence['packaging']}
        atomic(layout.runtime / 'packaging-attempts' / (attempt + '.json'), receipt, immutable=True)
        return {'diagnostic': str(diag), 'adapter': str(adapter) if adapter else None}
    except Exception as error:
        operational_error(layout, 'package', type(error).__name__, 1)
        atomic(layout.runtime / 'packaging-attempts' / (attempt + '.json'),
               {'attempt': attempt, 'failed': True, 'error_type': type(error).__name__}, immutable=True)
        raise


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run-id', required=True)
    a = p.parse_args()
    print(json.dumps(package(Layout(a.run_id)), indent=2), flush=True)
