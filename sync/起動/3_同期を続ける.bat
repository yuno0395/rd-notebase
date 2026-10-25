@echo off
chcp 65001 > nul
rem 知見同期プログラムを手で動かす(常駐にしないで試すとき)。置き場所: <正本>\sync\起動\
set PYTHONUTF8=1
set "PYTHONPATH=%~dp0.."
where python > nul 2> nul || (
  echo Python が見つかりません。python.org から 3.11 以上を入れ、「Add python.exe to PATH」にチェックしてください。
  pause
  exit /b 1
)
title 知見同期 動いています(閉じると止まります)
echo この画面を開いている間だけ、3分ごとに同期します。
echo Obsidian の Ctrl+Shift+S(今すぐ共有へ)も、この画面が開いている間だけ効きます。
echo 止めるときは、この画面を閉じるか Ctrl+C を押します。
echo.
python -m notesync watch --interval 3
pause
