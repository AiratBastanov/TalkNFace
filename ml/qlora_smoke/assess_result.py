"""Conservative gate verdict: process completion alone cannot certify GPU fit."""
PREFIX = 'LOCAL_QWEN_QLORA_'


def assess(preflight, training, reload_result, integrity_changed):
    if not preflight.get('passed'):
        return PREFIX + 'BNB_BACKEND_BLOCKED', ['Native CUDA preflight did not pass']
    failures = []
    if not training.get('passed') or training.get('actual_optimizer_steps') != 2:
        failures.append('Two-update adapter campaign did not pass')
    if training.get('nan_inf'):
        failures.append('Nonfinite training state')
    if not reload_result.get('passed'):
        failures.append('Adapter reload did not pass')
    if integrity_changed:
        failures.append('Protected state changed')
    if training.get('after_training'):
        peak = training['after_training']['peak_allocated_bytes']
        capacity = preflight['cuda_device_total_bytes']
        if peak > capacity:
            failures.append('Peak allocated CUDA bytes exceed physical device capacity; GPU-resident memory fit is not established')
    else:
        failures.append('Training peak-memory measurements missing')
    if failures:
        return PREFIX + 'FEASIBILITY_SMOKE_FAIL', failures
    suffix = 'PASS_WITH_REDUCED_SEQUENCE_LIMIT' if training['sequence_limit'] == 768 else 'PASS'
    return PREFIX + 'FEASIBILITY_SMOKE_' + suffix, []
