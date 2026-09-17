[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '04 - ONE q/v-r8 memory campaign, two updates, fresh-process reload' $DryRun
if ($DryRun) { Write-Host 'Would recheck resources, claim one-campaign lock, run 8 microbatches/2 updates, save/reload. NO retry, epoch, evaluation or 1536 run.'; exit 0 }
try {
    Require-RemotePython
    if (Test-Path -LiteralPath (Join-Path $script:ScratchRoot 'campaign-started.json')) { throw 'A campaign has already been claimed. Do not delete the marker or repeat training. Run script 05 and send the result.' }
    # The Python supervisor repeats this check and records it for the result ZIP.
    $null = Test-Resources -DiskGiB 5 -Training
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $PSScriptRoot 'runner.py'),'run') -Timeout 3000 -Name '04-campaign'
    Write-Host 'Finished. Run script 05. Full training is NOT authorized.'
} catch {
    Write-PhaseFailure '04' $_.Exception.Message
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'If no campaign-started.json exists and this was a GPU environment block: close GPU-heavy applications and rerun script 04. Otherwise do not retry; run 05.'
    exit 1
}
