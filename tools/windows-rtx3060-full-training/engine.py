"""Shared explicit AMP/update loop, exercised with a CPU synthetic adapter fixture."""
import time
from full_common import atomic, config, legacy, read, require
from checkpoints import Store, restore_engine, save_engine


class Cancelled(RuntimeError):
    pass


class Engine:
    def __init__(self, model, optimizer, scaler, cuda):
        import torch
        self.model, self.optimizer, self.scaler, self.cuda = model, optimizer, scaler, cuda
        # Full-run-only setting: constant 2e-4, no warmup/decay. Advance only on success.
        self.scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda _: 1.0)
        self.actual_calls = 0
        self.optimizer.register_step_post_hook(self._called)

    def _called(self, *unused):
        self.actual_calls += 1

    def synchronize(self):
        if self.cuda:
            import torch
            torch.cuda.synchronize()

    def microbatch(self, row):
        import torch
        loss = self.loss(row)
        require(bool(torch.isfinite(loss)), 'Nonfinite forward loss')
        value = float(loss.detach().item())
        self.scaler.scale(loss / 4).backward()
        self.synchronize()
        return value

    def update(self):
        import torch
        self.scaler.unscale_(self.optimizer)
        parameters = [p for p in self.model.parameters() if p.requires_grad]
        require(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in parameters),
                'Nonfinite/missing gradient: failed group, no cursor advance')
        norm = torch.nn.utils.clip_grad_norm_(parameters, 1.0)
        require(bool(torch.isfinite(norm)), 'Nonfinite gradient norm')
        before = self.actual_calls
        self.scaler.step(self.optimizer)
        self.scaler.update()
        self.synchronize()
        require(self.actual_calls == before + 1, 'AMP_SKIPPED_UPDATE: failed group, no cursor advance')
        require(all(bool(torch.isfinite(p).all()) for p in parameters), 'Nonfinite adapter')
        self.scheduler.step()
        self.optimizer.zero_grad(set_to_none=True)
        return {'gradient_norm': float(norm.item()), 'scaler_scale': self.scaler.get_scale(),
                'optimizer_called': True, 'grad_scaler_skipped': False}


def run_epoch(engine, layout, run, records, resume=None, stopped=lambda: False):
    """One pass. A verified boundary is the only definition of committed progress."""
    store = Store(layout, run)
    total = run['identity']['configuration']['optimizer_updates']
    def check_stop():
        if stopped():
            raise Cancelled('Cancellation requested; last verified checkpoint retained')
    def phase(name):
        atomic(layout.runtime / 'phase.json', {'phase': name, 'started_unix': time.time()})
    if resume:
        path, unused = store.select(resume)
        phase('checkpoint')
        progress = restore_engine(path, engine, run, records.order)
        prior = read(layout.runtime / 'inflight.json') if (layout.runtime / 'inflight.json').exists() else None
        if prior and prior['cursor'] < progress['cursor']:
            prior = None  # the old inflight record's group was durably committed before the crash
        atomic(layout.runtime / 'resume-replay.json', {
            'resume_from': path.name, 'cursor': progress['cursor'],
            'uncommitted_group_discarded': prior,
            'replay_positions': list(range(progress['cursor'], min(progress['cursor'] + 4, total * 4))),
            'reason': 'Only the accumulation group after this verified boundary can be replayed; no silent epoch restart'})
        print('EXPLICIT RESUME: {}; cursor={}; discarded partial group recorded'.format(path.name, progress['cursor']), flush=True)
    else:
        require(not store.committed(), 'Existing checkpoint requires explicit Resume')
        progress = {'run': run, 'optimizer_step': 0, 'cursor': 0, 'epoch': 0, 'skipped_updates': 0,
                    'order_sha256': run['identity']['prepared']['order_sha256'], 'loss_sum': 0.0,
                    'measurements': {}, 'elapsed_seconds': time.time() - run['started_unix']}
        phase('checkpoint')
        save_engine(store, engine, progress, records.order)
    # Initial RNG is committed before the first dropout/gradient operation.
    engine.optimizer.zero_grad(set_to_none=True)
    for step in range(progress['optimizer_step'], total):
        check_stop()
        phase('optimizer_group')
        started = time.monotonic()
        cursor = step * 4
        losses = []
        atomic(layout.runtime / 'inflight.json', {'base_checkpoint': 'step-{:04d}'.format(step),
                                                 'cursor': cursor, 'microbatches_finished': 0,
                                                 'optimizer_called': False})
        for offset in range(4):
            check_stop()
            losses.append(engine.microbatch(records[cursor + offset]))
            atomic(layout.runtime / 'inflight.json', {'base_checkpoint': 'step-{:04d}'.format(step),
                                                     'cursor': cursor, 'microbatches_finished': offset + 1,
                                                     'optimizer_called': False})
        check_stop()
        update = engine.update()
        atomic(layout.runtime / 'inflight.json', {'base_checkpoint': 'step-{:04d}'.format(step),
                                                 'cursor': cursor, 'microbatches_finished': 4,
                                                 'optimizer_called': True})
        measured = engine.measurements()
        if engine.cuda:
            require(measured['free_bytes'] >= config()['hardware_admission']['minimum_boundary_free_bytes'],
                    'CUDA_BOUNDARY_HEADROOM: stop without committing this group')
        progress = dict(progress, optimizer_step=step + 1, cursor=cursor + 4,
                        epoch=1 if step + 1 == total else 0,
                        loss_sum=progress['loss_sum'] + sum(losses),
                        elapsed_seconds=time.time() - run['started_unix'],
                        measurements=dict(measured, **update, mean_record_loss=sum(losses) / 4,
                                          group_seconds=time.monotonic() - started))
        phase('checkpoint')
        path = save_engine(store, engine, progress, records.order)
        atomic(layout.runtime / 'progress.json', {
            'committed_step': step + 1, 'cursor': cursor + 4, 'last_checkpoint': path.name,
            'elapsed_seconds': time.time() - run['started_unix'], 'memory': measured,
            'mean_record_loss': progress['loss_sum'] / (cursor + 4),
            'last_group_and_checkpoint_seconds': time.monotonic() - started,
            'rough_remaining_seconds': (time.monotonic() - started) * (total - step - 1)})
        print('COMMITTED {}/{}; rows={}; loss={:.6f}; checkpoint={}'.format(
            step + 1, total, cursor + 4, sum(losses) / 4, path.name), flush=True)
    return progress
