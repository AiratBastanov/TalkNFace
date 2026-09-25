"""Real Windows PowerShell 5.1 parsing/quoting; mocked hardware/install dispatch."""
import json
from pathlib import Path
import subprocess
import sys
import unittest
from common import HERE, read_json, sha256
from test_support import temporary, quote, powershell, common_ps, copy_tool


class PowerShellTests(unittest.TestCase):
    def test_actual_powershell51_parser_all_entrypoints(self):
        code="if($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1){throw 'Need PS5.1'};"
        for p in HERE.glob('*.ps1'):
            code+='$t=$null;$e=$null;$null=[System.Management.Automation.Language.Parser]::ParseFile('+quote(p)+",[ref]$t,[ref]$e);if($e.Count){throw ($e|Out-String)};"
        result=powershell(code); self.assertEqual(result.returncode,0,result.stderr)

    def test_all_dryruns_are_readonly_in_cyrillic_spaced_fresh_checkout(self):
        with temporary() as tmp:
            root=Path(tmp)/'Проект друга'; tool=copy_tool(root)
            before={p.relative_to(root).as_posix():sha256(p) for p in root.rglob('*') if p.is_file()}
            for p in tool.glob('*.ps1'):
                if p.name=='Remote.Common.ps1': continue
                result=powershell('& '+quote(p)+' -RepoRoot '+quote(root)+' -DryRun')
                self.assertEqual(result.returncode,0,result.stdout+result.stderr); self.assertIn('DRY RUN',result.stdout)
                self.assertIn(str(root),result.stdout)
            after={p.relative_to(root).as_posix():sha256(p) for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before,after); self.assertFalse((root/'.tmp').exists()); self.assertFalse((root/'.venv-qlora-remote').exists())

    def test_wrong_reporoot_refused_even_in_dryrun(self):
        with temporary() as tmp:
            result=powershell('& '+quote(HERE/'RUN-RTX3060-12GB-REMOTE.ps1')+' -RepoRoot '+quote(tmp)+' -DryRun')
            self.assertNotEqual(result.returncode,0); self.assertIn('RepoRoot must agree',result.stderr)

    def test_launcher_and_interpreter_argument_separation(self):
        cases=[('Launcher',r'C:\Windows\py.exe'),('Interpreter',r'C:\Users\Друг имя\Python312\python.exe')]
        for mode,exe in cases:
            code=common_ps()+'$c=Get-PythonInvocation -Mode '+mode+' -Executable '+quote(exe)+" -Arguments @('-m','venv','C:\\Проект друга\\.venv');"
            result=powershell(code+'$c|ConvertTo-Json -Compress')
            self.assertEqual(result.returncode,0,result.stderr)
            args=json.loads(result.stdout)['Arguments']
            self.assertEqual(args[0],'-3.12' if mode=='Launcher' else '-m')
        for bad in ('-3','-3.12','-V:PythonCore/3.12'):
            result=powershell(common_ps()+'ConvertTo-NativeArguments '+quote(sys.executable)+' @('+quote(bad)+')')
            self.assertNotEqual(result.returncode,0)

    def test_real_interpreter_probe_version_and_unicode_arguments(self):
        with temporary() as tmp:
            root=Path(tmp)/'Друг пробел'; root.mkdir(); helper=root/'аргументы.py'
            helper.write_text('import json,sys\nprint(json.dumps(sys.argv[1:]))\n',encoding='utf-8')
            args=['кириллица с пробелом','a"quote','end\\','']
            code=common_ps()+'Invoke-PythonProbe -Executable '+quote(sys.executable)+' -Arguments @('+','.join(quote(s) for s in ['-B',str(helper),*args])+')'
            result=powershell(code); self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(json.loads(result.stdout),args)
        result=powershell(common_ps()+'Invoke-PythonProbe '+quote(sys.executable)+" @('--version')")
        self.assertEqual(result.returncode,0,result.stderr); self.assertEqual(result.stdout.strip(),'Python 3.12.10')

    def test_bounded_native_nonzero_and_timeout_propagate(self):
        for code,budget,needle in [('raise SystemExit(7)',10,'exit 7'),('import time; time.sleep(30)',1,'Watchdog')]:
            with temporary() as tmp:
                p=common_ps()+'$script:ScratchRoot='+quote(Path(tmp)/'logs')+';Invoke-Bounded -Executable '+quote(sys.executable)
                p+=' -Arguments @(\'-B\',\'-c\','+quote(code)+') -Timeout '+str(budget)+" -Name fixture"
                result=powershell(p,timeout=25); self.assertNotEqual(result.returncode,0); self.assertIn(needle,result.stderr)
                self.assertIn('ACTIVE: fixture;',result.stdout)
                self.assertEqual(len(list((Path(tmp)/'logs').glob('fixture-*.stdout.log'))),1)

    def test_python_identity_rejects_wrong_version_or_bitness(self):
        for version,bits,valid in [('3.12.10',64,True),('3.12.9',64,False),('3.13.0',64,False),('3.12.10',32,False)]:
            code=common_ps()+'Assert-FrozenPythonIdentity ([pscustomobject]@{version='+quote(version)+';bits='+str(bits)+';executable='+quote(sys.executable)+'})'
            result=powershell(code); self.assertEqual(result.returncode==0,valid,result.stderr)

    def test_hardware_policy_powershell_matches_python(self):
        for name,capacity,free,ram,valid in [('NVIDIA GeForce RTX 3060',12288,11000,13,True),('RTX3060',12288,11000,13,True),
              ('RTX 3060 Ti',12288,11000,13,False),('RTX 3060 Laptop GPU',12288,11000,13,False),
              ('RTX 3060',8192,11000,13,False),('RTX 3060',12288,10799,13,False),('RTX 3060',12288,11000,11,False)]:
            code=common_ps()+'Assert-TargetHardware -Name '+quote(name)+' -Capacity '+str(capacity)+" -Capability '8.6' -Free "+str(free)+' -Available '+str(ram*2**30)+' -Training'
            result=powershell(code); self.assertEqual(result.returncode==0,valid,result.stderr)

    def test_top_level_modes_dispatch_actual_flow_without_training_in_prepare_or_package(self):
        for flag,state,expected in [('-PrepareOnly','fresh',[0,1,2,3]),('-PackageOnly','fresh',[5]),('', 'fresh',[0,1,2,3,4,5]),('', 'completed',[5]),('-PrepareOnly','completed',[5])]:
            with temporary() as tmp:
                root=Path(tmp)/'Друг space'; tool=copy_tool(root); calls=root/'calls.json'
                helpers='\nfunction Resolve-FrozenPython { return '+quote(sys.executable)+' }\n'
                helpers+='function Invoke-PythonProbe { param($Executable,$Arguments) return '+quote(state)+' }\n'
                helpers+='function Invoke-ResultVerification { param($ResolvedPython) }\n'
                helpers+='$script:record=@()\nfunction Invoke-HandoffPhase { param($Number,$ModelArchive,$AllowModelDownload,$TransportSha256) $script:record+= [int]$Number; ConvertTo-Json -InputObject @($script:record) | Set-Content -LiteralPath '+quote(calls)+' -Encoding UTF8 }\n'
                p=tool/'Remote.Common.ps1'; p.write_text(p.read_text(encoding='utf-8')+helpers,encoding='utf-8-sig')
                result=powershell('& '+quote(tool/'RUN-RTX3060-12GB-REMOTE.ps1')+' '+flag)
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(json.loads(calls.read_text(encoding='utf-8-sig')),expected)

    def test_real_setup_phase_dispatches_setup_and_cuda_not_stubs(self):
        with temporary() as tmp:
            root=Path(tmp); tool=copy_tool(root); calls=root/'calls.json'
            helper='\nfunction Test-Resources { param($DiskGiB) return @{} }\nfunction Resolve-FrozenPython { return '+quote(sys.executable)+' }\nfunction Require-RemotePython {}\n$script:record=@()\n'
            helper+='function Invoke-Bounded { param($Executable,$Arguments,$Timeout,$Name) $script:record+=@{executable=$Executable;arguments=@($Arguments);timeout=$Timeout}; $script:record|ConvertTo-Json -Depth 5|Set-Content -LiteralPath '+quote(calls)+' -Encoding UTF8 }\n'
            p=tool/'Remote.Common.ps1'; p.write_text(p.read_text(encoding='utf-8')+helper,encoding='utf-8-sig')
            result=powershell('& '+quote(tool/'01-setup-python-env.ps1'))
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            commands=json.loads(calls.read_text(encoding='utf-8-sig'))
            self.assertEqual(commands[0]['arguments'][-1],'setup'); self.assertEqual(commands[1]['arguments'][-1],'--backend')
            self.assertEqual(commands[0]['executable'],sys.executable)
            self.assertFalse(any('-3.12' in x['arguments'] for x in commands))

    def test_native_phase_failure_reaches_top_and_still_packages(self):
        with temporary() as tmp:
            root=Path(tmp); tool=copy_tool(root); calls=root/'calls.txt'
            helper='\nfunction Resolve-FrozenPython { return '+quote(sys.executable)+' }\nfunction Invoke-PythonProbe { return "fresh" }\n'
            helper+='function Invoke-HandoffPhase { param($Number,$ModelArchive,$AllowModelDownload,$TransportSha256) Add-Content -LiteralPath '+quote(calls)+' -Value $Number; if($Number -eq 1){throw "native exit 17 fixture"} }\n'
            p=tool/'Remote.Common.ps1'; p.write_text(p.read_text(encoding='utf-8')+helper,encoding='utf-8-sig')
            result=powershell('& '+quote(tool/'RUN-RTX3060-12GB-REMOTE.ps1'))
            self.assertNotEqual(result.returncode,0); self.assertIn('native exit 17',result.stderr)
            self.assertEqual(calls.read_text().splitlines(),['0','1','5'])


if __name__=='__main__': unittest.main(verbosity=2)
