[CmdletBinding()]
param([string]$RepoRoot,[string]$ModelArchive,[switch]$PrepareOnly,[switch]$PackageOnly,[switch]$DryRun,[switch]$AllowModelDownload,[ValidatePattern('^[a-fA-F0-9]{64}$')][string]$TransportSha256)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$requestedRoot = $RepoRoot
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Initialize-Checkout $requestedRoot
$plan = @(Get-HandoffPlan -PrepareOnly:$PrepareOnly -PackageOnly:$PackageOnly)
Show-Phase ('RTX3060 12GB handoff; phases ' + ($plan -join ',')) $DryRun
if ($DryRun) { exit 0 }
[IO.Directory]::CreateDirectory($script:ScratchRoot) | Out-Null
$lease = $null
try {
    $lease = [IO.File]::Open((Join-Path $script:ScratchRoot 'handoff-session.lock'),[IO.FileMode]::OpenOrCreate,[IO.FileAccess]::ReadWrite,[IO.FileShare]::None)
    if (-not $PackageOnly) {
        $resolvedPython = Resolve-FrozenPython
        $env:RTX3060_RESOLVED_PYTHON = $resolvedPython
        $state = Invoke-PythonProbe -Executable $resolvedPython -Arguments @('-B',(Join-Path $script:ToolRoot 'state.py'),'status')
        if ($state -in @('completed','active_or_ambiguous')) {
            Write-Host "Campaign state: $state. Reporting/packaging only."
            Invoke-HandoffPhase 5
            if ($state -ne 'completed') { exit 1 }
            Invoke-ResultVerification $resolvedPython
            exit 0
        }
    }
    foreach ($number in $plan) {
        try { Invoke-HandoffPhase -Number $number -ModelArchive $ModelArchive -AllowModelDownload:$AllowModelDownload -TransportSha256 $TransportSha256 }
        catch {
            Write-PhaseFailure ([string]$number) $_.Exception.Message
            if ($number -ne 5) {
                try { Invoke-HandoffPhase 5 } catch { Write-Host ('Packaging failed: ' + $_.Exception.Message) }
            }
            throw
        }
    }
    if ($PrepareOnly) { Write-Host 'PREPARE ONLY complete. Qwen campaign NOT STARTED. Run the one-campaign command when ready.' }
    if (-not $PrepareOnly -and -not $PackageOnly) { Invoke-ResultVerification $resolvedPython }
} finally { if ($null -ne $lease) { $lease.Dispose() } }
