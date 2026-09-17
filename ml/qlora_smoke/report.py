"""Assemble the bounded gate receipt from retained measurements, without a model call."""
import datetime
import hashlib
import json
from common import ROOT, HERE, SCRATCH, read_json, write_json, sha256
from assess_result import assess

NAME = 'LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE'
SOURCES = [
    ('bitsandbytes Windows CUDA support', 'https://huggingface.co/docs/bitsandbytes/installation'),
    ('PEFT quantization preparation and all-linear LoRA', 'https://huggingface.co/docs/peft/developer_guides/quantization'),
    ('TRL prompt-completion and prebuilt labels', 'https://huggingface.co/docs/trl/sft_trainer'),
    ('Transformers quantization and training placement', 'https://huggingface.co/docs/transformers/quantization/bitsandbytes'),
]


def main():
    before = read_json(SCRATCH / 'integrity-before.json')
    after = read_json(SCRATCH / 'integrity-after.json')
    preflight = read_json(SCRATCH / 'preflight.json')
    training = read_json(SCRATCH / 'train-1024.json')
    reload_result = read_json(SCRATCH / 'reload-1024.json')
    environment = read_json(SCRATCH / 'environment.json')
    git = read_json(SCRATCH / 'git-source-delivery.json')
    verdict, failures = assess(preflight, training, reload_result, after['changed'])
    assert not after['changed']
    executed = read_json(SCRATCH / 'executed-source-hashes.json')
    immutable_worker_names = ('common.py', 'config.json', 'prepare_smoke_data.py', 'train_smoke.py', 'verify_adapter.py', 'preflight.py')
    for name in immutable_worker_names:
        key = 'ml/qlora_smoke/' + name
        assert sha256(HERE / name) == executed[key], 'Executed worker changed after campaign: ' + name
    audits = {name: read_json(SCRATCH / filename).get('audit', read_json(SCRATCH / filename)) for name, filename in
              [('prepare', 'prepare-1024-audit.json'), ('preflight', 'preflight.json'),
               ('training', 'train-1024.json'), ('reload', 'reload-1024.json')]}
    assert all(not a['denied'] and not a['evaluation_file_reads'] for a in audits.values())
    metadata = read_json(SCRATCH / 'package-metadata.json')
    package_compatibility = {name: {'version': d['version'], 'requires_python': d['requires_python'],
                                   'runtime_requires_dist': [r for r in d['requires_dist'] if 'extra ==' not in r],
                                   'url': f'https://pypi.org/pypi/{name}/{d["version"]}/json'}
                             for name, d in metadata.items()}
    process_records = {p.stem: read_json(p) for p in SCRATCH.glob('*-process.json')}
    assert process_records['tests-verdict-process']['returncode'] == 0
    file_hashes = {name: {'before': value, 'after': after['files'][name], 'unchanged': value == after['files'][name]}
                   for name, value in before['files'].items()}
    inventory_digest = lambda data: hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    peak = training['after_training']
    memory_assessment = {
        'physical_VRAM_MiB': 6144, 'cuda_device_capacity_bytes': preflight['cuda_device_total_bytes'],
        'pre_model_load_free_MiB': training['before_load']['free_bytes']/1024**2,
        'initial_nvidia_smi_free_MiB': 5348,
        'peak_allocated_MiB': peak['peak_allocated_bytes']/1024**2,
        'peak_reserved_MiB': peak['peak_reserved_bytes']/1024**2,
        'peak_process_working_set_MiB': training['cleanup']['memory_before_exit']['peak_working_set_bytes']/1024**2,
        'zero_free_cuda_memory_at_step_boundaries': all(s['memory']['free_bytes'] == 0 for s in training['steps']),
        'all_model_parameters_on_cuda': True, 'configured_CPU_model_offload': False,
        'physical_GPU_resident_fit_verified': False,
        'interpretation': 'CUDA allocation exceeded physical VRAM under Windows WDDM. Completion proves runtime execution, not a GPU-resident 6 GiB training envelope.',
        'driver_shared_memory_at_training_peak': None,
        'driver_shared_memory_note': 'WDDM paging/oversubscription is inferred; exact dedicated/shared residency at the peak was not sampled. The attempted OS-counter inspection occurred after the training process exited.',
        'post_training_OS_counter_snapshot': {'dedicated_bytes': 516485120, 'shared_bytes': 19705856,
                                            'scope': 'Adapter-wide after exit; not attributable to the training peak'},
    }
    evidence = {
        'gate': NAME, 'schema_version': 1, 'verdict': verdict,
        'completed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'failed_verifications': failures,
        'scope': {'full_training_started': False, 'optimizer_rows': 8, 'selected_rows': 32,
                  'full_train_rows_used_for_gradients': False, 'evaluation_campaigns': [],
                  'application_integration': False, 'G3_started': False, 'weights_published': False},
        'environment': environment, 'package_compatibility': package_compatibility,
        'dependency_install': read_json(SCRATCH / 'install-result.json'),
        'official_sources': [{'title': t, 'url': u, 'checked_date': '2026-09-17'} for t, u in SOURCES],
        'hardware_backend_preflight': preflight,
        'training': training, 'reload': reload_result, 'memory_assessment': memory_assessment,
        'attempt_policy': {'1024_training_attempts': 1, 'cuda_oom': False, '768_training_attempts': 0,
                           'retry_not_run_reason': 'No CUDA OOM occurred; the sole authorized retry was conditional on CUDA OOM.',
                           'quality_tuning': False, 'settings_changed_after_training': False},
        'verification': {'cheap_tests_before_model_load': 12, 'final_cheap_tests': 13,
                         'final_test_failures': 0, 'final_test_log_sha256': sha256(SCRATCH / 'tests-verdict.log'),
                         'source_hashes_at_execution': executed,
                         'executed_worker_sources_unchanged_after_campaign': True,
                         'pre_campaign_corrections': ['Allowed Windows null-device import probe in audit guard',
                             'Compared rounded physical MiB instead of exact advertised CUDA bytes',
                             'Updated collator use for stable TRL 1.13 prebuilt-label API',
                             'Fixed negative unit-test expected exception before model loading'],
                         'metadata_transport_note': 'Initial HTTP body reads timed out before installation. Reading available chunks and validating a complete JSON document resolved the metadata transport issue; installation itself ran once.'},
        'isolation': {'TRAIN_only': True, 'DEV_training_exposure': 0, 'INTERNAL_TEST_training_exposure': 0,
                      'A01_A16_training_exposure': 0, 'tuning_eval_training_exposure': 0,
                      'holdout_hash_auditor_access': 'Byte hashing only, in separate supervisor; no content or labels passed to workers.',
                      'public_context_registry': 'Preparer reads registry and filters TRAIN contexts; no non-TRAIN examples are compiled.',
                      'worker_audits': audits},
        'integrity': {'unchanged': True, 'protected_file_count': len(file_hashes), 'files': file_hashes,
                      'base_shards_match_pinned_hashes_before_and_after': True,
                      'accepted_corpus_and_manifest_unchanged': True, 'raw_external_data_unchanged': True,
                      'all_preexisting_tracked_files_unchanged': True, 'application_and_frozen_planning_unchanged': True,
                      'baseline_environment_file_count': len(before['baseline_environment_file_stats']),
                      'baseline_inventory_before_sha256': inventory_digest(before['baseline_environment_file_stats']),
                      'baseline_inventory_after_sha256': inventory_digest(after['baseline_environment_file_stats']),
                      'baseline_environment_modified': False},
        'processes': process_records, 'post_training_release': read_json(SCRATCH / 'post-training-release.json'),
        'local_artifact_logs': {p.name: {'bytes': p.stat().st_size, 'sha256': sha256(p)} for p in SCRATCH.glob('*.log')},
        'git': git,
        'next': {'recommendation': 'Separate bounded GPU memory-envelope investigation before full-training authorization',
                 'LOCAL_QWEN_QLORA_TRAINING_V1_recommended': False, 'started': False},
        'limitations': ['No language-quality inference from the losses.', 'Only eight gradient microbatches executed.',
                       'No extrapolation to full-corpus memory or duration.',
                       'All-CUDA parameter placement does not establish physical VRAM residency under WDDM.',
                       'No OOM-only fallback was exercised.'],
    }
    write_json(ROOT / 'docs/gates/evidence' / (NAME + '.json'), evidence)
    receipt = f'''# {NAME}

**Verdict: `{verdict}`.** The NF4/LoRA pipeline executed, saved, and reloaded successfully, but the required **6 GiB GPU memory envelope was not established**. Peak allocated CUDA memory exceeded physical VRAM. This gate does not recommend full training.

## Observed result

| Check | Measurement |
| --- | --- |
| Runtime | Python 3.12.10; torch 2.14.0+cu126; Transformers 5.17.0; accelerate 1.15.0; safetensors 0.8.0 |
| Training libraries | bitsandbytes 0.50.2; PEFT 0.21.0; TRL 1.13.0; datasets 5.0.1 |
| Hardware | Windows x64; RTX 2060; physical 6144 MiB; sm75; CUDA runtime 12.6; driver 610.88; no native BF16 |
| CUDA backend | `libbitsandbytes_cuda126.dll`; native NF4 CUDA forward/backward and paged 8-bit optimizer mutation passed |
| Quantization | Original checkpoint loaded as NF4 4-bit, double quantization, FP16 compute; explicit CUDA:0; 252 quantized linear modules |
| LoRA | all-linear; r=8; alpha=16; dropout=0.05; bias=none; 16,515,072 trainable parameters |
| Frozen base | 4,022,468,096 parameters; no base gradients; all parameters placed on CUDA; use_cache=false |
| Campaign | limit 1024; microbatch 1; accumulation 4; two actual paged_adamw_8bit updates; no CPU model offload |
| Data | 32 complete TRAIN rows, 689–974 tokens, median 844.5; first optimized row 962 tokens; eight distinct rows received gradients |
| Step losses | {training['steps'][0]['loss']:.8f}, {training['steps'][1]['loss']:.8f} |
| Step times | {training['steps'][0]['seconds']:.3f} s, {training['steps'][1]['seconds']:.3f} s |
| Numerical state | finite losses and gradients; no NaN/Inf; no GradScaler skips; scale 65536 throughout |
| Adapter mutation | 504/504 tensors changed; initialized/final hashes and example deltas retained |
| Save/reload | Adapter saved; every reloaded adapter tensor hash matched; unused TRAIN row forward produced finite logits |

## Memory verification failed

Before model load CUDA reported **5103 MiB free**; the initial desktop snapshot reported **5348 MiB free** through nvidia-smi. Peak allocated memory was **6234.4541 MiB (6.0883 GiB)** and peak reserved memory **6750 MiB (6.5918 GiB)**. CUDA reports device capacity **6143.5625 MiB**; nvidia-smi reports physical capacity **6144 MiB**. Both optimizer-step boundaries reported **zero free CUDA memory**. Process peak working set, including adapter serialization, was **3257.3711 MiB**.

Windows WDDM allowed the campaign to finish despite CUDA allocations exceeding physical VRAM. Driver paging/oversubscription is an inference from those measurements; exact dedicated/shared residency at the training peak was not sampled. OS memory-counter inspection occurred after exit and cannot prove peak residency. All parameters being on CUDA and the absence of configured CPU layer offload do **not** establish that the workload stayed in dedicated VRAM. The receipt therefore records a failed memory-envelope verification rather than certifying a 1024 GPU fit.

No CUDA OOM was thrown. The user's single 768-token retry was specifically conditional on OOM, so it was **not run**. There was one model-training attempt, with no rank, learning-rate, length, or quality tuning. Process exit released the training resources before a fresh reload process. No unrelated GPU process was terminated.

## Data, masking and evaluation isolation

Selection used fixed seed 20260917, SHA-256 ordering, full intent coverage, critical ambiguity/negation/injection tags, and a boundary-length first row. All 8,000 TRAIN rows were token-measured; only the 32 selected records were exported and only eight received gradients. No epoch occurred. IDs, lengths, exact optimizer row IDs and the distinct reload row are in the [evidence](evidence/{NAME}.json). No target was truncated.

The unchanged compiler supplies system/public-context/Russian-utterance prompts and canonical interpretation JSON completions. The original non-thinking chat template was verified token by token. All 32 batches were checked before loading the model, and every optimized batch checked again: prompt labels -100, complete canonical JSON supervised, assistant EOS supervised exactly once, no thinking supervision, and padding ignored.

Stable TRL 1.13's documented text collator accepts prebuilt labels. `SFTConfig(completion_only_loss=True)` plus that collator and an explicit two-update AMP loop provide observable gradients/scaler/optimizer hooks without a full Trainer campaign. [TRL documentation](https://huggingface.co/docs/trl/sft_trainer).

Workers' Python audit hooks blocked eval/holdout/raw-data/receipt reads, network calls and protected writes. **DEV, INTERNAL_TEST, A01–A16 and tuning-eval training exposure: zero.** The separate integrity auditor hashed their bytes without parsing targets. The public context registry was filtered to TRAIN; the only eval-area worker read was the interpretation schema required by the existing compiler. Audit hooks are not a native-code sandbox; before/after hashes independently protect native model-file accesses.

## Integrity and verification

**12 focused tests passed before model load; 13 passed after adding the oversubscription-verdict regression test.** No model was loaded by unit tests. Exact package resolution passed `pip check`; installation used 61 stable binary wheels and took 230.406 seconds. All versions and official wheel URLs/SHA-256 are retained. In the isolated environment, datasets requires fsspec 2026.6.0; the resolver also selected filelock 4.0.0, huggingface_hub 1.32.0 and setuptools 84.0.0. These transitive differences are recorded. The known-good core versions and baseline environment remain unchanged.

All **{len(file_hashes)} protected file hashes** match before/after: the three pinned model shards, small model/cache files, accepted synthetic corpus, evaluation assets, raw external data, original application sources and frozen planning/gate documents. Baseline environment inventory/stats also match. Model shards retain:

- `model-00001-of-00003.safetensors`: `328a91d3122359d5547f9d79521205bc0a46e1f79a792dfe650e99fc2d651223`
- `model-00002-of-00003.safetensors`: `6cd087b316306a68c562436b5492edbcf6e16c6dba3a1308279caa5a58e21ca5`
- `model-00003-of-00003.safetensors`: `e4bf436957184f4eeb86a80e9db394503f1f56446b2e6b7edeac5b81470f4ca1`

Ignored adapter: `AlagModels/adapters/qlora-feasibility-smoke/1024/adapter_model.safetensors`, **66,126,768 bytes**, SHA-256 `9d902b8748c66be754b9a37f251d8d512bf5471640c4c1153789bd773bffd1c2`. Config, file sizes and all adapter tensor reload hashes are recorded. No weights were merged, committed or published.

## Git delivery and next boundary

Implementation commit **`{git['implementation_commit']}`** was normally pushed to the specified `origin/main`; remote equality and **0/0** were verified before this receipt. Source/config/docs only were staged by explicit paths. Existing ignore rules cover the private venv, expanded files, model, adapter and raw datasets. This receipt/evidence are delivered in a follow-up commit; resolve it with `git log -1 --format=%H -- docs/gates/{NAME}.md`. Final receipt-push synchronization is verified after that commit and reported in the final response, avoiding a self-referential commit hash.

The successful subchecks establish adapter pipeline execution, not the requested GPU-resident training envelope, language quality, full-corpus feasibility, production speed, or G3 readiness. **`LOCAL_QWEN_QLORA_TRAINING_V1` is not recommended.** First resolve memory residency in a separately authorized bounded investigation. Nothing further was trained or integrated.

Source/reproduction: [ml/qlora_smoke](../../ml/qlora_smoke/README.md). Official references: [bitsandbytes](https://huggingface.co/docs/bitsandbytes/installation), [PEFT](https://huggingface.co/docs/peft/developer_guides/quantization), [Transformers](https://huggingface.co/docs/transformers/quantization/bitsandbytes).

STOP — FULL QLORA TRAINING NOT STARTED.
'''
    (ROOT / 'docs/gates' / (NAME + '.md')).write_text(receipt, encoding='utf-8', newline='\n')
    print(verdict)


if __name__ == '__main__':
    main()
