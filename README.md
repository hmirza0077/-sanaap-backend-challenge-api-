# Sanaap DMS API

A Document Management System API built with **Django Rest Framework**.
Users can upload, update, download, and delete documents (images). Files are stored in **MinIO**, and access is controlled by role.

Stack: Django, DRF, PostgreSQL, Redis, MinIO, Celery, Django Channels, Daphne, Nginx, Docker.

## Features

- Login with username and password (JWT: short-lived access token + refresh token)
- Role-based access control (RBAC):

| Role   | List / Download | Upload / Update | Delete | Manage users |
|--------|:---------------:|:---------------:|:------:|:------------:|
| admin  | ✅ | ✅ | ✅ | ✅ |
| editor | ✅ | ✅ | ❌ | ❌ |
| viewer | ✅ | ❌ | ❌ | ❌ |

- Files are stored in a **private** MinIO bucket. Uploads are kept in memory and are never written to the server disk.
- Secure URLs: the MinIO path is never returned. Files are only served through `/api/documents/{id}/download/` to logged-in users. File names are replaced with random UUIDs.
- Only `jpg`, `jpeg`, and `png` files (max 10 MB)
- Filtering and pagination
- Swagger docs and unit tests
- Background storage: a **Celery** worker stores uploaded files in MinIO, so the request returns right away
- **Audit log** for every view, download, create, update, and delete of a document
- **Nginx** reverse proxy in front of **Daphne**
- **WebSocket** notifications (Django Channels) to all logged-in users when a document is created or updated

## Project structure

```
config/        settings, urls, asgi/wsgi, celery
common/        upload path helper, pagination
user/      user + role, login, user management, permissions, websocket auth
documents/     document model, serializer, filters, views, service, celery task, websocket
audit/         audit log model, service, read-only API for admin
nginx/         nginx config
```

Choices (roles, statuses, actions) are `TextChoices` inside each model, e.g. `User.Role.ADMIN`, `Document.Status.READY`. Each file has one job:
`permissions.py` (access rules), `filters.py` (django-filter), `serializers.py` (API data),
`views.py` (requests), `services.py` (business logic), `tasks.py` (Celery), `consumers.py` / `notifications.py` (WebSocket).

## Run with Docker

The env files are already filled with development values (`app.env`, `db.env`, `minio.env`).
They are in `.gitignore`; the `*.env.example` files show the keys. Change the passwords and `SECRET_KEY` for production.

```bash
docker compose up --build
docker compose exec app python manage.py createsuperuser   # a superuser is treated as admin
docker compose exec app python manage.py seed_data         # optional sample data
```

| Service | What it does |
|---------|--------------|
| `nginx` | reverse proxy, the only service open on port 80. Serves static files and passes WebSocket connections |
| `app` | Django on Daphne (ASGI: HTTP and WebSocket) |
| `celery` | Celery worker that stores uploaded files in MinIO |
| `db` | PostgreSQL |
| `redis` | cache (db 1), Celery broker (db 0), Channels layer (db 2) |
| `minio` | object storage. The private bucket is created on the first upload |

Migrations run automatically in `docker-entrypoint.sh` before the server starts.

- API: http://localhost/api/
- Swagger: http://localhost/api/docs/
- WebSocket: ws://localhost/ws/documents/?token=<access-token>
- MinIO console: http://localhost:9001

## Sample data

`seed_data` creates 7 users and 25 documents with different titles, uploaders, and dates. The password for every user is `pass12345`.

| Username | Role |
|----------|------|
| admin, sara_admin | admin |
| ali_editor, reza_editor, maryam_editor | editor |
| nima_viewer, zahra_viewer | viewer |

## Run tests

```bash
docker compose exec app python manage.py test
```

Tests use the real PostgreSQL, Redis, and MinIO containers, so run them inside Docker.
API tests mock `apply_async` and check that the file is sent to the queue; the Celery task is tested by calling it directly.

## API

All requests except login and refresh need the header `Authorization: Bearer <access-token>`.
The access token is valid for 15 minutes, the refresh token for 1 day.

| Method | URL                             | Who | Description |
|--------|---------------------------------|-----|-------------|
| POST | `/api/user/login/`              | anyone | `{username, password}` → `{access, refresh}` |
| POST | `/api/user/token/refresh/`      | anyone | `{refresh}` → `{access}` |
| GET | `/api/user/me/`                 | logged in | current user |
| GET/POST | `/api/user/users/`              | admin | list / create users (with `role`) |
| GET/PATCH/DELETE | `/api/user/users/{id}/`         | admin | view / change role / delete user |
| GET | `/api/documents/`               | all roles | list |
| POST | `/api/documents/`               | admin, editor | multipart: `title`, `file` |
| GET | `/api/documents/{id}/`          | all roles | details |
| PUT/PATCH | `/api/documents/{id}/`          | admin, editor | update |
| DELETE | `/api/documents/{id}/`          | admin | delete |
| GET | `/api/documents/{id}/download/` | all roles | download the file |
| GET | `/api/audit-logs/`              | admin | history (`?action=download`, `?document_id=5`) |

Document filters: `?title=invoice`, `?uploaded_by=ali_editor`, `?created_after=2026-01-01&created_before=2026-12-31`, `?page=2`, `?page_size=20`.

### Background storage
1. `POST /api/documents/` creates the document with `status: "pending"` and sends the file (base64) to Celery with `apply_async`.
2. The worker saves the file in MinIO and sets `status: "ready"`. On update, the old file is deleted from MinIO.
3. Download returns `409` until the status is `ready`.

### WebSocket notifications
```js
const ws = new WebSocket("ws://localhost/ws/documents/?token=" + accessToken);
ws.onmessage = (e) => console.log(JSON.parse(e.data));
// {"action": "created", "id": 12, "title": "my photo", "status": "pending"}
```
Browsers cannot send headers on WebSocket, so the JWT goes in the URL. Connections without a valid token are rejected.

### Example
```bash
TOKEN=$(curl -s -X POST localhost/api/user/login/ \
  -d "username=admin&password=pass12345" | python3 -c "import sys,json;print(json.load(sys.stdin)['access'])")

curl -H "Authorization: Bearer $TOKEN" -F "title=my photo" -F "file=@photo.png" localhost/api/documents/
```

## SOLID notes
- **Single responsibility:** permissions, filters, serializers, views, services, tasks, notifications, and audit logging each live in their own file.
- **Open/closed:** adding a new role only means changing `DocumentPermission`. Views do not change.
- **Dependency inversion:** views talk to `DocumentService` and `AuditLogService`, not to MinIO or Celery directly.
