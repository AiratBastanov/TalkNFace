[CmdletBinding()]
param([string]$RepoRoot,[switch]$DryRun,[string]$ModelArchive,[switch]$AllowModelDownload,[ValidatePattern("^[a-fA-F0-9]{64}$")][string]$TransportSha256)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$requestedRoot = $RepoRoot
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Initialize-Checkout $requestedRoot
Show-Phase '02 - Local pinned model verification/import; explicit download fallback' $DryRun
if ($DryRun) { exit 0 }
try {
    Require-RemotePython
    $argv = @('-B',(Join-Path $script:ToolRoot 'model_files.py'),'ensure')
    if ($ModelArchive) { $argv += @('--archive',(Resolve-Path -LiteralPath $ModelArchive).Path) }
    if ($AllowModelDownload) { $argv += '--allow-download' }
    if ($TransportSha256) { $argv += @('--transport-sha256',$TransportSha256) }
    Invoke-Bounded -Executable $script:PythonExe -Arguments $argv -Timeout 1780 -Name '02-model'
} catch { Write-PhaseFailure '02' $_.Exception.Message; throw }
