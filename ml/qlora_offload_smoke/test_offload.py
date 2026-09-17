"""Cheap API, CUDA hook, boundary, monitor and verdict tests; no 4B checkpoint."""
import copy
import json
import os
import subprocess
import sys
import unittest
from unittest.mock import patch
from common import ROOT,HERE,SCRATCH,MODEL,DATA,TRAIN,ADAPTER,FORBIDDEN,AccessGuard,read_json,write_json,configure_offline
from prepare_smoke_data import train_rows,select,verify_labels
from offload import inspect_runtime,OffloadObserver,prepare_with_offload
from monitor import host_sample,pagefiles,ram_stop,summarize,run
from integrity import historical_projection,HISTORY
from assess import assess,memory_failure,GATE,PREFIX


class OffloadTests(unittest.TestCase):
    def test_installed_api_and_versions(self):
        info=inspect_runtime()
        self.assertTrue(info['qwen3_supported'])
        self.assertFalse(info['nested_offload_kwarg_used'])
        write_json(SCRATCH/'runtime-api.json',info)

    def test_tiny_qwen_selects_host_checkpoint_path_and_restores_gradients(self):
        import torch
        from transformers import Qwen3Config,Qwen3ForCausalLM
        from peft import LoraConfig,get_peft_model
        config=Qwen3Config(vocab_size=128,hidden_size=32,intermediate_size=64,num_hidden_layers=2,
                          num_attention_heads=4,num_key_value_heads=2,head_dim=8,max_position_embeddings=64)
        model=Qwen3ForCausalLM(config).cuda()
        with OffloadObserver() as observer:
            model=prepare_with_offload(model)
            model=get_peft_model(model,LoraConfig(**read_json(HERE/'config.json')['lora']))
            model.config.use_cache=False;model.train()
            tokens=torch.arange(16,device='cuda').unsqueeze(0)
            with torch.autocast('cuda',dtype=torch.float16):
                loss=model(input_ids=tokens,labels=tokens).loss
            loss.backward();torch.cuda.synchronize()
            self.assertTrue(observer.verified())
            self.assertGreaterEqual(observer.stats['contexts'],2)
            self.assertGreater(observer.stats['peak_live_host_bytes'],0)
            self.assertTrue(all(p.grad is not None and bool(torch.isfinite(p.grad).all()) for p in model.parameters() if p.requires_grad))
            write_json(SCRATCH/'tiny-offload-proof.json',{'passed':True,'checkpoint_loaded':False,'layers':2,
                                                       'loss_finite':bool(torch.isfinite(loss)),'observations':observer.stats})
        del model,loss;torch.cuda.empty_cache()

    def test_historical_parser(self):
        parsed=historical_projection(read_json(HISTORY))
        self.assertEqual(parsed['peak_allocated_bytes']/2**20,6234.4541015625)
        self.assertEqual(len(parsed['selection']['selected_ids']),32)
        self.assertEqual(parsed['configuration']['training'],read_json(HERE/'config.json')['training'])

    def test_historical_ids_and_complete_labels_reused(self):
        from transformers import AutoTokenizer
        from trl.trainer.sft_trainer import DataCollatorForLanguageModeling
        data=read_json(SCRATCH/'data-1024.json');control=read_json(SCRATCH/'selection-control.json')
        self.assertEqual(data['selection']['selected_ids'],control['selected_ids'])
        self.assertEqual(data['selection']['lengths'],control['lengths'])
        self.assertNotIn(data['reload_row']['id'],control['selected_ids'])
        tokenizer=AutoTokenizer.from_pretrained(MODEL,local_files_only=True)
        collator=DataCollatorForLanguageModeling(pad_token_id=tokenizer.pad_token_id)
        for row in data['rows']+[data['reload_row']]:
            self.assertEqual(row['split'],'train');self.assertLessEqual(row['length'],1024)
            batch=collator([{k:row[k] for k in ('input_ids','labels')}])
            verify_labels(row,batch['labels'][0],tokenizer)
            self.assertNotIn('<think>',row['json'])
        bad=list(data['rows'][0]['labels']);bad[0]=1
        with self.assertRaises(AssertionError):verify_labels(data['rows'][0],bad,tokenizer)

    def test_train_only_path(self):
        for path in FORBIDDEN:
            with self.assertRaises(PermissionError):next(train_rows(path))

    def test_deterministic_complete_length_selection(self):
        rows=[dict(id=f'fixture-{i}',intent='offer',tags=['negation','ambiguity','prompt_injection'],length=700+i) for i in range(400)]
        original=copy.deepcopy(rows)
        first,_=select(rows,768);second,_=select(list(reversed(rows)),768)
        self.assertEqual(first,second);self.assertEqual(rows,original)
        self.assertTrue(all(r['length']<=768 for r in first))

    def test_unavailable_long_intent_is_excluded_without_target_truncation(self):
        rows=[dict(id=f'fixture-{i}',intent='ask_question',tags=['negation'],length=700+i) for i in range(60)]
        rows.append(dict(id='complete-long-offer',intent='offer',tags=['ambiguity'],length=900))
        first,_=select(rows,768)
        self.assertEqual(len(first),32)
        self.assertTrue(all(r['intent']=='ask_question' for r in first))
        self.assertEqual(rows[-1]['length'],900)

    def test_guard_and_no_historical_overwrite(self):
        guard=AccessGuard('unit')
        for path in (*FORBIDDEN,DATA/'contexts.json',ROOT/'.tmp/qlora-smoke/data-1024.json',HISTORY):
            with self.assertRaises(PermissionError):guard.check(path)
        for path in (ROOT/'ml/qlora_smoke/config.json',MODEL/'config.json',
                     ROOT/'AlagModels/adapters/qlora-feasibility-smoke/1024/adapter_model.safetensors'):
            with self.assertRaises(PermissionError):guard.check(path,True)
        guard.check(SCRATCH/'train-contexts.json');guard.check(ADAPTER/'1024/adapter_config.json',True)

    def test_audit_hook_blocks_real_opens_before_read(self):
        code=('from common import *\ng=AccessGuard("test").install()\n'
              'for p in FORBIDDEN:\n'
              ' try:p.read_bytes()\n'
              ' except PermissionError:pass\n'
              ' else:raise AssertionError("exposure")\n'
              'assert len(g.denied)==4\n')
        result=subprocess.run([sys.executable,'-B','-c',code],cwd=HERE,capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_host_memory_and_native_pagefile_sampler(self):
        sample=host_sample();pf=pagefiles()
        self.assertGreater(sample['total_bytes'],30*2**30)
        self.assertGreater(sample['available_bytes'],0)
        self.assertIn('available',pf)
        if pf['available']:self.assertLessEqual(pf['used_bytes'],pf['total_bytes'])

    def test_ram_floor_boundaries(self):
        self.assertFalse(ram_stop(6*2**30));self.assertTrue(ram_stop(6*2**30-1))

    def test_sampler_summary(self):
        samples=[{'time':t,'host':{'total_bytes':32,'available_bytes':20-t,'swap_used_bytes':t},
                  'pagefile':{'available':True,'used_bytes':t},'process':{'rss':t+1,'peak_wset':t+2,'private':t+3}}
                 for t in (0,1)]
        result=summarize(samples,[])
        self.assertEqual(result['host_min_available_bytes'],19)
        self.assertEqual(result['pagefile_peak_delta_bytes'],1)

    def test_monitor_terminates_only_owned_dummy_on_simulated_pressure(self):
        real=host_sample();high=dict(real,available_bytes=20*2**30);low=dict(real,available_bytes=5*2**30)
        name=f'unit-safety-{os.getpid()}'
        with patch('monitor.host_sample',side_effect=[high]+[low]*100):
            code=run(name,10,[sys.executable,'-B','-c','import time;time.sleep(20)'])
        result=read_json(SCRATCH/f'{name}-monitor.json')
        self.assertNotEqual(code,0);self.assertEqual(result['stop_reason'],'HOST_RAM_PRESSURE')
        self.assertEqual(result['unrelated_processes_terminated'],[])
        self.assertTrue(result['killed_gate_owned_pids'])

    def test_verdict_and_bounded_retry(self):
        training={'passed':True,'actual_optimizer_steps':2,'offload_verified':True,'sequence_limit':1024,
                  'before_load':{'total_bytes':6144*2**20},'after_training':{'peak_allocated_bytes':5000*2**20},
                  'steps':[{'memory':{'free_bytes':300*2**20},'grad_scaler_skipped':False,'gradients_finite':True}]*2}
        monitor={'host_min_available_bytes':10*2**30,'returncode':0,'pagefile_peak_delta_bytes':0,'gpu_samples':10}
        self.assertEqual(assess(training,monitor,{'passed':True}),GATE+'_PASS')
        tight=copy.deepcopy(training);tight['steps'][0]['memory']['free_bytes']=100*2**20
        self.assertEqual(assess(tight,monitor,{'passed':True}),GATE+'_PASS_TIGHT_MEMORY')
        bad=copy.deepcopy(training);bad['steps'][0]['memory']['free_bytes']=0
        self.assertTrue(memory_failure(bad));self.assertEqual(assess(bad,monitor),'RETRY_HOST_OFFLOAD_768_AUTHORIZED')
        reduced=copy.deepcopy(training);reduced['sequence_limit']=768
        self.assertEqual(assess(reduced,monitor,{'passed':True},bad),GATE+'_PASS_WITH_768_LIMIT')
        reduced['after_training']['peak_allocated_bytes']=7000*2**20
        self.assertEqual(assess(reduced,monitor,primary=bad),PREFIX+'HOST_OFFLOAD_MEMORY_BLOCKED')
        pressure=dict(monitor,host_min_available_bytes=5*2**30)
        self.assertEqual(assess(training,pressure),PREFIX+'HOST_RAM_PRESSURE_BLOCKED')
        paging=dict(monitor,pagefile_peak_delta_bytes=512*2**20)
        self.assertEqual(assess(training,paging,{'passed':True}),GATE+'_FAIL')

    def test_outputs_remain_ignored(self):
        paths=['.tmp/qlora-offload-smoke/data-1024.json','AlagModels/adapters/qlora-offload-smoke/1024/adapter_model.safetensors']
        p=subprocess.run(['git','check-ignore',*paths],cwd=ROOT,capture_output=True,text=True)
        self.assertEqual(set(p.stdout.splitlines()),set(paths))


if __name__=='__main__':
    configure_offline();unittest.main(verbosity=2)
