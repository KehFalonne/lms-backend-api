# GU-LMS Backend

Gracious University Learning Management System — Django REST backend.

## Stack

- Python 3.12 · Django 5 · Django REST Framework
- PostgreSQL (primary datastore)
- Redis (cache + broker + channel layer)
- Celery (background tasks) · Django Channels (WebSockets)
- Daphne (ASGI) · drf-spectacular (OpenAPI)

## Quick start

```bash
cp .env.example .env
docker compose up --build
docker compose exec backend python manage.py migrate
docker compose exec backend python manage.py createsuperuser
```
