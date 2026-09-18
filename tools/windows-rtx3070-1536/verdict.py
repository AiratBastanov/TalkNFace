"""1536 envelope acceptance: >=512 MiB enables full-training preparation; [256,512) is diagnostic tight only."""
import math

PREFIX = 'RTX3070_TARGETED_LORA_1536_ENVELOPE_SMOKE_'
MIB = 2**20


def decide(train, monitor, reload, integrity, tests, isolation):
    steps = train.get('steps', []); micro = train.get('microbatches', [])
    after = train.get('after_training', {}); selection = train.get('selection', {})
    free = [s['memory']['free_bytes'] for s in steps]
    minimum = min(free, default=0)
    checks = {
        'functional': train.get('passed', False),
        'two_updates': train.get('actual_optimizer_steps') == 2 and len(steps) == 2,
        'eight_rows': len(micro) == 8,
        'full_TRAIN_envelope': selection.get('source_rows_measured') == selection.get('eligible_rows') == 8000
            and selection.get('configured_max_length') == 1536 and selection.get('observed_max_length') == 1421
            and selection.get('rows_above_limit') == 0 and selection.get('truncated_rows') == 0,
        'finite': not train.get('nan_inf', True) and len(steps) == 2
            and all(math.isfinite(s['loss']) and s.get('gradients_finite', False) for s in steps + micro),
        'no_skip': len(steps) == 2 and all(s['grad_scaler_skipped'] is False for s in steps),
        'structure': train.get('adapter_structure', {}).get('trainable_parameters') == 2949120
            and train.get('adapter_structure', {}).get('A_tensors') == train.get('adapter_structure', {}).get('B_tensors') == 72
            and train.get('adapter_structure', {}).get('target_counts') == {'q_proj': 36, 'v_proj': 36},
        'CUDA_frozen_NF4': train.get('all_parameters_on_cuda', False) and train.get('only_adapters_trainable', False)
            and train.get('quantized_modules') == 252,
        'offload': train.get('offload_verified', False),
        'allocation': 0 < after.get('peak_allocated_bytes', 0) < after.get('total_bytes', 0),
        'headroom': len(free) == 2 and minimum >= 256*MIB,
        'no_oom': not train.get('cuda_oom', False),
        'RAM': monitor.get('host_min_available_bytes', 0) >= 6*2**30
            and train.get('before_load', {}).get('host_available_bytes', 0) >= 12*2**30
            and train.get('after_preparation', {}).get('host_available_bytes', 0) >= 12*2**30,
        'pagefile': monitor.get('pagefile_peak_delta_bytes', math.inf) <= 256*MIB,
        'monitor': monitor.get('returncode') == 0 and not monitor.get('stop_reason')
            and monitor.get('worker_exited', False) and monitor.get('gpu_samples', 0) > 0,
        'mutation': train.get('adapter_change', {}).get('changed_tensors', 0) > 0,
        'save': 'adapter_model.safetensors' in train.get('adapter', {}).get('files', {}),
        'reload': reload.get('passed', False) and reload.get('logits_finite', False)
            and reload.get('adapter_tensors_equal', False),
        'integrity': integrity, 'tests': tests, 'isolation': isolation,
    }
    failed = [k for k, v in checks.items() if not v]
    memory_failed = train.get('cuda_oom', False) or monitor.get('stop_reason') in ('HOST_RAM_PRESSURE', 'PAGEFILE_PRESSURE')
    if after or steps:
        memory_failed |= any(not checks[k] for k in ('allocation', 'headroom', 'RAM', 'pagefile'))
    if failed:
        suffix = 'MEMORY_FAIL' if memory_failed else 'FAIL'
    else:
        suffix = 'PASS' if minimum >= 512*MIB else 'PASS_TIGHT_MEMORY'
    if suffix == 'PASS':
        next_gate = 'QWEN3_4B_FULL_TRAINING_PREPARATION'
    elif suffix == 'PASS_TIGHT_MEMORY' or memory_failed:
        next_gate = 'QWEN3_4B_LARGER_GPU_TRAINING_ARCHITECTURE'
    else:
        next_gate = 'Return result to the project owner; no retry authorized'
    return {'verdict': PREFIX + suffix, 'checks': checks, 'failed_checks': failed,
            'minimum_boundary_free_bytes': minimum if free else None,
            'margin': 'COMFORTABLE' if minimum >= 512*MIB else 'TIGHT' if minimum >= 256*MIB else 'INSUFFICIENT',
            'full_training_preparation_authorized': suffix == 'PASS', 'next': next_gate}
