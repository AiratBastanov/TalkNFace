"""Read-only frozen runtime and fair-start checks; no model loading or kernels probe."""
import importlib.metadata
import os
import platform
import subprocess
import sys
import traceback
from common import SCRATCH, AccessGuard, read_json, write_json
from offload import inspect_runtime, memory
from monitor import host_sample, pagefiles

EXPECTED = {'torch': '2.14.0+cu126', 'transformers': '5.17.0', 'bitsandbytes': '0.50.2',
            'peft': '0.21.0', 'trl': '1.13.0', 'accelerate': '1.15.0',
            'datasets': '5.0.1', 'safetensors': '0.8.0'}
FAIR_START_TOLERANCE_BYTES = 256 * 2**20


def runtime():
    versions = {p: importlib.metadata.version(p) for p in EXPECTED}
    check = subprocess.run([sys.executable, '-B', '-m', 'pip', 'check'], capture_output=True,
                           text=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
    return {'python': platform.python_version(), 'versions': versions,
            'pip_check': {'returncode': check.returncode, 'stdout': check.stdout.strip(), 'stderr': check.stderr.strip()},
            'matches': platform.python_version() == '3.12.10' and versions == EXPECTED and check.returncode == 0}


def gpu_snapshot(torch):
    output = subprocess.check_output(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu',
                                      '--format=csv,noheader,nounits'], text=True, timeout=15,
                                     creationflags=subprocess.CREATE_NO_WINDOW).strip()
    name, total, used, free, utilization = [x.strip() for x in output.split(',')]
    return {'name': name, 'physical_MiB': float(total), 'used_MiB': float(used), 'free_MiB': float(free),
            'utilization_percent': float(utilization), 'cuda_name': torch.cuda.get_device_name(0),
            'capability': list(torch.cuda.get_device_capability(0)),
            'cuda_runtime': torch.version.cuda, 'native_bf16': torch.cuda.is_bf16_supported(including_emulation=False),
            'torch': memory(torch)}


def fair_start(snapshot, historical):
    baseline_cuda = historical['training']['before_load']['free_bytes']
    baseline_nvidia = historical['monitor']['gpu_initial']['free_MiB'] * 2**20
    cuda_deficit = baseline_cuda - snapshot['torch']['free_bytes']
    nvidia_deficit = baseline_nvidia - snapshot['free_MiB'] * 2**20
    return {'fair': cuda_deficit <= FAIR_START_TOLERANCE_BYTES and nvidia_deficit <= FAIR_START_TOLERANCE_BYTES,
            'tolerance_bytes': FAIR_START_TOLERANCE_BYTES, 'cuda_free_deficit_bytes': cuda_deficit,
            'nvidia_free_deficit_bytes': nvidia_deficit, 'historical_cuda_free_bytes': baseline_cuda,
            'historical_nvidia_free_bytes': baseline_nvidia}


if __name__ == '__main__':
    result = {'passed': False, 'model_loaded': False}
    # Run pip metadata check before installing the worker data guard: pip may
    # inspect editable metadata. It never installs or changes packages here.
    result['runtime'] = runtime()
    if not result['runtime']['matches']:
        result['blocker'] = 'LOCAL_QWEN_TARGETED_LORA_RUNTIME_DRIFT_BLOCKED'
        write_json(SCRATCH / 'preflight.json', result)
        raise SystemExit(2)
    guard = AccessGuard('preflight', tokenizer_only=True).install()
    try:
        import torch
        assert torch.cuda.is_available()
        result['installed_offload_api'] = inspect_runtime()
        result['allocator_environment'] = {k: os.environ.get(k) for k in ('PYTORCH_ALLOC_CONF', 'PYTORCH_CUDA_ALLOC_CONF')}
        assert not any(result['allocator_environment'].values()), 'Allocator environment differs from historical default'
        result['gpu'] = gpu_snapshot(torch)
        assert result['gpu']['name'] == 'NVIDIA GeForce RTX 2060'
        assert result['gpu']['physical_MiB'] == 6144 and result['gpu']['capability'] == [7, 5]
        assert result['gpu']['cuda_runtime'] == '12.6' and not result['gpu']['native_bf16']
        result['host'] = host_sample()
        result['pagefile'] = pagefiles()
        result['fair_start'] = fair_start(result['gpu'], read_json(SCRATCH / 'comparison-control.json'))
        if not result['fair_start']['fair']:
            result['blocker'] = 'LOCAL_QWEN_TARGETED_LORA_GPU_ENVIRONMENT_BLOCKED'
        elif result['host']['available_bytes'] < 12 * 2**30:
            result['blocker'] = 'LOCAL_QWEN_TARGETED_LORA_MEMORY_SMOKE_FAIL'
            result['reason'] = 'Host RAM below the frozen 12 GiB start floor'
        else:
            result['passed'] = True
    except Exception:
        result['error'] = traceback.format_exc()
        raise
    finally:
        result['audit'] = guard.report()
        write_json(SCRATCH / 'preflight.json', result)
        print('Preflight passed' if result['passed'] else result.get('blocker', 'Preflight failed'), flush=True)
    raise SystemExit(0 if result['passed'] else 2)
