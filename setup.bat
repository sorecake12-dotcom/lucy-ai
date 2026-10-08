@echo off
setlocal enabledelayedexpansion

:: -----------------------------------------------------------------------------
:: LUCY DESKTOP ASSISTANT - INSTALLER, SETUP & LAUNCHER
:: Target Installation Directory: %LOCALAPPDATA%\LUCY
:: -----------------------------------------------------------------------------

title LUCY Setup & Launcher

set "SRC_DIR=%~dp0"
if "%SRC_DIR:~-1%"=="\" set "SRC_DIR=%SRC_DIR:~0,-1%"

set "INSTALL_DIR=%LOCALAPPDATA%\LUCY"
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%INSTALL_DIR%\logs" mkdir "%INSTALL_DIR%\logs"
set "LOG_FILE=%INSTALL_DIR%\logs\setup.log"

echo ==================================================
echo                  LUCY ASSISTANT
echo ==================================================
echo.

:: 1. Synchronize source files to %INSTALL_DIR% if run from release/download folder
if /i not "%SRC_DIR%"=="%INSTALL_DIR%" (
    echo [%date% %time%] Syncing application files from "%SRC_DIR%" to "%INSTALL_DIR%" >> "%LOG_FILE%"
    robocopy "%SRC_DIR%" "%INSTALL_DIR%" /E /XD .git .github .freebuff __pycache__ runtime logs /XF *.pyc *.log *.tmp LUCY.exe LUCY.lnk face.png setup.log /R:1 /W:1 /NJH /NJS /NDL /NC /NS >nul 2>&1
    if !errorlevel! geq 8 (
        echo [WARNING] File sync encountered warnings. Continuing setup... >> "%LOG_FILE%"
    )
)

:: 2. Fast Path: If runtime and dependencies are already functional
if exist "%INSTALL_DIR%\runtime\python.exe" (
    "%INSTALL_DIR%\runtime\python.exe" -c "import PyQt6" >nul 2>&1
    if !errorlevel! equ 0 (
        echo [%date% %time%] Fast launch initiated >> "%LOG_FILE%"
        goto :LAUNCH
    )
)

:: 3. Provision Portable Runtime
cls
echo ==================================================
echo                 LUCY SETUP
echo ==================================================
echo.
echo Checking runtime...
echo [%date% %time%] Setting up portable runtime in "%INSTALL_DIR%" >> "%LOG_FILE%"

if not exist "%INSTALL_DIR%\runtime\python.exe" (
    echo Preparing portable Python runtime...
    where curl >nul 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] curl.exe is required for first-run setup.
        echo Please ensure Windows 10/11 is updated.
        echo [%date% %time%] curl.exe missing >> "%LOG_FILE%"
        goto :FAIL
    )

    set "STANDALONE_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20240814/cpython-3.11.9+20240814-x86_64-pc-windows-msvc-shared-install_only.tar.gz"
    set "PKG_TMP=%TEMP%\lucy_python_311.tar.gz"

    echo Downloading Python runtime (one-time download)...
    curl -L -s --fail "!STANDALONE_URL!" -o "!PKG_TMP!"
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to download runtime package.
        echo Please check your internet connection and try again.
        echo [%date% %time%] Failed download from !STANDALONE_URL! >> "%LOG_FILE%"
        goto :FAIL
    )

    echo Extracting runtime...
    if not exist "%INSTALL_DIR%\runtime" mkdir "%INSTALL_DIR%\runtime"
    tar -xzf "!PKG_TMP!" -C "%INSTALL_DIR%\runtime" --strip-components=1
    del /f /q "!PKG_TMP!" >nul 2>&1

    if not exist "%INSTALL_DIR%\runtime\python.exe" (
        echo [ERROR] Runtime extraction failed.
        echo [%date% %time%] python.exe missing after extraction >> "%LOG_FILE%"
        goto :FAIL
    )

    if exist "%INSTALL_DIR%\runtime\Lib\EXTERNALLY-MANAGED" (
        del /f /q "%INSTALL_DIR%\runtime\Lib\EXTERNALLY-MANAGED" >nul 2>&1
    )
)

:: 4. Install Dependencies
echo Checking dependencies...
"%INSTALL_DIR%\runtime\python.exe" -c "import PyQt6" >nul 2>&1
if !errorlevel! neq 0 (
    echo Installing application dependencies (one-time setup)...
    echo [%date% %time%] Installing requirements.txt >> "%LOG_FILE%"
    "%INSTALL_DIR%\runtime\python.exe" -m pip install --break-system-packages -r "%INSTALL_DIR%\requirements.txt" >> "%LOG_FILE%" 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] Dependency installation failed. Check "%LOG_FILE%".
        echo [%date% %time%] pip install failed with code !errorlevel! >> "%LOG_FILE%"
        goto :FAIL
    )
)

:: 5. Compile Native Launcher
:BUILD_LAUNCHER
if not exist "%INSTALL_DIR%\LUCY.exe" (
    if exist "%INSTALL_DIR%\launcher\LUCY_launcher.cs" (
        set "CSC_EXE=%SystemRoot%\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
        if not exist "!CSC_EXE!" set "CSC_EXE=%SystemRoot%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
        if exist "!CSC_EXE!" (
            echo Building native launcher...
            echo [%date% %time%] Compiling LUCY.exe into %INSTALL_DIR% >> "%LOG_FILE%"
            set "ICON_ARG="
            if exist "%INSTALL_DIR%\config\logo.ico" (
                set "ICON_ARG=/win32icon:\"%INSTALL_DIR%\config\logo.ico\""
            ) else if exist "%INSTALL_DIR%\config\jarvis.ico" (
                set "ICON_ARG=/win32icon:\"%INSTALL_DIR%\config\jarvis.ico\""
            )
            "!CSC_EXE!" /nologo /target:winexe !ICON_ARG! /out:"%INSTALL_DIR%\LUCY.exe" "%INSTALL_DIR%\launcher\LUCY_launcher.cs" >> "%LOG_FILE%" 2>&1
        )
    )
)

:: 6. Create Desktop and Start Menu Shortcuts
echo Creating shortcuts...
powershell -NoProfile -NonInteractive -Command ^
    "$ws = New-Object -ComObject WScript.Shell; " ^
    "$exe = '%INSTALL_DIR%\LUCY.exe'; " ^
    "if (-not (Test-Path $exe)) { $exe = '%INSTALL_DIR%\runtime\pythonw.exe'; $args = '\"%INSTALL_DIR%\main.py\"' } else { $args = '' }; " ^
    "$ico = '%INSTALL_DIR%\config\logo.ico'; " ^
    "if (-not (Test-Path $ico)) { $ico = '%INSTALL_DIR%\config\jarvis.ico' }; " ^
    "$paths = @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('CommonDesktopDirectory'), \"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\"); " ^
    "foreach ($p in $paths) { " ^
    "    if (Test-Path $p) { " ^
    "        $lnk = $ws.CreateShortcut(\"$p\LUCY.lnk\"); " ^
    "        $lnk.TargetPath = $exe; " ^
    "        if ($args) { $lnk.Arguments = $args }; " ^
    "        $lnk.WorkingDirectory = '%INSTALL_DIR%'; " ^
    "        $lnk.Description = 'LUCY AI Assistant'; " ^
    "        if (Test-Path $ico) { $lnk.IconLocation = $ico }; " ^
    "        $lnk.Save(); " ^
    "    } " ^
    "}" >nul 2>&1

:: 7. Launch LUCY
:LAUNCH
echo Starting LUCY...
echo [%date% %time%] Launching LUCY application >> "%LOG_FILE%"

if exist "%INSTALL_DIR%\LUCY.exe" (
    start "" "%INSTALL_DIR%\LUCY.exe"
) else if exist "%INSTALL_DIR%\runtime\pythonw.exe" (
    start "" "%INSTALL_DIR%\runtime\pythonw.exe" "%INSTALL_DIR%\main.py"
) else (
    start "" "%INSTALL_DIR%\runtime\python.exe" "%INSTALL_DIR%\main.py"
)

exit /b 0

:FAIL
echo.
echo ==================================================
echo LUCY setup could not complete.
echo.
echo Review log file for details:
echo %LOG_FILE%
echo ==================================================
echo.
pause
exit /b 1
