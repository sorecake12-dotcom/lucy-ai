# ==============================================================================
# LUCY AI Assistant — 1-Click PowerShell Launcher
# ==============================================================================

$baseDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $baseDir

# 1. Unblock local files
Get-ChildItem -Path $baseDir -Recurse -ErrorAction SilentlyContinue | Unblock-File -ErrorAction SilentlyContinue

# 2. Find best python interpreter
$py = $null
if (Get-Command "pythonw" -ErrorAction SilentlyContinue) {
    $py = "pythonw"
} elseif (Get-Command "python" -ErrorAction SilentlyContinue) {
    $py = "python"
} elseif (Get-Command "py" -ErrorAction SilentlyContinue) {
    $py = "py"
}

if (-not $py) {
    $userPythons = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python\", "$env:LOCALAPPDATA\Python\" -Recurse -Filter "python.exe" -ErrorAction SilentlyContinue
    if ($userPythons) {
        $py = $userPythons[0].FullName
    }
}

if (-not $py) {
    if (Test-Path "$baseDir\runtime\pythonw.exe") {
        $py = "$baseDir\runtime\pythonw.exe"
    } elseif (Test-Path "$baseDir\runtime\python.exe") {
        $py = "$baseDir\runtime\python.exe"
    }
}

if (-not $py) {
    Write-Host "[ERROR] Python 3.11+ not found. Please install Python." -ForegroundColor Red
    Pause
    exit 1
}

# 3. Launch main.py
Start-Process -FilePath $py -ArgumentList (Join-Path $baseDir "main.py") -WorkingDirectory $baseDir
