"""Exact bounded fallback and verdict policy; no inference from loss quality."""
PREFIX='LOCAL_QWEN_QLORA_'
GATE=PREFIX+'HOST_RAM_OFFLOAD_CORRECTION'


def memory_failure(run):
    if run.get('cuda_oom'): return True
    peak=run.get('after_training',{}).get('peak_allocated_bytes')
    capacity=run.get('before_load',{}).get('total_bytes')
    if peak is not None and capacity is not None and peak>=capacity: return True
    return any(s['memory']['free_bytes']<=0 for s in run.get('steps',[]))


def assess(run,monitor,reload_result=None,primary=None):
    if run.get('host_ram_pressure') or monitor.get('blocked')=='HOST_RAM_PRESSURE' or monitor.get('stop_reason')=='HOST_RAM_PRESSURE':
        return PREFIX+'HOST_RAM_PRESSURE_BLOCKED'
    if monitor.get('host_min_available_bytes',0)<6*2**30:
        return PREFIX+'HOST_RAM_PRESSURE_BLOCKED'
    if not run.get('offload_verified') and run.get('runtime_blocked'):
        return PREFIX+'HOST_OFFLOAD_RUNTIME_BLOCKED'
    if memory_failure(run):
        if run['sequence_limit']==768 and primary and memory_failure(primary):
            return PREFIX+'HOST_OFFLOAD_MEMORY_BLOCKED'
        return 'RETRY_HOST_OFFLOAD_768_AUTHORIZED'
    valid=(run.get('passed') and run.get('actual_optimizer_steps')==2 and run.get('offload_verified')
           and not run.get('nan_inf') and len(run.get('steps',[]))==2
           and all(not s['grad_scaler_skipped'] and s['gradients_finite'] for s in run['steps'])
           and monitor.get('returncode')==0 and not monitor.get('stop_reason')
           and monitor.get('pagefile_peak_delta_bytes',2**60)<=256*2**20
           and monitor.get('gpu_samples',0)>0)
    if not valid: return GATE+'_FAIL'
    if reload_result is None: return 'RELOAD_REQUIRED'
    if not reload_result.get('passed'): return GATE+'_FAIL'
    # Device allocator residency evidence plus nonzero step boundaries is
    # mandatory. Reserved bytes and optional PDH shared bytes alone are not
    # a failure: explicit pinned host activations may appear as shared usage.
    if run['sequence_limit']==768:
        assert primary and memory_failure(primary)
        return GATE+'_PASS_WITH_768_LIMIT'
    headroom=min(s['memory']['free_bytes'] for s in run['steps'])
    return GATE+('_PASS_TIGHT_MEMORY' if headroom<256*2**20 else '_PASS')
