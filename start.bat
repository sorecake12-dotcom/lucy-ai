@echo off
setlocal enabledelayedexpansion
title LUCY AI Assistant

cd /d "%~dp0"

:: 1. Unblock files in current folder to prevent Windows SmartScreen / Smart App Control Bad Image blocks
powershell -NoProfile -Command "Get-ChildItem -Path '%~dp0' -Recurse | Unblock-File" >nul 2>&1

:: 2. Find best signed Python interpreter (prioritizing system Python to avoid Smart App Control blocks)
set "PY_CMD="

:: Check system pythonw
where pythonw >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=pythonw"
    goto :RUN
)

:: Check system python
where python >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :RUN
)

:: Check py launcher
where py >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py"
    goto :RUN
)

:: Check user local python installations
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
    if exist "%%D\pythonw.exe" (
        set "PY_CMD=%%D\pythonw.exe"
        goto :RUN
    )
    if exist "%%D\python.exe" (
        set "PY_CMD=%%D\python.exe"
        goto :RUN
    )
)

for /d %%D in ("%LOCALAPPDATA%\Python\pythoncore-*") do (
    if exist "%%D\pythonw.exe" (
        set "PY_CMD=%%D\pythonw.exe"
        goto :RUN
    )
    if exist "%%D\python.exe" (
        set "PY_CMD=%%D\python.exe"
        goto :RUN
    )
)

:: Check bundled portable runtime
if exist "%~dp0runtime\pythonw.exe" (
    set "PY_CMD=%~dp0runtime\pythonw.exe"
    goto :RUN
)

if exist "%~dp0runtime\python.exe" (
    set "PY_CMD=%~dp0runtime\python.exe"
    goto :RUN
)

echo ==================================================
echo [ERROR] No valid Python installation detected.
echo Please run: python setup.py
echo ==================================================
pause
exit /b 1

:RUN
start "" "!PY_CMD!" "%~dp0main.py"
exit /b 0
