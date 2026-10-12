#!/bin/sh
set -eu
python manage.py check --deploy --fail-level WARNING
python manage.py collectstatic --noinput
exec gunicorn community_project.wsgi:application \
    --bind 0.0.0.0:8000 --workers 2 --threads 2 --timeout 120 \
    --access-logfile - --error-logfile -
