@echo off
chcp 65001 > nul
setlocal
rem チームメンバーの準備と更新(自分の環境)。何度押してもよい。
rem 置き場所: 共有 vault の _仕組み\tools\準備\。試しに動かすときは、コマンドプロンプトで「チームメンバー.bat 試し」。
set PYTHONUTF8=1
title 開発ノートの準備(チームメンバー)
call "%~dp0_python.bat" || (pause & exit /b 1)
set "VER="
if exist "%~dp0最新の版.txt" set /p VER=<"%~dp0最新の版.txt"
if not defined VER goto :nover
if not exist "%~dp0..\配布\%VER%\準備\setup.py" goto :nover
%PY% "%~dp0..\配布\%VER%\準備\setup.py" メンバー --here "%~dp0." %*
pause
exit /b

:nover
echo 配布物が見つかりません: %~dp0..\配布\%VER%
echo 共有クラウドフォルダの同期が終わるまで少し待つか、システム管理者に版を出してもらってください。
pause
exit /b 1
