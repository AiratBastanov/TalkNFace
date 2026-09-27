"""Bounded process ownership, streaming telemetry and fixed Windows safety policy."""
import ctypes
import json
import os
import shutil
import subprocess
import threading
import time
from full_common import NO_WINDOW, atomic, config, legacy, read, require


class OwnedProcess:
    """Windows kill-on-close Job contains this child and its descendants only."""
    def __init__(self, command, **kwargs):
        self.job = None
        if os.name == 'nt':
            from ctypes import wintypes as w
            class Basic(ctypes.Structure):
                _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                            ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                            ('process_limit', w.DWORD), ('affinity', ctypes.c_size_t),
                            ('priority', w.DWORD), ('scheduling', w.DWORD)]
            class Extended(ctypes.Structure):
                _fields_ = [('basic', Basic), ('io', ctypes.c_ulonglong * 6),
                            ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                            ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
            self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            self.kernel.CreateJobObjectW.argtypes = [w.LPVOID, w.LPCWSTR]
            self.kernel.CreateJobObjectW.restype = w.HANDLE
            self.kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, w.LPVOID, w.DWORD]
            self.kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
            self.kernel.CloseHandle.argtypes = [w.HANDLE]
            self.job = self.kernel.CreateJobObjectW(None, None)
            info = Extended()
            info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if not self.job or not self.kernel.SetInformationJobObject(self.job, 9, ctypes.byref(info), ctypes.sizeof(info)):
                self.close()
                raise OSError('Unable to establish owned Windows Job')
        try:
            self.process = subprocess.Popen(command, creationflags=NO_WINDOW, **kwargs)
            if self.job and not self.kernel.AssignProcessToJobObject(self.job, int(self.process._handle)):
                self.process.kill()
                self.process.wait(timeout=10)
                raise OSError('Unable to assign owned process to Job')
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.job:
            self.kernel.CloseHandle(self.job)
            self.job = None
        if hasattr(self, 'process'):
            if self.process.poll() is None:
                self.process.kill()
            self.process.wait(timeout=10)


class RollingLog:
    def __init__(self, path, limit=16777216):
        self.path, self.limit = path, limit
        self.stream = path.open('ab')

    def write(self, data):
        if self.stream.tell() + len(data) > self.limit:
            self.stream.close()
            oldest = self.path.with_suffix(self.path.suffix + '.2')
            if oldest.exists():
                oldest.unlink()
            previous = self.path.with_suffix(self.path.suffix + '.1')
            if previous.exists():
                previous.rename(oldest)
            self.path.rename(previous)
            self.stream = self.path.open('ab')
        self.stream.write(data)
        self.stream.flush()

    def close(self):
        self.stream.close()


class Nvidia:
    def __init__(self):
        self.latest, self.minimum, self.count = None, None, 0
        self.child = OwnedProcess(['nvidia-smi', '--id=0', '--query-gpu=memory.total,memory.used,memory.free,utilization.gpu',
                                   '--format=csv,noheader,nounits', '--loop-ms=200'],
                                  stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        def reader():
            for line in iter(self.child.process.stdout.readline, b''):
                try:
                    total, used, free, util = map(float, line.decode('ascii').strip().split(','))
                    self.latest = {'unix': time.time(), 'total_MiB': total, 'used_MiB': used,
                                   'free_MiB': free, 'utilization_percent': util}
                    self.minimum = free if self.minimum is None else min(self.minimum, free)
                    self.count += 1
                except (ValueError, UnicodeError):
                    pass  # stale measurement causes a bounded stop below
        self.thread = threading.Thread(target=reader, daemon=True)
        self.thread.start()

    def close(self):
        self.child.close()
        self.thread.join(timeout=3)
        self.child.process.stdout.close()


def bounded(command, seconds, runtime, label, env=None, training=False, deadline=None):
    """No ML execution in the supervisor. Native exit codes propagate unchanged."""
    c = config()
    started = time.monotonic()
    stop, stop_at, worker, gpu = None, None, None, None
    monitor = {'samples': 0, 'host_min_available_bytes': None, 'pagefile_initial_bytes': None,
               'pagefile_peak_bytes': None, 'external_gpu_min_free_MiB': None,
               'max_host_sample_gap_seconds': 0, 'last_sample': None}
    runtime.mkdir(parents=True, exist_ok=True)
    log = RollingLog(runtime / (label + '.log'))
    telemetry = RollingLog(runtime / (label + '-telemetry.jsonl')) if training else None
    reader_error = []
    last_tick, last_print, last_disk = started, started, 0
    def request_stop(reason):
        nonlocal stop, stop_at
        if stop is None:
            stop, stop_at = reason, time.monotonic()
            if training:
                atomic(runtime / 'cancel.json', {'reason': reason})
    try:
        if training:
            require(os.name == 'nt', 'Production monitoring requires Windows')
            before = legacy('monitor').host_sample()
            require(before['available_bytes'] >= c['host_memory']['start_min_available_bytes'], 'HOST_RAM_ADMISSION')
            gpu = Nvidia()
        worker = OwnedProcess(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        def reader():
            try:
                # Chunk reads bound memory even if native code emits no newline.
                while True:
                    chunk = worker.process.stdout.read1(4096)
                    if not chunk:
                        break
                    log.write(chunk)
            except Exception as error:
                reader_error.append(type(error).__name__)
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        while worker.process.poll() is None:
            tick = time.monotonic()
            try:
                if tick - started > seconds or (deadline is not None and time.time() > deadline):
                    request_stop('WALL_CLOCK_TIMEOUT')
                if training:
                    host = legacy('monitor').host_sample()
                    page = legacy('monitor').pagefiles()
                    sample = {'unix': time.time(), 'host': host, 'pagefile': page, 'external_gpu': gpu.latest}
                    monitor['samples'] += 1
                    monitor['last_sample'] = sample
                    monitor['max_host_sample_gap_seconds'] = max(monitor['max_host_sample_gap_seconds'], tick - last_tick)
                    v = host['available_bytes']
                    monitor['host_min_available_bytes'] = v if monitor['host_min_available_bytes'] is None else min(v, monitor['host_min_available_bytes'])
                    if v < c['host_memory']['stop_min_available_bytes']:
                        request_stop('HOST_RAM_PRESSURE')
                    if not page.get('available'):
                        request_stop('PAGEFILE_MEASUREMENT_UNAVAILABLE')
                    else:
                        if monitor['pagefile_initial_bytes'] is None:
                            monitor['pagefile_initial_bytes'] = page['used_bytes']
                        monitor['pagefile_peak_bytes'] = max(monitor['pagefile_peak_bytes'] or 0, page['used_bytes'])
                        if page['used_bytes'] - monitor['pagefile_initial_bytes'] > c['host_memory']['max_pagefile_growth_bytes']:
                            request_stop('PAGEFILE_PRESSURE')
                    if tick - started > 10 and (gpu.latest is None or time.time() - gpu.latest['unix'] > 10):
                        request_stop('GPU_TELEMETRY_STALE')
                    if (runtime / 'cancel.json').exists():
                        request_stop('CANCEL_REQUESTED')
                    if (runtime / 'phase.json').exists():
                        p = read(runtime / 'phase.json')
                        budget = c['timeouts_seconds'].get(p['phase'], c['timeouts_seconds']['admission'])
                        if time.time() - p['started_unix'] > budget:
                            request_stop('PHASE_TIMEOUT_' + p['phase'])
                    if tick - last_disk > 5:
                        if shutil.disk_usage(runtime).free < c['disk']['stop_free_bytes']:
                            request_stop('DISK_PRESSURE')
                        last_disk = tick
                    telemetry.write(json.dumps(sample, allow_nan=False).encode() + b'\n')
                if reader_error:
                    request_stop('LOG_WRITE_FAILURE')
                if tick - last_print >= 10:
                    progress = read(runtime / 'progress.json') if (runtime / 'progress.json').exists() else {}
                    print(json.dumps({'phase': label, 'attempt_elapsed_seconds': round(tick - started),
                                      'progress': progress, 'resources': monitor['last_sample']}, allow_nan=False), flush=True)
                    last_print = tick
                if stop_at is not None and tick - stop_at >= (c['timeouts_seconds']['cancel_grace'] if training else 0):
                    worker.close()
                    break
                last_tick = tick
                time.sleep(max(0, 0.2 - (time.monotonic() - tick)))
            except KeyboardInterrupt:
                request_stop('KEYBOARD_INTERRUPT')
        code = worker.process.wait(timeout=10)
        thread.join(timeout=5)
        require(not thread.is_alive(), 'Owned log reader did not exit')
        worker.process.stdout.close()
        if gpu:
            monitor['external_gpu_min_free_MiB'] = gpu.minimum
            monitor['external_gpu_samples'] = gpu.count
        monitor.update(native_returncode=code, stop_reason=stop, seconds=time.monotonic() - started,
                       watchdog_seconds=seconds, owned_worker_pid=worker.process.pid)
        atomic(runtime / (label + '-monitor.json'), monitor, immutable=True)
        return (124 if stop and 'TIMEOUT' in stop else 75 if stop else code), monitor
    finally:
        if worker:
            worker.close()
        if gpu:
            gpu.close()
        log.close()
        if telemetry:
            telemetry.close()
