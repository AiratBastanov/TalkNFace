"""Exactly eight TRAIN microbatches / two updates; TRL collator, explicit AMP loop.

The explicit loop makes GradScaler skips, gradient accumulation, and actual
optimizer calls observable. SFTConfig and the installed TRL completion collator
define the training representation; no Trainer epoch or evaluation is invoked.
"""
import argparse
import hashlib
import os
import threading
import time
import traceback
from common import HERE, MODEL, SCRATCH, ADAPTER, AccessGuard, read_json, write_json, sha256, start_safety_watch
from prepare_smoke_data import verify_labels
from offload import memory, inspect_runtime, prepare_with_offload, OffloadObserver
from configuration import ConfigurationError, validate_config, validate_adapter
from runtime_checks import gpu_snapshot, fair_start


class Deadline:
    def __init__(self, seconds, result, output, stage):
        def expired():
            result.update(watchdog_expired=True, failed_stage=stage)
            write_json(output, result)
            os._exit(124)  # only this gate-owned worker
        self.timer = threading.Timer(seconds, expired)
        self.timer.daemon = True

    def __enter__(self):
        self.timer.start()

    def __exit__(self, *args):
        self.timer.cancel()


def quantized_base():
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    quant = dict(read_json(HERE / 'config.json')['quantization'])
    quant['bnb_4bit_compute_dtype'] = torch.float16
    return AutoModelForCausalLM.from_pretrained(
        MODEL, local_files_only=True, trust_remote_code=False, dtype=torch.float16,
        device_map={'': 0}, quantization_config=BitsAndBytesConfig(**quant), attn_implementation='sdpa')


def tensor_hash(tensor):
    return hashlib.sha256(tensor.detach().float().cpu().contiguous().numpy().tobytes()).hexdigest()


def gradient_snapshot(trainable, scale):
    """Observe accumulated scaled gradients without unscaling/mutating them."""
    import math
    import torch
    grads = [p.grad for n, p in trainable]
    finite = all(g is not None and bool(torch.isfinite(g).all()) for g in grads)
    norms = [float(torch.linalg.vector_norm(g).item()) / scale for g in grads if g is not None]
    norm = math.sqrt(sum(n * n for n in norms))
    return {'gradient_tensors': sum(g is not None for g in grads), 'gradients_finite': finite,
            'gradient_norm': norm if math.isfinite(norm) else None,
            'gradient_norm_kind': 'Accumulated gradient L2, observed scaled values divided by current GradScaler scale',
            'gradient_presence': all(g is not None for g in grads)}


def train(limit, result, output, observer):
    import torch
    import bitsandbytes as bnb
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import AutoTokenizer, Trainer, set_seed
    from trl import SFTConfig
    from trl.trainer.sft_trainer import DataCollatorForLanguageModeling

    config = validate_config()
    assert limit == 1024 and read_json(SCRATCH / 'preflight.json')['passed']
    assert read_json(SCRATCH / 'tests.json')['passed'], 'Cheap tests must pass before model load'
    data = read_json(SCRATCH / f'data-{limit}.json')
    assert data['source'] == config['train'] and data['max_length'] == limit
    assert len(data['rows']) == 32 and all(r['split'] == 'train' and r['length'] <= limit for r in data['rows'])
    spec = read_json(SCRATCH / 'spec-control.json')
    assert [r['id'] for r in data['rows']] == spec['same_historical_selection']['selected_ids']
    assert [r['length'] for r in data['rows']] == spec['same_historical_selection']['lengths']
    assert data['reload_row']['id'] == spec['reload_row_id']
    assert data['rows'][0]['length'] >= 900
    training = dict(config['training'], max_length=limit)
    assert (training['max_steps'], training['gradient_accumulation_steps'], training['per_device_train_batch_size']) == (2, 4, 1)
    args = SFTConfig(output_dir=str(SCRATCH / f'trainer-{limit}'), **training)
    set_seed(args.seed)
    torch.cuda.set_device(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.cuda.reset_peak_memory_stats()
    result.update(configuration=config, sequence_limit=limit, selection=data['selection'], before_load=memory(torch))
    assert result['before_load']['host_available_bytes']>=12*2**30, 'HOST_RAM_PRESSURE before load'
    result['campaign_name']='RTX3070_TARGETED_QV_R8_1024'
    result['gpu_before_load'] = gpu_snapshot(torch)
    result['fair_start'] = fair_start(result['gpu_before_load'])
    if not result['fair_start']['fair']:
        result['gpu_environment_blocked'] = True
        raise RuntimeError('ACTION REQUIRED: close GPU-heavy applications and rerun script 04. No model load occurred.')
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True)
    assert args.completion_only_loss
    # TRL 1.13 moved mask construction into dataset preparation. Its text
    # collator now consumes prebuilt -100 labels (official documented API).
    collator = DataCollatorForLanguageModeling(pad_token_id=tokenizer.pad_token_id)
    for row in data['rows']:
        batch = collator([{k: row[k] for k in ('input_ids', 'labels')}])
        verify_labels(row, batch['labels'][0], tokenizer)
    result['completion_mask'] = {'verified_rows': len(data['rows']), 'prompt_ignored': True,
                                 'complete_json_supervised': True, 'eos_supervised': True,
                                 'enable_thinking': False, 'thinking_supervised': False, 'padding_ignored': True,
                                 'collator': type(collator).__module__ + '.' + type(collator).__name__}
    write_json(output, result)
    load_start = time.monotonic()
    result['model_load_started'] = True
    write_json(output, result)
    with Deadline(300, result, output, 'model_load'):
        model = quantized_base()
    torch.cuda.synchronize()
    modules = [m for m in model.modules() if isinstance(m, bnb.nn.Linear4bit)]
    assert len(modules) == 252 and model.is_loaded_in_4bit
    assert all(m.weight.device.type == 'cuda' and m.weight.dtype == torch.uint8
               and m.weight.quant_state.quant_type == 'nf4' and m.weight.quant_state.nested
               and m.compute_dtype == torch.float16 for m in modules)
    assert all(p.device.type == 'cuda' for p in model.parameters()), 'CPU model offload forbidden'
    result.update(load_seconds=time.monotonic()-load_start, quantized_modules=len(modules),
                  model_memory_footprint_bytes=model.get_memory_footprint(), after_quantized_load=memory(torch))
    model = prepare_with_offload(model)
    assert not any(p.requires_grad for p in model.parameters())
    model = get_peft_model(model, LoraConfig(**config['lora']))
    model.config.use_cache = False
    model.train()
    result['adapter_structure'] = validate_adapter(model)
    assert all(p.device == torch.device('cuda:0') for p in model.parameters()), 'Base and adapters must stay on CUDA:0'
    trainable = [(n, p) for n, p in model.named_parameters() if p.requires_grad]
    assert trainable and all('lora_' in n for n, p in trainable)
    assert all(not p.requires_grad for n, p in model.named_parameters() if 'lora_' not in n)
    assert model.is_gradient_checkpointing and not model.config.use_cache
    trainable_count, total_count = model.get_nb_trainable_parameters()
    result.update(trainable_parameters=trainable_count, total_parameters=total_count,
                  frozen_base_parameters=total_count-trainable_count, all_parameters_on_cuda=True,
                  only_adapters_trainable=True, use_cache=False, gradient_checkpointing=True,
                  after_preparation=memory(torch))
    result['checkpointed_decoder_layers']=sum(type(m).__name__=='Qwen3DecoderLayer' and m.gradient_checkpointing for m in model.modules())
    assert result['checkpointed_decoder_layers']==36
    assert result['after_preparation']['host_available_bytes']>=12*2**30, 'HOST_RAM_PRESSURE before training'
    initial = {n: p.detach().float().cpu().clone() for n, p in trainable}
    initial_hashes = {n: tensor_hash(p) for n, p in trainable}
    # Resolve the exact official Transformers alias, rather than inventing one.
    optimizer_cls, optimizer_kwargs = Trainer.get_optimizer_cls_and_kwargs(args, model)
    optimizer = optimizer_cls([p for n, p in trainable], **optimizer_kwargs)
    assert optimizer.is_paged and optimizer.args.optim_bits == 8
    result['optimizer'] = {'requested': args.optim.value, 'class': type(optimizer).__module__+'.'+type(optimizer).__name__,
                           'is_paged': optimizer.is_paged, 'optim_bits': optimizer.args.optim_bits,
                           'kwargs': optimizer_kwargs}
    scaler = torch.amp.GradScaler('cuda', enabled=args.fp16)
    actual_updates = []
    optimizer.register_step_post_hook(lambda *unused: actual_updates.append(time.monotonic()))
    result.update(steps=[], microbatches=[], actual_optimizer_steps=0, nan_inf=False,
                  instrumentation_note='Microbatch gradient norms and memory snapshots are read-only; timing includes observation overhead.')
    write_json(output, result)
    campaign_start = time.monotonic()
    with Deadline(1800, result, output, 'two_step_campaign'):
        for step in range(args.max_steps):
            step_start = time.monotonic()
            optimizer.zero_grad(set_to_none=True)
            losses = []
            for accumulation in range(args.gradient_accumulation_steps):
                row = data['rows'][step*args.gradient_accumulation_steps+accumulation]
                batch = collator([{k: row[k] for k in ('input_ids', 'labels')}])
                verify_labels(row, batch['labels'][0], tokenizer)
                inputs = {k: v.to('cuda:0') for k, v in batch.items()}
                micro_start = time.monotonic()
                with Deadline(600, result, output, 'forward_backward'):
                    with torch.autocast('cuda', dtype=torch.float16):
                        loss = model(**inputs, use_cache=False).loss
                    if not torch.isfinite(loss):
                        result['nan_inf'] = True
                        raise FloatingPointError('Nonfinite forward loss')
                    losses.append(loss.item())
                    scaler.scale(loss / args.gradient_accumulation_steps).backward()
                    torch.cuda.synchronize()
                grad_observation = gradient_snapshot(trainable, scaler.get_scale())
                if not grad_observation['gradients_finite'] or grad_observation['gradient_norm'] is None:
                    result['nan_inf'] = True
                    raise FloatingPointError('Nonfinite or missing microbatch gradients')
                result['microbatches'].append({'id': row['id'], 'tokens': row['length'], 'loss': losses[-1],
                    'step': step + 1, 'accumulation': accumulation + 1,
                    'seconds': time.monotonic()-micro_start, **grad_observation,
                    'scaler_scale': scaler.get_scale(), 'grad_scaler_skipped': None,
                    'optimizer_update_at_microbatch': False, 'memory': memory(torch)})
                del loss, inputs, batch
                result.update(offload=dict(observer.stats),offload_verified=observer.verified())
                write_json(output, result)
                print(f'microbatch {len(result["microbatches"])}/8 loss={losses[-1]:.6f}', flush=True)
            scaler.unscale_(optimizer)
            grads = [p.grad for n, p in trainable]
            finite = all(g is not None and bool(torch.isfinite(g).all()) for g in grads)
            nonzero = sum(bool(torch.count_nonzero(g)) for g in grads if g is not None)
            if not finite:
                result['nan_inf'] = True
                raise FloatingPointError('Nonfinite or missing adapter gradients')
            assert nonzero > 0
            norm = torch.nn.utils.clip_grad_norm_([p for n, p in trainable], args.max_grad_norm)
            assert torch.isfinite(norm)
            scale_before = scaler.get_scale()
            updates_before = len(actual_updates)
            scaler.step(optimizer)
            scaler.update()
            torch.cuda.synchronize()
            skipped = len(actual_updates) == updates_before
            result['actual_optimizer_steps'] = len(actual_updates)
            result['steps'].append({'step': step+1, 'loss': sum(losses)/len(losses), 'micro_losses': losses,
                                    'row_ids': [r['id'] for r in data['rows'][step*4:step*4+4]],
                                    'token_counts': [r['length'] for r in data['rows'][step*4:step*4+4]],
                                    'seconds': time.monotonic()-step_start, 'scaler_scale_before': scale_before,
                                    'scaler_scale_after': scaler.get_scale(), 'grad_scaler_skipped': skipped,
                                    'gradient_tensors': len(grads), 'nonzero_gradient_tensors': nonzero,
                                    'gradient_norm': norm.item(), 'gradients_finite': finite, 'memory': memory(torch)})
            write_json(output, result)
            assert not skipped, 'GradScaler skipped a required optimizer update'
            assert all(bool(torch.isfinite(p).all()) for n, p in trainable)
    result.update(campaign_seconds=time.monotonic()-campaign_start, after_training=memory(torch))
    result.update(offload=dict(observer.stats),offload_verified=observer.verified())
    assert observer.verified() and observer.stats['contexts']>=36*8
    changes = []
    for name, parameter in trainable:
        final_hash = tensor_hash(parameter)
        if final_hash != initial_hashes[name]:
            changes.append({'name': name, 'initial_sha256': initial_hashes[name], 'final_sha256': final_hash,
                            'max_abs_delta': (parameter.detach().float().cpu()-initial[name]).abs().max().item()})
    assert changes and result['actual_optimizer_steps'] == 2
    result['adapter_change'] = {'changed_tensors': len(changes), 'total_adapter_tensors': len(trainable), 'examples': changes[:4]}
    # Never serialize the quantized base or embeddings, and never merge.
    destination = ADAPTER / str(limit)
    if destination.exists():
        raise FileExistsError('Refusing to replace previous adapter evidence')
    destination.mkdir(parents=True)
    model.save_pretrained(destination, safe_serialization=True, save_embedding_layers=False)
    files = {p.name: {'bytes': p.stat().st_size, 'sha256': sha256(p)} for p in destination.iterdir() if p.is_file()}
    assert 'adapter_model.safetensors' in files and 'adapter_config.json' in files
    result.update(adapter={'path': str(destination), 'files': files, 'config': read_json(destination / 'adapter_config.json')},
                  adapter_final_tensor_hashes={n: tensor_hash(p) for n, p in trainable}, passed=True)
    write_json(output, result)
    optimizer.zero_grad(set_to_none=True)
    del initial, optimizer, model, modules, trainable, grads
    import gc
    gc.collect()
    torch.cuda.empty_cache()
    result['cleanup'] = {'process_exit_releases_remaining_references': True, 'memory_before_exit': memory(torch)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--max-length', type=int, choices=[1024], default=1024)
    args = parser.parse_args()
    authorization = read_json(SCRATCH / 'campaign-started.json')
    assert authorization['gate'] == 'RTX3070_TARGETED_LORA_MEMORY_SMOKE'
    assert authorization['worker_may_start'] and authorization['sequence_limit'] == 1024
    if (SCRATCH / f'train-{args.max_length}.json').exists():
        raise FileExistsError('No unchanged repeated training runs; preserve the existing attempt')
    # Creating the parent is supervisor work; the guard only permits this gate's subtree.
    ADAPTER.mkdir(parents=True, exist_ok=True)
    guard = AccessGuard('train').install()
    start_safety_watch()
    output = SCRATCH / f'train-{args.max_length}.json'
    result = {'passed': False, 'sequence_limit': args.max_length, 'training_kind': 'bounded_manual_TRL_completion_only_loop'}
    try:
        result['runtime']=inspect_runtime()
        with OffloadObserver() as observer:
            train(args.max_length, result, output, observer)
    except Exception as error:
        result.update(error_type=type(error).__name__, error=traceback.format_exc(),
                      configuration_failure=isinstance(error, ConfigurationError),
                      cuda_oom='out of memory' in str(error).lower(),host_ram_pressure='HOST_RAM_PRESSURE' in str(error))
        if 'observer' in locals():
            result.update(offload=dict(observer.stats),offload_verified=observer.verified())
        try:
            import torch
            result['failure_memory'] = memory(torch)
        except Exception:
            pass
        raise
    finally:
        result['audit'] = guard.report()
        write_json(output, result)
