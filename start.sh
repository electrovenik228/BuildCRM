#!/usr/bin/env bash
set -o errexit

python manage.py migrate
python manage.py seed_demo
python manage.py ensure_superuser
python -m gunicorn core.wsgi:application --bind 0.0.0.0:${PORT:-8000}
