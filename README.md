# Full Stack FastAPI Template

[![Test Docker Compose](../../actions/workflows/test-docker-compose.yml/badge.svg)](../../actions/workflows/test-docker-compose.yml)
[![Test Backend](../../actions/workflows/test-backend.yml/badge.svg)](../../actions/workflows/test-backend.yml)

## Technology Stack and Features

- ⚡ [**FastAPI**](https://fastapi.tiangolo.com) for the Python backend API.
  - 🧰 [SQLModel](https://sqlmodel.tiangolo.com) for the Python SQL database interactions (ORM).
  - 🔍 [Pydantic](https://docs.pydantic.dev), used by FastAPI, for the data validation and settings management.
  - 💾 [PostgreSQL](https://www.postgresql.org) as the SQL database.
- 🚀 [React](https://react.dev) for the frontend.
  - 🧩 Built into the backend application and served by FastAPI on the same domain as the API.
  - 💃 Using TypeScript, hooks, [Vite](https://vitejs.dev), and other parts of a modern frontend stack.
  - 🎨 [Tailwind CSS](https://tailwindcss.com) and [shadcn/ui](https://ui.shadcn.com) for the frontend components.
  - 🤖 An automatically generated frontend client.
  - 🧪 [Playwright](https://playwright.dev) for end-to-end testing.
  - 🦇 Dark mode support.
- ☁️ [FastAPI Cloud](https://fastapicloud.com) for deployment.
- 🐋 [Docker Compose](https://www.docker.com) for local services and self-hosted deployment.
  - 📞 [Traefik](https://traefik.io) as a reverse proxy with automatic HTTPS.
- 🔒 Secure password hashing by default.
- 🔑 JWT (JSON Web Token) authentication.
- 📫 Email-based password recovery.
- ✉️ [React Email](https://react.email) for email templates.
- 📬 [Mailpit](https://mailpit.axllent.org) for local email testing during development.
- ✅ Tests with [Pytest](https://pytest.org).
- 🏭 CI (continuous integration) and CD (continuous deployment) based on GitHub Actions.

### Dashboard Login

![Dashboard login screenshot](img/login.png)

### Dashboard - Admin

![Admin dashboard screenshot](img/dashboard.png)

### Dashboard - Items

![Items dashboard screenshot](img/dashboard-items.png)

### Dashboard - Dark Mode

![Dark mode dashboard screenshot](img/dashboard-dark.png)

### React Email Templates

![Email templates screenshot](img/react-email.png)

### Mailpit - Local Email Testing

![Mailpit screenshot](img/mailpit.png)

### Interactive API Documentation

![API docs](img/docs.png)

## How to Use It

Click the **Use this template** button at the top of this page to create a new repository.

## Backend Development

Backend docs: [backend/README.md](./backend/README.md).

## Frontend Development

Frontend docs: [frontend/README.md](./frontend/README.md).

## Deployment

FastAPI Cloud deployment: [deployment.md](./deployment.md).

Self-hosted deployment with Docker Compose: [deployment-docker-compose.md](./deployment-docker-compose.md).

## Development

General development docs: [development.md](./development.md).

This includes the local FastAPI and Vite workflow, Docker Compose services, `.env` configuration, and more.

## Google Sheet Task Domain (Migration)

This repository hosts the migration of the former Flask project `google_sheet_task` onto this template (FastAPI + SQLModel + React 19). Domain docs live in [docs/migration/](./docs/migration/); the phase ledger with acceptance results is [docs/migration/07-phases.md](./docs/migration/07-phases.md).

### Deployment differences vs. the upstream template

- **Worker service (required for task execution).** `compose.yml` defines a single-instance `worker` service (image `backend:latest`, command `python -m app.worker`). The API processes are stateless: they only write rows; the worker claims pending tasks, heartbeats, evicts stale runs and runs cron cleanups. Deployments without the worker will keep tasks `pending` forever.
- **Google OAuth token volume.** OAuth user tokens live in `GOOGLE_TOKEN_DIR` (default `./data`; mounted as the `app-data` volume at `/app/backend/data` in compose). Import tokens via the admin UI (`/google-sheet-tokens`) or the token pool API. Without a valid token, real Google Sheet runs cannot start.
- **MySQL switch (5.7.8+ / 8.0+).** Default DB is PostgreSQL. To use MySQL, point `DATABASE_URL` at e.g.
  `mysql+pymysql://user:pass@host:3306/app?charset=utf8mb4`
  and create the database as `CREATE DATABASE app CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;`. The schema is dialect-neutral (single Alembic baseline: `alembic upgrade head` works on PostgreSQL 18 / MySQL 5.7 / MySQL 8.0). Code avoids window functions, CTEs and dialect-specific JSON path queries; hot query columns are physical columns.
- **DingTalk stream bot (optional).** `docker compose --profile dingtalk up -d` starts the `ding-stream` service (`ding_stream_service/`, env `DING_STREAM_CLIENT_ID`/`DING_STREAM_CLIENT_SECRET`) for listing/restarting tasks from chat.
- **No RBAC on business APIs.** The template login gates the SPA only; the migrated business routes (`/api/v1/tasks`, `/api/v1/task-results`, ...) intentionally carry no per-user permission checks (decision ① in docs/migration-plan.md).

## Release Notes

Check the file [release-notes.md](./release-notes.md).

## License

The Full Stack FastAPI Template is licensed under the terms of the MIT license.
