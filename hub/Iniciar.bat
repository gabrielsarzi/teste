@echo off
chcp 65001 >nul
title Hub de Projetos
cd /d "%~dp0"

echo.
echo   Iniciando o Hub de Projetos...
echo   (Isso roda somente na sua maquina. Feche esta janela para encerrar.)
echo.

rem 1) Tenta o Python pelo lancador "py"
py -3 --version >nul 2>nul
if %errorlevel%==0 (
    py -3 server.py
    goto :fim
)

rem 2) Tenta "python" no PATH
python --version >nul 2>nul
if %errorlevel%==0 (
    python server.py
    goto :fim
)

rem 3) Tenta Node.js
node --version >nul 2>nul
if %errorlevel%==0 (
    node server.js
    goto :fim
)

rem 4) Nada encontrado
echo.
echo   =====================================================
echo   Nao encontrei Python nem Node.js instalados.
echo.
echo   Instale UM dos dois (qualquer um serve):
echo     - Python: https://www.python.org/downloads/
echo       (marque "Add Python to PATH" na instalacao)
echo     - Node.js: https://nodejs.org/
echo.
echo   Depois e so dar duplo-clique aqui de novo.
echo   =====================================================
echo.

:fim
echo.
echo   O Hub foi encerrado. Pode fechar esta janela.
pause >nul
