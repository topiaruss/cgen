# Repository Guidelines

## Project Structure & Module Organization
- `app/manage.py` — Django entrypoint for admin tasks.
- `config/settings.py` — project settings.
- `templates/` and `static/` — project-level templates and assets; per‑app folders preferred (`apps/blog/templates/blog/...`).
- `media/` — user uploads (never commit); `fixtures/` — sample data; `scripts/` — helper scripts.

Keep apps small and focused. Name apps and modules in `snake_case`; classes in `PascalCase` (e.g., `BlogPost`).

## Build, Test, and Development Commands
- Setup: `python -m venv .venv && source .venv/bin/activate`
- Install: `pip install -r requirements.txt`
- Env: `cp .env.example .env` then set `DATABASE_URL`, `SECRET_KEY`, etc.
- DB: `python manage.py migrate` | Superuser: `python manage.py createsuperuser`
- Run: `python manage.py runserver`
- Static (prod): `python manage.py collectstatic --noinput`

## Coding Style & Naming Conventions
- Indentation: 4 spaces; follow PEP 8 naming: modules `snake_case`, classes `PascalCase`.
- Tooling: Ruff only. Lint: `ruff check .`; Format: `ruff format .` (use as the single source of style; do not use Black or isort).
- Django specifics: models singular (`BlogPost`); app URLs live in `apps/<app>/urls.py` and are included from `config/urls.py`.
- Prefer type hints; optional: `django-stubs` for mypy.

## Testing Guidelines
- Framework: `pytest` + `pytest-django` is required. Do not use `unittest.TestCase` or `django.test.TestCase`.
- Run: `pytest -q`; Coverage: `pytest --cov=config --cov=apps --cov-report=term-missing` (target ≥80%).
- Layout: `apps/<app>/tests/` with files like `test_models.py`, `test_views.py`, `test_api.py`.
- Patterns: function-style tests with fixtures; mark DB tests with `@pytest.mark.django_db`.
- Use factories (`tests/factories.py`) instead of static fixtures; keep tests fast and isolated.

## Commit & Pull Request Guidelines
- Conventional Commits (e.g., `feat(auth): allow password reset`).
- Include migrations when models change (`python manage.py makemigrations`) and review them in PRs.
- PRs: purpose, testing steps, screenshots for UI, linked issues (`Closes #123`); CI must pass.

## Static & Media
- Static (WhiteNoise): install `whitenoise`, add `"whitenoise.middleware.WhiteNoiseMiddleware"` after `SecurityMiddleware`, run `collectstatic` for builds. Configure `STATIC_ROOT` and ensure static files are committed only if generated assets are intended.
- Media (uploads): store under `media/` (git-ignored). For image handling use `django-versatileimagefield`: add `"versatileimagefield"` to `INSTALLED_APPS`, ensure Pillow installed, and use `VersatileImageField` in models (e.g., `image = VersatileImageField(upload_to="uploads/")`).

## Security & Configuration Tips
- Never commit secrets; manage via `.env` (provide `.env.example`).
- Production: set `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, secure cookies (`SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`).
- Prefer `DATABASE_URL` for DB config.

## Agent-Specific Instructions
- Keep edits minimal and scoped; avoid unrelated refactors.
- Use `rg` for search; read files in ≤250-line chunks.
- Apply changes via `apply_patch`; document commands in messages.
