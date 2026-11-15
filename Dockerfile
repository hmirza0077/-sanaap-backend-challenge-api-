FROM python:3.12-slim

# set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# set work directory
WORKDIR /home/user/app

# install dependencies (in their own layer, so they are cached when only the code changes)
COPY ./requirements.txt /home/user/app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# copy project (app.env is not copied, see .dockerignore; docker-compose passes it with env_file)
COPY . /home/user/app/

# run as a non-root user
# (the static folder is created here so the shared volume is owned by appuser)
RUN useradd --create-home appuser \
    && mkdir -p /home/user/app/static \
    && chmod +x /home/user/app/docker-entrypoint.sh \
    && chown -R appuser /home/user/app
USER appuser

ENTRYPOINT [ "/home/user/app/docker-entrypoint.sh" ]
