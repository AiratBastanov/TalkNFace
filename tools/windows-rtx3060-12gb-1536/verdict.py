"""Fail-closed evidence evaluation. A good archive alone never certifies training."""
import math
from common import HERE, read_json
from policy import hardware_checks, hardware_policy, host_policy
from selection import validate_selection, STEP1, STEP2, RELOAD

PREFIX = 'RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_SMOKE_'


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def audit_ok(audit):
    return (audit['network_allowed'] is False and audit['evaluation_file_reads'] == []
            and audit['denied'] == [] and isinstance(audit['reads'], list) and bool(audit['limitation']))


def monitor_ok(m, budget):
    h = host_policy()
    return (m['returncode'] == 0 and m['worker_exited'] is True and m['stop_reason'] is None
            and m['watchdog_seconds'] == budget and 0 < m['seconds'] <= budget + 15
            and m['samples'] >= 2 and m['gpu_samples'] >= 1
            and m['gpu_initial']['total_MiB'] >= hardware_policy()['physical_vram_min_MiB']
            and finite(m['gpu_min_free_MiB']) and m['gpu_min_free_MiB'] >= 0
            and finite(m['gpu_peak_used_MiB']) and 0 <= m['gpu_peak_used_MiB'] <= m['gpu_initial']['total_MiB']
            and m['gpu_sampler_error'] is None and m['pagefile_available_all'] is True
            and m['gpu_process_counters_available'] is True
            and finite(m['gpu_process_shared_peak_bytes']) and finite(m['gpu_process_dedicated_peak_bytes'])
            and m['host_available_before_bytes'] >= h['start_min_available_bytes']
            and m['host_min_available_bytes'] >= h['stop_min_available_bytes']
            and 0 <= m['pagefile_peak_delta_bytes'] <= h['max_pagefile_growth_bytes']
            and m['unrelated_processes_terminated'] == [])


def decide(train, monitor, reload, integrity, tests, isolation, reload_monitor=None):
    p, h = hardware_policy(), host_policy()
    checks = {}
    def check(name, predicate):
        try: checks[name] = predicate() is True
        except (KeyError, TypeError, ValueError, AssertionError, IndexError, AttributeError): checks[name] = False
    check('functional', lambda: train['passed'] is True and train['model_load_started'] is True and train['full_training_started'] is False)
    check('configuration', lambda: train['configuration'] == read_json(HERE / 'config.json'))
    check('hardware', lambda: all(hardware_checks(train['gpu_before_load']).values()) and train['fair_start']['fair'] is True)
    check('two_updates', lambda: train['actual_optimizer_steps'] == 2 and [s['step'] for s in train['steps']] == [1, 2])
    check('selection', lambda: validate_selection(train['selection']))
    check('executed_lengths', lambda: [m['tokens'] for m in train['microbatches']] == STEP1 + STEP2
          and [m['id'] for m in train['microbatches']] == train['selection']['selected_ids']
          and [m['step'] for m in train['microbatches']] == [1]*4 + [2]*4
          and [m['accumulation'] for m in train['microbatches']] == [1,2,3,4]*2
          and [s['token_counts'] for s in train['steps']] == [STEP1, STEP2]
          and [s['row_ids'] for s in train['steps']] == [train['selection']['optimizer_step_1_ids'], train['selection']['optimizer_step_2_ids']])
    check('finite', lambda: train['nan_inf'] is False and all(finite(s['loss']) and s['gradients_finite'] is True
          and finite(s['gradient_norm']) and s['gradient_tensors'] == 144 for s in train['steps'] + train['microbatches'])
          and all(s['nonzero_gradient_tensors'] > 0 for s in train['steps']))
    check('no_skip', lambda: len(train['steps']) == 2 and all(s['grad_scaler_skipped'] is False for s in train['steps']))
    check('structure', lambda: train['adapter_structure']['trainable_parameters'] == train['trainable_parameters'] == 2949120
          and train['adapter_structure']['A_tensors'] == train['adapter_structure']['B_tensors'] == 72
          and train['adapter_structure']['target_counts'] == {'q_proj':36, 'v_proj':36})
    check('CUDA_frozen_NF4', lambda: train['all_parameters_on_cuda'] is True and train['only_adapters_trainable'] is True
          and train['quantized_modules'] == 252 and train['use_cache'] is False)
    check('optimizer', lambda: train['optimizer']['requested'] == 'paged_adamw_8bit' and train['optimizer']['is_paged'] is True
          and train['optimizer']['optim_bits'] == 8 and train['optimizer']['kwargs']['lr'] == 0.0002)
    check('completion_mask', lambda: all(train['completion_mask'][k] is True for k in
          ('prompt_ignored','complete_json_supervised','eos_supervised','padding_ignored'))
          and train['completion_mask']['verified_rows'] == 8 and train['completion_mask']['thinking_supervised'] is False)
    check('offload', lambda: train['offload_verified'] is True and train['gradient_checkpointing'] is True
          and train['checkpointed_decoder_layers'] == 36 and train['offload']['contexts'] >= 288)
    check('allocation', lambda: 0 < train['after_training']['peak_allocated_bytes'] < train['after_training']['total_bytes']
          and finite(train['after_training']['peak_reserved_bytes']))
    check('headroom', lambda: len(train['steps']) == 2 and all(
          finite(s['memory']['free_bytes']) and p['minimum_boundary_free_bytes'] <= s['memory']['free_bytes'] <= s['memory']['total_bytes']
          and s['memory']['total_bytes'] >= p['cuda_capacity_min_MiB'] * 2**20
          and finite(s['memory']['allocated_bytes']) and finite(s['memory']['reserved_bytes']) for s in train['steps']))
    check('no_oom', lambda: train['cuda_oom'] is False)
    check('RAM', lambda: train['before_load']['host_available_bytes'] >= h['start_min_available_bytes']
          and train['after_preparation']['host_available_bytes'] >= h['start_min_available_bytes']
          and monitor['host_min_available_bytes'] >= h['stop_min_available_bytes'])
    check('pagefile', lambda: monitor['pagefile_available_all'] is True
          and 0 <= monitor['pagefile_peak_delta_bytes'] <= h['max_pagefile_growth_bytes'])
    check('monitor', lambda: monitor_ok(monitor, 1800))
    check('mutation', lambda: 0 < train['adapter_change']['changed_tensors'] <= 144
          and train['adapter_change']['total_adapter_tensors'] == 144
          and all(e['initial_sha256'] != e['final_sha256'] and finite(e['max_abs_delta']) and e['max_abs_delta'] > 0
                  for e in train['adapter_change']['examples']) and bool(train['adapter_change']['examples']))
    check('save', lambda: all(train['adapter']['files'][n]['bytes'] > 0 and len(train['adapter']['files'][n]['sha256']) == 64
          for n in ('adapter_model.safetensors','adapter_config.json')) and len(train['adapter_final_tensor_hashes']) == 144)
    check('saved_adapter_configuration', lambda: all(train['adapter']['config'][k] == train['configuration']['lora'][k]
          for k in ('r','lora_alpha','lora_dropout','bias','task_type'))
          and set(train['adapter']['config']['target_modules']) == {'q_proj','v_proj'})
    check('reload', lambda: reload['passed'] is True and reload['logits_finite'] is True and reload['adapter_tensors_equal'] is True
          and reload['fresh_process'] is True and reload['worker_pid'] != train['worker_pid'] == reload['training_worker_pid']
          and reload['row_id'] == train['selection']['reload_id'] and reload['complete_record_tokens'] == RELOAD
          and 0 < reload['prompt_tokens'] < RELOAD and reload['generated_tokens'] == 0 and reload['quality_evaluation'] is False
          and reload['configured_max_length'] == 1536 and reload['active_adapters'] == ['default'])
    check('reload_monitor', lambda: monitor_ok(reload_monitor, 600))
    check('integrity', lambda: integrity is True)
    check('tests', lambda: tests is True)
    check('isolation', lambda: isolation is True and audit_ok(train['audit']) and audit_ok(reload['audit']))
    failed = [k for k, v in checks.items() if not v]
    free = [s['memory']['free_bytes'] for s in train.get('steps', []) if isinstance(s, dict)
            and isinstance(s.get('memory'), dict) and finite(s['memory'].get('free_bytes'))]
    minimum = min(free) if len(free) == 2 else None
    resource_failure = (train.get('cuda_oom') is True or monitor.get('stop_reason') in ('HOST_RAM_PRESSURE','PAGEFILE_PRESSURE')
                        or (minimum is not None and minimum < p['minimum_boundary_free_bytes']))
    suffix = ('MEMORY_FAIL' if resource_failure else 'FAIL') if failed else (
        'PASS' if minimum >= p['comfortable_boundary_free_bytes'] else 'PASS_TIGHT_MEMORY')
    return {'verdict': PREFIX + suffix, 'checks': checks, 'failed_checks': failed,
            'minimum_boundary_free_bytes': minimum, 'full_training_preparation_authorized': False,
            'next': 'Return this diagnostic archive to the owner. Full training requires a separate decision.'}
