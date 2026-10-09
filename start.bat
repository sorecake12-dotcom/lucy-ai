@echo off
setlocal enabledelayedexpansion
title LUCY AI Assistant

cd /d "%~dp0"

echo [LUCY] Launching Assistant...

:: 1. Unblock local files to prevent Smart App Control blocks
powershell -NoProfile -Command "Get-ChildItem -Path '%~dp0' -Recurse | Unblock-File" >nul 2>&1

:: 2. Find best signed Python interpreter
set "PY_CMD="

where pythonw >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=pythonw"
    goto :RUN
)

where python >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=python"
    goto :RUN
)

where py >nul 2>&1
if !errorlevel! equ 0 (
    set "PY_CMD=py"
    goto :RUN
)

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

if exist "%~dp0runtime\pythonw.exe" (
    set "PY_CMD=%~dp0runtime\pythonw.exe"
    goto :RUN
)

if exist "%~dp0runtime\python.exe" (
    set "PY_CMD=%~dp0runtime\python.exe"
    goto :RUN
)

echo [ERROR] No valid Python installation detected.
pause
exit /b 1

:RUN
echo [LUCY] Starting main.py with !PY_CMD!...
start "" "!PY_CMD!" "%~dp0main.py"
echo [LUCY] Online.
exit /b 0
