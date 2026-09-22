@echo off
setlocal enabledelayedexpansion

:: -----------------------------------------------------------------------------
:: LUCY DESKTOP ASSISTANT - LAUNCHER & SETUP
:: Works on Windows 10 & 11 (64-bit). No Python installation required.
:: -----------------------------------------------------------------------------

title LUCY Setup & Launcher

:: Resolve absolute directory where setup.bat lives
set "APP_DIR=%~dp0"
if "%APP_DIR:~-1%"=="\" set "APP_DIR=%APP_DIR:~0,-1%"
cd /d "%APP_DIR%"

:: Ensure logs folder exists
if not exist "%APP_DIR%\logs" mkdir "%APP_DIR%\logs"
set "LOG_FILE=%APP_DIR%\logs\setup.log"

:: Fast Path: Check if runtime is already prepared and functional
if exist "%APP_DIR%\runtime\python.exe" (
    :: Quick verification of core package
    "%APP_DIR%\runtime\python.exe" -c "import PyQt6" >nul 2>&1
    if !errorlevel! equ 0 (
        echo [%date% %time%] Fast launch initiated >> "%LOG_FILE%"
        if exist "%APP_DIR%\LUCY.exe" (
            start "" "%APP_DIR%\LUCY.exe"
        ) else if exist "%APP_DIR%\runtime\pythonw.exe" (
            start "" "%APP_DIR%\runtime\pythonw.exe" "%APP_DIR%\main.py"
        ) else (
            start "" "%APP_DIR%\runtime\python.exe" "%APP_DIR%\main.py"
        )
        exit /b 0
    )
)

:: -----------------------------------------------------------------------------
:: First Run Setup Flow
:: -----------------------------------------------------------------------------
cls
echo ==================================================
echo                   LUCY SETUP
echo ==================================================
echo.
echo [%date% %time%] First-time setup initiated in "%APP_DIR%" >> "%LOG_FILE%"

echo Checking runtime...
echo [%date% %time%] Checking runtime... >> "%LOG_FILE%"

:: If runtime directory is missing, provision it automatically
if not exist "%APP_DIR%\runtime\python.exe" (
    echo Preparing LUCY components...
    echo [%date% %time%] Local runtime missing. Provisioning portable Python 3.11... >> "%LOG_FILE%"

    :: Check if curl and tar are available (native on Win 10/11)
    where curl >nul 2>&1
    if !errorlevel! neq 0 (
        echo.
        echo [ERROR] curl.exe is required for automatic download on first run.
        echo Please ensure Windows 10/11 is updated.
        echo [%date% %time%] curl.exe not found >> "%LOG_FILE%"
        goto :FAIL
    )

    set "STANDALONE_URL=https://github.com/astral-sh/python-build-standalone/releases/download/20240814/cpython-3.11.9+20240814-x86_64-pc-windows-msvc-shared-install_only.tar.gz"
    set "PKG_TMP=%TEMP%\lucy_python_311.tar.gz"

    echo Downloading portable Python runtime (one-time setup)...
    curl -L -s --fail "!STANDALONE_URL!" -o "!PKG_TMP!"
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to download portable Python runtime.
        echo Please check your internet connection and try again.
        echo [%date% %time%] Failed to download runtime from !STANDALONE_URL! >> "%LOG_FILE%"
        goto :FAIL
    )

    echo Extracting runtime...
    if not exist "%APP_DIR%\runtime" mkdir "%APP_DIR%\runtime"
    tar -xzf "!PKG_TMP!" -C "%APP_DIR%\runtime" --strip-components=1
    del /f /q "!PKG_TMP!" >nul 2>&1

    if not exist "%APP_DIR%\runtime\python.exe" (
        echo [ERROR] Runtime extraction failed.
        echo [%date% %time%] runtime\python.exe missing after tar extraction >> "%LOG_FILE%"
        goto :FAIL
    )
    echo [%date% %time%] Standalone runtime extraction complete. >> "%LOG_FILE%"
)

:: Checking dependencies
echo Checking dependencies...
echo [%date% %time%] Checking dependencies... >> "%LOG_FILE%"

"%APP_DIR%\runtime\python.exe" -c "import PyQt6" >nul 2>&1
if !errorlevel! neq 0 (
    echo Installing required components (one-time setup, may take a few minutes)...
    echo [%date% %time%] Installing packages from requirements.txt... >> "%LOG_FILE%"
    "%APP_DIR%\runtime\python.exe" -m pip install -r "%APP_DIR%\requirements.txt" >> "%LOG_FILE%" 2>&1
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install application dependencies.
        echo Please inspect logs\setup.log for details.
        echo [%date% %time%] pip install failed with code !errorlevel! >> "%LOG_FILE%"
        goto :FAIL
    )
)

:: Verify critical files
echo Validating installation...
if not exist "%APP_DIR%\main.py" (
    echo [ERROR] main.py is missing from %APP_DIR%.
    echo [%date% %time%] main.py missing >> "%LOG_FILE%"
    goto :FAIL
)

"%APP_DIR%\runtime\python.exe" -c "import main" >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARNING] Dependency validation returned non-zero. See setup.log.
    echo [%date% %time%] import main check non-zero >> "%LOG_FILE%"
)

echo Starting LUCY...
echo [%date% %time%] Launching LUCY application >> "%LOG_FILE%"

if exist "%APP_DIR%\LUCY.exe" (
    start "" "%APP_DIR%\LUCY.exe"
) else if exist "%APP_DIR%\runtime\pythonw.exe" (
    start "" "%APP_DIR%\runtime\pythonw.exe" "%APP_DIR%\main.py"
) else (
    start "" "%APP_DIR%\runtime\python.exe" "%APP_DIR%\main.py"
)

exit /b 0

:FAIL
echo.
echo ==================================================
echo LUCY could not start.
echo.
echo Possible cause:
echo A required component or network resource was missing.
echo.
echo Please review "%LOG_FILE%" for details.
echo ==================================================
echo.
pause
exit /b 1
