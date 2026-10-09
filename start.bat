@echo off
setlocal enabledelayedexpansion
title LUCY AI Assistant

cd /d "%~dp0"

:: 1. Auto-generate desktop shortcut if not already present
if not exist "%USERPROFILE%\Desktop\LUCY.lnk" (
    powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_shortcuts.ps1" >nul 2>&1
)

:: 2. Launch with bundled portable runtime if present
if exist "%~dp0runtime\pythonw.exe" (
    start "" "%~dp0runtime\pythonw.exe" "%~dp0main.py"
    exit /b 0
)

if exist "%~dp0runtime\python.exe" (
    start "" "%~dp0runtime\python.exe" "%~dp0main.py"
    exit /b 0
)

:: 3. Launch with system Python
where pythonw >nul 2>&1
if !errorlevel! equ 0 (
    start "" pythonw "%~dp0main.py"
    exit /b 0
)

where python >nul 2>&1
if !errorlevel! equ 0 (
    start "" python "%~dp0main.py"
    exit /b 0
)

echo [ERROR] Python not found. Please ensure Python 3.11+ is installed.
pause
exit /b 1
