"""Gunicorn entry point: gunicorn wsgi:app"""

from fvp import create_app

app = create_app()
