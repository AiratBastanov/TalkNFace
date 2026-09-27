"""CPU-only fixtures. Not reachable from the production workflow."""
import copy
import os
import random
import time
from pathlib import Path
os.environ['CUDA_VISIBLE_DEVICES'] = '-1'  # owner CPU fixtures only, never production
import numpy as np
import torch
from safetensors.torch import load_file, save_file
from checkpoints import rng_state
from engine import Engine
from full_common import HERE, LEGACY, Layout, atomic, config, digest, pin, read
from identity import TRAINING_FILES, prepared_identity

torch.set_num_threads(1)


class TinyAdapter(torch.nn.Module):
    def __init__(self):
        super().__init__()
        self.register_buffer('base', torch.arange(16, dtype=torch.float32).reshape(4, 4) / 50)
        self.lora_A = torch.nn.Parameter(torch.randn(2, 4) / 8)
        self.lora_B = torch.nn.Parameter(torch.zeros(4, 2))
        self.dropout = torch.nn.Dropout(0.05)

    def forward(self, x):
        return self.base @ x + self.lora_B @ (self.lora_A @ self.dropout(x))


class TinyEngine(Engine):
    def __init__(self):
        random.seed(20260917)
        np.random.seed(20260917)
        torch.manual_seed(20260917)
        model = TinyAdapter()
        optimizer = torch.optim.AdamW(model.parameters(), lr=0.0002, betas=(0.9, 0.999), eps=1e-8, weight_decay=0.01)
        super().__init__(model, optimizer, torch.amp.GradScaler('cpu', enabled=True, growth_interval=2), False)

    def loss(self, row):
        x = torch.tensor([row / 9, 0.2, 0.5, -0.1])
        target = x * (0.5 + random.random() / 10 + float(np.random.random()) / 10)
        return torch.nn.functional.mse_loss(self.model(x), target)

    def measurements(self):
        return {'cpu_fixture': True}

    def save_adapter(self, path):
        path.mkdir()
        save_file({k: p.detach().clone() for k, p in self.model.named_parameters()}, path / 'adapter_model.safetensors')
        atomic(path / 'adapter_config.json', dict(config()['lora'], base_model_name_or_path='Qwen/Qwen3-4B',
                                                revision=read(HERE / 'accepted-baseline.json')['model']['revision']))

    def validate_saved_adapter(self, path):
        state = load_file(path / 'adapter_model.safetensors')
        assert set(state) == {'lora_A', 'lora_B'}
        assert all(torch.isfinite(v).all() for v in state.values())

    def load_adapter(self, path):
        self.validate_saved_adapter(path)
        state = load_file(path / 'adapter_model.safetensors')
        with torch.no_grad():
            for k, p in self.model.named_parameters():
                p.copy_(state[k])


class Rows:
    def __init__(self, count):
        from full_data import shuffled_order
        self.order = shuffled_order(count, 20260917)

    def __getitem__(self, i):
        return self.order[i]


def setup(root, updates=3, suffix='fixture'):
    layout = Layout('qwen3-4b-v1-' + suffix, Path(root))
    layout.runtime.mkdir(parents=True)
    rows = Rows(updates * 4)
    files = {'tools/windows-rtx3060-full-training/' + n: pin(HERE / n) for n in TRAINING_FILES}
    source = {'kind': 'full_training_source', 'commit': '1' * 40, 'origin': 'https://github.com/AiratBastanov/TalkNFace.git',
              'files': files, 'files_digest': digest(files)}
    empty_pin = {'bytes': 0, 'sha256': '0' * 64}
    summary = {'rows': updates * 4, 'minimum_length': 4, 'maximum_length': 4, 'rows_above_1536': 0,
               'truncated_rows': 0, 'prompt_masks_verified': updates * 4, 'complete_json_and_eos_verified': updates * 4,
               'order_sha256': digest(rows.order),
               'files': {n: empty_pin for n in ('train-tokens.jsonl', 'order.json', 'offsets.json', 'train-contexts.json')}}
    identity = prepared_identity(read(HERE / 'accepted-baseline.json'), source, {'kind': 'cpu_fixture_runtime'}, summary)
    identity['configuration'] = dict(config(), rows=updates * 4, microbatches=updates * 4, optimizer_updates=updates)
    now = time.time()
    run = {'schema_version': 1, 'kind': 'full_training_run', 'run_id': layout.run_id, 'nonce': 'a' * 32,
           'identity': identity, 'started_unix': now, 'deadline_unix': now + 86400, 'authorization': 'EXPLICIT_START'}
    atomic(layout.runtime / 'prepared.json', {'identity': identity}, immutable=True)
    atomic(layout.runtime / 'run.json', run, immutable=True)
    return layout, run, rows


def equal_tree(a, b):
    if isinstance(a, torch.Tensor):
        return torch.equal(a, b)
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(equal_tree(a[k], b[k]) for k in a)
    if isinstance(a, (list, tuple)):
        return len(a) == len(b) and all(equal_tree(x, y) for x, y in zip(a, b))
    return a == b
