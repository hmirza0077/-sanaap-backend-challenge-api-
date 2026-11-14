#!/bin/bash
# stop if any command fails (e.g. do not start the server when migrate fails)
set -e

if [ "$1" = "daphne" ]; then
    # migrations run inside the container before the server starts
    python3 manage.py migrate --noinput
    python3 manage.py collectstatic --noinput
fi

# run the command of the service (daphne, celery, or anything given to "docker compose run")
exec "$@"
