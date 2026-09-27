"""Atomic, hash-verified optimizer-boundary checkpoints; no model base serialization."""
import os
from pathlib import Path
import re
import shutil
import uuid
from full_common import atomic, digest, no_links, pin, read, require, sha

PAYLOAD = {'adapter/adapter_config.json', 'adapter/adapter_model.safetensors', 'state.pt', 'progress.json'}


def cpu_tree(value):
    import torch
    if isinstance(value, torch.Tensor):
        return value.detach().to('cpu', copy=True)
    if isinstance(value, dict):
        return {k: cpu_tree(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return type(value)(cpu_tree(v) for v in value)
    return value


def rng_state(cuda):
    import random
    import numpy as np
    import torch
    n = np.random.get_state()
    return {'python': random.getstate(), 'numpy': [n[0], n[1].tolist(), n[2], n[3], n[4]],
            'torch': torch.get_rng_state(), 'cuda': torch.cuda.get_rng_state_all() if cuda else []}


def restore_rng(state, cuda):
    import random
    import numpy as np
    import torch
    random.setstate(state['python'])
    n = state['numpy']
    np.random.set_state((n[0], np.array(n[1], dtype=np.uint32), n[2], n[3], n[4]))
    torch.set_rng_state(state['torch'])
    require(bool(state['cuda']) == cuda, 'CUDA RNG state mismatch')
    if cuda:
        torch.cuda.set_rng_state_all(state['cuda'])


def verify_checkpoint(path, run, maximum=536870912):
    path = no_links(path)
    require(path.is_dir(), 'Checkpoint not found')
    members = {p.relative_to(path).as_posix() for p in path.rglob('*') if p.is_file()}
    require(members == PAYLOAD | {'manifest.json', 'COMPLETE.json'}, 'Incomplete/unknown checkpoint files')
    for p in path.rglob('*'):
        no_links(p)
    require(sum(p.stat().st_size for p in path.rglob('*') if p.is_file()) <= maximum, 'Oversized checkpoint')
    marker = read(path / 'COMPLETE.json')
    require(marker == {'manifest_sha256': sha(path / 'manifest.json')}, 'Checkpoint seal mismatch')
    manifest = read(path / 'manifest.json')
    require(set(manifest) == {'schema_version', 'run_digest', 'files'} and manifest['schema_version'] == 1,
            'Unknown checkpoint manifest')
    require(manifest['run_digest'] == digest(run), 'Checkpoint belongs to a different run/config/runtime')
    require(set(manifest['files']) == PAYLOAD, 'Checkpoint manifest coverage mismatch')
    for name, expected in manifest['files'].items():
        require(pin(path / name) == expected, 'Corrupt checkpoint payload: ' + name)
    progress = read(path / 'progress.json')
    require(progress['run'] == run, 'Checkpoint pin mismatch')
    step, cursor = progress['optimizer_step'], progress['cursor']
    total = run['identity']['configuration']['optimizer_updates']
    require(type(step) is int and 0 <= step <= total and cursor == step * 4,
            'Not a complete accumulation boundary')
    require(progress['epoch'] == (1 if step == total else 0) and progress['skipped_updates'] == 0,
            'Wrong epoch or skipped optimizer update')
    require(progress['order_sha256'] == run['identity']['prepared']['order_sha256'], 'Order identity mismatch')
    return progress


class Store:
    def __init__(self, layout, run):
        self.layout, self.run = layout, run
        self.root = layout.checkpoints
        self.maximum = run['identity']['configuration']['checkpoint']['max_bytes']

    def committed(self):
        return sorted(p for p in self.root.glob('step-*') if re.fullmatch(r'step-\d{4}', p.name))

    def select(self, name):
        require(bool(re.fullmatch(r'step-\d{4}', name or '')), 'Explicit checkpoint name required')
        candidates = self.committed()
        require(candidates and candidates[-1].name == name, 'Resume must name the newest committed checkpoint')
        p = self.root / name
        progress = verify_checkpoint(p, self.run, self.maximum)
        # Recover a crash between the durable directory rename and LATEST/journal writes.
        self.publish(p, progress)
        return p, progress

    def publish(self, path, progress):
        seal = sha(path / 'manifest.json')
        atomic(self.root / 'LATEST.json', {'checkpoint': path.name, 'manifest_sha256': seal})
        receipt = {'checkpoint': path.name, 'manifest_sha256': seal, 'run_digest': digest(self.run),
                   **{k: progress[k] for k in ('optimizer_step', 'cursor', 'epoch', 'skipped_updates',
                                               'loss_sum', 'measurements', 'elapsed_seconds')}}
        journal = self.layout.runtime / 'commits' / (path.name + '.json')
        if journal.exists():
            require(read(journal) == receipt, 'Immutable checkpoint receipt differs')
        else:
            atomic(journal, receipt, immutable=True)

    def save(self, progress, writer, validator):
        self.root.mkdir(parents=True, exist_ok=True)
        stage = self.root / ('.incomplete-' + uuid.uuid4().hex)
        stage.mkdir()
        writer(stage)
        atomic(stage / 'progress.json', progress, immutable=True)
        members = {p.relative_to(stage).as_posix() for p in stage.rglob('*') if p.is_file()}
        require(members == PAYLOAD, 'Checkpoint writer emitted unexpected files')
        for p in stage.rglob('*'):
            if p.is_file():
                with p.open('rb+') as stream:
                    os.fsync(stream.fileno())
        manifest = {'schema_version': 1, 'run_digest': digest(self.run),
                    'files': {name: pin(stage / name) for name in sorted(PAYLOAD)}}
        atomic(stage / 'manifest.json', manifest, immutable=True)
        atomic(stage / 'COMPLETE.json', {'manifest_sha256': sha(stage / 'manifest.json')}, immutable=True)
        verify_checkpoint(stage, self.run, self.maximum)
        validator(stage)  # deserialize state on CPU and read safetensors before committing
        target = self.root / 'step-{:04d}'.format(progress['optimizer_step'])
        require(not target.exists(), 'Refusing to overwrite a committed checkpoint')
        stage.rename(target)  # same volume, complete directory becomes visible in one rename
        verify_checkpoint(target, self.run, self.maximum)
        self.publish(target, progress)
        # Keep the previous verified state until the replacement has passed every check.
        candidates = self.committed()
        for old in candidates[:-2]:
            require(no_links(old).parent == no_links(self.root), 'Unsafe retention path')
            verify_checkpoint(old, self.run, self.maximum)
            shutil.rmtree(old)
        return target


def state_payload(engine, order):
    return {'optimizer': cpu_tree(engine.optimizer.state_dict()),
            'scheduler': engine.scheduler.state_dict(), 'scaler': engine.scaler.state_dict(),
            'rng': rng_state(engine.cuda), 'order': list(order)}


def save_engine(store, engine, progress, order):
    import torch
    state = state_payload(engine, order)
    def writer(path):
        engine.save_adapter(path / 'adapter')
        torch.save(state, path / 'state.pt')
    def validate(path):
        loaded = torch.load(path / 'state.pt', map_location='cpu', weights_only=True)
        require(set(loaded) == {'optimizer', 'scheduler', 'scaler', 'rng', 'order'}, 'Missing resume state')
        require(loaded['order'] == order, 'State data-order mismatch')
        engine.validate_saved_adapter(path / 'adapter')
    try:
        return store.save(progress, writer, validate)
    finally:
        restore_rng(state['rng'], engine.cuda)


def restore_engine(path, engine, run, order):
    import torch
    progress = verify_checkpoint(path, run)
    state = torch.load(path / 'state.pt', map_location='cpu', weights_only=True)
    require(set(state) == {'optimizer', 'scheduler', 'scaler', 'rng', 'order'} and state['order'] == order,
            'Missing resume state or data-order mismatch')
    engine.load_adapter(path / 'adapter')
    engine.optimizer.load_state_dict(state['optimizer'])
    engine.scheduler.load_state_dict(state['scheduler'])
    engine.scaler.load_state_dict(state['scaler'])
    require(engine.scheduler.last_epoch == progress['optimizer_step'], 'Scheduler position mismatch')
    restore_rng(state['rng'], engine.cuda)  # last, after model construction/adapter loading
    return progress
