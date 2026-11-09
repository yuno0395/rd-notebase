@echo off
chcp 65001 > nul
rem 別の Obsidian の vault のノートと添付を、自分の個人 vault に取り込む(仕様書「別の Obsidian から取り込む」、要件書 F-62)。
rem 元の vault は書き換えない。取り込んだノートは自分だけのメモ(PIP)になり、「共有する」を押すまでどこへも出ない。
set PYTHONUTF8=1
set "PYTHONPATH=%~dp0.."
where python > nul 2> nul || (
  echo Python が見つかりません。python.org から 3.11 以上を入れ、「Add python.exe to PATH」にチェックしてください。
  pause
  exit /b 1
)
title 別の vault から取り込む
echo 取り込む元の vault は書き換えません。まず試し実行で数を見せます。
echo.
python -m notesync import %*
pause
