@echo off
REM Gera o LimpaPC.exe (portatil, nao precisa instalar) na pasta dist\
REM Requer Python 3.10+ instalado (marque "Add python.exe to PATH" ao instalar).
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install pyinstaller psutil send2trash
python -m PyInstaller --noconfirm --onefile --windowed --name LimpaPC main.py
echo.
echo Pronto! O executavel esta em: %~dp0dist\LimpaPC.exe
echo Para gerar o instalador, abra installer.iss no Inno Setup (https://jrsoftware.org/isdl.php) e clique em Compile.
pause
