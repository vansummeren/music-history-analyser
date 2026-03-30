#!/bin/sh
# Entrypoint for the production backend container.
# Runs Alembic database migrations before starting the application server
# so that the schema is always up-to-date when the backend starts accepting
# requests.  Using `exec` replaces the shell with uvicorn so that OS signals
# (e.g. SIGTERM from Docker) are delivered directly to the server process.
set -e

echo "Running database migrations..."
alembic upgrade head
echo "Migrations complete. Starting server..."

exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2
