param([Parameter(Mandatory=$true)][string]$OutputPath)
$ErrorActionPreference = 'Stop'
$osInfo = Get-CimInstance Win32_OperatingSystem
$cpuInfo = Get-CimInstance Win32_Processor
$evidence = [ordered]@{
    at_utc = [DateTime]::UtcNow.ToString('o')
    windows = [ordered]@{ caption = $osInfo.Caption; version = $osInfo.Version; architecture = $osInfo.OSArchitecture }
    cpu = @($cpuInfo | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors)
    ram_total_bytes = [long]$osInfo.TotalVisibleMemorySize * 1024
    ram_available_bytes = [long]$osInfo.FreePhysicalMemory * 1024
    installed_python_launcher = @(& py -0p 2>&1 | ForEach-Object { "$_" })
    selected_python = (& .venv-ml/Scripts/python.exe --version 2>&1 | Out-String).Trim()
    nvidia_smi = (& nvidia-smi --query-gpu=name,memory.total,memory.free,driver_version --format=csv,noheader | Out-String).Trim()
    nvidia_smi_header = @(& nvidia-smi | Select-Object -First 12)
    system_changes = $false
}
$json = $evidence | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText((Join-Path (Get-Location) $OutputPath), $json + "`n", [System.Text.UTF8Encoding]::new($false))
Write-Output $json
