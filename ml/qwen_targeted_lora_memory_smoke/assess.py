"""Fixed acceptance thresholds. Functional completion alone cannot pass the gate."""
import math

PREFIX = 'LOCAL_QWEN_TARGETED_LORA_'
MIB = 2**20


def assess(training, monitor, reload, *, integrity, tests, isolation, preflight):
    if preflight.get('blocker'):
        return {'verdict': preflight['blocker'], 'margin': 'NOT_MEASURED', 'failed_checks': ['precondition']}
    if training.get('configuration_failure'):
        return {'verdict': PREFIX + 'CONFIGURATION_FAIL', 'margin': 'NOT_MEASURED', 'failed_checks': ['adapter_configuration']}
    if training.get('gpu_environment_blocked'):
        return {'verdict': PREFIX + 'GPU_ENVIRONMENT_BLOCKED', 'margin': 'NOT_MEASURED', 'failed_checks': ['fair_start']}
    steps = training.get('steps', [])
    micros = training.get('microbatches', [])
    after = training.get('after_training', {})
    free = [s['memory']['free_bytes'] for s in steps]
    minimum = min(free, default=0)
    structure = training.get('adapter_structure', {})
    checks = {
        'preflight': preflight.get('passed', False),
        'functional_training': training.get('passed', False),
        'exact_adapter': structure.get('target_counts') == {'q_proj': 36, 'v_proj': 36}
            and structure.get('A_tensors') == structure.get('B_tensors') == 72
            and structure.get('trainable_parameters') == 2949120,
        'base_frozen_cuda_nf4': training.get('only_adapters_trainable', False)
            and training.get('all_parameters_on_cuda', False) and training.get('quantized_modules') == 252,
        'offload': training.get('offload_verified', False),
        'two_updates': training.get('actual_optimizer_steps') == 2 and len(steps) == 2,
        'eight_microbatches': len(micros) == 8,
        'finite_losses': len(steps) == 2 and all(math.isfinite(s['loss']) for s in steps + micros),
        'finite_gradients': len(micros) == 8 and all(s.get('gradients_finite', False) and
            s.get('gradient_tensors', 0) == 144 and math.isfinite(s.get('gradient_norm', math.inf)) for s in steps + micros),
        'no_skipped_update': len(steps) == 2 and all(s.get('grad_scaler_skipped') is False for s in steps),
        'no_nan_inf_oom': not training.get('nan_inf', True) and not training.get('cuda_oom', False),
        'allocated_fits': 0 < after.get('peak_allocated_bytes', 0) < after.get('total_bytes', 0),
        'boundary_headroom': len(free) == 2 and minimum >= 256 * MIB,
        'host_start': training.get('before_load', {}).get('host_available_bytes', 0) >= 12 * 2**30
            and training.get('after_preparation', {}).get('host_available_bytes', 0) >= 12 * 2**30,
        'host_floor': monitor.get('host_min_available_bytes', 0) >= 6 * 2**30,
        'pagefile': monitor.get('pagefile_peak_delta_bytes', math.inf) <= 256 * MIB,
        'supervisor': monitor.get('returncode') == 0 and monitor.get('stop_reason') is None
            and monitor.get('worker_exited', False) and monitor.get('gpu_samples', 0) > 0,
        'no_watchdog': not training.get('watchdog_expired', False),
        'adapter_mutation': training.get('adapter_change', {}).get('changed_tensors', 0) > 0,
        'adapter_only_save': 'adapter_model.safetensors' in training.get('adapter', {}).get('files', {})
            and 'adapter_config.json' in training.get('adapter', {}).get('files', {}),
        'fresh_reload': reload.get('passed', False) and reload.get('adapter_tensors_equal', False)
            and reload.get('logits_finite', False),
        'oversubscription_review': training.get('no_unexplained_oversubscription', False),
        'integrity': integrity, 'tests': tests, 'isolation': isolation,
    }
    failed = [name for name, passed in checks.items() if not passed]
    return {'verdict': PREFIX + 'MEMORY_SMOKE_' + ('FAIL' if failed else 'PASS'),
            'margin': 'COMFORTABLE' if minimum >= 512 * MIB else 'ACCEPTABLE' if minimum >= 256 * MIB else 'INSUFFICIENT',
            'minimum_boundary_free_bytes': minimum, 'checks': checks, 'failed_checks': failed}
