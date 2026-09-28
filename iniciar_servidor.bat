@echo off
REM Carpetas con espacios -> usar rutas cortas no funciona con venvs: mejor relativo
cd /d "%~dp0"
call entorno\Scripts\activate.bat
python manage.py runserver