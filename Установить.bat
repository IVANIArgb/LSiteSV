@echo off
chcp 65001 >nul
cd /d "%~dp0"
title LearningSite — установка

where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%~dp0install.py"
  goto :end
)
where python >nul 2>&1
if %errorlevel%==0 (
  python "%~dp0install.py"
  goto :end
)
where python3 >nul 2>&1
if %errorlevel%==0 (
  python3 "%~dp0install.py"
  goto :end
)

echo Python не найден. Пытаюсь установить Python 3.12 через winget...
where winget >nul 2>&1
if %errorlevel%==0 (
  winget install -e --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
  echo Закройте это окно и снова запустите Установить.bat — чтобы подхватился PATH.
  pause
  exit /b 1
)

echo Не удалось найти Python и winget.
echo Скачайте Python 3.12 с https://www.python.org/downloads/ и отметьте "Add python.exe to PATH".
pause
exit /b 1

:end
if errorlevel 1 pause
