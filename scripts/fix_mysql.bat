@echo off
echo Stopping any conflicting service...
taskkill /F /IM mysqld.exe >nul 2>&1

echo Configuring MySQL80 service path to MySQL Server 8.4...
sc.exe config MySQL80 binPath= "\"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe\" --defaults-file=\"C:\ProgramData\MySQL\MySQL Server 8.4\my.ini\" MySQL80"

echo Starting MySQL80 service...
net start MySQL80

echo.
if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] MySQL 8.4 service started successfully!
) else (
    echo [ERROR] Failed to start service. Make sure you ran this script as Administrator.
)
echo.
pause
