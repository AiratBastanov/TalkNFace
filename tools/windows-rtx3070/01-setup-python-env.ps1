[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '01 - Private pinned Python environment and tiny CUDA NF4 check' $DryRun
if ($DryRun) { Write-Host 'Would resolve and validate Python 3.12.10 x64, then use that python.exe -m venv; binary/hash-locked wheels and CUDA preflight only.'; exit 0 }
try {
    $null = Test-Resources -DiskGiB 30
    $resolvedPython = Resolve-FrozenPython
    Invoke-Bounded -Executable $resolvedPython -Arguments @('-B',(Join-Path $PSScriptRoot 'environment.py'),'setup') -Timeout 1800 -Name '01-setup'
    Require-RemotePython
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $PSScriptRoot 'runtime_checks.py'),'--backend') -Timeout 120 -Name '01-cuda'
    Write-Host 'PASS. Next: script 02. No Qwen model was loaded.'
} catch {
    Write-PhaseFailure '01' $_.Exception.Message
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'If CUDA/driver failed, verify or update the NVIDIA driver manually. Do not install CUDA Toolkit or a compiler.'
    exit 1
}
