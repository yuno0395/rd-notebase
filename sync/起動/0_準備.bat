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
title 知見同期 準備
echo yaml を読む部品を入れます。
python -m pip install --user --quiet pyyaml
if errorlevel 1 (
  echo 入れられませんでした。ネットにつながっているか確かめてください。
  pause
  exit /b 1
)
set "CONF=%APPDATA%\知見同期\config.yaml"
if not exist "%APPDATA%\知見同期" mkdir "%APPDATA%\知見同期"
if exist "%CONF%" (
  echo 設定はもうあります: %CONF%
) else (
  copy "%~dp0..\config.example.yaml" "%CONF%" > nul
  echo 設定のひな形を置きました: %CONF%
  echo メモ帳で開きます。自分の名前と Box の場所に直して保存してください。dry_run は true のままにします。
)
notepad "%CONF%"
pause
