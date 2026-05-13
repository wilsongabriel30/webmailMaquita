# Local Development Guide

This guide covers setting up a local development environment for Maquita Webmail.

## Prerequisites

| Tool         | Version   | Notes                          |
|--------------|-----------|--------------------------------|
| Python       | 3.12+     | Required for backend           |
| Node.js      | 20 LTS    | Required for frontend          |
| PostgreSQL   | 17        | Primary database               |
| Redis        | 7         | Caching and sessions           |
| Git          | 2.40+     | Version control                |

Optional but recommended:

- **Docker / Podman** -- for running PostgreSQL and Redis without local install
- **direnv** -- automatic `.env` loading
- **httpie** or **curl** -- API testing

## Clone and Setup

```bash
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd maquita-webmail
```

## Backend Setup

### 1. Create a virtual environment

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt   # linting, testing, etc.
```

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your local settings. At a minimum set:

```
DATABASE_URL=postgresql://maquita:maquita@localhost:5432/maquita_webmail
REDIS_URL=redis://localhost:6379/0
ADMIN_JWT_SECRET=change-me-local-dev-only
SECRET_KEY=change-me-local-dev-only
CORS_ORIGINS=http://localhost:5173
```

See [CONFIGURATION.md](CONFIGURATION.md) for the full reference.

### 4. Run the backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API docs are available at `http://localhost:8000/docs` (Swagger) and `http://localhost:8000/redoc`.

## Frontend Setup

```bash
cd frontend
npm ci
npm run dev
```

The dev server starts at `http://localhost:5173` and proxies API calls to the backend.

## Database Setup

### Create the database

```bash
createuser -s maquita 2>/dev/null || true
createdb -O maquita maquita_webmail
```

### Run migrations

Migrations are plain SQL files in `migrations/`. Apply them in order:

```bash
for f in $(ls migrations/*.sql | sort); do
  echo "Applying $f ..."
  psql -U maquita -d maquita_webmail -f "$f"
done
```

Or use the helper script if available:

```bash
python scripts/migrate.py
```

### Seed data (optional)

```bash
psql -U maquita -d maquita_webmail -f scripts/seed_dev.sql
```

## Running Tests

### Backend

```bash
cd backend
source .venv/bin/activate

# All tests
pytest

# With coverage
pytest --cov=app --cov-report=term-missing

# Specific module
pytest tests/test_compliance.py -v
```

### Frontend

```bash
cd frontend
npm test            # unit tests (Vitest)
npm run test:e2e    # end-to-end tests (Playwright), requires backend running
```

## Code Formatting

### Python (backend)

```bash
# Format
black app/ tests/
isort app/ tests/

# Check only (CI mode)
black --check app/ tests/
isort --check-only app/ tests/
```

### TypeScript/React (frontend)

```bash
# Lint
npm run lint

# Fix automatically
npm run lint -- --fix

# Format with Prettier (if configured)
npx prettier --write "src/**/*.{ts,tsx,css}"
```

## Hot Reload

- **Backend**: `uvicorn --reload` watches for file changes and restarts automatically.
- **Frontend**: Vite HMR updates the browser instantly on save.

Both are enabled by default when using the dev commands above.

## Troubleshooting

### `psql: FATAL: role "maquita" does not exist`

Create the role first:

```bash
sudo -u postgres createuser -s maquita
```

### `ModuleNotFoundError: No module named 'app'`

Make sure you activated the virtualenv and installed dependencies:

```bash
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

### Port 5173 already in use

Another Vite instance or process is using the port. Kill it or change the port:

```bash
lsof -ti :5173 | xargs kill -9
# or
npm run dev -- --port 5174
```

### Redis connection refused

Start the Redis server:

```bash
# systemd
sudo systemctl start redis-server

# Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### Migrations fail with "relation already exists"

Migrations are not idempotent by default. If you need a fresh start:

```bash
dropdb maquita_webmail
createdb -O maquita maquita_webmail
# Re-run migrations
```

### CORS errors in the browser

Ensure `CORS_ORIGINS` in `.env` includes your frontend URL (e.g., `http://localhost:5173`).

### Backend cannot connect to PostgreSQL on macOS

If using Homebrew PostgreSQL, the socket path may differ. Use TCP explicitly:

```
DATABASE_URL=postgresql://maquita:maquita@127.0.0.1:5432/maquita_webmail
```
