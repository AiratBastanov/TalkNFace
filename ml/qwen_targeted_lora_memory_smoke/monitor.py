"""Independent 200 ms host/process safety sampler and read-only GPU telemetry."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
import os
import subprocess
import threading
import time
import psutil
from common import ROOT, HERE, SCRATCH, read_json, write_json, sha256

GIB=2**30


def ram_stop(available):
    return available < 6*GIB


def host_sample():
    physical=psutil.virtual_memory(); swap=psutil.swap_memory()
    return {'total_bytes':physical.total,'available_bytes':physical.available,'used_bytes':physical.used,
            'swap_used_bytes':swap.used,'swap_total_bytes':swap.total}


def pagefiles():
    """Actual system pagefile pages via EnumPageFilesW; process commit is separate."""
    class Info(C.Structure):
        _fields_=[('cb',W.DWORD),('reserved',W.DWORD),('total',C.c_size_t),
                  ('used',C.c_size_t),('peak',C.c_size_t)]
    rows=[]
    callback_type=C.WINFUNCTYPE(W.BOOL,W.LPVOID,C.POINTER(Info),W.LPCWSTR)
    @callback_type
    def callback(context,info,name):
        rows.append((info.contents.total,info.contents.used,info.contents.peak))
        return True
    dll=C.WinDLL('psapi',use_last_error=True)
    dll.EnumPageFilesW.argtypes=[callback_type,W.LPVOID]; dll.EnumPageFilesW.restype=W.BOOL
    if not dll.EnumPageFilesW(callback,None):
        return {'available':False,'error':C.get_last_error()}
    # Windows page size, not allocation granularity; psutil's mmap backend uses it too.
    import mmap
    return {'available':True,'page_size':mmap.PAGESIZE,'total_bytes':sum(r[0] for r in rows)*mmap.PAGESIZE,
            'used_bytes':sum(r[1] for r in rows)*mmap.PAGESIZE,
            'boot_peak_bytes':sum(r[2] for r in rows)*mmap.PAGESIZE}


class GPUCounters:
    """English PDH names avoid a localized PowerShell counter dependency."""
    def __init__(self):
        self.error=None; self.query=W.HANDLE(); self.handles={}
        try:
            self.dll=C.WinDLL('pdh')
            self.dll.PdhOpenQueryW.argtypes=[W.LPCWSTR,C.c_size_t,C.POINTER(W.HANDLE)]
            self.dll.PdhAddEnglishCounterW.argtypes=[W.HANDLE,W.LPCWSTR,C.c_size_t,C.POINTER(W.HANDLE)]
            self.dll.PdhCollectQueryData.argtypes=[W.HANDLE]
            self.dll.PdhGetFormattedCounterArrayW.argtypes=[W.HANDLE,W.DWORD,C.POINTER(W.DWORD),C.POINTER(W.DWORD),W.LPVOID]
            self.dll.PdhCloseQuery.argtypes=[W.HANDLE]
            assert self.dll.PdhOpenQueryW(None,0,C.byref(self.query))==0
            for key,label in [('dedicated_bytes','Dedicated Usage'),('shared_bytes','Shared Usage')]:
                handle=W.HANDLE()
                status=self.dll.PdhAddEnglishCounterW(self.query,'\\GPU Process Memory(*)\\'+label,0,C.byref(handle))
                if status: raise OSError(f'PdhAddEnglishCounterW status {status}')
                self.handles[key]=handle
        except Exception as error:
            self.error=str(error)

    def sample(self,pid):
        if self.error: return {'available':False,'reason':self.error}
        class Value(C.Structure):
            _fields_=[('status',W.DWORD),('value',C.c_double)]
        class Item(C.Structure):
            _fields_=[('name',W.LPWSTR),('value',Value)]
        try:
            self.dll.PdhCollectQueryData(self.query)
            result={'available':True,'pid':pid,'instances':0}
            for key,handle in self.handles.items():
                size,count=W.DWORD(),W.DWORD()
                self.dll.PdhGetFormattedCounterArrayW(handle,0x200,C.byref(size),C.byref(count),None)
                if not size.value: return {'available':False,'reason':'No GPU counter instances yet'}
                buffer=C.create_string_buffer(size.value)
                status=self.dll.PdhGetFormattedCounterArrayW(handle,0x200,C.byref(size),C.byref(count),buffer)
                if status: return {'available':False,'reason':f'PDH status {status}'}
                values=C.cast(buffer,C.POINTER(Item))
                matching=[values[i].value.value for i in range(count.value)
                          if values[i].name.startswith(f'pid_{pid}_') and values[i].value.status in (0,1)]
                result[key]=int(sum(matching)); result['instances']=max(result['instances'],len(matching))
            return result
        except Exception as error:
            return {'available':False,'reason':str(error)}

    def close(self):
        if self.query: self.dll.PdhCloseQuery(self.query)


class NvidiaSampler:
    def __init__(self):
        self.latest=None; self.samples=[]; self.error=None
        command=['nvidia-smi','--query-gpu=memory.total,memory.used,memory.free,utilization.gpu',
                 '--format=csv,noheader,nounits','--loop-ms=200']
        self.process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
                                      creationflags=subprocess.CREATE_NO_WINDOW)
        self.thread=threading.Thread(target=self.read,daemon=True); self.thread.start()

    def read(self):
        for line in self.process.stdout:
            try:
                total,used,free,util=[float(v.strip()) for v in line.split(',')]
                self.latest={'time':time.time(),'total_MiB':total,'used_MiB':used,'free_MiB':free,'utilization_percent':util}
                self.samples.append(self.latest)
            except ValueError:
                self.error=line.strip()

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()  # only our read-only sampler subprocess
        self.process.wait(timeout=10); self.thread.join(timeout=2)
        self.process.stdout.close(); self.process.stderr.close()


def summarize(samples,gpu_samples):
    assert samples
    native=[s['pagefile']['used_bytes'] for s in samples if s['pagefile'].get('available')]
    swap=[s['host']['swap_used_bytes'] for s in samples]
    procs=[s['process'] for s in samples if s.get('process')]
    counters=[s['gpu_process'] for s in samples if s.get('gpu_process',{}).get('available') and s['gpu_process'].get('instances')]
    gaps=[b['time']-a['time'] for a,b in zip(samples,samples[1:])]
    return {'samples':len(samples),'requested_interval_seconds':0.2,'max_sample_gap_seconds':max(gaps,default=0),
            'mean_sample_gap_seconds':sum(gaps)/len(gaps) if gaps else 0,
            'host_total_bytes':samples[0]['host']['total_bytes'],
            'host_available_before_bytes':samples[0]['host']['available_bytes'],
            'host_min_available_bytes':min(s['host']['available_bytes'] for s in samples),
            'process_peak_rss_bytes':max((p['rss'] for p in procs),default=0),
            'process_peak_working_set_bytes':max((p.get('peak_wset',p['rss']) for p in procs),default=0),
            'process_peak_private_commit_bytes':max((p.get('private',0) for p in procs),default=0),
            'process_commit_note':'Process pagefile/private fields are committed bytes, not measured disk paging.',
            'pagefile_source':'EnumPageFilesW' if native else 'psutil.swap_memory fallback',
            'pagefile_used_before_bytes':(native or swap)[0], 'pagefile_peak_used_bytes':max(native or swap),
            'pagefile_peak_delta_bytes':max(native or swap)-(native or swap)[0],
            'swap_used_before_bytes':swap[0],'swap_peak_used_bytes':max(swap),'swap_delta_bytes':max(swap)-swap[0],
            'gpu_samples':len(gpu_samples),
            'gpu_initial':gpu_samples[0] if gpu_samples else None,
            'gpu_min_free_MiB':min((s['free_MiB'] for s in gpu_samples),default=None),
            'gpu_peak_used_MiB':max((s['used_MiB'] for s in gpu_samples),default=None),
            'gpu_process_counters_available':bool(counters),
            'gpu_process_dedicated_peak_bytes':max((s['dedicated_bytes'] for s in counters),default=None),
            'gpu_process_shared_peak_bytes':max((s['shared_bytes'] for s in counters),default=None)}


def terminate_owned(process,record):
    try:
        owner=psutil.Process(process.pid)
        for child in reversed(owner.children(recursive=True)):
            try: child.terminate(); record.append(child.pid)
            except psutil.NoSuchProcess: pass
        owner.terminate(); record.append(owner.pid)
    except psutil.NoSuchProcess:
        pass


def run(name,timeout,command):
    SCRATCH.mkdir(parents=True,exist_ok=True)
    before=host_sample()
    if before['available_bytes']<12*GIB:
        write_json(SCRATCH/f'{name}-monitor.json',{'blocked':'HOST_RAM_PRESSURE','before':before,'worker_started':False})
        return 75
    output=SCRATCH/f'{name}.log'; samples=[]; killed=[]; stop_reason=None
    if output.exists(): raise FileExistsError('No unchanged repeated campaign')
    stop_file=SCRATCH/f'{name}-stop.json'
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',TMP=str(SCRATCH),TEMP=str(SCRATCH),
             QLORA_STOP_FILE=str(stop_file),QLORA_PHASE=name,HF_HUB_OFFLINE='1',HF_DATASETS_OFFLINE='1')
    gpu=NvidiaSampler(); counters=GPUCounters(); start=time.monotonic(); stopped_at=None
    with output.open('x',encoding='utf-8') as log, (SCRATCH/f'{name}-samples.jsonl').open('x',encoding='utf-8') as raw:
        worker=subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
        owner=psutil.Process(worker.pid); worker_pid=worker.pid
        while worker.poll() is None:
            tick=time.monotonic()
            try:
                children=owner.children(recursive=True)
                alive=[p for p in children if p.name().lower()=='python.exe']
            except psutil.NoSuchProcess:
                if worker.poll() is not None: break
                alive=[]
            target=alive[-1] if alive else owner; worker_pid=target.pid
            try: process=target.memory_info()._asdict()
            except psutil.NoSuchProcess: process=None
            sample={'time':time.time(),'elapsed':tick-start,'pid':worker_pid,'host':host_sample(),
                    'pagefile':pagefiles(),'process':process,'gpu':gpu.latest,'gpu_process':counters.sample(worker_pid)}
            samples.append(sample); raw.write(json.dumps(sample)+'\n'); raw.flush()
            if not stop_reason and ram_stop(sample['host']['available_bytes']): stop_reason='HOST_RAM_PRESSURE'
            if not stop_reason and tick-start>timeout: stop_reason='WATCHDOG_EXPIRED'
            if stop_reason and stopped_at is None:
                write_json(stop_file,{'reason':stop_reason}); stopped_at=tick
            if stopped_at is not None and tick-stopped_at>2:
                terminate_owned(worker,killed)
            # wait at most one sample interval; never block the host safety sampler on nvidia-smi.
            time.sleep(max(0,0.2-(time.monotonic()-tick)))
        code=worker.wait(timeout=10)
    gpu.close(); counters.close()
    result=summarize(samples,gpu.samples)
    result.update(returncode=code,stop_reason=stop_reason,seconds=time.monotonic()-start,watchdog_seconds=timeout,
                  worker_pid=worker_pid,launcher_pid=worker.pid,killed_gate_owned_pids=killed,
                  unrelated_processes_terminated=[],raw_samples_sha256=sha256(SCRATCH/f'{name}-samples.jsonl'),
                  gpu_sampler_error=gpu.error,gpu_counter_initial_error=counters.error,worker_exited=True)
    write_json(SCRATCH/f'{name}-monitor.json',result)
    write_json(SCRATCH/f'{name}-gpu-samples.json',gpu.samples)
    print(json.dumps(result),flush=True)
    return code


if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('name');p.add_argument('timeout',type=int);p.add_argument('command',nargs=argparse.REMAINDER)
    a=p.parse_args();raise SystemExit(run(a.name,a.timeout,a.command))
