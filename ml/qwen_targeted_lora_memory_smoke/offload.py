"""Installed Transformers checkpoint offload, with metadata-only hook observation."""
import hashlib
import importlib.metadata
import inspect
import weakref
from common import HERE, read_json


def inspect_runtime():
    import torch
    from transformers import PreTrainedModel
    from transformers.models.qwen3.modeling_qwen3 import Qwen3DecoderLayer, Qwen3PreTrainedModel
    from transformers.modeling_layers import GradientCheckpointingLayer
    from peft import prepare_model_for_kbit_training
    expected = {'torch':'2.14.0+cu126','transformers':'5.17.0','bitsandbytes':'0.50.2','peft':'0.21.0',
                'trl':'1.13.0','accelerate':'1.15.0','datasets':'5.0.1','safetensors':'0.8.0'}
    versions = {p:importlib.metadata.version(p) for p in expected}
    assert versions == expected, 'Verified stack changed; no automatic reinstall/upgrade'
    hf = PreTrainedModel.gradient_checkpointing_enable
    assert 'offload' in inspect.signature(hf).parameters
    assert 'gradient_checkpointing_kwargs' in inspect.signature(prepare_model_for_kbit_training).parameters
    assert 'save_on_cpu(pin_memory=True' in inspect.getsource(hf)
    assert issubclass(Qwen3DecoderLayer, GradientCheckpointingLayer) and Qwen3PreTrainedModel.supports_gradient_checkpointing
    functions = {'Transformers.gradient_checkpointing_enable': hf,
                 'PEFT.prepare_model_for_kbit_training': prepare_model_for_kbit_training,
                 'torch.autograd.graph.save_on_cpu': torch.autograd.graph.save_on_cpu}
    return {'versions':versions, 'qwen3_supported':True,
            'functions':{name:{'signature':str(inspect.signature(fn)), 'file':inspect.getsourcefile(fn),
                               'source_sha256':hashlib.sha256(inspect.getsource(fn).encode()).hexdigest()}
                         for name,fn in functions.items()},
            'method':'PEFT preparation without enabling checkpointing; then model.gradient_checkpointing_enable(offload=True, every_n_layers=1, gradient_checkpointing_kwargs={use_reentrant: True})',
            'reentrant_note':'Explicit True preserves the effective PyTorch default used by the historical PEFT kwargs={} path.',
            'nested_offload_kwarg_used':False}


def prepare_with_offload(model):
    from peft import prepare_model_for_kbit_training
    settings = read_json(HERE/'config.json')['activation_offload']
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=False)
    assert not any(p.requires_grad for p in model.parameters())
    model.gradient_checkpointing_enable(offload=settings['offload'], every_n_layers=settings['every_n_layers'],
                                        gradient_checkpointing_kwargs=settings['gradient_checkpointing_kwargs'])
    checkpointed = [m for m in model.modules() if getattr(m,'gradient_checkpointing',False)]
    assert checkpointed
    assert all(m._gradient_checkpointing_func.func.__name__ == 'checkpoint_func' for m in checkpointed
               if hasattr(m,'_gradient_checkpointing_func'))
    return model


class OffloadObserver:
    """Wrap the installed save_on_cpu hooks, never replace their copy policy.

    No activation values are read, retained, serialized or interpreted. CPU
    allocation/device/pinning metadata and restored-device metadata prove the
    exact path. Weak finalizers estimate simultaneous live packed host bytes.
    """
    def __init__(self):
        self.stats = dict(contexts=0,cuda_tensors_packed=0,cuda_tensors_unpacked=0,
                          total_cuda_to_host_bytes=0,live_host_bytes=0,peak_live_host_bytes=0,
                          all_packed_on_cpu=True,all_packed_pinned=True,all_restored_on_cuda=True,examples=[])

    def __enter__(self):
        import transformers.modeling_utils as module
        self.module, self.original = module, module.save_on_cpu
        observer = self
        class ObservedSaveOnCPU(self.original):
            def __init__(self,*args,**kwargs):
                super().__init__(*args,**kwargs)
                observer.stats['contexts'] += 1
                original_pack, original_unpack = self.pack_hook, self.unpack_hook
                def pack(tensor):
                    packed = original_pack(tensor)
                    device, host = packed
                    if tensor.device.type == 'cuda':
                        s=observer.stats; size=tensor.numel()*tensor.element_size()
                        s['cuda_tensors_packed']+=1; s['total_cuda_to_host_bytes']+=size; s['live_host_bytes']+=size
                        s['peak_live_host_bytes']=max(s['peak_live_host_bytes'],s['live_host_bytes'])
                        s['all_packed_on_cpu'] &= host.device.type=='cpu'
                        s['all_packed_pinned'] &= host.is_pinned()
                        assert host.device.type=='cpu' and host.is_pinned()
                        weakref.finalize(host, observer.release, size)
                        if len(s['examples'])<4:
                            s['examples'].append({'shape':list(tensor.shape),'dtype':str(tensor.dtype),'bytes':size,
                                                  'source':str(device),'packed_device':str(host.device),'pinned':host.is_pinned()})
                    return packed
                def unpack(packed):
                    result=original_unpack(packed)
                    if packed[0].type=='cuda':
                        observer.stats['cuda_tensors_unpacked']+=1
                        observer.stats['all_restored_on_cuda'] &= result.device==packed[0]
                        assert result.device==packed[0]
                    return result
                self.pack_hook,self.unpack_hook=pack,unpack
        module.save_on_cpu=ObservedSaveOnCPU
        return self

    def release(self,size):
        self.stats['live_host_bytes']-=size

    def verified(self):
        s=self.stats
        return bool(s['cuda_tensors_packed'] and s['cuda_tensors_unpacked'] and s['all_packed_on_cpu']
                    and s['all_packed_pinned'] and s['all_restored_on_cuda'])

    def __exit__(self,*unused):
        self.module.save_on_cpu=self.original


def memory(torch):
    import psutil
    free,total=torch.cuda.mem_get_info(); process=psutil.Process().memory_info()
    host=psutil.virtual_memory(); swap=psutil.swap_memory()
    return {'free_bytes':free,'total_bytes':total,'allocated_bytes':torch.cuda.memory_allocated(),
            'reserved_bytes':torch.cuda.memory_reserved(),'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
            'peak_reserved_bytes':torch.cuda.max_memory_reserved(),'rss_bytes':process.rss,
            'peak_working_set_bytes':process.peak_wset,'host_total_bytes':host.total,
            'host_available_bytes':host.available,'swap_used_bytes':swap.used}
