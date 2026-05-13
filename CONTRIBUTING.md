# Contributing to Webmail Maquita

Gracias por tu interés en contribuir a **Webmail Maquita**, una plataforma libre de correo institucional con capa de auditoría, trazabilidad, eDiscovery, legal hold y preservación de evidencia para entornos basados en Postfix/Dovecot.

Este proyecto busca ofrecer una alternativa abierta, auditable y soberana para organizaciones que necesitan controles avanzados de correo sin depender exclusivamente de suites corporativas cerradas.

---

## 1. Alcance del proyecto

Webmail Maquita incluye componentes para:

- Gestión de correo institucional.
- Integración con Postfix, Dovecot y Rspamd.
- Auditoría de actividad de usuarios.
- Message trace estructurado.
- eDiscovery por casos.
- Legal hold.
- Exportación de evidencia con hash.
- Firma y sellado de evidencias.
- Alertas antifraude.
- Control de impersonación.
- Roles específicos de compliance.

No es únicamente un webmail. Es una plataforma de correo con una capa de cumplimiento, trazabilidad y auditoría antifraude.

---

## 2. Principios de contribución

Toda contribución debe respetar estos principios:

1. **Seguridad primero**
   Ningún cambio debe debilitar la seguridad, la trazabilidad o la cadena de custodia.

2. **Privacidad por diseño**
   No se deben exponer correos reales, datos personales, credenciales, direcciones internas, IPs sensibles ni evidencias reales.

3. **Reproducibilidad**
   Todo cambio debe poder instalarse, probarse y auditarse desde un clon limpio del repositorio.

4. **Transparencia técnica**
   Las funcionalidades críticas deben estar documentadas y ser verificables mediante pruebas.

5. **Mínimo privilegio**
   Los permisos deben separarse por rol. No se aceptan accesos amplios sin justificación.

6. **Auditabilidad**
   Las acciones críticas deben dejar trazabilidad: quién hizo qué, cuándo, desde dónde y sobre qué recurso.

---

## 3. Cómo empezar

### 3.1. Clonar el repositorio

```bash
git clone https://github.com/wilsongabriel30/webmailMaquita.git
cd webmailMaquita
```

### 3.2. Configurar el entorno de desarrollo

```bash
# Backend
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tus valores locales

# Frontend
cd ../frontend
npm ci
```

### 3.3. Levantar servicios locales

Necesitas PostgreSQL 17+ y Redis 7+ corriendo localmente, o bien:

```bash
# Con Docker Compose (recomendado para desarrollo)
cp .env.example .env
docker compose up -d postgres redis
```

### 3.4. Ejecutar migraciones

```bash
psql -d maildb -f migrations/001_compliance_tables.sql
psql -d maildb -f migrations/002_compliance_columns.sql
```

### 3.5. Arrancar en desarrollo

```bash
# Backend (hot reload)
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend (hot reload)
cd frontend && npm run dev
```

Ver [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md) para la guía completa.

---

## 4. Estilo de código

### Python (backend)

- **Formatter:** [black](https://github.com/psf/black) (configuración por defecto)
- **Imports:** [isort](https://pycqa.github.io/isort/) (perfil: black)
- **Seguridad:** [bandit](https://bandit.readthedocs.io/) para análisis estático

```bash
black backend/app/
isort backend/app/
bandit -r backend/app/ -ll
```

### TypeScript / JavaScript (frontend)

- **Linting:** ESLint con la configuración del proyecto
- **Formatting:** Prettier (vía eslint-plugin-prettier)

```bash
cd frontend && npm run lint
```

### Verificación rápida

```bash
make lint      # Ejecuta todos los linters
make format    # Aplica formateo automático
```

---

## 5. Ejecutar pruebas

```bash
# Backend
cd backend
source venv/bin/activate
pytest --tb=short -q

# Frontend (build = type-check + compilación)
cd frontend
npm run build

# Todo junto
make test
```

---

## 6. Crear migraciones de base de datos

Las migraciones son archivos SQL planos en `migrations/`:

1. Crear archivo: `migrations/NNN_descripcion.sql`
2. Usar `IF NOT EXISTS` / `DO $$ ... $$` para idempotencia
3. Probar desde una base de datos limpia:

```bash
createdb testdb
psql -d testdb -f migrations/001_compliance_tables.sql
psql -d testdb -f migrations/002_compliance_columns.sql
psql -d testdb -f migrations/NNN_descripcion.sql
dropdb testdb
```

4. Documentar las tablas o columnas nuevas en el PR

---

## 7. Política de commits

Seguimos [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: agregar sistema de notificación de legal hold
fix: corregir parsing de fechas Dovecot 2.4
docs: actualizar guía de despliegue Docker
security: sanitizar archivos de evidencia exportados
chore: actualizar dependencias
```

- Commits firmados (GPG o SSH) son recomendados pero no obligatorios.
- Un commit debe representar un cambio lógico completo.
- No mezclar cambios funcionales con cambios de formato.

---

## 8. Proceso de Pull Request

1. Asegurarse de que tu rama está actualizada con `main`
2. Todos los checks de CI deben pasar (lint, tests, security scan)
3. Llenar la plantilla de PR completamente
4. Se requiere al menos una aprobación de un maintainer
5. Squash merge preferido para PRs de un solo propósito

### Checklist del PR

- [ ] El código sigue el estilo del proyecto (black, isort, eslint)
- [ ] Las pruebas pasan localmente
- [ ] No incluye secretos, credenciales ni datos reales de usuarios
- [ ] No incluye IPs internas, dominios privados ni rutas sensibles
- [ ] Las migraciones son idempotentes (si aplica)
- [ ] Documentación actualizada si cambió el comportamiento
- [ ] CHANGELOG.md actualizado si el cambio es visible para el usuario

---

## 9. Revisión de seguridad en PRs

Todo PR que toque autenticación, autorización, compliance o exportación de datos requiere verificar:

- [ ] Sin secretos ni credenciales hardcodeados
- [ ] Validación de entrada en todos los parámetros expuestos al usuario
- [ ] Consultas SQL usan sentencias parametrizadas (sin formateo de strings)
- [ ] Rutas de archivos validadas y sandboxeadas
- [ ] Permisos RBAC correctamente aplicados
- [ ] Entradas de audit trail generadas para operaciones sensibles

---

## 10. Cambios al módulo de compliance

El módulo de compliance (eDiscovery, legal holds, audit trail, detección de fraude) es sensible y tiene implicaciones legales. Para proponer cambios:

1. Abrir un issue en GitHub con la etiqueta `compliance`
2. Describir el cambio, la motivación y el contexto regulatorio si aplica
3. Esperar feedback del maintainer antes de implementar
4. Todo PR de compliance requiere revisión de al menos un maintainer con conocimiento del dominio

---

## 11. Datos y privacidad

### Prohibido

- Subir correos reales de cualquier organización
- Incluir direcciones de email de personas reales en código o tests
- Publicar logs de producción, IPs internas o rutas de servidores
- Incluir dumps de base de datos con datos reales
- Usar credenciales reales en ejemplos o documentación

### Permitido

- Usar dominios de ejemplo: `example.com`, `test.org`, `demo.local`
- Usar datos sintéticos generados con `scripts/seed_demo_data.py`
- Referenciar la arquitectura sin exponer datos internos

---

## 12. Reportar bugs

Usa la [plantilla de bug report](.github/ISSUE_TEMPLATE/bug_report.yml). Incluye:

- Pasos para reproducir
- Comportamiento esperado vs real
- Detalles del entorno (OS, versión de Python/Node, navegador)
- Logs relevantes (sin secretos ni credenciales)

---

## 13. Reportar vulnerabilidades de seguridad

**NO abrir un issue público.** Ver [SECURITY.md](SECURITY.md) para instrucciones de reporte responsable.

---

## 14. Preguntas

Abre una [discusión](https://github.com/wilsongabriel30/webmailMaquita/discussions) o un issue de documentación.

---

*Fundación Maquita — Tecnología al servicio de todos, no solo de quienes pueden pagarla.*
