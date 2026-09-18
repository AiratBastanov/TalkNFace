[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '00 - 1536 envelope preflight; reuses verified environment/model' $DryRun
if ($DryRun) { exit 0 }
Require-RemotePython
$null=Test-Resources -DiskGiB 5
$base=Join-Path $script:RepoRoot 'handoff-results/RTX3070_TARGETED_LORA_SMOKE_RESULT.zip'
if (-not (Test-Path -LiteralPath $base -PathType Leaf)) { throw 'Successful 1024 result ZIP is missing.' }
$hash=(Get-FileHash -LiteralPath $base -Algorithm SHA256).Hash.ToLowerInvariant()
if ($hash -ne '82d727d431ecbb91585d53961442eeab2f544c5f74b19f5572cea30dd1389fb9') { throw 'Successful 1024 result ZIP hash differs.' }
Write-Host 'PASS: remote environment/model are reused; successful 1024 evidence hash matches.'
