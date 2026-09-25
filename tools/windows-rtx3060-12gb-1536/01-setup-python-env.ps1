[CmdletBinding()]
param([string]$RepoRoot,[switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$requestedRoot = $RepoRoot
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Initialize-Checkout $requestedRoot
Show-Phase '01 - Private pinned environment and tiny CUDA NF4 backend' $DryRun
if ($DryRun) { exit 0 }
try {
    $null = Test-Resources -DiskGiB 30
    $resolvedPython = Resolve-FrozenPython
    Invoke-Bounded -Executable $resolvedPython -Arguments @('-B',(Join-Path $script:ToolRoot 'environment.py'),'setup') -Timeout 1600 -Name '01-setup'
    Require-RemotePython
    Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $script:ToolRoot 'runtime_checks.py'),'--backend') -Timeout 180 -Name '01-cuda'
} catch { Write-PhaseFailure '01' $_.Exception.Message; throw }
