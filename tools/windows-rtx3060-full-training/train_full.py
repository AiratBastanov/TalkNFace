"""Production CUDA path. Called only by an authorized Start or explicit Resume."""
import argparse
import os
import shutil
import time
from full_common import (HERE, MODEL, AccessGuard, Layout, atomic, config, digest, legacy,
                         phase, read, require)
from full_data import TrainRecords
from engine import Engine, run_epoch


class QwenEngine(Engine):
    def __init__(self, tokenizer):
        import torch
        import bitsandbytes as bnb
        from transformers import AutoModelForCausalLM, BitsAndBytesConfig
        from peft import LoraConfig, get_peft_model
        from trl.trainer.sft_trainer import DataCollatorForLanguageModeling
        c = config()
        quant = dict(c['quantization'], bnb_4bit_compute_dtype=torch.float16)
        model = AutoModelForCausalLM.from_pretrained(
            MODEL, local_files_only=True, trust_remote_code=False, dtype=torch.float16,
            device_map={'': 0}, quantization_config=BitsAndBytesConfig(**quant), attn_implementation='sdpa')
        modules = [m for m in model.modules() if isinstance(m, bnb.nn.Linear4bit)]
        require(len(modules) == 252 and model.is_loaded_in_4bit, 'NF4 module count mismatch')
        require(all(m.weight.device.type == 'cuda' and m.weight.dtype == torch.uint8
                    and m.weight.quant_state.quant_type == 'nf4' and m.weight.quant_state.nested
                    and m.compute_dtype == torch.float16 for m in modules), 'Quantization mismatch')
        model = legacy('offload').prepare_with_offload(model)
        # Always initialize a NEW adapter. Resume subsequently restores its full training state.
        model = get_peft_model(model, LoraConfig(**c['lora']))
        model.config.use_cache = False
        model.train()
        legacy('configuration').validate_adapter(model)
        require(all(p.device == torch.device('cuda:0') for p in model.parameters()), 'CPU weight offload forbidden')
        require(model.is_gradient_checkpointing and sum(type(m).__name__ == 'Qwen3DecoderLayer'
                and m.gradient_checkpointing for m in model.modules()) == 36, 'Checkpoint semantics changed')
        require(all(torch.count_nonzero(p).item() == 0 for n, p in model.named_parameters() if '.lora_B.' in n),
                'Fresh adapter must have initial zero B tensors')
        pc = model.peft_config['default']
        pc.base_model_name_or_path = 'Qwen/Qwen3-4B'
        pc.revision = read(HERE / 'accepted-baseline.json')['model']['revision']
        self.tokenizer = tokenizer
        self.collator = DataCollatorForLanguageModeling(pad_token_id=tokenizer.pad_token_id)
        kwargs = {k: v for k, v in c['optimizer'].items() if k not in ('name', 'class')}
        kwargs['betas'] = tuple(kwargs['betas'])
        optimizer = bnb.optim.AdamW([p for p in model.parameters() if p.requires_grad], **kwargs)
        require(optimizer.is_paged and optimizer.args.optim_bits == 8, 'Optimizer changed')
        amp = {k: v for k, v in c['amp'].items() if k != 'skipped_update_policy'}
        super().__init__(model, optimizer, torch.amp.GradScaler('cuda', enabled=True, **amp), True)

    def loss(self, row):
        import torch
        batch = self.collator([{k: row[k] for k in ('input_ids', 'labels')}])
        legacy('prepare_smoke_data').verify_labels(row, batch['labels'][0], self.tokenizer)
        with torch.autocast('cuda', dtype=torch.float16):
            return self.model(**{k: v.to('cuda:0') for k, v in batch.items()}, use_cache=False).loss

    def measurements(self):
        import torch
        return legacy('offload').memory(torch)

    def save_adapter(self, path):
        from peft import get_peft_model_state_dict
        from safetensors.torch import save_file
        path.mkdir()
        # Only LoRA tensors copied to CPU. Never clone/serialize base weights to GPU or disk.
        state = get_peft_model_state_dict(self.model, save_embedding_layers=False)
        require(len(state) == 144 and all('lora_' in k for k in state), 'Non-adapter save forbidden')
        state = {k: v.detach().to('cpu', copy=True).contiguous() for k, v in state.items()}
        save_file(state, path / 'adapter_model.safetensors', metadata={'format': 'pt'})
        self.model.peft_config['default'].save_pretrained(path)

    def validate_saved_adapter(self, path):
        import torch
        from safetensors.torch import load_file
        c = read(path / 'adapter_config.json')
        require(c['base_model_name_or_path'] == 'Qwen/Qwen3-4B'
                and c['revision'] == read(HERE / 'accepted-baseline.json')['model']['revision'], 'Adapter base pin changed')
        for k, v in config()['lora'].items():
            require((sorted(c[k]) == sorted(v)) if k == 'target_modules' else c[k] == v, 'Adapter config mismatch')
        state = load_file(path / 'adapter_model.safetensors', device='cpu')
        require(len(state) == 144 and all('lora_' in k and bool(torch.isfinite(v).all()) for k, v in state.items())
                and sum(v.numel() for v in state.values()) == 2949120, 'Invalid adapter payload')

    def load_adapter(self, path):
        from peft import set_peft_model_state_dict, get_peft_model_state_dict
        from safetensors.torch import load_file
        self.validate_saved_adapter(path)
        state = load_file(path / 'adapter_model.safetensors', device='cpu')
        require(set(state) == set(get_peft_model_state_dict(self.model)), 'Adapter tensor coverage mismatch')
        result = set_peft_model_state_dict(self.model, state)
        require(not result.unexpected_keys and not any('lora_' in k for k in result.missing_keys), 'Adapter restore failed')
        legacy('configuration').validate_adapter(self.model)


def execute(layout, resume):
    # Supervisor must hold a live per-run lock and own this worker. No CLI bypass.
    token = os.environ.get('QWEN_FULL_WORKER_TOKEN')
    lease = read(layout.runtime / 'worker-lease.json')
    import psutil
    require(token and token == lease['token'] and lease['parent_pid'] in [p.pid for p in psutil.Process().parents()],
            'Worker requires supervisor lease')
    run = read(layout.runtime / 'run.json')
    require(time.time() < run['deadline_unix'], 'Run wall-clock budget exhausted')
    AccessGuard(layout).install()
    import torch
    from transformers import AutoTokenizer, set_seed
    require(not any(os.environ.get(k) for k in ('CUDA_VISIBLE_DEVICES', 'PYTORCH_ALLOC_CONF',
                                               'PYTORCH_CUDA_ALLOC_CONF')), 'Device/allocator override forbidden')
    set_seed(config()['seed'])
    torch.cuda.set_device(0)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    snapshot = legacy('runtime_checks').gpu_snapshot(torch)
    require(legacy('runtime_checks').fair_start(snapshot)['fair'], 'Fresh RTX3060 admission failed')
    require(snapshot['torch']['host_available_bytes'] >= config()['host_memory']['start_min_available_bytes'],
            'HOST_RAM_PRESSURE before load')
    hardware = {k: snapshot[k] for k in ('name', 'driver', 'cuda_name', 'capability', 'cuda_runtime', 'physical_MiB')}
    fingerprint = layout.runtime / 'hardware.json'
    if fingerprint.exists():
        require(read(fingerprint) == hardware, 'Resume hardware/driver mismatch')
    else:
        atomic(fingerprint, hardware, immutable=True)
    legacy('offload').inspect_runtime()
    records = TrainRecords(layout.runtime, run['identity']['prepared'])
    tokenizer = AutoTokenizer.from_pretrained(MODEL, local_files_only=True, trust_remote_code=False)
    with legacy('offload').OffloadObserver() as observer:
        with phase(layout, 'load'):
            engine = QwenEngine(tokenizer)
        require(engine.measurements()['host_available_bytes'] >= config()['host_memory']['start_min_available_bytes'],
                'HOST_RAM_PRESSURE before training')
        progress = run_epoch(engine, layout, run, records, resume,
                             stopped=lambda: (layout.runtime / 'cancel.json').exists())
        require(observer.verified() or progress['optimizer_step'] == 2000 and resume == 'step-2000',
                'Pinned activation offload not observed')
        records.close()
    require(progress['cursor'] == 8000 and progress['optimizer_step'] == 2000, 'Incomplete epoch')
    # Facts are immutable. The supervisor will attach the bounded external monitor receipt.
    finish = layout.runtime / 'worker-completed.json'
    facts = {'run_digest': digest(run), 'completed_updates': 2000, 'completed_microbatches': 8000,
             'epochs': 1, 'skipped_updates': 0, 'mean_record_loss': progress['loss_sum'] / 8000,
             'checkpoint': 'step-2000', 'offload_observed': observer.verified(),
             'quality_evaluation': 'NOT_RUN', 'finished_unix': time.time()}
    if not finish.exists():
        atomic(finish, facts, immutable=True)


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--run-id', required=True)
    p.add_argument('--resume')
    a = p.parse_args()
    execute(Layout(a.run_id), a.resume)
