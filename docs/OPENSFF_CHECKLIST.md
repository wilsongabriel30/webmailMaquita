# OpenSSF Scorecard y Mejores Prácticas — Lista de verificación

> Repositorio: [wilsongabriel30/webmailMaquita](https://github.com/wilsongabriel30/webmailMaquita)
> Resultados Scorecard: https://scorecard.dev/viewer/?uri=github.com/wilsongabriel30/webmailMaquita

---

## Resumen de criterios

| Criterio | Estado | Acción requerida |
|---|---|---|
| Branch Protection | Recomendado | Activar reglas en `main`: requerir revisión de PR, verificaciones de estado, sin force push |
| Signed Releases | Planificado | Firmar tags con GPG o usar Sigstore/cosign para releases |
| Dependency Pinning | Hecho | Dependencias fijadas en `requirements.txt` y `package-lock.json` |
| Token Permissions | Hecho | Los workflows usan `permissions: contents: read` por defecto |
| Security Policy | Hecho | `SECURITY.md` con proceso de reporte, plazos, alcance y divulgación responsable |
| Maintained Status | Hecho | Commits y actividad recientes en el repositorio |
| Tests | Hecho | CI con pytest (backend) y npm build (frontend) |
| Fuzzing | Planificado | Integrar OSS-Fuzz o Atheris para endpoints críticos |
| SAST | Hecho | Bandit (Python) integrado en `security-scan.yml` |
| License | Hecho | AGPL-3.0-or-later — archivo `LICENSES/AGPL-3.0-or-later.txt` |
| SBOM | Hecho | El script `scripts/generate_sbom.sh` genera CycloneDX |
| Vulnerabilities | Hecho | pip-audit, npm audit, Trivy en CI |
| Code Review | Recomendado | Activar branch protection: requerir al menos 1 aprobación en PRs a `main` |
| CI Tests | Hecho | GitHub Actions en push y PRs |
| Dangerous Workflow | Hecho | No se usa `pull_request_target` con checkout inseguro |
| Packaging | Planificado | Publicar imagen Docker firmada en GHCR |

---

## Detalle por criterio

### 1. Branch Protection
**Estado:** Recomendado

Ir a Settings > Branches > Branch protection rules para `main`:
- [x] Requerir revisión de pull request (mínimo 1)
- [x] Requerir que las verificaciones de estado pasen
- [x] No permitir force pushes
- [x] No permitir eliminaciones
- [ ] Requerir commits firmados (opcional pero recomendado)

### 2. Signed Releases
**Estado:** Planificado

```bash
# Opción A: GPG
git tag -s v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# Opción B: Sigstore cosign (sin claves)
cosign sign-blob --bundle release.bundle release.tar.gz
```

### 3. Dependency Pinning
**Estado:** Hecho

- `backend/requirements.txt` — versiones fijadas con `==`
- `frontend/package-lock.json` — lockfile con hashes
- GitHub Actions — actions fijadas a SHA o versión mayor

Para mejorar: fijar actions por SHA completo:
```yaml
# En vez de:
uses: actions/checkout@v4
# Usar:
uses: actions/checkout@b4ffde65f46336ab88eb53be808477a3936bae11  # v4.1.1
```

### 4. Token Permissions
**Estado:** Hecho

Todos los workflows declaran `permissions: contents: read` a nivel top-level.
Solo el job de Scorecard eleva a `security-events: write`.

### 5. Security Policy
**Estado:** Hecho

`SECURITY.md` ya existe en la raíz con:

```markdown
# Política de Seguridad

## Reporte de Vulnerabilidades

Por favor, reporta las vulnerabilidades a: security@maquita.org

NO crees issues públicos para vulnerabilidades de seguridad.

Acusaremos recibo en 48 horas y proporcionaremos un plazo de corrección en 7 días.
```

### 6. Tests
**Estado:** Hecho

- Backend: pytest con PostgreSQL y Redis en CI
- Frontend: npm run build (verificación de compilación)
- Migraciones: prueba de SQL contra PostgreSQL limpio

### 7. Fuzzing
**Estado:** Planificado

Opciones:
- [Atheris](https://github.com/google/atheris) para fuzzing de Python
- [OSS-Fuzz](https://google.github.io/oss-fuzz/) para integración continua

### 8. SAST (Análisis estático)
**Estado:** Hecho

- Bandit para código Python
- ESLint para frontend (TypeScript/React)

### 9. SBOM
**Estado:** Hecho

Generar con: `bash scripts/generate_sbom.sh`
Formato: CycloneDX JSON

---

## Aplicar al badge de Mejores Prácticas de OpenSSF

1. Ir a https://www.bestpractices.dev/en
2. Hacer clic en "Get Your Badge Now"
3. Ingresar la URL del repositorio: `https://github.com/wilsongabriel30/webmailMaquita`
4. Completar el cuestionario (la mayoría de criterios ya están cubiertos)
5. Agregar el badge al README:

```markdown
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/XXXXX/badge)](https://www.bestpractices.dev/projects/XXXXX)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/wilsongabriel30/webmailMaquita/badge)](https://scorecard.dev/viewer/?uri=github.com/wilsongabriel30/webmailMaquita)
```

---

## Próximos pasos (prioridad)

1. **Activar branch protection** en `main`
2. ~~Crear SECURITY.md~~ — **Hecho**
3. **Fijar actions por SHA** en workflows
4. **Firmar releases** con GPG o Sigstore
5. **Integrar fuzzing** con Atheris
