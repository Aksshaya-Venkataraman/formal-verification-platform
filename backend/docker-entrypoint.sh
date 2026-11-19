#!/bin/sh
# Apply database migrations, then serve the API with gunicorn.
set -eu

alembic upgrade head
exec gunicorn --config gunicorn.conf.py wsgi:app
