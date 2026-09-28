# Windows PowerShell 5.1+, no administrator rights or permanent environment changes.
[CmdletBinding()]
param(
    [switch]$Prepare, [switch]$Start, [switch]$Status, [switch]$Stop,
    [switch]$Verify, [switch]$ResetDemoData, [switch]$Backup,
    [string]$Restore, [switch]$SetAdminPassword, [switch]$Help,
    [string]$NodePath, [ValidateRange(1024,65535)][int]$Port = 3000,
    [switch]$PasswordFromStdin
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
if ($PasswordFromStdin) { [Console]::InputEncoding = New-Object Text.UTF8Encoding($false) }
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$runtimeName = 'node-v24.21.0-win-x64'
$archiveHash = '158f7685b44de51f6c0df1d153526cbcd3e1bc739a8dfc607721cef75de9e541'
$release = 'https://nodejs.org/download/release/v24.21.0/'
$toolRoot = Join-Path $root '.tools\arena-runtime'
$localNode = Join-Path $toolRoot "$runtimeName\node.exe"
$timer = [Diagnostics.Stopwatch]::StartNew()

function Assert-SafePath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($root + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Path escapes this checkout; no files changed.' }
    $part = $full
    while ($part) {
        try {
            if ([IO.File]::GetAttributes($part) -band [IO.FileAttributes]::ReparsePoint) {
                throw 'Symlink/junction in demo path. Use a regular checkout directory; data was not removed.'
            }
        } catch [IO.FileNotFoundException] { } catch [IO.DirectoryNotFoundException] { }
        $part = [IO.Path]::GetDirectoryName($part)
    }
}
function Quote-Argument([string]$Value) {
    '"' + [regex]::Replace([regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1') + '"'
}
function Invoke-Captured([string]$Exe, [string[]]$Arguments, [string]$InputText = '', [int]$Seconds = 20) {
    $psi = New-Object Diagnostics.ProcessStartInfo
    $psi.FileName = $Exe
    $psi.Arguments = ($Arguments | ForEach-Object { Quote-Argument $_ }) -join ' '
    $psi.WorkingDirectory = $root
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = New-Object Text.UTF8Encoding($false)
    $psi.StandardErrorEncoding = New-Object Text.UTF8Encoding($false)
    $psi.EnvironmentVariables.Remove('NODE_OPTIONS')
    $psi.EnvironmentVariables.Remove('NODE_PATH')
    $p = New-Object Diagnostics.Process
    $p.StartInfo = $psi
    try {
        [void]$p.Start()
        $stdout = $p.StandardOutput.ReadToEndAsync()
        $stderr = $p.StandardError.ReadToEndAsync()
        if ($InputText) {
            $bytes = [Text.Encoding]::UTF8.GetBytes($InputText)
            $p.StandardInput.BaseStream.Write($bytes, 0, $bytes.Length)
            $p.StandardInput.BaseStream.Flush()
        }
        $p.StandardInput.Close()
        if (-not $p.WaitForExit($Seconds * 1000)) { $p.Kill(); throw 'Runtime check timed out. Retry -Prepare; database and configuration are preserved.' }
        @{ Code = $p.ExitCode; Out = $stdout.GetAwaiter().GetResult().Trim(); Err = $stderr.GetAwaiter().GetResult().Trim() }
    } finally { $p.Dispose() }
}
function Test-Runtime([string]$Exe) {
    if (-not (Test-Path -LiteralPath $Exe -PathType Leaf)) { return $false }
    $npm = Join-Path (Split-Path $Exe) 'node_modules\npm\bin\npm-cli.js'
    if (-not (Test-Path -LiteralPath $npm -PathType Leaf)) { return $false }
    $n = Invoke-Captured $Exe @('-p', 'process.version+" "+process.arch')
    # Reading bundled metadata avoids npm creating global cache/log files during read-only Status.
    $v = Invoke-Captured $Exe @('-p', 'JSON.parse(require("node:fs").readFileSync(process.argv[1],"utf8")).version', (Join-Path (Split-Path $Exe) 'node_modules\npm\package.json'))
    return ($n.Code -eq 0 -and $n.Out -eq 'v24.21.0 x64' -and $v.Code -eq 0 -and $v.Out -eq '11.19.0')
}
function Download-Official([string]$Name, [string]$Destination, [int]$Seconds) {
    Add-Type -AssemblyName System.Net.Http
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $handler = New-Object Net.Http.HttpClientHandler
    $handler.AllowAutoRedirect = $false
    $client = New-Object Net.Http.HttpClient($handler)
    $client.Timeout = [TimeSpan]::FromSeconds($Seconds)
    $client.MaxResponseContentBufferSize = 100MB
    try {
        $response = $client.GetAsync($release + $Name).GetAwaiter().GetResult()
        if (-not $response.IsSuccessStatusCode) { throw 'Official download returned a non-success status.' }
        [IO.File]::WriteAllBytes($Destination, $response.Content.ReadAsByteArrayAsync().GetAwaiter().GetResult())
    } catch { throw 'Node download failed. Allow HTTPS to nodejs.org and retry -Prepare, or supply -NodePath to exact Node 24.21.0 x64/npm 11.19.0. Demo data is unchanged.' }
    finally { $client.Dispose(); $handler.Dispose() }
}
function Check-Archive([string]$ZipPath, [string]$Target, [bool]$Extract) {
    Assert-SafePath $ZipPath
    Assert-SafePath $Target
    if ((Get-FileHash -LiteralPath $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $archiveHash) {
        throw 'Node ZIP checksum failed. Move .tools\arena-runtime aside and retry -Prepare. Database/configuration are safe in .local.'
    }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::OpenRead($ZipPath)
    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        $seen = New-Object 'Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
        $total = 0L
        # Inspect every entry before extracting any entry. Reject links, Windows aliases and zip slip.
        foreach ($entry in $zip.Entries) {
            $name = $entry.FullName
            $parts = $name.TrimEnd('/').Split('/')
            $kind = (($entry.ExternalAttributes -shr 16) -band 61440)
            if (-not $name.StartsWith($runtimeName + '/', [StringComparison]::Ordinal) -or
                $name -match '[\\:\x00-\x1f<>"|?*]' -or ($parts | Where-Object { $_ -eq '' -or $_ -eq '.' -or $_ -eq '..' -or $_ -match '[. ]$|^(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(\.|$)' }) -or
                $kind -notin @(0,16384,32768) -or ($entry.ExternalAttributes -band 1024) -or -not $seen.Add($name.TrimEnd('/'))) {
                throw 'Unsafe Node archive layout; nothing extracted. Retry from the official release.'
            }
            $total += $entry.Length
            if ($total -gt 500MB -or $zip.Entries.Count -gt 15000) { throw 'Node archive exceeds extraction limits.' }
            Assert-SafePath (Join-Path $Target $name)
        }
        if (-not $seen.Contains("$runtimeName/node.exe") -or -not $seen.Contains("$runtimeName/node_modules/npm/bin/npm-cli.js")) { throw 'Incomplete Node archive.' }
        foreach ($entry in $zip.Entries) {
            if ($watch.Elapsed.TotalSeconds -gt 120) { throw 'Node verification/extraction exceeded 120 seconds. Retry -Prepare; demo data is safe.' }
            $dest = Join-Path $Target $entry.FullName
            if ($entry.FullName.EndsWith('/')) {
                if ($Extract) { [void][IO.Directory]::CreateDirectory($dest) }
                continue
            }
            if ($Extract) {
                [void][IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($dest))
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $dest, $false)
            } else {
                if (-not (Test-Path -LiteralPath $dest -PathType Leaf)) { throw 'Incomplete local Node runtime. Move .tools\arena-runtime aside, then retry -Prepare; .local is safe.' }
                $hash = [Security.Cryptography.SHA256]::Create(); $inputStream = $entry.Open()
                try { $expected = [BitConverter]::ToString($hash.ComputeHash($inputStream)).Replace('-', '') }
                finally { $inputStream.Dispose(); $hash.Dispose() }
                $hash = [Security.Cryptography.SHA256]::Create(); $actualStream = [IO.File]::OpenRead($dest)
                try { $actual = [BitConverter]::ToString($hash.ComputeHash($actualStream)).Replace('-', '') }
                finally { $actualStream.Dispose(); $hash.Dispose() }
                if ($actual -ne $expected) { throw 'Corrupted local Node runtime. Move .tools\arena-runtime aside, then retry -Prepare; .local is safe.' }
            }
        }
    } finally { $zip.Dispose() }
}
function Resolve-Node([bool]$MayDownload) {
    if ($NodePath) {
        $candidate = [IO.Path]::GetFullPath($NodePath)
        if (-not (Test-Runtime $candidate)) { throw 'Unsupported -NodePath: require Node 24.21.0 x64 and bundled npm 11.19.0. Omit -NodePath to bootstrap. Database/configuration are unchanged.' }
        return $candidate
    }
    $zipPath = Join-Path $toolRoot "$runtimeName.zip"
    if (Test-Path -LiteralPath (Join-Path $toolRoot $runtimeName)) {
        if (-not (Test-Path -LiteralPath $zipPath)) { throw 'Local runtime verification ZIP is missing. Move .tools\arena-runtime aside and retry -Prepare; .local is safe.' }
        Check-Archive $zipPath $toolRoot $false
        if (-not (Test-Runtime $localNode)) { throw 'Invalid local Node/npm versions. Move .tools\arena-runtime aside and retry -Prepare; .local is safe.' }
        return $localNode
    }
    $system = Get-Command node.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($system -and (Test-Runtime $system.Source)) { return $system.Source }
    if (-not $MayDownload) { throw 'Exact Node runtime is unavailable. Run -Prepare (or provide -NodePath). Existing demo data is safe.' }
    Write-Host 'Obtaining official Node 24.21.0 x64 + npm 11.19.0 (installed incompatible Node is not used).'
    Assert-SafePath $toolRoot
    [void][IO.Directory]::CreateDirectory($toolRoot)
    $acquire = [Diagnostics.Stopwatch]::StartNew()
    $sums = Join-Path $toolRoot 'SHASUMS256.txt'
    Download-Official 'SHASUMS256.txt' $sums 30
    $expectedLine = "$archiveHash  $runtimeName.zip"
    if (-not ([IO.File]::ReadAllLines($sums) -contains $expectedLine)) { throw 'Official SHASUMS does not match the pinned release. Stop and check release provenance; demo data is unchanged.' }
    if (-not (Test-Path -LiteralPath $zipPath)) {
        $partial = Join-Path $toolRoot ('download-' + [Guid]::NewGuid().ToString('N') + '.partial')
        Download-Official "$runtimeName.zip" $partial ([Math]::Max(1, 300 - [int]$acquire.Elapsed.TotalSeconds))
        if ((Get-FileHash -LiteralPath $partial -Algorithm SHA256).Hash.ToLowerInvariant() -ne $archiveHash) { throw 'Downloaded Node checksum failed; untrusted archive was not extracted. Retry -Prepare; data is safe.' }
        Move-Item -LiteralPath $partial -Destination $zipPath
    }
    # A crash leaves only a staging directory. A later Prepare uses a fresh staging name.
    $stage = Join-Path $toolRoot ('extract-' + [Guid]::NewGuid().ToString('N'))
    Check-Archive $zipPath $stage $true
    $from = Join-Path $stage $runtimeName; $to = Join-Path $toolRoot $runtimeName
    Assert-SafePath $from; Assert-SafePath $to
    Move-Item -LiteralPath $from -Destination $to
    if (-not (Test-Runtime $localNode)) { throw 'Downloaded runtime version check failed; demo data is unchanged.' }
    Write-Host ('Runtime acquisition: {0:N3}s; SHA256 verified against official SHASUMS.' -f $acquire.Elapsed.TotalSeconds)
    return $localNode
}

$mutex = $null; $held = $false; $exitCode = 0
try {
    $actions = @(@($Prepare,$Start,$Status,$Stop,$Verify,$ResetDemoData,$Backup,$SetAdminPassword,$Help) | Where-Object { $_ }).Count
    if ($Restore) { $actions++ }
    if ($Help -or $actions -eq 0) {
        Write-Host @'
Negotiation Arena / Windows x64 / local guided demo (no AI)
  -Prepare          Obtain exact Node, securely set first password, npm ci, build, verify DB
  -Start            Start production on http://127.0.0.1:3000 (optional -Port 1024..65535)
  -Status           Read-only status; never downloads or installs
  -Stop             Gracefully stop only this checkout's managed demo
  -Verify           Check prepared source/build/dependencies/config/database
  -Backup           Safe SQLite backup, including during a running demo
  -Restore ID       Restore a listed backup (server must be stopped); preserves previous DB
  -ResetDemoData     Explicitly reset only demo DB (stopped); preserves backup and password
  -SetAdminPassword Explicitly replace password (stopped); old admin sessions become invalid
  -Help             This text
Options: -NodePath C:\path\node.exe (exact 24.21.0 x64/npm 11.19.0).
-PasswordFromStdin is for automation only: secret through UTF-8 stdin, never an argument.
Data: .local\arena-demo\   Secret config: .local\arena-config\admin.json
No Git, Python, CUDA, Docker, model, system install or permanent PATH change at runtime.
'@
        exit 0
    }
    if ($actions -ne 1) { throw 'Select exactly one action. Use -Help.' }
    if ($env:OS -ne 'Windows_NT' -or -not [Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') { throw 'Use 64-bit Windows PowerShell on Windows x64. This demo path is not certified on ARM/Linux/macOS.' }
    Assert-SafePath (Join-Path $root '.local\arena-demo')
    Assert-SafePath (Join-Path $root '.local\arena-config')
    $h = [Security.Cryptography.SHA256]::Create()
    try { $key = [BitConverter]::ToString($h.ComputeHash([Text.Encoding]::UTF8.GetBytes($root.ToLowerInvariant()))).Replace('-', '') } finally { $h.Dispose() }
    $mutex = New-Object Threading.Mutex($false, ('Local\ArenaDemo-' + $key))
    try { $held = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $held = $true }
    if (-not $held) { throw 'Another demo command is running in this checkout. Wait for it to finish; data is unchanged.' }
    if (($Status -or $Stop) -and -not (Test-Path -LiteralPath (Join-Path $root '.local\arena-demo'))) { Write-Host 'Demo is stopped; not prepared.'; exit 0 }
    $node = Resolve-Node ([bool]$Prepare)
    Write-Host ('Runtime: Node 24.21.0 x64 / npm 11.19.0; resolution {0:N3}s' -f $timer.Elapsed.TotalSeconds)
    $cli = Join-Path $PSScriptRoot 'demo\cli.mjs'
    if ($Prepare -or $SetAdminPassword) {
        $check = Invoke-Captured $node @($cli, 'config-check', $(if ($SetAdminPassword) { 'replace' } else { 'keep' }))
        if ($check.Code -ne 0) { throw $check.Err }
        if ($check.Out -eq 'PASSWORD_REQUIRED') {
            if ($PasswordFromStdin) { $password = [Console]::In.ReadToEnd().TrimEnd("`r", "`n") }
            else {
                $secure = Read-Host 'Create local administrator password (12-256 characters, hidden)' -AsSecureString
                $confirm = Read-Host 'Repeat administrator password' -AsSecureString
                $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
                $ptr2 = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($confirm)
                try {
                    $password = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
                    if ($password -cne [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr2)) { throw 'Passwords differ. Retry -Prepare; existing data is safe.' }
                } finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr); [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr2); $secure.Dispose(); $confirm.Dispose() }
            }
            try {
                $result = Invoke-Captured $node @($cli, 'configure', $(if ($SetAdminPassword) { 'replace' } else { 'keep' })) $password
                if ($result.Code -ne 0) { throw $result.Err }
                Write-Host $result.Out
            } finally { $password = $null }
        }
    }
    $action = if ($Prepare) { 'prepare' } elseif ($Start) { 'start' } elseif ($Status) { 'status' } elseif ($Stop) { 'stop' } elseif ($Verify) { 'verify' } elseif ($Backup) { 'backup' } elseif ($Restore) { 'restore' } elseif ($ResetDemoData) { 'reset' } else { 'config-check' }
    # Only this child process receives the selected runtime at the front of PATH.
    $savedPath = $env:PATH; $savedOptions = $env:NODE_OPTIONS; $savedNodePath = $env:NODE_PATH
    try {
        $env:PATH = (Split-Path $node) + ';' + $savedPath
        $env:NODE_OPTIONS = $null; $env:NODE_PATH = $null
        & $node $cli $action $(if ($Restore) { $Restore } else { [string]$Port })
        if ($LASTEXITCODE -ne 0) { $exitCode = 1 }
    } finally { $env:PATH = $savedPath; $env:NODE_OPTIONS = $savedOptions; $env:NODE_PATH = $savedNodePath }
    Write-Host ('Command elapsed: {0:N3}s' -f $timer.Elapsed.TotalSeconds)
} catch {
    [Console]::Error.WriteLine('Demo: ' + $_.Exception.Message)
    $exitCode = 1
} finally {
    if ($held) { $mutex.ReleaseMutex() }
    if ($mutex) { $mutex.Dispose() }
}
exit $exitCode
