Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$script:RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
$script:ToolRoot = Join-Path $script:RepoRoot 'tools/windows-rtx3060-12gb-1536'
$script:ScratchRoot = Join-Path $script:RepoRoot '.tmp/rtx3060-12gb-targeted-1536-smoke'
$script:PythonExe = Join-Path $script:RepoRoot '.venv-qlora-remote/Scripts/python.exe'

function Show-Phase([string]$Name, [bool]$DryRun) {
    Write-Host "=== $Name ==="
    Write-Host "Repository: $script:RepoRoot"
    if ($DryRun) {
        Write-Host 'DRY RUN: no files, downloads, environment changes, CUDA operations or training.'
        Write-Host "Python: $script:PythonExe"
        Write-Host "Scratch: $script:ScratchRoot"
        Write-Host "Model: $(Join-Path $script:RepoRoot 'AlagModels/Qwen3-4B')"
        Write-Host "Adapter: $(Join-Path $script:RepoRoot 'AlagModels/adapters/rtx3060-12gb-targeted-1536-smoke')"
        $lock = Get-Content -LiteralPath (Join-Path $script:ToolRoot 'runtime-lock.json') -Raw | ConvertFrom-Json
        Write-Host "Pinned Python: $($lock.python); torch: $($lock.packages.torch); no automatic alternatives."
    }
}

function Test-Resources([double]$DiskGiB = 30, [switch]$Training) {
    if (-not [Environment]::Is64BitOperatingSystem -or -not [Environment]::Is64BitProcess) {
        throw 'Use ordinary 64-bit Windows PowerShell on Windows x86-64.'
    }
    $os = Get-CimInstance -ClassName Win32_OperatingSystem -OperationTimeoutSec 10
    $cpu = @(Get-CimInstance -ClassName Win32_Processor -OperationTimeoutSec 10)[0]
    if ($cpu.Architecture -ne 9 -or $os.ProductType -ne 1 -or [version]$os.Version -lt [version]'10.0') {
        throw 'This handoff requires an x86-64 Windows 10/11 desktop. Windows 11 is recommended.'
    }
    if (-not (Get-Command nvidia-smi -ErrorAction SilentlyContinue)) {
        throw 'nvidia-smi was not found. Install/verify the NVIDIA driver manually from nvidia.com; do not install CUDA Toolkit.'
    }
    $policy = Get-Content -LiteralPath (Join-Path $script:ToolRoot 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $gpu = $policy.remote_resources
    $smi = (Get-Command nvidia-smi -CommandType Application).Source
    $line = Invoke-PythonProbe -Executable $smi -Arguments @('--id=0','--query-gpu=name,memory.total,memory.free,memory.used,driver_version,compute_cap','--format=csv,noheader,nounits')
    $v = $line.Split(',') | ForEach-Object { $_.Trim() }
    if ($v.Count -ne 6) { throw 'Unexpected nvidia-smi output; verify the driver manually.' }
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
    Assert-TargetHardware -Name $v[0] -Capacity $gpuTotal -Capability $v[5] -Free $gpuFree -Available $available -Training:$Training
    if ($drive.AvailableFreeSpace -lt $DiskGiB * 1GB) { throw "Need at least $DiskGiB GiB free on the repository volume." }
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

function Get-PythonInvocation {
    param([ValidateSet('Launcher','Interpreter')][string]$Mode, [string]$Executable, [string[]]$Arguments)
    $leaf = [IO.Path]::GetFileName($Executable)
    if ($Mode -eq 'Launcher') {
        if ($leaf -ine 'py.exe') { throw 'Launcher mode requires py.exe, never python.exe.' }
        return @{ Executable = $Executable; Arguments = @('-3.12') + $Arguments }
    }
    if ($leaf -ine 'python.exe') { throw 'Resolved interpreter mode requires the exact python.exe path.' }
    foreach ($argument in $Arguments) {
        if ($argument -match '^-(?:[23](?:[.\-]|$)|V:)') { throw 'Never pass a launcher selector to python.exe.' }
    }
    return @{ Executable = $Executable; Arguments = @($Arguments) }
}

function ConvertTo-NativeArguments([string]$Executable, [string[]]$Arguments) {
    $leaf = [IO.Path]::GetFileName($Executable)
    if ($leaf -ieq 'python.exe') {
        $null = Get-PythonInvocation -Mode Interpreter -Executable $Executable -Arguments $Arguments
    }
    # The legacy launcher parses selectors from the raw command line. Quoting
    # "-3.12" makes it reach python.exe instead. Paths/payloads still need quoting.
    return (($Arguments | ForEach-Object {
        if ($leaf -ieq 'py.exe' -and $_ -match '^-(?:[23](?:\.\d+)*(?:-(?:32|64))?|V:[A-Za-z0-9_./-]+)$') { $_ }
        else { Quote-NativeArgument $_ }
    }) -join ' ')
}

function Invoke-PythonProbe([string]$Executable, [string[]]$Arguments) {
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $Executable
    $info.Arguments = ConvertTo-NativeArguments -Executable $Executable -Arguments $Arguments
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $info.StandardOutputEncoding = [Text.UTF8Encoding]::new($false)
    $info.StandardErrorEncoding = [Text.UTF8Encoding]::new($false)
    $info.EnvironmentVariables['PYTHONIOENCODING'] = 'utf-8'
    # Never let an inherited launcher preference trigger an installation.
    foreach ($name in @('PYLAUNCHER_ALLOW_INSTALL','PYLAUNCHER_ALWAYS_INSTALL','PYLAUNCHER_DRYRUN','PYTHONPATH','PYTHONHOME','PYTHONOPTIMIZE')) {
        $info.EnvironmentVariables.Remove($name)
    }
    $process = [Diagnostics.Process]::new()
    $process.StartInfo = $info
    try {
        $null = $process.Start()
        $stdout = $process.StandardOutput.ReadToEndAsync()
        $stderr = $process.StandardError.ReadToEndAsync()
        if (-not $process.WaitForExit(15000)) { Stop-OwnedTree $process.Id; throw 'Python identity probe timed out; no setup started.' }
        if (-not $stdout.Wait(2000) -or -not $stderr.Wait(2000)) { throw 'Bounded output drain expired.' }
        $output = $stdout.GetAwaiter().GetResult()
        $errorText = $stderr.GetAwaiter().GetResult()
        if ($process.ExitCode -ne 0) { throw "Python identity probe failed (exit $($process.ExitCode)): $errorText" }
        return $output.Trim()
    } finally { $process.Dispose() }
}

function Assert-FrozenPythonIdentity($Identity) {
    if ($Identity.version -cne '3.12.10' -or $Identity.bits -ne 64) {
        throw 'Python must be exactly 3.12.10 x64. Do not change the pinned version or reinstall a working launcher.'
    }
    if (-not [IO.Path]::IsPathRooted($Identity.executable) -or [IO.Path]::GetFileName($Identity.executable) -ine 'python.exe') {
        throw 'Python did not report an absolute python.exe interpreter path.'
    }
}

function Resolve-FrozenPython([string]$LauncherPath = '') {
    if (-not $LauncherPath -and $env:RTX3060_RESOLVED_PYTHON) {
        $probe = 'import json,platform,struct,sys; print(json.dumps(dict(executable=sys.executable,version=platform.python_version(),bits=struct.calcsize(chr(80))*8)))'
        $identity = Invoke-PythonProbe -Executable $env:RTX3060_RESOLVED_PYTHON -Arguments @('-B','-c',$probe) | ConvertFrom-Json
        Assert-FrozenPythonIdentity $identity
        if (-not [string]::Equals([IO.Path]::GetFullPath($env:RTX3060_RESOLVED_PYTHON),[IO.Path]::GetFullPath($identity.executable),[StringComparison]::OrdinalIgnoreCase)) { throw 'Cached interpreter identity changed.' }
        return [string]$identity.executable
    }
    if (-not $LauncherPath) {
        $launcher = Get-Command py -CommandType Application -ErrorAction SilentlyContinue
        if (-not $launcher) {
            $candidate = Get-Command python -CommandType Application -ErrorAction SilentlyContinue
            if (-not $candidate -or $candidate.Source -match 'WindowsApps') { throw 'ACTION REQUIRED: install Python 3.12.10 x64 manually from python.org, then rerun.' }
            $probe = 'import json,platform,struct,sys; print(json.dumps(dict(executable=sys.executable,version=platform.python_version(),bits=struct.calcsize(chr(80))*8)))'
            $identity = Invoke-PythonProbe -Executable $candidate.Source -Arguments @('-B','-c',$probe) | ConvertFrom-Json
            Assert-FrozenPythonIdentity $identity
            return [string]$identity.executable
        }
        $LauncherPath = $launcher.Source
    }
    # JSON escapes Unicode paths, avoiding console-codepage corruption on PS 5.1.
    $probe = 'import json,platform,struct,sys; print(json.dumps(dict(executable=sys.executable,version=platform.python_version(),bits=struct.calcsize(chr(80))*8)))'
    $command = Get-PythonInvocation -Mode Launcher -Executable $LauncherPath -Arguments @('-B','-c',$probe)
    $selected = Invoke-PythonProbe @command | ConvertFrom-Json
    Assert-FrozenPythonIdentity $selected
    if (-not (Test-Path -LiteralPath $selected.executable -PathType Leaf)) { throw 'Resolved Python interpreter does not exist.' }
    $command = Get-PythonInvocation -Mode Interpreter -Executable $selected.executable -Arguments @('--version')
    if ((Invoke-PythonProbe @command) -cne 'Python 3.12.10') { throw 'Resolved interpreter version check failed; setup stopped.' }
    $command = Get-PythonInvocation -Mode Interpreter -Executable $selected.executable -Arguments @('-B','-c',$probe)
    $verified = Invoke-PythonProbe @command | ConvertFrom-Json
    Assert-FrozenPythonIdentity $verified
    if (-not [string]::Equals([IO.Path]::GetFullPath($selected.executable), [IO.Path]::GetFullPath($verified.executable), [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Resolved interpreter identity changed; setup stopped.'
    }
    Write-Host "Verified Python 3.12.10 x64: $($verified.executable)"
    return [string]$verified.executable
}

function Stop-OwnedTree([int]$OwnerPid) {
    $children = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$OwnerPid" -OperationTimeoutSec 10 -ErrorAction SilentlyContinue)
    foreach ($child in $children) { Stop-OwnedTree -OwnerPid ([int]$child.ProcessId) }
    Stop-Process -Id $OwnerPid -ErrorAction SilentlyContinue
}

function Invoke-Bounded([string]$Executable, [string[]]$Arguments, [int]$Timeout, [string]$Name) {
    [IO.Directory]::CreateDirectory($script:ScratchRoot) | Out-Null
    foreach ($environmentName in @('PYTHONHOME','PYTHONPATH','PYTHONOPTIMIZE')) { [Environment]::SetEnvironmentVariable($environmentName,$null,'Process') }
    $env:PYTHONUNBUFFERED = '1'
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
    $quoted = ConvertTo-NativeArguments -Executable $Executable -Arguments $Arguments
    $process = Start-Process -FilePath $Executable -ArgumentList $quoted -WorkingDirectory $script:RepoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    # Windows PowerShell 5.1 otherwise may expose a null ExitCode after a fast
    # child exits. Keep the native handle open until its exit code is consumed.
    $taskProcessHandle = $process.Handle
    Write-Host "ACTIVE: $Name; budget=$Timeout s; log=$stdout"
    $clock = [Diagnostics.Stopwatch]::StartNew()
    try {
        while (-not $process.WaitForExit(1000)) {
            if ($clock.Elapsed.TotalSeconds -gt $Timeout) {
                Stop-OwnedTree -OwnerPid $process.Id
                throw "Watchdog $Timeout seconds expired during $Name. Only the gate-owned process tree was stopped; run script 05 and send the result."
            }
            if ([int]$clock.Elapsed.TotalSeconds % 10 -eq 0) { Write-Host "$Name ($([int]$clock.Elapsed.TotalSeconds)s), stdout bytes=$((Get-Item -LiteralPath $stdout).Length), stderr bytes=$((Get-Item -LiteralPath $stderr).Length)"; Get-Content -LiteralPath $stdout -Tail 2 -Encoding UTF8 | Write-Host }
        }
        if (-not $process.WaitForExit(2000)) { throw 'Bounded exit wait expired' }
        if (Test-Path -LiteralPath $stdout) { Get-Content -LiteralPath $stdout -Tail 40 -Encoding UTF8 | Write-Host }
        if (Test-Path -LiteralPath $stderr) { Get-Content -LiteralPath $stderr -Tail 40 -Encoding UTF8 | Write-Host }
        if ($null -eq $process.ExitCode -or $process.ExitCode -ne 0) { throw "$Name failed (exit $($process.ExitCode)). Follow the message above; run script 05 to package diagnostics. Do not change versions or retry training." }
    } finally {
        if (-not $process.HasExited) { Stop-OwnedTree -OwnerPid $process.Id }
        $process.Dispose()
    }
}

function Initialize-Checkout([string]$RequestedRoot) {
    $actual = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..')).TrimEnd('\','/')
    if ($RequestedRoot) {
        $requested = (Resolve-Path -LiteralPath $RequestedRoot).Path.TrimEnd('\','/')
        if (-not [string]::Equals($actual,$requested,[StringComparison]::OrdinalIgnoreCase)) { throw 'RepoRoot must agree with the checkout containing the invoked scripts.' }
    }
    $script:RepoRoot = $actual
    foreach ($relative in @('.tmp/rtx3060-12gb-targeted-1536-smoke','.venv-qlora-remote','AlagModels/Qwen3-4B','AlagModels/adapters/rtx3060-12gb-targeted-1536-smoke','handoff-results')) {
        $path = Join-Path $actual $relative
        while ($path -and $path.Length -ge $actual.Length) {
            if ((Test-Path -LiteralPath $path) -and ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Runtime path is a reparse point; preserve it and use a real local checkout.' }
            $path = Split-Path -Parent $path
        }
    }
    $cursor = Get-Item -LiteralPath $actual
    while ($null -ne $cursor) {
        if ($cursor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Repository ancestor is a reparse point; use its real location.' }
        $cursor = $cursor.Parent
    }
}

function Assert-TargetHardware([string]$Name,[double]$Capacity,[string]$Capability,[double]$Free,[double]$Available,[switch]$Training) {
    $p = Get-Content -LiteralPath (Join-Path $script:ToolRoot 'config.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    $g = $p.remote_resources
    $failed = @()
    if ($Name.Trim() -notmatch $g.gpu_name_pattern) { $failed += 'desktop_RTX3060_name' }
    if ($Capacity -lt $g.physical_vram_min_MiB) { $failed += 'physical_capacity' }
    if ($Capability -ne ($g.gpu_capability -join '.')) { $failed += 'capability' }
    if ($Available -lt $p.host_memory.start_min_available_bytes) { $failed += 'host_available' }
    if ($Training -and $Free -lt $g.nvidia_min_free_before_training_MiB) { $failed += 'nvidia_free' }
    if ($failed.Count) { throw ('Hardware precondition failed: ' + ($failed -join ', ') + '. No Qwen load started.') }
}

function Get-HandoffPlan([switch]$PrepareOnly,[switch]$PackageOnly) {
    if ($PrepareOnly -and $PackageOnly) { throw 'Choose PrepareOnly or PackageOnly.' }
    if ($PackageOnly) { return @(5) }
    if ($PrepareOnly) { return @(0,1,2,3) }
    return @(0,1,2,3,4,5)
}

function Invoke-HandoffPhase([int]$Number,[string]$ModelArchive,[switch]$AllowModelDownload,[string]$TransportSha256) {
    $names = @('00-preflight.ps1','01-setup-python-env.ps1','02-download-and-verify-model.ps1','03-prepare-smoke.ps1','04-run-targeted-memory-smoke.ps1','05-package-result.ps1')
    $limits = @(180,1800,1800,1200,3000,180)
    $argv = @('-NoProfile','-ExecutionPolicy','Bypass','-File',(Join-Path $script:ToolRoot $names[$Number]),'-RepoRoot',$script:RepoRoot)
    if ($Number -eq 2) {
        if ($ModelArchive) { $argv += @('-ModelArchive',$ModelArchive) }
        if ($AllowModelDownload) { $argv += '-AllowModelDownload' }
        if ($TransportSha256) { $argv += @('-TransportSha256',$TransportSha256) }
    }
    Invoke-Bounded -Executable (Join-Path $PSHOME 'powershell.exe') -Arguments $argv -Timeout $limits[$Number] -Name ('phase-{0:00}' -f $Number)
}

function Invoke-ResultVerification([string]$ResolvedPython) {
    $archive = Join-Path $script:RepoRoot 'handoff-results/RTX3060_12GB_TARGETED_LORA_1536_ENVELOPE_RESULT.zip'
    Invoke-Bounded -Executable $ResolvedPython -Arguments @('-B',(Join-Path $script:ToolRoot 'verify_result.py'),$archive) -Timeout 180 -Name 'result-verification'
}
