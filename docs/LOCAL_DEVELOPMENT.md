# Guía de Desarrollo Local

Esta guía cubre la configuración de un entorno de desarrollo local para Maquita Webmail.

## Requisitos previos

| Herramienta  | Versión   | Notas                          |
|--------------|-----------|--------------------------------|
| Python       | 3.12+     | Requerido para el backend      |
| Node.js      | 20 LTS    | Requerido para el frontend     |
| PostgreSQL   | 17        | Base de datos principal        |
| Redis        | 7         | Caché y sesiones               |
| Git          | 2.40+     | Control de versiones           |

Opcionales pero recomendados:

- **Docker / Podman** -- para ejecutar PostgreSQL y Redis sin instalación local
- **direnv** -- carga automática de `.env`
- **httpie** o **curl** -- pruebas de API

## Clonar y configurar

```bash
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd maquita-webmail
```

## Configuración del backend

### 1. Crea un entorno virtual

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
```

### 2. Instala las dependencias

```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt   # linting, testing, etc.
```

### 3. Configura el entorno

```bash
cp .env.example .env
```

Edita `.env` con tu configuración local. Como mínimo, define:

```
DATABASE_URL=postgresql://maquita:maquita@localhost:5432/maquita_webmail
REDIS_URL=redis://localhost:6379/0
ADMIN_JWT_SECRET=change-me-local-dev-only
SECRET_KEY=change-me-local-dev-only
CORS_ORIGINS=http://localhost:5173
```

Consulta [CONFIGURATION.md](CONFIGURATION.md) para la referencia completa.

### 4. Ejecuta el backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

La documentación de la API está disponible en `http://localhost:8000/docs` (Swagger) y `http://localhost:8000/redoc`.

## Configuración del frontend

```bash
cd frontend
npm ci
npm run dev
```

El servidor de desarrollo inicia en `http://localhost:5173` y redirige las llamadas de API hacia el backend.

## Configuración de la base de datos

### Crear la base de datos

```bash
createuser -s maquita 2>/dev/null || true
createdb -O maquita maquita_webmail
```

### Ejecutar las migraciones

Las migraciones son archivos SQL planos ubicados en `migrations/`. Aplícalos en orden:

```bash
for f in $(ls migrations/*.sql | sort); do
  echo "Applying $f ..."
  psql -U maquita -d maquita_webmail -f "$f"
done
```

O utiliza el script auxiliar si está disponible:

```bash
python scripts/migrate.py
```

### Datos de prueba (opcional)

```bash
psql -U maquita -d maquita_webmail -f scripts/seed_dev.sql
```

## Ejecutar las pruebas

### Backend

```bash
cd backend
source .venv/bin/activate

# Todas las pruebas
pytest

# Con cobertura
pytest --cov=app --cov-report=term-missing

# Módulo específico
pytest tests/test_compliance.py -v
```

### Frontend

```bash
cd frontend
npm test            # pruebas unitarias (Vitest)
npm run test:e2e    # pruebas de extremo a extremo (Playwright), requiere el backend en ejecución
```

## Formato de código

### Python (backend)

```bash
# Formatear
black app/ tests/
isort app/ tests/

# Solo verificar (modo CI)
black --check app/ tests/
isort --check-only app/ tests/
```

### TypeScript/React (frontend)

```bash
# Linting
npm run lint

# Corregir automáticamente
npm run lint -- --fix

# Formatear con Prettier (si está configurado)
npx prettier --write "src/**/*.{ts,tsx,css}"
```

## Recarga en caliente

- **Backend**: `uvicorn --reload` detecta cambios en los archivos y reinicia automáticamente.
- **Frontend**: Vite HMR actualiza el navegador al instante al guardar.

Ambos están habilitados por defecto al usar los comandos de desarrollo indicados arriba.

## Solución de problemas

### `psql: FATAL: role "maquita" does not exist`

Crea el rol primero:

```bash
sudo -u postgres createuser -s maquita
```

### `ModuleNotFoundError: No module named 'app'`

Asegúrate de haber activado el entorno virtual e instalado las dependencias:

```bash
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
```

### El puerto 5173 ya está en uso

Otra instancia de Vite o un proceso distinto está ocupando el puerto. Termínalo o cambia el puerto:

```bash
lsof -ti :5173 | xargs kill -9
# o
npm run dev -- --port 5174
```

### Conexión a Redis rechazada

Inicia el servidor de Redis:

```bash
# systemd
sudo systemctl start redis-server

# Docker
docker run -d --name redis -p 6379:6379 redis:7-alpine
```

### Las migraciones fallan con "relation already exists"

Las migraciones no son idempotentes por defecto. Si necesitas comenzar desde cero:

```bash
dropdb maquita_webmail
createdb -O maquita maquita_webmail
# Vuelve a ejecutar las migraciones
```

### Errores de CORS en el navegador

Asegúrate de que `CORS_ORIGINS` en `.env` incluya la URL de tu frontend (por ejemplo, `http://localhost:5173`).

### El backend no puede conectarse a PostgreSQL en macOS

Si usas PostgreSQL de Homebrew, la ruta del socket puede ser diferente. Usa TCP explícitamente:

```
DATABASE_URL=postgresql://maquita:maquita@127.0.0.1:5432/maquita_webmail
```
