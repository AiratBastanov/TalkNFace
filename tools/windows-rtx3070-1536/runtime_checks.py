"""Remote CUDA identity and tiny NF4 inference-only backend probe; no Qwen load."""
import argparse
import os
import platform
import shutil
import subprocess
import traceback
from common import HERE, ROOT, SCRATCH, read_json, write_json
from environment import capture
from offload import inspect_runtime, memory
from monitor import host_sample, pagefiles


def gpu_snapshot(torch):
    text = subprocess.check_output(['nvidia-smi', '--id=0', '--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,driver_version',
                                    '--format=csv,noheader,nounits'], text=True, timeout=15,
                                    creationflags=subprocess.CREATE_NO_WINDOW).strip()
    name, total, used, free, util, driver = [x.strip() for x in text.split(',')]
    return {'name': name, 'physical_MiB': float(total), 'used_MiB': float(used), 'free_MiB': float(free),
            'utilization_percent': float(util), 'driver': driver, 'cuda_name': torch.cuda.get_device_name(0),
            'capability': list(torch.cuda.get_device_capability(0)), 'cuda_runtime': torch.version.cuda,
            'cuda_capacity_bytes': torch.cuda.get_device_properties(0).total_memory, 'torch': memory(torch)}


def fair_start(snapshot):
    policy = read_json(HERE / 'config.json')['remote_resources']
    checks = {'physical_capacity': snapshot['physical_MiB'] >= policy['physical_vram_min_MiB'],
              'CUDA_capacity': snapshot['cuda_capacity_bytes'] >= 8000 * 2**20,
              'capability_86': snapshot['capability'] == [8, 6],
              'nvidia_free': snapshot['free_MiB'] >= policy['nvidia_min_free_before_training_MiB'],
              'CUDA_free': snapshot['torch']['free_bytes'] >= policy['cuda_min_free_before_training_MiB'] * 2**20}
    return {'fair': all(checks.values()), 'checks': checks, 'policy': policy}


def check(backend=False):
    result = {'passed': False, 'Qwen_model_loaded': False, 'optimizer_updates': 0}
    try:
        result['packages'] = capture()
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('CUDA is unavailable. Verify/update the NVIDIA driver manually from NVIDIA. Do not install CUDA Toolkit.')
        assert not any(os.environ.get(k) for k in ('CUDA_VISIBLE_DEVICES', 'PYTORCH_ALLOC_CONF', 'PYTORCH_CUDA_ALLOC_CONF')), 'Do not set device remapping or allocator overrides for this controlled gate'
        torch.cuda.set_device(0)
        result['gpu'] = gpu_snapshot(torch)
        assert result['gpu']['capability'] == [8, 6] and result['gpu']['physical_MiB'] >= 8000, 'This handoff requires an sm86 / 8 GiB-class NVIDIA GPU'
        assert result['gpu']['cuda_capacity_bytes'] >= 8000 * 2**20 and torch.version.cuda == '12.6'
        result['installed_offload_api'] = inspect_runtime()
        result['host'] = host_sample(); result['pagefile'] = pagefiles()
        assert result['host']['available_bytes'] >= 12 * 2**30, 'Need >=12 GiB physical RAM available'
        result['disk_free_bytes'] = shutil.disk_usage(ROOT).free
        if backend:
            import bitsandbytes as bnb
            from bitsandbytes.cextension import lib
            assert lib.compiled_with_cuda, 'bitsandbytes CUDA backend did not load'
            result['backend'] = {'wrapper': type(lib).__name__, 'compiled_with_cuda': bool(lib.compiled_with_cuda),
                                 'library': str(getattr(getattr(lib, '_lib', None), '_name', 'unknown'))}
            torch.manual_seed(20260917)
            with torch.inference_mode():
                linear = bnb.nn.Linear4bit(128, 64, bias=False, compute_dtype=torch.float16,
                                          compress_statistics=True, quant_type='nf4').to('cuda:0')
                x = torch.randn(4, 128, device='cuda:0', dtype=torch.float16)
                y = linear(x); torch.cuda.synchronize()
                assert y.is_cuda and bool(torch.isfinite(y).all())
                assert linear.weight.dtype == torch.uint8 and linear.weight.quant_state.quant_type == 'nf4' and linear.weight.quant_state.nested
                result['nf4'] = {'executed_on_cuda': True, 'double_quant': True, 'compute_dtype': 'float16',
                                  'finite_output': True, 'backward': False, 'optimizer_updates': 0}
        else:
            assert read_json(SCRATCH / 'cuda-backend.json')['passed'], 'CUDA NF4 preflight missing'
            result['fair_start'] = fair_start(result['gpu'])
            if not result['fair_start']['fair']:
                result['gpu_environment_blocked'] = True
                raise RuntimeError('ACTION REQUIRED: close GPU-heavy applications and rerun script 04.')
            assert result['disk_free_bytes'] >= 5 * 2**30, 'Need >=5 GiB free for runtime/results'
        result['passed'] = True
    except Exception as error:
        result.update(error_type=type(error).__name__, error=traceback.format_exc())
        raise
    finally:
        write_json(SCRATCH / ('cuda-backend.json' if backend else 'preflight.json'), result)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('--backend', action='store_true'); args = parser.parse_args()
    check(args.backend)
    print('CUDA NF4 backend PASS (tiny forward only)' if args.backend else 'Fresh resources PASS; no Qwen model loaded')
