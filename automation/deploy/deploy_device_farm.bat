@echo off
SET APP_DIR=C:\device_farm
SET VENV_DIR=%APP_DIR%\venv
SET PYTHON_EXE=python

echo Creating virtual environment...
%PYTHON_EXE% -m venv %VENV_DIR%

echo Activating virtual environment...
call %VENV_DIR%\Scripts\activate.bat

echo Installing dependencies...
pip install --upgrade pip
pip install -r %APP_DIR%\requirements.txt

echo Creating logs folder...
IF NOT EXIST "%APP_DIR%\logs" (
    mkdir "%APP_DIR%\logs"
)

echo Creating run script...
echo @echo off > %APP_DIR%\start_device_farm.bat
echo call %VENV_DIR%\Scripts\activate.bat >> %APP_DIR%\start_device_farm.bat
echo python %APP_DIR%\main.py >> %APP_DIR%\start_device_farm.bat

echo Creating startup task...
schtasks /Create /F /TN "DeviceFarmService" /TR "%APP_DIR%\start_device_farm.bat" /SC ONSTART /RL HIGHEST


echo @echo off > %APP_DIR%\start_device_farm.bat

:: Set text color to green (0A)
echo color 0A >> %APP_DIR%\start_device_farm.bat

:: Print banner-style message
echo echo ########################################################## >> %APP_DIR%\start_device_farm.bat
echo echo #                                                        # >> %APP_DIR%\start_device_farm.bat
echo echo #   DO NOT CLOSE THIS WINDOW                              # >> %APP_DIR%\start_device_farm.bat
echo echo #   Device Farm Microservice is RUNNING on this system    # >> %APP_DIR%\start_device_farm.bat
echo echo #                                                        # >> %APP_DIR%\start_device_farm.bat
echo echo ########################################################## >> %APP_DIR%\start_device_farm.bat
echo echo. >> %APP_DIR%\start_device_farm.bat


echo ✅ Device Farm Microservice is ready and will run on system startup.
