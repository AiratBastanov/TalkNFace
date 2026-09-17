Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$script:ToolRoot = Join-Path $script:RepoRoot 'tools/windows-rtx3070'
$script:ScratchRoot = Join-Path $script:RepoRoot '.tmp/rtx3070-targeted-smoke'
$script:PythonExe = Join-Path $script:RepoRoot '.venv-qlora-remote/Scripts/python.exe'

function Show-Phase([string]$Name, [bool]$DryRun) {
    Write-Host "=== $Name ==="
    Write-Host "Repository: $script:RepoRoot"
    if ($DryRun) {
        Write-Host 'DRY RUN: no files, downloads, environment changes, CUDA operations or training.'
        Write-Host "Python: $script:PythonExe"
        Write-Host "Scratch: $script:ScratchRoot"
        Write-Host "Model: $(Join-Path $script:RepoRoot 'AlagModels/Qwen3-4B')"
        Write-Host "Adapter: $(Join-Path $script:RepoRoot 'AlagModels/adapters/rtx3070-targeted-smoke')"
        $lock = Get-Content -LiteralPath (Join-Path $script:ToolRoot 'runtime-lock.json') -Raw | ConvertFrom-Json
        Write-Host "Pinned Python: $($lock.python); torch: $($lock.packages.torch); no automatic alternatives."
    }
}

function Test-Resources([double]$DiskGiB = 30, [switch]$Training) {
    if (-not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) {
        throw 'Use ordinary 64-bit Windows PowerShell on Windows x86-64.'
    }
    $os = Get-CimInstance -ClassName Win32_OperatingSystem
    $cpu = @(Get-CimInstance -ClassName Win32_Processor)[0]
    if ($cpu.Architecture -ne 9 -or $os.ProductType -ne 1 -or [version]$os.Version -lt [version]'10.0') {
        throw 'This handoff requires an x86-64 Windows 10/11 desktop. Windows 11 is recommended.'
    }
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        throw 'nvidia-smi was not found. Install/verify the NVIDIA driver manually from nvidia.com; do not install CUDA Toolkit.'
    }
    $lines = @(& nvidia-smi --id=0 --query-gpu=name,memory.total,memory.free,memory.used,driver_version --format=csv,noheader,nounits)
    if ($LASTEXITCODE -ne 0 -or $lines.Count -ne 1) { throw 'Cannot query NVIDIA GPU 0. Verify the NVIDIA driver manually.' }
    $v = $lines[0].Split(',') | ForEach-Object { $_.Trim() }
    if ($v.Count -ne 5) { throw 'Unexpected nvidia-smi output; send its output to the project owner.' }
    $gpuTotal = [double]::Parse($v[1], [Globalization.CultureInfo]::InvariantCulture)
    $gpuFree = [double]::Parse($v[2], [Globalization.CultureInfo]::InvariantCulture)
    $available = [double]$os.FreePhysicalMemory * 1024
    $total = [double]$os.TotalVisibleMemorySize * 1024
    $drive = [System.IO.DriveInfo]::new([System.IO.Path]::GetPathRoot($script:RepoRoot))
    $result = [ordered]@{ windows = $os.Caption; windows_version = $os.Version; architecture = 'x86-64';
        gpu_index = 0; gpu_name = $v[0]; gpu_total_MiB = $gpuTotal; gpu_free_MiB = $gpuFree;
        gpu_used_MiB = [double]$v[3]; driver = $v[4]; host_total_bytes = $total; host_available_bytes = $available;
        volume_free_bytes = $drive.AvailableFreeSpace; required_disk_bytes = $DiskGiB * 1GB }
    Write-Host ($result | ConvertTo-Json -Compress)
    if ($gpuTotal -lt 8000) { throw 'An 8192 MiB-class GPU is required (minimum reported capacity 8000 MiB). Do not run this on a 6 GiB GPU.' }
    if ($v[0] -notmatch '3070') { Write-Warning 'Name differs from RTX 3070. CUDA capability 8.6 and capacity must still pass script 01; no naming-prefix assumption is used.' }
    if ($available -lt 12GB) { throw 'At least 12 GiB physical RAM must be available. Close memory-heavy apps and repeat this phase.' }
    if ($drive.AvailableFreeSpace -lt $DiskGiB * 1GB) { throw "Need at least $DiskGiB GiB free on the repository volume. Free space or clone onto a larger volume." }
    if ($Training -and $gpuFree -lt 7168) { throw 'ACTION REQUIRED: close GPU-heavy applications and rerun script 04.' }
    return $result
}

function Require-RemotePython {
    if (-not (Test-Path -LiteralPath $script:PythonExe -PathType Leaf)) { throw 'Run script 01 successfully first. Do not use a global Python environment.' }
}

function Write-PhaseFailure([string]$Phase, [string]$Message) {
    # Script 00 never calls this: its checks are strictly read-only.
    [IO.Directory]::CreateDirectory($script:ScratchRoot) | Out-Null
    $record = @{ phase = $Phase; message = $Message; time_utc = [DateTime]::UtcNow.ToString('o') }
    $text = $record | ConvertTo-Json
    [IO.File]::WriteAllText((Join-Path $script:ScratchRoot 'last-phase-error.json'), $text, [Text.UTF8Encoding]::new($false))
}

function Quote-NativeArgument([string]$Value) {
    # Windows CommandLineToArgvW-compatible escaping, including paths with spaces.
    $escaped = [regex]::Replace($Value, '(\\*)"', '$1$1\"')
    $escaped = [regex]::Replace($escaped, '(\\+)$', '$1$1')
    return '"' + $escaped + '"'
}

function Stop-OwnedTree([int]$OwnerPid) {
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$OwnerPid" -ErrorAction SilentlyContinue)
    foreach ($child in $children) { Stop-OwnedTree -OwnerPid ([int]$child.ProcessId) }
    Stop-Process -Id $OwnerPid -ErrorAction SilentlyContinue
}

function Invoke-Bounded([string]$Executable, [string[]]$Arguments, [int]$Timeout, [string]$Name) {
    [IO.Directory]::CreateDirectory($script:ScratchRoot) | Out-Null
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
    $env:HF_HUB_DISABLE_TELEMETRY = '1'
    $env:HF_HOME = Join-Path $script:ScratchRoot 'hf'
    $env:TMP = $script:ScratchRoot
    $env:TEMP = $script:ScratchRoot
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfff')
    $stdout = Join-Path $script:ScratchRoot "$Name-$stamp.stdout.log"
    $stderr = Join-Path $script:ScratchRoot "$Name-$stamp.stderr.log"
    $quoted = ($Arguments | ForEach-Object { Quote-NativeArgument $_ }) -join ' '
    $process = Start-Process -FilePath $Executable -ArgumentList $quoted -WorkingDirectory $script:RepoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    # Windows PowerShell 5.1 otherwise may expose a null ExitCode after a fast
    # child exits. Keep the native handle open until its exit code is consumed.
    $taskProcessHandle = $process.Handle
    $clock = [Diagnostics.Stopwatch]::StartNew()
    try {
        while (-not $process.WaitForExit(1000)) {
            if ($clock.Elapsed.TotalSeconds -gt $Timeout) {
                Stop-OwnedTree -OwnerPid $process.Id
                throw "Watchdog $Timeout seconds expired during $Name. Only the gate-owned process tree was stopped; run script 05 and send the result."
            }
            if ([int]$clock.Elapsed.TotalSeconds % 10 -eq 0) { Write-Host "$Name running ($([int]$clock.Elapsed.TotalSeconds)s). Logs: $script:ScratchRoot" }
        }
        $process.WaitForExit()
        if (Test-Path -LiteralPath $stdout) { Get-Content -LiteralPath $stdout | Write-Host }
        if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr | Write-Host }
        if ($null -eq $process.ExitCode -or $process.ExitCode -ne 0) { throw "$Name failed (exit $($process.ExitCode)). Follow the message above; run script 05 to package diagnostics. Do not change versions or retry training." }
    } finally {
        if (-not $process.HasExited) { Stop-OwnedTree -OwnerPid $process.Id }
        $process.Dispose()
    }
}
