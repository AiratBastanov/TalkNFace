"""Prove CUDA NF4 forward/backward and a real bitsandbytes optimizer update."""
import importlib.metadata
import platform
import subprocess
import sys
import time
import traceback
from common import SCRATCH, AccessGuard, write_json


def memory(torch):
    import psutil
    free, total = torch.cuda.mem_get_info()
    ram = psutil.Process().memory_info()
    return {'free_bytes': free, 'total_bytes': total, 'allocated_bytes': torch.cuda.memory_allocated(),
            'reserved_bytes': torch.cuda.memory_reserved(), 'peak_allocated_bytes': torch.cuda.max_memory_allocated(),
            'peak_reserved_bytes': torch.cuda.max_memory_reserved(), 'rss_bytes': ram.rss,
            'peak_working_set_bytes': getattr(ram, 'peak_wset', ram.rss)}


def preflight(result):
    import torch
    import bitsandbytes as bnb
    from bitsandbytes.cextension import lib
    import peft
    import trl
    from transformers.training_args import OptimizerNames
    versions = {p: importlib.metadata.version(p) for p in ('torch', 'transformers', 'accelerate',
                'safetensors', 'bitsandbytes', 'peft', 'trl', 'datasets', 'psutil')}
    assert versions['torch'] == '2.14.0+cu126' and versions['transformers'] == '5.17.0'
    assert sys.version_info[:3] == (3, 12, 10)
    assert torch.cuda.is_available()
    torch.cuda.set_device(0)
    props = torch.cuda.get_device_properties(0)
    result.update(versions=versions, python=platform.python_version(), platform=platform.platform(),
                  device=props.name, capability=list(torch.cuda.get_device_capability(0)),
                  torch_cuda=torch.version.cuda, native_bf16=torch.cuda.is_bf16_supported(including_emulation=False),
                  before=memory(torch), optimizer_enum=OptimizerNames('paged_adamw_8bit').value)
    assert result['capability'] == [7, 5] and '2060' in props.name
    # CUDA reports 6143.5625 MiB on this WDDM device; nvidia-smi reports
    # physical capacity as 6144 MiB. Do not require byte-exact advertised RAM.
    result['cuda_device_total_bytes'] = props.total_memory
    assert round(props.total_memory / 1024**2) == 6144 and not result['native_bf16']
    assert torch.version.cuda == '12.6'
    result['nvidia_smi'] = subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,memory.free,memory.used,utilization.gpu,driver_version', '--format=csv'], text=True)
    result['backend'] = {'wrapper': type(lib).__name__, 'compiled_with_cuda': bool(lib.compiled_with_cuda),
                         'library': str(getattr(getattr(lib, '_lib', None), '_name', 'unknown'))}
    assert lib.compiled_with_cuda
    torch.manual_seed(20260917)
    linear = bnb.nn.Linear4bit(128, 64, bias=False, compute_dtype=torch.float16,
                              compress_statistics=True, quant_type='nf4').cuda()
    x = torch.randn(4, 128, device='cuda', dtype=torch.float16, requires_grad=True)
    y = linear(x)
    loss = y.float().square().mean()
    loss.backward()
    torch.cuda.synchronize()
    assert y.is_cuda and x.grad is not None and torch.isfinite(x.grad).all()
    assert linear.weight.dtype == torch.uint8 and linear.weight.quant_state.quant_type == 'nf4'
    # Large enough to enter the native 8-bit optimizer path (not its tiny-tensor fallback).
    parameter = torch.nn.Parameter(torch.randn(8192, device='cuda'))
    initial = parameter.detach().clone()
    optimizer = bnb.optim.PagedAdamW8bit([parameter], lr=2e-4)
    parameter.square().mean().backward()
    optimizer.step()
    torch.cuda.synchronize()
    assert not torch.equal(parameter, initial) and torch.isfinite(parameter).all()
    result.update(nf4={'weight_device': str(linear.weight.device), 'weight_dtype': str(linear.weight.dtype),
                      'quant_type': linear.weight.quant_state.quant_type,
                      'double_quant': linear.weight.quant_state.nested, 'output_device': str(y.device),
                      'compute_dtype': str(linear.compute_dtype), 'loss': loss.item(),
                      'input_gradient_finite': True, 'backward_executed': True},
                  optimizer={'class': type(optimizer).__name__, 'is_paged': optimizer.is_paged,
                             'optim_bits': optimizer.args.optim_bits, 'weights_changed': True},
                  after=memory(torch), passed=True)


if __name__ == '__main__':
    guard = AccessGuard('bnb-preflight', tokenizer_only=True).install()
    result = {'passed': False}
    start = time.monotonic()
    try:
        preflight(result)
        print('CUDA NF4 forward/backward and PagedAdamW8bit update passed', flush=True)
    except Exception:
        result['error'] = traceback.format_exc()
        raise
    finally:
        result.update(seconds=time.monotonic()-start, audit=guard.report())
        write_json(SCRATCH / 'preflight.json', result)
