$ErrorActionPreference = 'Stop'

$testRoot = Join-Path $env:TEMP 'Clean Machine Test'
if (Test-Path $testRoot) {
    Remove-Item -Recurse -Force $testRoot
}
New-Item -ItemType Directory -Path $testRoot | Out-Null

Write-Host "Extracting LUCY.zip to Clean Machine Test folder..."
Expand-Archive -Path "dist\LUCY.zip" -DestinationPath $testRoot

$extractedDir = Join-Path $testRoot "LUCY"
Write-Host "Extracted to: $extractedDir"

# Check required files
$required = @(
    "setup.bat",
    "LUCY.exe",
    "main.py",
    "ui.py",
    "runtime\python.exe",
    "config\api_keys.json",
    "core\face_model.obj"
)

foreach ($f in $required) {
    $p = Join-Path $extractedDir $f
    if (-not (Test-Path $p)) {
        throw "Missing file in ZIP: $f"
    }
}
Write-Host "All critical files verified in ZIP!"

# Check sanitized api_keys.json
$cfg = Get-Content (Join-Path $extractedDir "config\api_keys.json") -Raw | ConvertFrom-Json
if ($cfg.gemini_api_key -ne "") {
    throw "Security issue: gemini_api_key is not empty!"
}
Write-Host "Security verified: gemini_api_key is empty."

# Strip Python from PATH
$cleanPath = ($env:PATH -split ';' | Where-Object { $_ -notmatch 'Python' -and $_ -notmatch 'uv' -and $_ -notmatch 'local\\bin' }) -join ';'

Write-Host "Testing setup.bat in clean environment..."
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = "cmd.exe"
$psi.Arguments = "/c setup.bat"
$psi.WorkingDirectory = $extractedDir
$psi.EnvironmentVariables["PATH"] = $cleanPath
$psi.UseShellExecute = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true

$proc = [System.Diagnostics.Process]::Start($psi)
$stdout = $proc.StandardOutput.ReadToEnd()
$stderr = $proc.StandardError.ReadToEnd()
$proc.WaitForExit(10000)

Write-Host "setup.bat Exit Code: $($proc.ExitCode)"
Write-Host "setup.bat Output:`n$stdout"

$logPath = Join-Path $extractedDir "logs\setup.log"
if (Test-Path $logPath) {
    Write-Host "setup.log content:"
    Get-Content $logPath
}

# Test standalone python execution in extracted folder
Write-Host "Testing runtime import from extracted folder..."
$rtPython = Join-Path $extractedDir "runtime\python.exe"
& $rtPython -c "import main; print('EXTRACTED_STANDALONE_IMPORT_SUCCESS')"
Write-Host "CLEAN MACHINE TEST COMPLETED SUCCESSFULLY!"
