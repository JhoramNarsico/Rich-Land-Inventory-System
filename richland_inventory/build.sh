#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python manage.py collectstatic --no-input
python manage.py migrate

# --- ADD THIS LINE TEMPORARILY ---
# The --noinput flag tells it to read credentials from environment variables.
python manage.py createsuperuser --noinput
