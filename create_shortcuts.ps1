$ws = New-Object -ComObject WScript.Shell
$base = Split-Path -Parent $MyInvocation.MyCommand.Definition
$target = Join-Path $base "start.bat"
$icon = Join-Path $base "config\jarvis.ico"

$desks = @(
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('CommonDesktopDirectory'),
    "$env:USERPROFILE\OneDrive\Desktop",
    "$env:PUBLIC\Desktop"
)

foreach ($d in $desks) {
    if (Test-Path $d) {
        foreach ($name in @('LUCY.lnk', 'JARVIS.lnk')) {
            $lnkPath = Join-Path $d $name
            $lnk = $ws.CreateShortcut($lnkPath)
            $lnk.TargetPath = $target
            $lnk.WorkingDirectory = $base
            $lnk.Description = "LUCY / JARVIS Desktop Assistant"
            if (Test-Path $icon) {
                $lnk.IconLocation = $icon
            }
            $lnk.Save()
            Write-Host "Created shortcut: $lnkPath"
        }
    }
}
