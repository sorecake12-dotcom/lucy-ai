$ws = New-Object -ComObject WScript.Shell
$base = Split-Path -Parent $MyInvocation.MyCommand.Definition
$target = Join-Path $base "start.bat"
$icon = Join-Path $base "config\logo.ico"

$desks = @(
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('CommonDesktopDirectory'),
    "$env:USERPROFILE\OneDrive\Desktop",
    "$env:PUBLIC\Desktop"
)

foreach ($d in $desks) {
    if (Test-Path $d) {
        # 1. Remove any old JARVIS shortcuts
        $oldJarvis = Join-Path $d "JARVIS.lnk"
        if (Test-Path $oldJarvis) {
            Remove-Item -Path $oldJarvis -Force -ErrorAction SilentlyContinue
            Write-Host "Removed old shortcut: $oldJarvis"
        }

        # 2. Create the official LUCY shortcut
        $lnkPath = Join-Path $d "LUCY.lnk"
        $lnk = $ws.CreateShortcut($lnkPath)
        $lnk.TargetPath = $target
        $lnk.WorkingDirectory = $base
        $lnk.Description = "LUCY Desktop AI Assistant"
        if (Test-Path $icon) {
            $lnk.IconLocation = $icon
        }
        $lnk.Save()
        Write-Host "Created shortcut: $lnkPath"
    }
}
