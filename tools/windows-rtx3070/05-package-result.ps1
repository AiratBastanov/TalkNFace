[CmdletBinding()]
param([switch]$DryRun)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Remote.Common.ps1')
Show-Phase '05 - Package text/JSON diagnostics only; no data or weights' $DryRun
if ($DryRun) { Write-Host 'Would create handoff-results/RTX3070_TARGETED_LORA_SMOKE_RESULT.zip from an explicit safe file allowlist.'; exit 0 }
try {
    if (Test-Path -LiteralPath $script:PythonExe -PathType Leaf) {
        Invoke-Bounded -Executable $script:PythonExe -Arguments @('-B',(Join-Path $PSScriptRoot 'package_result.py')) -Timeout 120 -Name '05-package'
    } elseif (Get-Command py -ErrorAction SilentlyContinue) {
        Invoke-Bounded -Executable (Get-Command py).Source -Arguments @('-3.12','-B',(Join-Path $PSScriptRoot 'package_result.py')) -Timeout 120 -Name '05-package'
    } else {
        # No Python was installed: still return a minimal, safe diagnostic archive.
        $output = Join-Path $script:RepoRoot 'handoff-results'
        [IO.Directory]::CreateDirectory($output) | Out-Null
        $zip = Join-Path $output 'RTX3070_TARGETED_LORA_SMOKE_RESULT.zip'
        if (Test-Path -LiteralPath $zip) { throw 'Result ZIP already exists. Keep it; rename the older ZIP before packaging again.' }
        $result = "VERDICT: RTX3070_TARGETED_LORA_MEMORY_SMOKE_RUNTIME_BLOCKED`nGPU/VRAM/CUDA/RUNTIME: NOT MEASURED; Python 3.12 launcher missing.`nMODEL HASH STATUS: NOT RUN`nTRAINABLE PARAMETERS: 2949120 expected`nOPTIMIZER UPDATES: 0`nLOSSES/PEAK ALLOCATED/BOUNDARY FREE 1/BOUNDARY FREE 2/MIN HOST RAM/PAGEFILE DELTA: NOT MEASURED`nADAPTER CHANGED: NO`nSAVE/RELOAD: NOT RUN`nNEXT: Install Python 3.12.10 as documented; no training started.`n"
        $textPath = Join-Path $output 'RESULT.txt'
        $jsonPath = Join-Path $output 'evidence.json'
        [IO.File]::WriteAllText($textPath, $result, [Text.UTF8Encoding]::new($false))
        [IO.File]::WriteAllText($jsonPath, '{"verdict":"RTX3070_TARGETED_LORA_MEMORY_SMOKE_RUNTIME_BLOCKED","optimizer_updates":0,"reason":"Python launcher missing"}', [Text.UTF8Encoding]::new($false))
        Compress-Archive -LiteralPath @($textPath,$jsonPath) -DestinationPath $zip
        Write-Host $zip
    }
    Write-Host 'Send only the result ZIP to the project owner. No Git write access is needed. Do not send model, datasets or adapter binaries.'
} catch {
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
