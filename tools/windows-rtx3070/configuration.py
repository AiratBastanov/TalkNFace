"""Fail-closed checks against the decision gate's frozen control projection."""
from collections import Counter
from common import HERE, SCRATCH, read_json


class ConfigurationError(AssertionError):
    pass


def require(condition, message):
    if not condition:
        raise ConfigurationError(message)


def validate_config():
    config = read_json(HERE / 'config.json')
    spec = read_json(SCRATCH / 'spec-control.json')
    require(config == spec['configuration'], 'Configuration drift from frozen decision')
    require(config['lora']['target_modules'] == ['q_proj', 'v_proj'], 'Explicit q/v only')
    require(config['lora']['r'] == 8 and config['retry_sequence_limit'] is None, 'No rank or length retry')
    dimensions = read_json(SCRATCH / 'module-control.json')
    count = sum(dimensions[t]['count'] for t in config['lora']['target_modules'])
    parameters = sum(8 * dimensions[t]['count'] * (dimensions[t]['in'] + dimensions[t]['out'])
                     for t in config['lora']['target_modules'])
    require(parameters == spec['expected_trainable_parameters'] == 2949120, 'Parameter formula mismatch')
    require(count == spec['expected_A_tensors'] == spec['expected_B_tensors'] == 72, 'Tensor formula mismatch')
    return config


def validate_adapter(model):
    """Actual runtime module/tensor assertions, before the first forward."""
    targeted = [(n, m) for n, m in model.named_modules() if hasattr(m, 'lora_A') and len(m.lora_A)]
    counts = Counter(n.rsplit('.', 1)[-1] for n, m in targeted)
    require(counts == {'q_proj': 36, 'v_proj': 36}, 'Expected exactly 36 q + 36 v projections')
    named = list(model.named_parameters())
    a = [(n, p) for n, p in named if '.lora_A.' in n]
    b = [(n, p) for n, p in named if '.lora_B.' in n]
    trainable = [(n, p) for n, p in named if p.requires_grad]
    require(len(a) == len(b) == 72, 'Expected exactly 72 A + 72 B tensors')
    require(set(n for n, p in trainable) == set(n for n, p in a + b), 'Only adapter tensors may train')
    require(all(p.shape[0] == 8 for n, p in a) and all(p.shape[1] == 8 for n, p in b), 'Rank must be 8')
    count = sum(p.numel() for n, p in trainable)
    require(count == 2949120, 'Actual trainable parameters differ from 2,949,120')
    require(all(not p.requires_grad for n, p in named if '.lora_' not in n), 'Base must be frozen')
    return {'target_counts': dict(counts), 'A_tensors': len(a), 'B_tensors': len(b),
            'trainable_parameters': count, 'adapter_dtypes': sorted({str(p.dtype) for n, p in trainable}),
            'parameter_bytes': sum(p.numel() * p.element_size() for n, p in trainable)}
