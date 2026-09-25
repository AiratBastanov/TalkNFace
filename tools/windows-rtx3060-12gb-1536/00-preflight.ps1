[CmdletBinding()]
param([string]$RepoRoot,[switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$requestedRoot = $RepoRoot
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Initialize-Checkout $requestedRoot
Show-Phase '00 - Read-only fresh-computer prerequisites' $DryRun
if ($DryRun) { exit 0 }
if (-not (Get-Command git -CommandType Application -ErrorAction SilentlyContinue)) { throw 'ACTION REQUIRED: install Git for Windows manually, then clone the authoritative repository.' }
$git = (Get-Command git -CommandType Application).Source
$branch = Invoke-PythonProbe $git @('-C',$script:RepoRoot,'branch','--show-current')
$origin = Invoke-PythonProbe $git @('-C',$script:RepoRoot,'remote','get-url','origin')
$status = Invoke-PythonProbe $git @('-C',$script:RepoRoot,'status','--porcelain=v1','--untracked-files=all')
if ($branch -cne 'main' -or $origin -cne 'https://github.com/AiratBastanov/TalkNFace.git') { throw 'Expected authoritative origin and branch main.' }
if ($status) { throw 'Source worktree changed. Preserve changes; use the reviewed checkout before preparing.' }
$null = Resolve-FrozenPython
$null = Test-Resources -DiskGiB 30
Write-Host 'Read-only prerequisites passed. Environment and model are verified by phases 01/02.'
