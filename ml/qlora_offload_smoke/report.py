"""Assemble the bounded gate receipt from recorded runs; never loads a model."""
import argparse
from datetime import datetime, timezone
from pathlib import Path
from common import ROOT, HERE, SCRATCH, read_json, write_json, sha256
from assess import assess, memory_failure, GATE

MIB = 2**20
GIB = 2**30
REFERENCES = {
    'Transformers 5.17 checkpoint offload': 'https://huggingface.co/docs/transformers/v5.17.0/grad_checkpointing',
    'PEFT 0.21 preparation': 'https://huggingface.co/docs/peft/v0.21.0/en/package_reference/peft_model#peft.prepare_model_for_kbit_training',
    'PyTorch saved-tensor CPU storage': 'https://docs.pytorch.org/docs/2.14/autograd.html#torch.autograd.graph.save_on_cpu',
    'TRL activation offloading': 'https://huggingface.co/docs/trl/reducing_memory_usage#activation-offloading',
}


def build():
    old = read_json(SCRATCH/'historical-comparison.json')
    campaigns = {}
    for limit in (1024, 768):
        run = read_json(SCRATCH/f'train-{limit}.json')
        monitor = read_json(SCRATCH/f'HOST_OFFLOAD_{limit}-monitor.json')
        reload_result = read_json(SCRATCH/f'reload-{limit}.json')
        reload_monitor = read_json(SCRATCH/f'reload-{limit}-monitor.json')
        assert monitor['worker_exited'] and reload_monitor['worker_exited']
        assert not monitor['unrelated_processes_terminated']
        assert run['configuration']['training'] == old['configuration']['training']
        if limit == 1024:
            assert run['selection']['selected_ids'] == old['selection']['selected_ids']
            assert run['selection']['lengths'] == old['selection']['lengths']
        allocated = run['after_training']['peak_allocated_bytes']
        saved = old['peak_allocated_bytes'] - allocated
        step_seconds = [s['seconds'] for s in run['steps']]
        minimum_free = min(s['memory']['free_bytes'] for s in run['steps'])
        comparison = {
            'cuda_peak_reduction_bytes': saved,
            'cuda_peak_reduction_MiB': saved/MIB,
            'cuda_peak_reduction_percent': 100*saved/old['peak_allocated_bytes'],
            'process_peak_working_set_increase_bytes': monitor['process_peak_working_set_bytes']-old['process_peak_bytes'],
            'step_seconds': step_seconds,
            'step_time_ratios_to_historical': [new/prior for new, prior in zip(step_seconds, old['step_seconds'], strict=True)],
            'aggregate_two_step_time_ratio': sum(step_seconds)/sum(old['step_seconds']),
            'aggregate_two_step_time_change_percent': 100*(sum(step_seconds)/sum(old['step_seconds'])-1),
            'minimum_cuda_step_headroom_bytes': minimum_free,
            'allocation_capacity_margin_bytes': run['before_load']['total_bytes']-allocated,
            'minimum_host_available_bytes': monitor['host_min_available_bytes'],
            'host_margin_above_safety_floor_bytes': monitor['host_min_available_bytes']-6*GIB,
            'causality_limit': '1024 reuses the historical sample; timing is a two-step observation only.' if limit == 1024
                               else '768 changes sequence limit and eligible sample; its difference cannot be attributed solely to activation offload.',
        }
        campaigns[str(limit)] = {'training': run, 'monitor': monitor, 'reload': reload_result,
                                 'reload_monitor': reload_monitor, 'comparison': comparison,
                                 'physical_gpu_fit': not memory_failure(run),
                                 'failed_fit_conditions': ['CUDA free memory is zero at both optimizer-step boundaries']
                                      if minimum_free == 0 else []}
    primary = campaigns['1024']['training']
    last = campaigns['768']
    assert memory_failure(primary), 'Second campaign required the authorized primary memory failure'
    verdict = assess(last['training'], last['monitor'], last['reload'], primary)
    # This is an evidence assembler for these two recorded campaigns, not an experiment scheduler.
    assert verdict == 'LOCAL_QWEN_QLORA_HOST_OFFLOAD_MEMORY_BLOCKED'
    before = read_json(SCRATCH/'integrity-before.json')
    after = read_json(SCRATCH/'integrity-after.json')
    assert not after['changed'] and not after['environment_changed']
    assert before['files'] == after['files']
    audits = {}
    for limit, record in campaigns.items():
        audits[f'train-{limit}'] = record['training']['audit']
        audits[f'reload-{limit}'] = record['reload']['audit']
        audits[f'prepare-{limit}'] = read_json(SCRATCH/f'prepare-{limit}-audit.json')
    for audit in audits.values():
        assert audit['evaluation_file_reads'] == [] and audit['denied'] == []
    tests = {}
    for name, count in (('tests', 14), ('tests-final', 15)):
        monitor = read_json(SCRATCH/f'{name}-monitor.json')
        log = (SCRATCH/f'{name}.log').read_text(encoding='utf-8')
        assert monitor['returncode'] == 0 and f'Ran {count} tests' in log and '\nOK' in log
        tests[name] = {'passed': True, 'count': count, 'monitor': monitor, 'log_sha256': sha256(SCRATCH/f'{name}.log')}
    sources = {str(limit): {Path(name).name: value for name, value in
                            read_json(SCRATCH/f'executed-source-hashes-{limit}.json').items()}
               for limit in (1024, 768)}
    final_sources = {p.name: sha256(p) for p in HERE.iterdir() if p.is_file()}
    unchanged_executed = ['train_smoke.py', 'verify_adapter.py', 'offload.py', 'common.py', 'config.json', 'monitor.py', 'assess.py']
    assert all(sources['1024'][name] == sources['768'][name] == final_sources[name] for name in unchanged_executed)
    artifacts = {p.relative_to(ROOT).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha256(p)}
                 for p in SCRATCH.iterdir() if p.is_file()
                 and p.suffix in ('.json', '.jsonl', '.log', '.py')
                 and not p.name.startswith(('evidence-preview', 'receipt-preview'))}
    delivery_path = SCRATCH/'git-source-delivery.json'
    git = read_json(delivery_path) if delivery_path.exists() else {'status': 'PENDING_SOURCE_DELIVERY'}
    return {
        'gate': GATE, 'verdict': verdict, 'recorded_utc': datetime.now(timezone.utc).isoformat(),
        'reason': 'Explicit host activation storage worked and reduced peak CUDA allocation, but both authorized configurations reported zero CUDA free bytes at both update boundaries. Physical GPU headroom is not established.',
        'runtime': read_json(SCRATCH/'runtime-verification.json'),
        'installed_api': read_json(SCRATCH/'runtime-api.json'), 'official_sources': REFERENCES,
        'configuration': read_json(HERE/'config.json'), 'historical_baseline': old,
        'campaigns': campaigns, 'cheap_tests': tests,
        'pretraining_tiny_qwen_proof': read_json(SCRATCH/'tiny-offload-proof-pretraining.json'),
        'fallback_preload_masks': read_json(SCRATCH/'masks-768-preload.json'),
        'preparation_correction': {
            'initial_768_preparation_exit': read_json(SCRATCH/'prepare-768-monitor.json')['returncode'],
            'reason': 'The inherited selector required every corpus intent, but three have no complete row <=768. It failed before any 768 model load.',
            'correction': 'Deterministically cover eligible intents/tags, record unavailable coverage, and keep every selected completion intact.',
            'excluded_intents': last['training']['selection']['unavailable_intents_within_limit'],
            'eligible_train_rows': last['training']['selection']['eligible_rows'],
            'original_preparation_source_sha256': sha256(SCRATCH/'prepare-before-fallback-correction.py'),
            'regression_test': 'test_unavailable_long_intent_is_excluded_without_target_truncation',
            'additional_training_attempts': 0,
        },
        'isolation': {'train_only': True, 'DEV': 0, 'INTERNAL_TEST': 0, 'tuning_eval': 0, 'A01_A16': 0,
                      'worker_audits': audits,
                      'hash_auditor_note': 'A separate byte-only auditor opens protected files for hashing. No evaluation records enter a worker or gradient update.',
                      'audit_limit': 'Python audit hooks are an accidental-access guard, not a native-code sandbox; hashes establish integrity, not absence of native reads.'},
        'integrity': {'protected_file_count': len(before['files']),
                      'files': {p: {'before': item, 'after': after['files'][p], 'unchanged': True} for p, item in before['files'].items()},
                      'environment_inventories_before': before['environments'],
                      'environment_inventories_after': after['environments'],
                      'all_protected_bytes_unchanged': True, 'both_environments_unchanged': True,
                      'base_model_pins_verified': True, 'corpus_unchanged': True,
                      'application_unchanged': True, 'historical_gate_and_adapter_unchanged': True},
        'monitor_interpretation': {
            'mandatory': 'PyTorch allocated/capacity and CUDA free at update boundaries, explicit pack/unpack evidence, and physical host RAM/pagefile telemetry.',
            'reserved': 'Reported without imposing a physical-capacity ceiling on reserved bytes.',
            'shared': 'PDH shared usage includes possible intentional pinned-host allocations; it is not a direct attribution of WDDM oversubscription.',
            'different_gpu_counters': 'nvidia-smi dedicated free remained positive, but mandatory torch.cuda.mem_get_info free was zero. This discrepancy does not satisfy the gate.',
            'pagefile': 'EnumPageFilesW reports actual used pagefile pages. Process private/commit bytes do not measure disk paging.',
            'unit_safety': 'Only dummy descendants were terminated under simulated low RAM in unit tests. Actual campaigns/reloads had no safety stop and terminated no unrelated processes.',
        },
        'source_provenance': {'executed': sources, 'final': final_sources, 'unchanged_executed_modules': unchanged_executed},
        'local_artifact_hashes': artifacts,
        'git_initial': {'branch': 'main', 'clean': True, 'head': '899fa18734f83c0a6d2b4a74cba6888703345772',
                        'origin': 'https://github.com/AiratBastanov/TalkNFace.git', 'ahead': 0, 'behind': 0},
        'git_source_delivery': git,
        'receipt_delivery': 'This receipt is committed and pushed immediately after the recorded source commit. Its own Git hash is resolved with git log -- this receipt; the final response reports that delivery commit.',
        'next_recommendation': 'LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION',
        'next_scope': 'A separate bounded decision on memory policy/placement is required before another training gate. No additional configuration is authorized by this result; full V1 training is not recommended.',
        'stop': {'full_training_started': False, 'evaluation_started': False, 'quality_claim': False,
                 'application_integration': False, 'G3_started': False, 'adapter_merged_or_published': False,
                 'model_weight_cpu_offload': False, 'authorized_training_campaigns': 2},
    }


def markdown(e):
    old = e['historical_baseline']
    a, b = (e['campaigns'][str(limit)] for limit in (1024, 768))
    def pair(callback):
        return ' | '.join(str(callback(c)) for c in (a, b))
    def peak(c, key):
        return f"{c['training']['after_training'][key]/MIB:.3f}"
    lines = [f'# {GATE}', '', f"**VERDICT: {e['verdict']}**", '', e['reason'], '',
        'The gate is complete as a measured blocker. Two optimizer updates, finite gradients, 504/504 changed adapter tensors, adapter save and fresh-process reload passed in each campaign. Neither campaign certifies the required local GPU envelope. No third configuration was attempted.', '',
        '## Runtime and offload proof', '',
        'Reused Python 3.12.10 / torch 2.14.0+cu126 / Transformers 5.17.0 / bitsandbytes 0.50.2 / PEFT 0.21.0 / TRL 1.13.0 / accelerate 1.15.0 / datasets 5.0.1 / safetensors 0.8.0. `pip check` passed; both environment inventories are unchanged. RTX 2060, sm75, CUDA 12.6, no native BF16.', '',
        'Installed source/signatures select `prepare_model_for_kbit_training(..., use_gradient_checkpointing=False)` followed by `model.gradient_checkpointing_enable(offload=True, every_n_layers=1, gradient_checkpointing_kwargs={"use_reentrant": True})`, then LoRA. The top-level Transformers argument is required; passing nested `offload` through PEFT would target PyTorch checkpoint kwargs.', '',
        'The installed `save_on_cpu(pin_memory=True)` hooks were instrumented without changing their copy policy. Each real campaign recorded 288 CUDA-to-pinned-CPU packs and 288 restorations to CUDA across 36 decoder layers and eight microbatches. CPU storage, pinning and restore devices passed independently of the configuration flag. The cheap two-layer random Qwen test proved the path before loading the 4B checkpoint.', '',
        'Only activation checkpoint storage changed in the primary comparison. NF4 double-quantized weights and LoRA remain on CUDA:0, with FP16 compute, SDPA, r=8, alpha=16, dropout=0.05, all-linear targets, batch 1, accumulation 4, two paged_adamw_8bit updates, learning rate 2e-4 and seed 20260917. All 252 quantized modules were checked; 16,515,072 parameters were trainable and 4,022,468,096 base parameters frozen. No model-weight CPU offload or device_map auto was used.', '',
        '## Measured memory and training', '',
        'Physical GPU memory is 6144 MiB by nvidia-smi; the CUDA API reports 6143.5625 MiB capacity. All values below are measured; process peaks cover the complete worker lifetime.', '',
        '| Measurement | HOST_OFFLOAD_1024 | HOST_OFFLOAD_768 |', '|---|---:|---:|',
        '| Initial nvidia-smi free, MiB | '+pair(lambda c:c['monitor']['gpu_initial']['free_MiB'])+' |',
        '| CUDA free before load, MiB | '+pair(lambda c:c['training']['before_load']['free_bytes']/MIB)+' |',
        '| Peak CUDA allocated, MiB | '+pair(lambda c:peak(c,'peak_allocated_bytes'))+' |',
        '| Peak CUDA reserved, MiB | '+pair(lambda c:peak(c,'peak_reserved_bytes'))+' |',
        '| Minimum CUDA free at update boundaries, MiB | '+pair(lambda c:c['comparison']['minimum_cuda_step_headroom_bytes']/MIB)+' |',
        '| Minimum nvidia-smi free sampled, MiB | '+pair(lambda c:c['monitor']['gpu_min_free_MiB'])+' |',
        '| Host RAM total, GiB | '+pair(lambda c:f"{c['monitor']['host_total_bytes']/GIB:.3f}")+' |',
        '| Host available before / minimum, GiB | '+pair(lambda c:f"{c['monitor']['host_available_before_bytes']/GIB:.3f} / {c['monitor']['host_min_available_bytes']/GIB:.3f}")+' |',
        '| Process peak RSS / working set, MiB | '+pair(lambda c:f"{c['monitor']['process_peak_rss_bytes']/MIB:.3f} / {c['monitor']['process_peak_working_set_bytes']/MIB:.3f}")+' |',
        '| Pagefile used before / peak / increase, MiB | '+pair(lambda c:' / '.join(f"{c['monitor'][k]/MIB:.3f}" for k in ('pagefile_used_before_bytes','pagefile_peak_used_bytes','pagefile_peak_delta_bytes')))+' |',
        '| Peak observed live offloaded activations, MiB | '+pair(lambda c:f"{c['training']['offload']['peak_live_host_bytes']/MIB:.3f}")+' |',
        '| Losses (two accumulated updates) | '+pair(lambda c:' / '.join(f"{s['loss']:.6f}" for s in c['training']['steps']))+' |',
        '| Update wall times, seconds | '+pair(lambda c:' / '.join(f"{s['seconds']:.3f}" for s in c['training']['steps']))+' |',
        '| Complete subset rows / rows contributing gradients | 32 / 8 | 32 / 8 |',
        '| Actual optimizer updates / scaler skips | 2 / 0 | 2 / 0 |',
        '| NaN/Inf | None | None |',
        '| Adapter tensors changed / save / reload | 504/504 / PASS / PASS | 504/504 / PASS / PASS |', '',
        'Peak allocated fits below physical capacity in both runs, but zero CUDA free bytes at both step boundaries fails the mandatory headroom requirement. Reserved bytes are not independently used as the rejection criterion. nvidia-smi and CUDA free counters disagree; positive dedicated free does not replace the required CUDA measurement. Optional per-process dedicated/shared PDH measurements are retained in JSON. Shared bytes can include intentional pinned-host memory, so they do not identify all WDDM paging.', '',
        'The independent 200 ms supervisor observed no real host-RAM safety stop, no pagefile growth and no terminated user process. The 12 GiB start requirement and 6 GiB floor held. Unit tests separately simulated low RAM and terminated only an owned dummy process. All watchdogs remained unchanged: tests 120 s, load 300 s, forward/backward 600 s, campaign 1800 s and reload 600 s.', '',
        '## Comparison with frozen no-offload evidence', '',
        f"Historical allocated/reserved peaks were {old['peak_allocated_bytes']/MIB:.4f} / {old['peak_reserved_bytes']/MIB:.0f} MiB; process peak was {old['process_peak_bytes']/MIB:.4f} MiB; update times were 33.172 / 46.656 s. The historical experiment was not rerun.", '',
        '| Difference from historical run | 1024 | 768 |', '|---|---:|---:|',
        '| CUDA peak reduction, MiB / percent | '+pair(lambda c:f"{c['comparison']['cuda_peak_reduction_MiB']:.3f} / {c['comparison']['cuda_peak_reduction_percent']:.2f}%")+' |',
        '| Process peak working-set increase, MiB | '+pair(lambda c:f"{c['comparison']['process_peak_working_set_increase_bytes']/MIB:.3f}")+' |',
        '| Aggregate two-update time ratio | '+pair(lambda c:f"{c['comparison']['aggregate_two_step_time_ratio']:.3f}x")+' |', '',
        'The 1024 aggregate showed no measured slowdown, although its second update took longer. The 768 result also changes sequence lengths and rows, so it cannot isolate the effect of offloading. These tiny-run timings do not predict full-training speed. Minimum proven step-boundary CUDA headroom remains zero for both.', '',
        '## Data, tests and integrity', '',
        'The 1024 subset reuses all 32 historical IDs, their order and full lengths (689–974 tokens); its first optimized row is 962 tokens. The 768 pool contains 934 complete eligible TRAIN examples; selection is seeded and records 32 IDs with lengths 663–767. Three intents have no eligible complete example: argument, close_attempt and counter_offer. The first fallback preparation stopped on that coverage constraint before any 768 model load. A focused selector correction permits coverage of eligible intents and explicitly records omissions; it never shortens JSON. There was exactly one 768 training campaign.', '',
        'Canonical JSON plus EOS are fully supervised; all system/user prompt tokens are -100. enable_thinking=false is preserved and no thinking content is supervised. All masks were checked before model load. Reloads used separate unused TRAIN rows and finite-logit forward passes, with zero generated tokens and no quality assessment. Selected/optimized/reload IDs and adapter config/file sizes/SHA-256 are in the JSON evidence.', '',
        'Fourteen cheap tests passed before the 4B run; the added fallback regression and final 15-test suite passed. Tests cover the installed API, actual tiny-Qwen offload, deterministic complete-row selection, completion masks, blocked evaluation opens, RAM sampling/floor/owned-process stop, historical parsing, verdicts and ignored outputs. No unit test loads Qwen3-4B.', '',
        f"All {e['integrity']['protected_file_count']} protected file hashes and both environment inventories are unchanged. This includes original pinned model shards, accepted corpus, raw datasets, evaluation files, application/planning sources, historical gate source/evidence and historical adapter. Hashing is performed by a separate byte-only auditor. Worker exposure: DEV=0, INTERNAL_TEST=0, tuning eval=0, A01–A16=0. Python audit hooks are not a native-code security sandbox; file hashes prove integrity rather than absence of arbitrary native reads.", '',
        '## Delivery and next decision', '',
        f"Source delivery: `{e['git_source_delivery'].get('commit', 'PENDING')}`; normal origin/main push and 0/0 synchronization are recorded in JSON. This receipt follows in its own normal commit; use `git log -- docs/gates/{GATE}.md` to resolve its self-referential delivery hash. Model/adapter binaries, venv and scratch remain ignored.", '',
        f"Recommend **{e['next_recommendation']}** only: make a separate bounded decision on memory policy/placement before authorizing another training experiment. No full V1 recommendation, model-weight offload implementation, extra configuration, evaluation or G3 integration was started.", '',
        'Official API references: '+', '.join(f'[{name}]({url})' for name,url in REFERENCES.items())+'.', '',
        'STOP — FULL QLORA TRAINING NOT STARTED.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', action='store_true')
    args = parser.parse_args()
    evidence = build()
    if args.preview:
        json_path, receipt_path = SCRATCH/'evidence-preview.json', SCRATCH/'receipt-preview.md'
    else:
        git = evidence['git_source_delivery']
        assert git.get('pushed') and git['ahead'] == git['behind'] == 0 and git['head_equals_origin_main']
        json_path = ROOT/f'docs/gates/evidence/{GATE}.json'
        receipt_path = ROOT/f'docs/gates/{GATE}.md'
        assert not json_path.exists() and not receipt_path.exists(), 'Refusing to overwrite a completed receipt'
    write_json(json_path, evidence)
    receipt_path.write_text(markdown(evidence), encoding='utf-8')
    print(evidence['verdict'])
    print(json_path)
    print(receipt_path)
