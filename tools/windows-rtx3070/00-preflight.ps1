[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '00 - Read-only Windows / GPU / RAM / disk preflight' $DryRun
if ($DryRun) { exit 0 }
try {
    $null = Test-Resources -DiskGiB 30
    Write-Host 'PASS. Next: script 01. Nothing on this machine was changed.'
} catch {
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
