#!/bin/bash
# Quick Start Script for Celery Email Setup

echo "================================"
echo "NavPrana Celery Email Setup"
echo "================================"

# Step 1: Install packages
echo -e "\n[1/4] Installing required packages..."
pip install -r requirements.txt

# Step 2: Install Redis (optional - show instructions)
echo -e "\n[2/4] Redis Installation:"
echo "Please ensure Redis is installed and running."
echo "To install Redis:"
echo "  Ubuntu/Debian: sudo apt-get install redis-server"
echo "  macOS: brew install redis"
echo "  Windows: Download from https://github.com/microsoftarchive/redis/releases"
echo "  Docker: docker run -d -p 6379:6379 redis:7-alpine"

# Step 3: Run migrations
echo -e "\n[3/4] Running Django migrations..."
python manage.py migrate

# Step 4: Create superuser (if needed)
echo -e "\n[4/4] Setup complete!"
echo ""
echo "================================"
echo "To start the application:"
echo "================================"
echo ""
echo "Terminal 1 - Redis (if not already running):"
echo "  redis-server"
echo ""
echo "Terminal 2 - Celery Worker:"
echo "  celery -A config worker -l info"
echo ""
echo "Terminal 3 - Celery Beat (Scheduler):"
echo "  celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler"
echo ""
echo "Terminal 4 - Django Server:"
echo "  python manage.py runserver"
echo ""
echo "================================"
echo "Documentation:"
echo "See CELERY_EMAIL_SETUP.md for detailed setup instructions"
echo "================================"
