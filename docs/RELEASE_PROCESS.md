# Proceso de publicación de versiones

Este documento describe cómo preparar, probar y publicar una nueva versión de Maquita Webmail.

## Política de versionado

Este proyecto sigue el [Versionado Semántico](https://semver.org/spec/v2.0.0.html):

- **MAJOR** (X.0.0) -- cambios de API que rompen compatibilidad, cambios arquitectónicos mayores
- **MINOR** (0.X.0) -- nuevas funcionalidades, compatibles con versiones anteriores
- **PATCH** (0.0.X) -- correcciones de errores, parches de seguridad, compatibles con versiones anteriores

Las versiones previas al lanzamiento usan sufijos: `1.2.0-rc.1`, `1.2.0-beta.1`.

## Estrategia de ramas

| Rama        | Propósito                                                              |
|-------------|------------------------------------------------------------------------|
| `main`      | Rama de lanzamiento estable. Siempre desplegable.                      |
| `develop`   | Rama de integración para la próxima versión.                           |
| `feature/*` | Ramas de funcionalidades, se integran a `develop`.                     |
| `hotfix/*`  | Correcciones urgentes, se ramifican desde `main` y se integran a `main` y `develop`. |
| `release/*` | Preparación de la versión, se ramifica desde `develop`.                |

### Flujo de trabajo

1. Las funcionalidades se desarrollan en ramas `feature/*` y se integran a `develop` mediante pull request.
2. Cuando `develop` está listo para publicación, crea una rama `release/vX.Y.Z`.
3. Las pruebas finales y actualizaciones del changelog ocurren en la rama de lanzamiento.
4. Integra la rama de lanzamiento a `main` y aplica la etiqueta.
5. Integra la rama de lanzamiento de vuelta a `develop`.
6. Para correcciones urgentes, ramifica `hotfix/*` desde `main`, corrige e integra a `main` y `develop`.

## Lista de verificación para el lanzamiento

Verifica cada elemento antes de etiquetar una versión:

### Calidad del código

- [ ] Todas las pruebas de CI pasan en la rama de lanzamiento
- [ ] Sin errores de linting (`black --check`, `isort --check`, `npm run lint`)
- [ ] Sin errores de tipos (`mypy app/`, `npx tsc --noEmit`)
- [ ] La cobertura de código cumple el umbral mínimo (80%+)

### Seguridad

- [ ] `gitleaks detect` no reporta hallazgos
- [ ] No hay dependencias nuevas con vulnerabilidades conocidas (`pip audit`, `npm audit`)
- [ ] No hay secretos codificados directamente en el código fuente
- [ ] SBOM generado e incluido en los artefactos de la versión

### Documentación

- [ ] `CHANGELOG.md` actualizado con todos los cambios bajo la nueva versión
- [ ] Número de versión incrementado en `backend/app/__init__.py` y `frontend/package.json`
- [ ] Guía de migración redactada (si hay cambios que rompen compatibilidad)
- [ ] La documentación de API refleja los cambios en los endpoints

### Base de datos

- [ ] Migraciones nuevas probadas desde una base de datos limpia (`createdb` + aplicar todas)
- [ ] Migraciones nuevas probadas como actualización desde la versión anterior
- [ ] Existe migración de reversión (si aplica)
- [ ] No hay pérdida de datos en la ruta de migración

### Verificación final

- [ ] Instalación nueva probada en una VM Debian 12 limpia
- [ ] Ruta de actualización probada desde la versión anterior
- [ ] Todas las funcionalidades de cumplimiento verificadas (retención legal, auditoría, exportación)
- [ ] Envío y recepción de correo probados de extremo a extremo
- [ ] Calendario, contactos y tareas funcionando

## Cómo crear una versión

### 1. Prepara la rama de lanzamiento

```bash
git checkout develop
git pull origin develop
git checkout -b release/v1.2.0
```

### 2. Actualiza la versión y el changelog

Edita los números de versión:

```bash
# backend/app/__init__.py
__version__ = "1.2.0"

# frontend/package.json
# "version": "1.2.0"
```

Mueve las entradas de `[Unreleased]` en `CHANGELOG.md` a la sección de la nueva versión.

### 3. Ejecuta la suite de pruebas completa

```bash
cd backend && pytest --cov=app
cd frontend && npm test && npm run test:e2e
```

### 4. Análisis de seguridad

```bash
gitleaks detect --source .
pip audit
cd frontend && npm audit
```

### 5. Genera el SBOM

```bash
# Python
pip-licenses --format=json --output-file=sbom-backend.json

# Node
npx @cyclonedx/cyclonedx-npm --output-file sbom-frontend.json
```

### 6. Integra y etiqueta

```bash
git checkout main
git merge --no-ff release/v1.2.0
git tag -s v1.2.0 -m "Release v1.2.0: <brief description>"
git push origin main --tags

# Integrar de vuelta a develop
git checkout develop
git merge --no-ff release/v1.2.0
git push origin develop

# Limpiar
git branch -d release/v1.2.0
```

### 7. Crea el lanzamiento en GitHub

```bash
# Generar sumas de verificación
sha256sum sbom-*.json > SHA256SUMS

gh release create v1.2.0 \
  --title "v1.2.0 - <Title>" \
  --notes-file release-notes-v1.2.0.md \
  sbom-backend.json \
  sbom-frontend.json \
  SHA256SUMS
```

### 8. Tareas posteriores al lanzamiento

- [ ] Verifica la página del lanzamiento en GitHub
- [ ] Despliega en staging y ejecuta pruebas de humo
- [ ] Despliega en producción
- [ ] Anuncia la versión (si aplica)
- [ ] Cierra el hito en GitHub

## Proceso de corrección urgente (hotfix)

Para correcciones críticas que no pueden esperar al próximo lanzamiento regular:

```bash
git checkout main
git checkout -b hotfix/v1.2.1

# Corrige el problema, actualiza CHANGELOG.md, incrementa la versión de parche

git checkout main
git merge --no-ff hotfix/v1.2.1
git tag -s v1.2.1 -m "Hotfix v1.2.1: <description>"
git push origin main --tags

git checkout develop
git merge --no-ff hotfix/v1.2.1
git push origin develop
```

## Paquete de evidencia

Para versiones con relevancia de cumplimiento normativo, crea un paquete de evidencia:

```
evidence/
  v1.2.0/
    CHANGELOG.md          # Cambios en esta versión
    test-results.xml      # Salida de las pruebas de CI
    coverage-report.html  # Cobertura de código
    gitleaks-report.json  # Resultados del análisis de secretos
    sbom-backend.json     # Dependencias del backend
    sbom-frontend.json    # Dependencias del frontend
    SHA256SUMS            # Sumas de verificación de todos los artefactos
    migration-test.log    # Registro de pruebas de migración de base de datos
```

Este paquete debe archivarse y conservarse según la política de retención de cumplimiento de la organización.
