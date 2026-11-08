#!/usr/bin/env bash
set -o errexit

exec gunicorn oneclinic_backend.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --worker-class gthread \
    --workers 2 \
    --threads 4 \
    --timeout 120