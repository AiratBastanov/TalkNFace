[CmdletBinding()]
param([string]$RepoRoot,[switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$requestedRoot = $RepoRoot
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Initialize-Checkout $requestedRoot
Show-Phase '04 - At most one bounded campaign and fresh-process reload' $DryRun
if ($DryRun) { exit 0 }
try {
    Require-RemotePython
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $script:ToolRoot 'runner.py'),'run') -Timeout 2980 -Name '04-campaign'
} catch { Write-PhaseFailure '04' $_.Exception.Message; throw }
