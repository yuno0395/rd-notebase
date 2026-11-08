@echo off
chcp 65001 > nul
setlocal
rem システム管理者の準備と更新。初めて押すとチームの土台(共有 vault など)を作り、2回目からは新しい版を出して配る。
rem 置き場所: 正本(rd-notebase)の tools\。正本は共有クラウドフォルダの外に置く(例 C:\dev\rd-notebase)。
rem 試しに動かすときは、コマンドプロンプトで「システム管理者.bat 試し」(何も変えない)。
set PYTHONUTF8=1
title 開発ノートの準備(システム管理者)
call "%~dp0..\vault\共有\_仕組み\tools\準備\_python.bat" || (pause & exit /b 1)
%PY% "%~dp0setup.py" 管理者 %*
pause
