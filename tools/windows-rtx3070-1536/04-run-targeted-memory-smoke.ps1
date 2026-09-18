[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '04 - ONE 1536/full-TRAIN-envelope q/v-r8 campaign, two updates, fresh-process reload' $DryRun
if ($DryRun) { Write-Host 'Would recheck resources, claim one 1536-campaign lock, run 8 longest TRAIN microbatches/2 updates, save/reload. No full training.'; exit 0 }
try {
    Require-RemotePython
    if (Test-Path -LiteralPath (Join-Path $script:ScratchRoot 'campaign-started.json')) { throw 'A 1536 campaign has already been claimed. Do not delete the marker or repeat training. Run script 05.' }
    $null=Test-Resources -DiskGiB 5 -Training
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $PSScriptRoot 'runner.py'),'run') -Timeout 3000 -Name '04-campaign-1536'
    Write-Host 'Finished. Run script 05. Full training is NOT started by this gate.'
} catch {
    Write-PhaseFailure '04-1536' $_.Exception.Message
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'If no campaign-started.json exists, this was a prerequisite/GPU block and no training was consumed. Otherwise do not retry; package evidence with 05.'
    exit 1
}
