@echo off
rem Abre o Stardew CastMaster com dois cliques.
rem O "cd /d %~dp0" entra na pasta deste arquivo, entao funciona de qualquer
rem lugar (inclusive de um atalho na area de trabalho).
cd /d "%~dp0"
title Stardew CastMaster
python app.py

rem Se o app fechar com erro, segura a janela aberta pra voce ler a mensagem.
rem Sem isso o console some junto e voce nao ve o que aconteceu.
if errorlevel 1 (
    echo.
    echo ============================================
    echo  O app fechou com erro. A mensagem esta acima.
    echo ============================================
    pause
)
