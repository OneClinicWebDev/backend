#!/usr/bin/env bash
set -o errexit

exec gunicorn oneclinic_backend.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers 2 \
    --timeout 120