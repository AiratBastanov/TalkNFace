[CmdletBinding()]
param([string]$RepoRoot,[switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$requestedRoot = $RepoRoot
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Initialize-Checkout $requestedRoot
Show-Phase '05 - Sanitized diagnostics only; never training' $DryRun
if ($DryRun) { exit 0 }
$resolvedPython = Resolve-FrozenPython
Invoke-Bounded -Executable $resolvedPython -Arguments @('-B',(Join-Path $script:ToolRoot 'package_result.py')) -Timeout 170 -Name '05-package'
