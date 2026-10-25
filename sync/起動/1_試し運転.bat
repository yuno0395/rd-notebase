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
title 知見同期 試し運転
echo 試し運転です。ノートは何も変えず、個人 vault の _仕組み\同期レポート.md に「することの予定」だけを書きます。
python -m notesync once --dry-run
pause
