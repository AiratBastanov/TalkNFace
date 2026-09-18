[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '05 - Package 1536 text/JSON diagnostics only; no data or weights' $DryRun
if ($DryRun) { Write-Host 'Would create handoff-results/RTX3070_TARGETED_LORA_1536_ENVELOPE_RESULT.zip from an explicit safe allowlist.'; exit 0 }
try {
    Require-RemotePython
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $PSScriptRoot 'package_result.py')) -Timeout 120 -Name '05-package-1536'
    Write-Host 'Send only RTX3070_TARGETED_LORA_1536_ENVELOPE_RESULT.zip to the project owner. Do not send model/dataset/adapter binaries.'
} catch {
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
