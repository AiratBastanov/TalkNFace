[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$RepoRoot=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$Tool=Join-Path $RepoRoot 'tools/windows-rtx3070-1536'
$Scratch=Join-Path $RepoRoot '.tmp/rtx3070-targeted-1536-smoke'
$Baseline=Join-Path $RepoRoot 'handoff-results/RTX3070_TARGETED_LORA_SMOKE_RESULT.zip'
$Expected='82D727D431ECBB91585D53961442EEAB2F544C5F74B19F5572CEA30DD1389FB9'
$Result=Join-Path $RepoRoot 'handoff-results/RTX3070_TARGETED_LORA_1536_ENVELOPE_RESULT.zip'

if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot '.git') -PathType Container)) { throw 'RepoRoot is not a Git working tree.' }
Set-Location $RepoRoot
if ((git status --porcelain=v1 --untracked-files=all)) { throw 'Repository must be clean before pulling/running the gate.' }
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'git pull --ff-only failed.' }
if ((git branch --show-current).Trim() -ne 'main') { throw 'Expected branch main.' }
if ((git remote get-url origin).Trim() -ne 'https://github.com/AiratBastanov/TalkNFace.git') { throw 'Unexpected origin.' }
git fetch origin
if ((git rev-list --left-right --count HEAD...origin/main).Trim() -notmatch '^0\s+0$') { throw 'Repository is not synchronized 0/0.' }
if (-not (Test-Path -LiteralPath $Tool -PathType Container)) { throw '1536 gate is not present after pull.' }
if (-not (Test-Path -LiteralPath $Baseline -PathType Leaf)) { throw 'Accepted 1024 result ZIP is missing.' }
if ((Get-FileHash -LiteralPath $Baseline -Algorithm SHA256).Hash -ne $Expected) { throw 'Accepted 1024 evidence hash mismatch.' }
if (Test-Path -LiteralPath $Result) { throw '1536 result ZIP already exists. Preserve it; do not overwrite/repeat.' }

Write-Host '=== 1536 gate: read-only preflight ==='
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Tool '00-preflight.ps1')
if ($LASTEXITCODE -ne 0) { throw '00 preflight failed.' }

Write-Host '=== 1536 gate: full TRAIN measurement / selection ==='
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Tool '03-prepare-smoke.ps1')
if ($LASTEXITCODE -ne 0) { throw '03 preparation failed. No training started.' }
$dataPath=Join-Path $Scratch 'data-1536.json'
if (-not (Test-Path -LiteralPath $dataPath -PathType Leaf)) { throw '03 did not create data-1536.json.' }
$d=Get-Content -LiteralPath $dataPath -Raw -Encoding UTF8 | ConvertFrom-Json
$s=$d.selection
if ($d.max_length -ne 1536 -or $s.source_rows_measured -ne 8000 -or $s.eligible_rows -ne 8000 -or
    $s.observed_max_length -ne 1421 -or $s.rows_above_limit -ne 0 -or $s.truncated_rows -ne 0 -or
    @($d.rows).Count -ne 8) { throw 'Prepared 1536 selection failed the independent PowerShell assertions.' }
$step1=@($s.optimizer_step_1_lengths | ForEach-Object {[int]$_})
$step2=@($s.optimizer_step_2_lengths | ForEach-Object {[int]$_})
if ($step1.Count -ne 4 -or $step2.Count -ne 4) { throw 'Expected exactly 4+4 optimizer microbatches.' }
$max1=($step1 | Measure-Object -Maximum).Maximum; $min2=($step2 | Measure-Object -Minimum).Minimum
if ($min2 -lt $max1) { throw 'The globally longest records are not concentrated in optimizer update #2.' }
if (Test-Path -LiteralPath (Join-Path $Scratch 'campaign-started.json')) { throw 'Campaign marker exists before the authorized run.' }
Write-Host ("PREP VERIFIED: TRAIN=8000, max=1421, step1=[{0}], step2=[{1}], reload={2}" -f ($step1 -join ','),($step2 -join ','),$s.reload_length) -ForegroundColor Green

Write-Host '=== ONE authorized 1536 training campaign ==='
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Tool '04-run-targeted-memory-smoke.ps1')
$campaignExit=$LASTEXITCODE
$claimed=Test-Path -LiteralPath (Join-Path $Scratch 'campaign-started.json')
if ($campaignExit -ne 0 -and -not $claimed) {
    Write-Host 'ACTION REQUIRED FROM USER: training was NOT consumed. Close GPU-heavy applications if reported, then rerun this orchestrator.' -ForegroundColor Yellow
    exit $campaignExit
}

Write-Host '=== Package immutable 1536 evidence ==='
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $Tool '05-package-result.ps1')
if ($LASTEXITCODE -ne 0) { throw '05 packaging failed. Do not repeat training.' }
if (-not (Test-Path -LiteralPath $Result -PathType Leaf)) { throw 'Expected 1536 result ZIP was not created.' }
$hash=(Get-FileHash -LiteralPath $Result -Algorithm SHA256).Hash
Write-Host "RESULT: $Result"
Write-Host "SHA256: $hash"
$outcomePath=Join-Path $Scratch 'outcome.json'
if (Test-Path -LiteralPath $outcomePath) {
    $o=Get-Content -LiteralPath $outcomePath -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host "VERDICT: $($o.verdict)"
    Write-Host "NEXT: $($o.next)"
}
if ($campaignExit -ne 0) { exit $campaignExit }
