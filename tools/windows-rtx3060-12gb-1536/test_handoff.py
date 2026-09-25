"""Source/recovery/selection/resource regressions; no ML imports or weights."""
import ast
import copy
import json
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch
from common import ROOT, HERE, AccessGuard, FORBIDDEN, write_json, read_json, sha256
import control
from policy import hardware_checks, target_name
from selection import validate_selection
from recovery import identify_partial, preserve_partial
from test_support import temporary, hardware, selection, training_fixture
from verdict import PREFIX, decide


class SourceTests(unittest.TestCase):
    def test_actual_current_control_structure_and_preserved_architecture(self):
        legacy = (ROOT/'tools/windows-rtx3070-1536/control.py').read_text(encoding='utf-8')
        self.assertIn("('seed', 'model', 'train', 'quantization', 'lora', 'activation_offload', 'host_memory', 'remote_resources')",legacy)
        self.assertNotIn("for key in ('quantization', 'lora', 'activation_offload', 'host_memory', 'remote_resources'):",legacy)
        new, old = read_json(HERE/'config.json'), read_json(ROOT/'tools/windows-rtx3070-1536/config.json')
        for key in ('seed','model','train','quantization','lora','training','activation_offload','host_memory'):
            self.assertEqual(new[key],old[key],key)

    def test_exact_accepted_locks_and_wheel_requirements(self):
        for n in ('runtime-lock.json','model-lock.json','requirements.txt','requirements-torch.txt','offload.py'):
            self.assertEqual((HERE/n).read_bytes(),(ROOT/'tools/windows-rtx3070-1536'/n).read_bytes(),n)

    def test_historical_references_are_read_only_not_renamed_results(self):
        text=(HERE/'control.py').read_text()
        self.assertIn('LOCAL_QWEN_QLORA_MEMORY_ARCHITECTURE_DECISION.json',text)
        self.assertIn("BASE_TOOL = ROOT / 'tools/windows-rtx3070'",text)
        for n in ('runner.py','00-preflight.ps1','RUN-RTX3060-12GB-REMOTE.ps1'):
            self.assertNotIn('baseline-1024', (HERE/n).read_text())
            self.assertNotIn('RTX3070_TARGETED_LORA_SMOKE_RESULT.zip',(HERE/n).read_text())

    def test_source_syntax_and_no_unwanted_hardware_thresholds(self):
        for p in HERE.glob('*.py'): ast.parse(p.read_text(encoding='utf-8'),filename=str(p))
        for n in ('runtime_checks.py','Remote.Common.ps1','train_smoke.py','runner.py'):
            text=(HERE/n).read_text()
            for bad in ('>= 8000 *','-lt 8000','7168','6656','observed_corpus_max_length'):
                self.assertNotIn(bad,text,n)

    def test_git_nul_parser_keeps_filename_whitespace_and_unicode(self):
        raw=' leading space.py\0кириллица file.py\0trailing \0'
        with patch('control.subprocess.check_output',return_value=raw) as cmd:
            self.assertEqual(control.git('ls-files','-z').split('\0')[:-1],[' leading space.py','кириллица file.py','trailing '])
            self.assertEqual(cmd.call_args.kwargs['encoding'],'utf-8')
            self.assertIn('timeout',cmd.call_args.kwargs)

    def test_runtime_paths_are_git_ignored(self):
        paths=['.tmp/rtx3060-12gb-targeted-1536-smoke/marker.json','.venv-qlora-remote/pyvenv.cfg',
               'AlagModels/adapters/rtx3060-12gb-targeted-1536-smoke/1536/x',
               'handoff-results/RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip']
        result=control.git('check-ignore','-z','--stdin',input='\0'.join(paths)+'\0')
        self.assertEqual(set(result.split('\0')[:-1]),set(paths))

    def test_production_git_preflight_executes_real_native_commands(self):
        native_git=control.git
        def allow_in_progress_task_edits(*args,**kwargs):
            # The test can run before commit. Every other production Git command,
            # including check-ignore's NUL stdin/output, executes against Git.
            if args==('status','--porcelain=v1','--untracked-files=all'): return ''
            return native_git(*args,**kwargs)
        with patch('control.git',side_effect=allow_in_progress_task_edits):
            result=control.assert_git_safe()
        self.assertEqual(result['commit'],native_git('rev-parse','HEAD').rstrip('\r\n'))
        self.assertEqual(len(result['ignored_paths']),4)
        self.assertTrue(result['clean'])

    def test_workers_reject_historical_writes_and_holdouts(self):
        guard=AccessGuard('fixture')
        for p in FORBIDDEN:
            with self.assertRaises(PermissionError): guard.check(p)
        for folder in ('tools/windows-rtx3070','tools/windows-rtx3070-1536','.tmp/rtx3070-targeted-smoke',
                       'AlagModels/adapters/rtx3070-targeted-smoke'):
            with self.assertRaises(PermissionError): guard.check(ROOT/folder/'fixture',True)

    def test_worker_network_denial(self):
        for event in ('socket.connect','socket.getaddrinfo'):
            with self.assertRaises(PermissionError): AccessGuard('fixture').hook(event,())


class RecoveryTests(unittest.TestCase):
    def make_partial(self, candidate):
        source=ROOT/'tools/windows-rtx3070-1536'; candidate.mkdir()
        for p in source.iterdir():
            if not p.is_file() or p.name=='RUN-1536-REMOTE.ps1': continue
            s=p.read_text(encoding='utf-8-sig')
            for old,new in [('RTX3070_TARGETED_LORA_1536_ENVELOPE','RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE'),
                            ('RTX3070_TARGETED_QV_R8_1536','RTX3060_12GB_TARGETED_QV_R8_1536'),
                            ('rtx3070-targeted-1536-smoke','rtx3060-12gb-targeted-1536-smoke')]: s=s.replace(old,new)
            (candidate/p.name).write_text(s,encoding='utf-8')
        c=read_json(candidate/'config.json'); c['remote_resources'].update(physical_vram_min_MiB=12000,
            nvidia_min_free_before_training_MiB=10800,cuda_min_free_before_training_MiB=10500)
        write_json(candidate/'config.json',c)
        return source

    def test_identified_partial_backup_and_unrelated_change_untouched(self):
        with temporary() as tmp:
            r=Path(tmp); user=r/'unrelated.txt'; user.write_bytes(b'USER CHANGE')
            source=self.make_partial(r/'candidate')
            inventory=preserve_partial(source,r/'candidate',r/'backup')
            self.assertEqual(len(inventory),30)
            self.assertEqual(user.read_bytes(),b'USER CHANGE')
            for row in inventory: self.assertEqual(sha256(r/'backup/partial-gate'/row['path']),row['sha256'])

    def test_ambiguous_partial_is_not_modified_or_backed_up_as_owned(self):
        with temporary() as tmp:
            r=Path(tmp); source=self.make_partial(r/'candidate')
            path=r/'candidate/control.py'; path.write_bytes(b'UNRELATED EDIT')
            with self.assertRaises(ValueError): preserve_partial(source,r/'candidate',r/'backup')
            self.assertEqual(path.read_bytes(),b'UNRELATED EDIT'); self.assertFalse((r/'backup').exists())

    def test_actual_owner_backup_when_available(self):
        records=list((ROOT/'.tmp/rtx3060-handoff-recovery').glob('*/initial-state.json'))
        if not records: self.skipTest('Owner recovery receipt not present on this computer')
        record=records[0]; state=read_json(record)
        inventory=identify_partial(ROOT/'tools/windows-rtx3070-1536',record.parent/'partial-gate')
        self.assertEqual(len(inventory),len(state['inventory']))
        self.assertTrue(all(x['identified_failed_installer_output'] for x in state['inventory']))
        self.assertEqual(state['runtime_markers'],[])


class PolicySelectionTests(unittest.TestCase):
    def test_exact_desktop_names_with_harmless_variations(self):
        for name in ('NVIDIA GeForce RTX 3060','  NVIDIA  GeForce RTX3060  ','GeForce RTX 3060','RTX 3060'):
            self.assertTrue(target_name(name))
        for name in ('NVIDIA GeForce RTX 3060 Ti','RTX 3060 Laptop GPU','RTX 3070','3060','RTX 3060 Mobile'):
            self.assertFalse(target_name(name))

    def test_12gb_valid_8gb_variant_and_each_admission_failure(self):
        self.assertTrue(all(hardware_checks(hardware()).values()))
        for key,value in [('physical_MiB',8192),('cuda_capacity_bytes',8192*2**20),('capability',[7,5]),
                          ('free_MiB',10799),('cuda_name','RTX 3060 Ti')]:
            h=hardware(); h[key]=value; self.assertFalse(all(hardware_checks(h).values()))
        h=hardware(); h['torch']['free_bytes']=10499*2**20
        self.assertFalse(hardware_checks(h)['CUDA_free'])

    def test_schema_and_real_lengths(self):
        self.assertTrue(validate_selection(selection()))
        s=selection(); s['observed_corpus_max_length']=s.pop('observed_max_length')
        with self.assertRaises(KeyError): validate_selection(s)
        s=selection(); s['optimizer_step_1_lengths'][0]=1536
        with self.assertRaises(AssertionError): validate_selection(s)

    def test_ranks_ids_and_reload_cannot_be_swapped(self):
        for key in ('selected_ids','optimizer_step_1_ids','optimizer_step_2_ids'):
            s=selection(); s[key]=list(reversed(s[key]))
            with self.assertRaises(AssertionError): validate_selection(s)
        s=selection(); s['reload_id']=s['selected_ids'][0]
        with self.assertRaises(AssertionError): validate_selection(s)

    def test_verdict_boundaries_preserve_512_256_semantics(self):
        for free,suffix in [(512,'PASS'),(511,'PASS_TIGHT_MEMORY'),(256,'PASS_TIGHT_MEMORY'),(255,'MEMORY_FAIL')]:
            t,m,r,rm=training_fixture()
            for step in t['steps']: step['memory']['free_bytes']=free*2**20
            result=decide(t,m,r,True,True,True,rm)
            self.assertEqual(result['verdict'],PREFIX+suffix,result)
            self.assertFalse(result['full_training_preparation_authorized'])

    def test_missing_evidence_never_defaults_to_success(self):
        result=decide({}, {}, {}, True, True, True, {})
        self.assertEqual(result['verdict'],PREFIX+'FAIL'); self.assertGreater(len(result['failed_checks']),10)

    def test_nonfinite_skip_and_actual_wrong_microbatch_lengths_fail(self):
        for change in ('nan','skip','length','updates','gradient'):
            t,m,r,rm=training_fixture()
            if change=='nan': t['steps'][0]['loss']=float('nan')
            if change=='skip': t['steps'][0]['grad_scaler_skipped']=True
            if change=='length': t['microbatches'][0]['tokens']=1536
            if change=='updates': t['actual_optimizer_steps']=1
            if change=='gradient': t['steps'][0]['gradient_norm']=None
            self.assertNotEqual(decide(t,m,r,True,True,True,rm)['verdict'],PREFIX+'PASS')

    def test_host_pagefile_and_missing_shared_telemetry_fail(self):
        for key,value in [('host_min_available_bytes',5*2**30),('pagefile_peak_delta_bytes',257*2**20),
                          ('gpu_process_counters_available',False),('pagefile_available_all',False)]:
            t,m,r,rm=training_fixture(); m[key]=value
            self.assertTrue(decide(t,m,r,True,True,True,rm)['failed_checks'])


if __name__=='__main__': unittest.main(verbosity=2)
