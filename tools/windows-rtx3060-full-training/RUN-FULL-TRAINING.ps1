[CmdletBinding()]
param(
    [ValidateSet('Help','Prepare','Start','Resume','Status','Package','Cancel')]
    [string]$Action = 'Help',
    [string]$RunId = '',
    [string]$AuthorizeNewRun = '',
    [string]$Checkpoint = '',
    [string]$PythonExe = '',
    [switch]$DryRun
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
try {
    $repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
    if ($Action -eq 'Help') {
        Write-Output 'V1: one TRAIN epoch, 8000 rows, 2000 updates. Default action: help.'
        Write-Output '-Action Prepare|Start|Resume|Status|Package|Cancel -RunId qwen3-4b-v1'
        Write-Output 'Start additionally requires -AuthorizeNewRun matching RunId.'
        Write-Output 'Resume additionally requires -Checkpoint step-NNNN (newest verified checkpoint).'
        Write-Output '-DryRun: no writes, model execution, installation or downloads.'
        Write-Output 'Read README_RU.md. FULL TRAINING / QUALITY EVALUATION NOT AUTHORIZED YET.'
        exit 0
    }
    if ($RunId -cnotmatch '^qwen3-4b-v1(?:-[a-z0-9]{1,32})?$') { throw 'Explicit valid RunId required.' }
    if (-not $PythonExe) { $PythonExe = Join-Path $repo '.venv-qlora-remote/Scripts/python.exe' }
    if ([IO.Path]::GetFileName($PythonExe) -ine 'python.exe') {
        throw 'Use the exact existing python.exe interpreter, not py.exe. No launcher selector is passed.'
    }
    $arguments = @('-B','-u',(Join-Path $PSScriptRoot 'workflow.py'),$Action.ToLowerInvariant(),'--run-id',$RunId)
    if ($AuthorizeNewRun) { $arguments += @('--authorize-new-run',$AuthorizeNewRun) }
    if ($Checkpoint) { $arguments += @('--checkpoint',$Checkpoint) }
    if ($DryRun) {
        Write-Output ('DRY RUN: {0}; RunId={1}; Python={2}' -f $Action,$RunId,$PythonExe)
        Write-Output ('Runtime/checkpoints/adapter: {0}' -f (Join-Path $repo ('.tmp/qwen3-4b-full-training/' + $RunId)))
        Write-Output ('Results: {0}' -f (Join-Path $repo ('handoff-results/qwen3-4b-full-training/' + $RunId)))
        exit 0
    }
    if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { throw 'Existing validated venv is required. Nothing will be installed.' }
    if ($Action -eq 'Start' -and $AuthorizeNewRun -cne $RunId) { throw 'Start requires explicit -AuthorizeNewRun equal to RunId.' }
    if ($Action -eq 'Resume' -and $Checkpoint -cnotmatch '^step-\d{4}$') { throw 'Resume requires explicit -Checkpoint step-NNNN.' }
    & $PythonExe @arguments
    $nativeCode = $LASTEXITCODE
    exit $nativeCode
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
