[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '03 - Measure all 8000 TRAIN sequences and freeze the 1536 envelope selection (no 4B load)' $DryRun
if ($DryRun) { Write-Host 'Would recheck pinned runtime/NF4 backend, verify model hashes, tokenize all TRAIN rows, select the 9 longest complete records, and run cheap checks. No Qwen weights loaded.'; exit 0 }
try {
    Require-RemotePython
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $PSScriptRoot 'runner.py'),'prepare') -Timeout 900 -Name '03-prepare-1536'
    Write-Host 'Preparation PASS. Do not edit source/data. Script 04 is the only training campaign.'
} catch {
    Write-PhaseFailure '03-1536' $_.Exception.Message
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
