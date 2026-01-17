@echo off
REM Quick Start Script for Celery Email Setup (Windows)

echo.
echo ================================
echo NavPrana Celery Email Setup
echo ================================
echo.

REM Step 1: Install packages
echo [1/4] Installing required packages...
call pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo Error installing packages. Please check your pip installation.
    pause
    exit /b 1
)

REM Step 2: Show Redis instructions
echo.
echo [2/4] Redis Installation:
echo Please ensure Redis is installed and running.
echo.
echo To install Redis on Windows:
echo   Option 1: Download from https://github.com/microsoftarchive/redis/releases
echo   Option 2: Use Docker: docker run -d -p 6379:6379 redis:7-alpine
echo   Option 3: Use WSL: wsl sudo apt-get install redis-server
echo.

REM Step 3: Run migrations
echo.
echo [3/4] Running Django migrations...
call python manage.py migrate
if %errorlevel% neq 0 (
    echo Error running migrations.
    pause
    exit /b 1
)

REM Step 4: Complete
echo.
echo [4/4] Setup complete!
echo.
echo ================================
echo To start the application:
echo ================================
echo.
echo Terminal 1 - Redis (if not already running):
echo   redis-server
echo.
echo Terminal 2 - Celery Worker (Windows):
echo   celery -A config worker -l info --pool=solo
echo.
echo Terminal 3 - Celery Beat (Scheduler):
echo   celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
echo.
echo Terminal 4 - Django Server:
echo   python manage.py runserver
echo.
echo ================================
echo Documentation:
echo See CELERY_EMAIL_SETUP.md for detailed setup instructions
echo ================================
echo.
pause
