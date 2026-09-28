param(
    [string]$Pptx = "",
    [string]$Pdf = "",
    [string]$PngDir = ""
)
$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..\..\..')
if (-not $Pptx) { $Pptx = Join-Path $root 'docs\submission\TALKNFACE_PRODUCT_PITCH_RU.pptx' }
if (-not $Pdf) { $Pdf = Join-Path $root 'docs\submission\TALKNFACE_PRODUCT_PITCH_RU.pdf' }
if (-not $PngDir) { $PngDir = Join-Path $root '.tmp\organizer-presentation-01\slides' }
New-Item -ItemType Directory -Force -Path $PngDir | Out-Null
$Pptx = (Resolve-Path $Pptx).Path
$pdfParent = Split-Path $Pdf
if (-not (Test-Path $pdfParent)) { New-Item -ItemType Directory -Force -Path $pdfParent | Out-Null }
$Pdf = [IO.Path]::GetFullPath($Pdf)
$PngDir = [IO.Path]::GetFullPath($PngDir)
if (Test-Path $PngDir) { Get-ChildItem $PngDir -Filter '*.PNG' | Remove-Item -Force }
$ppSaveAsPDF = 32
$ppSaveAsPNG = 18
$ppt = New-Object -ComObject PowerPoint.Application
try {
    $ppt.DisplayAlerts = 1
    $pres = $ppt.Presentations.Open($Pptx, $true, $false, $false)
    try {
        if (Test-Path $Pdf) { Remove-Item -LiteralPath $Pdf -Force }
        $pres.SaveCopyAs($Pdf, $ppSaveAsPDF)
        $i = 1
        foreach ($slide in $pres.Slides) {
            $out = Join-Path $PngDir ('slide-{0:D2}.png' -f $i)
            $slide.Export($out, 'PNG', 1920, 1080)
            $i++
        }
        Write-Output ("slides=" + $pres.Slides.Count)
        Write-Output ("pdf=" + $Pdf)
        Write-Output ("png=" + $PngDir)
    } finally {
        $pres.Close()
    }
} finally {
    $ppt.Quit()
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
