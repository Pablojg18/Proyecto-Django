@echo off
REM Inicia MySQL 8.4 (puerto 3307) si no esta corriendo
set BASE=%LOCALAPPDATA%\mysql84\mysql-8.4.11-winx64
set DATA=%LOCALAPPDATA%\mysql84\data

netstat -an | findstr ":3307" | findstr "LISTENING" >nul
if %errorlevel%==0 (
    echo MySQL 8.4 ya esta corriendo en el puerto 3307
) else (
    echo Iniciando MySQL 8.4 en el puerto 3307...
    start "MySQL84" "%BASE%\bin\mysqld.exe" --no-defaults --basedir="%BASE%" --datadir="%DATA%" --port=3307 --console
    echo Esperando...
    timeout /t 10 /nobreak >nul
)