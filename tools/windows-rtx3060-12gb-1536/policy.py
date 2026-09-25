"""One hardware policy: config.json, shared with PowerShell and all workers."""
import re
from common import HERE, read_json


def hardware_policy():
    return read_json(HERE / 'config.json')['remote_resources']


def host_policy():
    return read_json(HERE / 'config.json')['host_memory']


def target_name(name):
    return isinstance(name, str) and re.fullmatch(hardware_policy()['gpu_name_pattern'], name.strip(), re.I) is not None


def hardware_checks(snapshot, training=True):
    p = hardware_policy()
    checks = {
        'desktop_RTX3060_name': target_name(snapshot['name']) and target_name(snapshot['cuda_name']),
        'physical_capacity': snapshot['physical_MiB'] >= p['physical_vram_min_MiB'],
        'CUDA_capacity': snapshot['cuda_capacity_bytes'] >= p['cuda_capacity_min_MiB'] * 2**20,
        'capability': snapshot['capability'] == p['gpu_capability'],
        'CUDA_runtime': snapshot['cuda_runtime'] == '12.6',
    }
    if training:
        checks.update(nvidia_free=snapshot['free_MiB'] >= p['nvidia_min_free_before_training_MiB'],
                      CUDA_free=snapshot['torch']['free_bytes'] >= p['cuda_min_free_before_training_MiB'] * 2**20)
    return checks
