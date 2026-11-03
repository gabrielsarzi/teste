@echo off
REM Gera o LimpaOne.exe (portatil) na pasta dist\ e, se o Inno Setup estiver instalado, o instalador.
REM Requer Python 3.10+ (marque "Add python.exe to PATH" ao instalar).
cd /d "%~dp0"
python -m pip install --upgrade pip
python -m pip install pyinstaller psutil send2trash pillow qrcode
python tools\make_icon.py
python tools\make_version_file.py 3.0.0
python -m PyInstaller --noconfirm --onefile --windowed --name LimpaOne --icon assets\icon.ico --version-file version_info.txt --collect-submodules limpaone main.py
if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" /DMyAppVersion=3.0.0 installer.iss
echo.
echo Pronto! Veja a pasta: %~dp0dist
pause
