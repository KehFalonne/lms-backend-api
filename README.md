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

## Deployment notes

**Static files (WhiteNoise).** Production settings (`config.settings.production`)
serve all Django static assets — admin CSS/JS, DRF assets — straight from the
Daphne/ASGI process via WhiteNoise's `CompressedManifestStaticFilesStorage`.
They do **not** go to R2, and the bucket should stay private. Because the
manifest backend needs the collected output, `collectstatic` must run before
startup or admin pages will 404 their assets:

```bash
python manage.py collectstatic --noinput --clear
```

`Dockerfile.prod` already does this at build time; run it again on every deploy
that changes static files. Output lands in `backend/staticfiles/` (ignored by git).

**User uploads (R2).** With `STORAGE_PROVIDER=R2` (see `.env.example`), all user
files — materials, submissions, profile pictures, imports — are stored in the
Cloudflare R2 bucket under the folders `uploads/`, `profiles/`, `materials/`,
and `submissions/`. Uploads and downloads use short-lived presigned URLs, so the
bucket itself must **not** be made publicly readable. `MEDIA_ROOT`/`MEDIA_URL`
are only used by the local dev flow (`STORAGE_PROVIDER=LOCAL`).

