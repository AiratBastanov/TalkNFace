[CmdletBinding()]
param([string]$RepoRoot,[switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$requestedRoot = $RepoRoot
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Initialize-Checkout $requestedRoot
Show-Phase '03 - Measure all 8000 TRAIN records without loading Qwen weights' $DryRun
if ($DryRun) { exit 0 }
try {
    Require-RemotePython
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $script:ToolRoot 'runner.py'),'prepare') -Timeout 1180 -Name '03-prepare'
} catch { Write-PhaseFailure '03' $_.Exception.Message; throw }
