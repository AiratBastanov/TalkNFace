param(
    [Parameter(Mandatory = $true)][string]$Template,
    [Parameter(Mandatory = $true)][string]$OutFile
)
$ErrorActionPreference = 'Stop'
$Template = (Resolve-Path -LiteralPath $Template).Path
$outDir = Split-Path -Parent $OutFile
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
$OutFile = [IO.Path]::GetFullPath($OutFile)
Copy-Item -LiteralPath $Template -Destination $OutFile -Force
$ppt = New-Object -ComObject PowerPoint.Application
$ppt.DisplayAlerts = 1
try {
    $pres = $ppt.Presentations.Open($OutFile, $false, $false, $false)
    try {
        $keep = @(7, 8, 9, 11, 12, 13, 14, 16, 17, 18, 24, 26)
        for ($i = $pres.Slides.Count; $i -ge 1; $i--) {
            if ($keep -notcontains $i) { $pres.Slides.Item($i).Delete() }
        }
        $pres.Slides.Item(4).Duplicate() | Out-Null
        $pres.Slides.Item(4).Duplicate() | Out-Null
        $roles = @('title','team','members','attempts','next','marketing','quiz','materials','settings','families','journey','problem','tech','evidence')
        for ($i = 1; $i -le $pres.Slides.Count; $i++) {
            $pres.Slides.Item($i).Tags.Add('role', $roles[$i - 1])
        }
        $order = @('title','team','members','problem','journey','settings','families','attempts','evidence','quiz','marketing','tech','next','materials')
        for ($pos = 0; $pos -lt $order.Count; $pos++) {
            $want = $order[$pos]
            for ($j = 1; $j -le $pres.Slides.Count; $j++) {
                if ($pres.Slides.Item($j).Tags.Item('role') -eq $want) {
                    if ($j -ne ($pos + 1)) { $pres.Slides.Item($j).MoveTo($pos + 1) }
                    break
                }
            }
        }
        foreach ($slide in $pres.Slides) {
            $slide.SlideShowTransition.Hidden = $false
            if ($slide.HasNotesPage) {
                foreach ($sh in $slide.NotesPage.Shapes) {
                    if ($sh.HasTextFrame -eq -1) {
                        if ($sh.TextFrame.HasText -eq -1) { $sh.TextFrame.TextRange.Text = '' }
                    }
                }
            }
        }
        $pres.Save()
        Write-Output ("slides=" + $pres.Slides.Count)
    } finally {
        $pres.Close()
    }
} finally {
    $ppt.Quit()
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}
