[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '01 - Private pinned Python environment and tiny CUDA NF4 check' $DryRun
if ($DryRun) { Write-Host 'Would use py -3.12 -m venv, binary/hash-locked wheels and CUDA preflight only.'; exit 0 }
try {
    $null = Test-Resources -DiskGiB 30
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) { throw 'Install Python 3.12.10 x64 from python.org for your user, including the Python launcher; reopen PowerShell. See README.' }
    $version = & py -3.12 -c 'import platform,struct; print(platform.python_version(),struct.calcsize(chr(80))*8)'
    if ($LASTEXITCODE -ne 0 -or "$version".Trim() -ne '3.12.10 64') { throw 'The frozen interpreter is Python 3.12.10 x64. Install it manually from the official link in README; no system Python is installed by this script.' }
    Invoke-Bounded -Executable (Get-Command py).Source -Arguments @('-3.12','-B',(Join-Path $PSScriptRoot 'environment.py'),'setup') -Timeout 1800 -Name '01-setup'
    Require-RemotePython
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $PSScriptRoot 'runtime_checks.py'),'--backend') -Timeout 120 -Name '01-cuda'
    Write-Host 'PASS. Next: script 02. No Qwen model was loaded.'
} catch {
    Write-PhaseFailure '01' $_.Exception.Message
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'If CUDA/driver failed, verify or update the NVIDIA driver manually. Do not install CUDA Toolkit or a compiler.'
    exit 1
}
