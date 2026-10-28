@echo off
REM Run from backend/ directory.
python manage.py spectacular --file schema.yml --validate
if errorlevel 1 exit /b 1
cd ..\frontend
call npm run types:api
if errorlevel 1 exit /b 1
echo Types regenerated successfully.