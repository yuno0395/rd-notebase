@echo off
rem 準備の bat から呼ぶ。Python 3.11 以上を探し、見つけたら PY に入れて戻る。なければ winget で入れる(自分のユーザーだけ)。
set "PY="
set "CHK=import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)"
python -c "%CHK%" > nul 2> nul && (set "PY=python" & goto :eof)
py -3 -c "%CHK%" > nul 2> nul && (set "PY=py -3" & goto :eof)
call :local
if defined PY goto :eof
where winget > nul 2> nul || goto :none
echo Python を入れます(winget。自分のユーザーだけに入れるので、管理者の権限はいりません)。
winget install --id Python.Python.3.12 -e --scope user --accept-package-agreements --accept-source-agreements
call :local
if defined PY goto :eof
:none
echo Python 3.11 以上が見つかりません。
echo https://www.python.org/downloads/ から入れ、「Add python.exe to PATH」にチェックしてから、もう一度押してください。
exit /b 1

:local
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do (
  if exist "%%D\python.exe" "%%D\python.exe" -c "%CHK%" > nul 2> nul && set PY="%%D\python.exe"
)
goto :eof
