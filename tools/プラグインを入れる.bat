@echo off
chcp 65001 > nul
rem コミュニティプラグインを vault に入れる。置き場所: Box の共有 _仕組み\tools\配布\<版>\
set PYTHONUTF8=1
where python > nul 2> nul || (
  echo Python が見つかりません。python.org から 3.11 以上を入れ、「Add python.exe to PATH」にチェックしてください。
  pause
  exit /b 1
)
title プラグインを入れる
echo Obsidian を閉じてから進めてください。
python "%~dp0plugins.py" install
pause
