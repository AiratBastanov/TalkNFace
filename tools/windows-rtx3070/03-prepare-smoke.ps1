[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '03 - Frozen TRAIN selection and cheap checks (no 4B load)' $DryRun
if ($DryRun) { Write-Host 'Would compile the same 32 IDs plus the unused reload row, verify complete JSON/EOS masks and q/v-r8 counts.'; exit 0 }
try {
    Require-RemotePython
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $PSScriptRoot 'runner.py'),'prepare') -Timeout 300 -Name '03-prepare'
    Write-Host 'PASS. Next: script 04, once only. This phase did not train.'
} catch {
    Write-PhaseFailure '03' $_.Exception.Message
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
