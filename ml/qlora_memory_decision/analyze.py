"""Read-only metadata/API analysis. No model load, forward, backward or update."""
import argparse
from collections import Counter
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT/'.tmp/qlora-memory-decision'
MODEL = ROOT/'AlagModels/Qwen3-4B'
OLD = ROOT/'docs/gates/evidence/LOCAL_QWEN_QLORA_FEASIBILITY_SMOKE.json'
OFFLOAD = ROOT/'docs/gates/evidence/LOCAL_QWEN_QLORA_HOST_RAM_OFFLOAD_CORRECTION.json'
MODULES = ('q_proj', 'k_proj', 'v_proj', 'o_proj', 'gate_proj', 'up_proj', 'down_proj')
PINS = ('328a91d3122359d5547f9d79521205bc0a46e1f79a792dfe650e99fc2d651223',
        '6cd087b316306a68c562436b5492edbcf6e16c6dba3a1308279caa5a58e21ca5',
        'e4bf436957184f4eeb86a80e9db394503f1f56446b2e6b7edeac5b81470f4ca1')


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def snapshot(phase):
    """Separate byte-only auditor; never parses a corpus or evaluation record."""
    if phase == 'before':
        assert not (SCRATCH/'before.json').exists()
        paths = set(read(OFFLOAD)['integrity']['files'])
        paths.update(p for p in subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0') if p)
        for folder in (MODEL, ROOT/'AlagModels/adapters', ROOT/'AlagDatasets'):
            paths.update(p.relative_to(ROOT).as_posix() for p in folder.rglob('*') if p.is_file())
    else:
        paths = read(SCRATCH/'before.json')['files']
    files = {name: {'bytes': (ROOT/name).stat().st_size, 'sha256': digest(ROOT/name)} for name in sorted(paths)}
    for i, pin in enumerate(PINS, 1):
        assert files[f'AlagModels/Qwen3-4B/model-{i:05d}-of-00003.safetensors']['sha256'] == pin
    envs = {}
    for name in ('.venv-ml', '.venv-qlora-smoke'):
        items = {p.relative_to(ROOT/name).as_posix(): [p.stat().st_size, p.stat().st_mtime_ns]
                 for p in (ROOT/name).rglob('*') if p.is_file()}
        envs[name] = {'files': len(items), 'stats_sha256': hashlib.sha256(json.dumps(items, sort_keys=True).encode()).hexdigest()}
    value = {'files': files, 'environments': envs}
    if phase == 'after':
        assert value == read(SCRATCH/'before.json'), 'Protected bytes or environment changed'
    write(SCRATCH/f'{phase}.json', value)
    print(f'{phase}: {len(files)} protected files; pinned shards verified')


def header(path):
    with path.open('rb') as stream:
        size = struct.unpack('<Q', stream.read(8))[0]
        assert 0 < size < 2**20, 'Only a bounded safetensors metadata header may be parsed'
        raw = stream.read(size)
    return json.loads(raw), {'header_bytes': size, 'header_sha256': hashlib.sha256(raw).hexdigest()}


def adapter(shapes, targets, rank):
    selected = [s for s in shapes if s['module'] in targets]
    a_sizes = [rank*s['in'] for s in selected]
    b_sizes = [rank*s['out'] for s in selected]
    n = sum(a_sizes+b_sizes)
    # Installed Optimizer2State: two uint8 states, 2 FP32 absmax values per 256 elements.
    # Two shared 256-element FP32 quantization maps, once per optimizer.
    sizes = a_sizes+b_sizes
    assert all(s >= 4096 for s in sizes)
    moments = 2*n
    scales = 8*sum(math.ceil(s/256) for s in sizes)
    maps = 2*256*4
    return {'targets': list(targets), 'rank': rank, 'target_module_count': len(selected),
            'A_tensors': len(a_sizes), 'B_tensors': len(b_sizes), 'A_parameters': sum(a_sizes),
            'B_parameters': sum(b_sizes), 'trainable_parameters': n,
            'parameter_reduction': 16515072-n, 'parameter_reduction_percent': 100*(1-n/16515072),
            'EXACT_raw_parameter_bytes': {'FP16': n*2, 'BF16': n*2, 'FP32': n*4},
            'ESTIMATED_gradient_bytes': {'FP16_parameters': n*2, 'FP32_parameters': n*4},
            'optimizer_formula': {'two_uint8_moments_bytes': moments, 'FP32_block_scales_bytes': scales,
                                  'shared_quantization_maps_bytes': maps, 'payload_bytes': moments+scales+maps,
                                  'min_tensor_elements': min(sizes), 'max_tensor_elements': max(sizes),
                                  'tensors_meeting_paged_buffer_threshold_100000': sum(s >= 100000 for s in sizes)},
            'ESTIMATED_FP32_weight_gradient_optimizer_payload_bytes': 8*n+moments+scales+maps,
            'activation_shape_proxy': {
                'scope': 'Summed LoRA-A input volumes within ONE recomputed decoder block, not unique saved storage or whole-model live VRAM.',
                'input_elements_per_token_per_layer': sum(s['in'] for s in selected if s['layer'] == 0),
                'FP16_at_1024_bytes': 1024*2*sum(s['in'] for s in selected if s['layer'] == 0),
                'FP32_at_1024_bytes': 1024*4*sum(s['in'] for s in selected if s['layer'] == 0)},
            'classification': 'Parameter counts and raw dtype bytes EXACT. Runtime gradients/state residency and activation effects ESTIMATED; allocator/workspaces excluded.'}


def source_record(obj):
    source = inspect.getsource(obj)
    return {'signature': str(inspect.signature(obj)), 'path': inspect.getsourcefile(obj),
            'source_sha256': hashlib.sha256(source.encode()).hexdigest()}


def analyze():
    os.environ.update(CUDA_VISIBLE_DEVICES='-1', PYTHONDONTWRITEBYTECODE='1', HF_HUB_OFFLINE='1',
                      HF_DATASETS_OFFLINE='1', HF_HOME=str(SCRATCH/'hf'), TMP=str(SCRATCH), TEMP=str(SCRATCH))
    sys.dont_write_bytecode = True
    opened = set()
    def audit(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo'):
            raise PermissionError('Decision analysis is offline')
        if event == 'open' and isinstance(args[0], (str, bytes, os.PathLike)):
            path = Path(os.fsdecode(args[0])).resolve()
            if path.is_relative_to(ROOT) and (path.suffix == '.jsonl' or path.is_relative_to(ROOT/'evals')):
                raise PermissionError('No training/evaluation record access in decision worker')
            if path.is_relative_to(ROOT) and not path.is_relative_to(ROOT/'.venv-qlora-smoke'):
                opened.add(path.relative_to(ROOT).as_posix())
    sys.addaudithook(audit)
    config = read(MODEL/'config.json'); index = read(MODEL/'model.safetensors.index.json')
    tensors = {}; headers = {}
    for shard in sorted(set(index['weight_map'].values())):
        values, headers[shard] = header(MODEL/shard)
        tensors.update({k: v for k, v in values.items() if k != '__metadata__'})
    assert set(tensors) == set(index['weight_map'])
    shapes = []
    for name, tensor in tensors.items():
        parts = name.split('.')
        if len(parts) >= 3 and parts[-2] in MODULES and parts[-1] == 'weight':
            out_dim, in_dim = tensor['shape']
            shapes.append({'name': name, 'module': parts[-2], 'layer': int(parts[2]),
                           'in': in_dim, 'out': out_dim, 'source_dtype': tensor['dtype']})
    h, d, kv, heads, intermediate = (config[k] for k in ('hidden_size', 'head_dim', 'num_key_value_heads', 'num_attention_heads', 'intermediate_size'))
    expected = {'q_proj': (h, heads*d), 'k_proj': (h, kv*d), 'v_proj': (h, kv*d), 'o_proj': (heads*d, h),
                'gate_proj': (h, intermediate), 'up_proj': (h, intermediate), 'down_proj': (intermediate, h)}
    assert len(shapes) == 7*config['num_hidden_layers'] == 252
    for item in shapes:
        assert (item['in'], item['out']) == expected[item['module']]
    assert all(set(s['layer'] for s in shapes if s['module'] == name) == set(range(36)) for name in MODULES)
    candidates = {'all_linear_r8': adapter(shapes, MODULES, 8),
                  'qv_r8': adapter(shapes, ('q_proj', 'v_proj'), 8),
                  'qkvo_r8': adapter(shapes, ('q_proj', 'k_proj', 'v_proj', 'o_proj'), 8),
                  'qv_r4': adapter(shapes, ('q_proj', 'v_proj'), 4)}
    assert candidates['all_linear_r8']['trainable_parameters'] == read(OLD)['training']['trainable_parameters']
    import importlib.metadata
    import torch
    from torch import nn
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from peft.optimizers import create_lorafa_optimizer
    from peft.optimizers.lorafa import LoraFAOptimizer
    from peft.utils.constants import TRANSFORMERS_MODELS_TO_LORA_TARGET_MODULES_MAPPING as mapping
    from peft.tuners.lora.bnb import Linear4bit
    from peft.tuners.tuners_utils import BaseTuner
    from bitsandbytes.optim.optimizer import Optimizer2State, Optimizer8bit
    from transformers.loss.loss_utils import ForCausalLMLoss
    from accelerate import cpu_offload
    assert not torch.cuda.is_available()
    class ProjectionMetadata(nn.Module):
        def __init__(self):
            super().__init__(); self.config = {'model_type': 'qwen3'}
            self.layers = nn.ModuleList([nn.ModuleDict({name: nn.Linear(*dims, bias=False, device='meta')
                                                       for name, dims in expected.items()}) for _ in range(36)])
    # Metadata-only projections: no model implementation, checkpoint tensors or forward exists.
    for name, item in candidates.items():
        peft_model = get_peft_model(ProjectionMetadata(), LoraConfig(r=item['rank'], lora_alpha=16,
                                    target_modules=item['targets'], bias='none'))
        actual = sum(p.numel() for p in peft_model.parameters() if p.requires_grad)
        assert actual == item['trainable_parameters']
        assert all(p.device.type == 'meta' for p in peft_model.parameters())
        item['PEFT_meta_instantiation_verified_parameters'] = actual
        del peft_model
    class Tiny(nn.Module):
        def __init__(self):
            super().__init__(); self.config = {'model_type': 'qwen3'}
            self.q_proj = nn.Linear(16, 12, bias=False)
            self.v_proj = nn.Linear(16, 4, bias=False)
    tiny = get_peft_model(Tiny(), LoraConfig(r=4, lora_alpha=16, bias='none'))
    targets = sorted(tiny.peft_config['default'].target_modules)
    assert targets == sorted(mapping['qwen3']) == ['q_proj', 'v_proj']
    before_trainable = sum(p.numel() for p in tiny.parameters() if p.requires_grad)
    optimizer = create_lorafa_optimizer(tiny, r=4, lora_alpha=16, lr=2e-4)
    trainable = {n: p.numel() for n, p in tiny.named_parameters() if p.requires_grad}
    assert trainable and all('lora_B' in n for n in trainable)
    assert all(not p.requires_grad for n, p in tiny.named_parameters() if 'lora_A' in n)
    assert not optimizer.state and not torch.cuda.is_initialized()
    objects = {'PEFT.create_lorafa_optimizer': create_lorafa_optimizer, 'PEFT.LoraFAOptimizer.step': LoraFAOptimizer.step,
               'PEFT.prepare_model_for_kbit_training': prepare_model_for_kbit_training,
               'PEFT.Linear4bit.forward': Linear4bit.forward, 'PEFT.adapter_dtype': BaseTuner._cast_adapter_dtype,
               'bnb.init_state': Optimizer2State.init_state, 'bnb.get_state_buffer': Optimizer8bit.get_state_buffer,
               'Transformers.ForCausalLMLoss': ForCausalLMLoss, 'Accelerate.cpu_offload': cpu_offload}
    runtime = {'versions': {p: importlib.metadata.version(p) for p in ('torch', 'transformers', 'peft', 'trl', 'bitsandbytes', 'accelerate', 'datasets', 'safetensors')},
               'python': sys.version, 'cuda_visible_devices': os.environ['CUDA_VISIBLE_DEVICES'],
               'cuda_initialized': torch.cuda.is_initialized(),
               'sources': {name: source_record(obj) for name, obj in objects.items()},
               'default_targets': {name: mapping[name] for name in ('qwen3', 'qwen2', 'llama', 'mistral', 'gpt2', 'bloom')},
               'tiny_nontraining_FA_probe': {'targets_resolved_from_default': targets, 'trainable_before': before_trainable,
                                           'trainable_after': sum(trainable.values()), 'A_frozen': True, 'B_trainable': True,
                                           'optimizer': type(optimizer).__name__, 'state_entries': len(optimizer.state),
                                           'forward_calls': 0, 'backward_calls': 0, 'optimizer_steps': 0,
                                           'quantized_compatibility_proven_by_this_probe': False}}
    embedding = math.prod(tensors['model.embed_tokens.weight']['shape'])
    nonquant = sum(math.prod(v['shape']) for k, v in tensors.items() if k not in {s['name'] for s in shapes})
    result = {'module_dimensions': {name: {'in': dims[0], 'out': dims[1], 'count': 36} for name, dims in expected.items()},
              'module_metadata': sorted(shapes, key=lambda s:s['name']), 'headers': headers, 'candidates': candidates,
              'embedding_parameters': embedding, 'nonquantized_parameter_count': nonquant,
              'PEFT_FP16_to_FP32_upcast_additional_raw_bytes': nonquant*2,
              'runtime': runtime, 'input_hashes': {p.relative_to(ROOT).as_posix(): digest(p) for p in
                  (MODEL/'config.json', MODEL/'model.safetensors.index.json', OLD, OFFLOAD,
                   ROOT/'ml/data/synthetic_ru/manifest.json', ROOT/'ml/data/synthetic_ru/token_statistics.json', ROOT/'ml/data/synthetic_ru/next_gate.json')},
              'audit': {'opened_repository_paths': sorted(opened), 'corpus_records_opened': 0, 'evaluation_records_opened': 0,
                        'model_tensor_payloads_loaded': False, 'model_forward_calls': 0,
                        'backward_calls': 0, 'optimizer_steps': 0, 'network_connections': 0}}
    write(SCRATCH/'analysis.json', result)
    for name, item in candidates.items():
        print(name, item['trainable_parameters'], 'parameters; payload MiB', item['ESTIMATED_FP32_weight_gradient_optimizer_payload_bytes']/2**20)


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('operation', choices=('before', 'analyze', 'after')); args = p.parse_args()
    SCRATCH.mkdir(parents=True, exist_ok=True)
    analyze() if args.operation == 'analyze' else snapshot(args.operation)
