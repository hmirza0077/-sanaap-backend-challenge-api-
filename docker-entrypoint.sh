#!/bin/bash
if [ "$1" = "daphne" ]; then
        shift
        # migrations run inside the container before the server starts
        cd /home/user/app/ && python3 manage.py migrate --noinput
        python3 manage.py collectstatic --noinput
        exec daphne "$@"
elif [ "$1" = "celery" ]; then
        shift
        exec celery "$@"
elif [ "$1" = "manage.py" ]; then
        shift
        exec python3 manage.py "$@"
fi
