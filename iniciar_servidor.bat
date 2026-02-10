@echo off
for /f "tokens=4" %%a in ('route print ^| find " 0.0.0.0 "') do set IP=%%a
echo Instando servidor Nunut...
echo Tu IP local es: %IP%
echo Puedes acceder desde tu telefono en: http://%IP%:8000
echo.
python manage.py runserver 0.0.0.0:8000
pause
