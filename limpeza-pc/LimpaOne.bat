@echo off
REM Executa o LimpaOne direto pelo Python, sem compilar.
cd /d "%~dp0"
python -m pip install --quiet psutil send2trash
start "" pythonw main.py
