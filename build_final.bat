@echo off
chcp 65001 >nul
echo ========================================
echo PUMC Course Scheduling - Final Build Script
echo ========================================
echo.

echo [1/6] Checking virtual environment...
if not exist "PUMC_venv" (
    echo ERROR: PUMC_venv virtual environment not found
    echo Please ensure the virtual environment exists in the project directory
    pause
    exit /b 1
)

if not exist "PUMC_venv\Scripts\python.exe" (
    echo ERROR: Python executable not found in virtual environment
    echo Please check the virtual environment installation
    pause
    exit /b 1
)

echo SUCCESS: Virtual environment found
echo.

echo [2/6] Verifying dependencies...
echo Checking OR-Tools...
PUMC_venv\Scripts\python.exe -c "import ortools; print('OR-Tools version:', ortools.__version__)" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: OR-Tools not found in virtual environment
    echo Please install with: PUMC_venv\Scripts\pip.exe install ortools
    pause
    exit /b 1
)
echo SUCCESS: OR-Tools found

echo Checking PyQt5...
PUMC_venv\Scripts\python.exe -c "from PyQt5.QtCore import QT_VERSION_STR; print('PyQt5 version:', QT_VERSION_STR)" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: PyQt5 not found in virtual environment
    echo Please install with: PUMC_venv\Scripts\pip.exe install PyQt5
    pause
    exit /b 1
)
echo SUCCESS: PyQt5 found

echo Checking PyInstaller...
PUMC_venv\Scripts\python.exe -m PyInstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: PyInstaller not found in virtual environment
    echo Please install with: PUMC_venv\Scripts\pip.exe install pyinstaller
    pause
    exit /b 1
)
echo SUCCESS: PyInstaller found
echo.

echo [3/6] Cleaning old build files...
if exist "dist" (
    echo Removing old dist directory...
    rmdir /s /q "dist"
)
if exist "build" (
    echo Removing old build directory...
    rmdir /s /q "build"
)
if exist "PUMC_with_ortools.spec" (
    echo Removing old spec file...
    del "PUMC_with_ortools.spec"
)
echo SUCCESS: Cleanup completed
echo.

echo [4/6] Running PyInstaller build script...
echo This may take 5-10 minutes, please wait...
echo.
PUMC_venv\Scripts\python.exe build_with_ortools.py
if %errorlevel% neq 0 (
    echo ERROR: Build script failed
    echo Please check the error messages above
    pause
    exit /b 1
)
echo.

echo [5/6] Verifying build results...
if not exist "dist\PUMC_Course_Scheduling\PUMC_Course_Scheduling.exe" (
    echo ERROR: Executable file not found
    echo Build may have failed
    pause
    exit /b 1
)

if not exist "dist\PUMC_Course_Scheduling\ortools" (
    echo ERROR: OR-Tools directory not found in build
    echo OR-Tools dependency may not be properly included
    pause
    exit /b 1
)

echo SUCCESS: Build verification passed
echo.

echo [6/6] Build results summary...
echo ========================================
echo BUILD COMPLETED SUCCESSFULLY!
echo ========================================
echo.
echo Executable location: dist\PUMC_Course_Scheduling\PUMC_Course_Scheduling.exe
echo.

echo File size information:
if exist "dist\PUMC_Course_Scheduling\PUMC_Course_Scheduling.exe" (
    for %%I in ("dist\PUMC_Course_Scheduling\PUMC_Course_Scheduling.exe") do echo Executable size: %%~zI bytes (~11MB)
)

echo.
echo Directory contents:
dir /b "dist\PUMC_Course_Scheduling"
echo.

echo Build process completed!
echo.
echo Next steps:
echo 1. Test the executable: dist\PUMC_Course_Scheduling\PUMC_Course_Scheduling.exe
echo 2. Create installer with Inno Setup (optional)
echo 3. Distribute the entire dist\PUMC_Course_Scheduling\ folder
echo.
echo NOTE: This script stops before Inno Setup compilation
echo Use installer_config.iss separately if you need an installer
echo.
pause
