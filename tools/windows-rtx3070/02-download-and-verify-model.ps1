[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '02 - Official pinned Qwen3-4B download and byte verification' $DryRun
if ($DryRun) { Write-Host 'Would reuse verified model or download pinned Qwen/Qwen3-4B safetensors; no token.'; exit 0 }
try {
    Require-RemotePython
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $PSScriptRoot 'model_files.py'),'download') -Timeout 3600 -Name '02-model'
    Write-Host 'PASS. Close GPU-heavy apps, then run script 03.'
} catch {
    Write-PhaseFailure '02' $_.Exception.Message
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'Do not substitute another Qwen model or alter hash pins. For hash failures, package diagnostics with script 05 and contact the project owner.'
    exit 1
}
