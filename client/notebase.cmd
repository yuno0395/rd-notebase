@echo off
rem rd-notebase launcher. Put this file in your workspace folder and double-click it.
rem   notebase.cmd          first run: setup / later: update + check + push
rem   notebase.cmd push     check + push only (used by the scheduled task)
rem   notebase.cmd status   show status
setlocal
chcp 65001 >nul
set "PYTHONIOENCODING=utf-8"
set "WS=%~dp0"
set "NB=%WS%.notebase"
set "REPO=https://github.com/yuno0395/rd-notebase.git"
set "BRANCH=stable"
rem Developers can override REPO / BRANCH in notebase.local.cmd (e.g. set "BRANCH=main")
if exist "%WS%notebase.local.cmd" call "%WS%notebase.local.cmd"

where git >nul 2>nul || (echo [notebase] Git for Windows is required: https://git-scm.com/download/win & goto :end_err)

if not exist "%NB%\.git" (
  echo [notebase] Downloading the system ...
  git clone -q -b %BRANCH% "%REPO%" "%NB%" || goto :end_err
  attrib +h "%NB%"
) else (
  git -C "%NB%" pull -q --ff-only || echo [notebase] Could not check for updates. Continuing with the local version.
)

set "UV=%NB%\.tools\uv.exe"
where uv >nul 2>nul && set "UV=uv"
if not "%UV%"=="uv" if not exist "%UV%" (
  echo [notebase] Installing the runtime ^(uv^) ...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "$env:UV_UNMANAGED_INSTALL='%NB%\.tools'; irm https://astral.sh/uv/install.ps1 | iex" || goto :end_err
)

"%UV%" run -q --frozen --project "%NB%" python "%NB%\client\run.py" %*
set "RC=%ERRORLEVEL%"
if "%~1"=="" pause
exit /b %RC%

:end_err
if "%~1"=="" pause
exit /b 1
