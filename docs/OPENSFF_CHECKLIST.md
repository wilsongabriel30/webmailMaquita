# OpenSSF Scorecard & Best Practices — Checklist

> Repositorio: [wilsongabriel30/webmailMaquita](https://github.com/wilsongabriel30/webmailMaquita)
> Resultados Scorecard: https://scorecard.dev/viewer/?uri=github.com/wilsongabriel30/webmailMaquita

---

## Resumen de criterios

| Criterio | Estado | Acción requerida |
|---|---|---|
| Branch Protection | Recomendado | Activar reglas en `main`: require PR review, status checks, no force push |
| Signed Releases | Planificado | Firmar tags con GPG o usar Sigstore/cosign para releases |
| Dependency Pinning | Hecho | Dependencias fijadas en `requirements.txt` y `package-lock.json` |
| Token Permissions | Hecho | Workflows usan `permissions: contents: read` por defecto |
| Security Policy | Recomendado | Crear `SECURITY.md` con proceso de reporte de vulnerabilidades |
| Maintained Status | Hecho | Commits y actividad recientes en el repositorio |
| Tests | Hecho | CI con pytest (backend) y npm build (frontend) |
| Fuzzing | Planificado | Integrar OSS-Fuzz o Atheris para endpoints críticos |
| SAST | Hecho | Bandit (Python) integrado en `security-scan.yml` |
| License | Hecho | MIT — archivo `LICENSES/MIT.txt` |
| SBOM | Hecho | Script `scripts/generate_sbom.sh` genera CycloneDX |
| Vulnerabilities | Hecho | pip-audit, npm audit, Trivy en CI |
| Code Review | Recomendado | Requerir al menos 1 aprobación en PRs a `main` |
| CI Tests | Hecho | GitHub Actions en push y PRs |
| Dangerous Workflow | Hecho | No se usa `pull_request_target` con checkout inseguro |
| Packaging | Planificado | Publicar imagen Docker firmada en GHCR |

---

## Detalle por criterio

### 1. Branch Protection
**Estado:** Recomendado

Ir a Settings > Branches > Branch protection rules para `main`:
- [x] Require pull request reviews (mínimo 1)
- [x] Require status checks to pass
- [x] Do not allow force pushes
- [x] Do not allow deletions
- [ ] Require signed commits (opcional pero recomendado)

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
- GitHub Actions — actions pinneadas a SHA o versión mayor

Para mejorar: pinnear actions por SHA completo:
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
**Estado:** Recomendado

Crear `SECURITY.md` en la raíz del repositorio:

```markdown
# Security Policy

## Reporting a Vulnerability

Please report vulnerabilities to: seguridad@maquita.org

Do NOT create public issues for security vulnerabilities.

We will acknowledge within 48 hours and provide a fix timeline within 7 days.
```

### 6. Tests
**Estado:** Hecho

- Backend: pytest con PostgreSQL y Redis en CI
- Frontend: npm run build (verificación de compilación)
- Migraciones: test de SQL contra PostgreSQL limpio

### 7. Fuzzing
**Estado:** Planificado

Opciones:
- [Atheris](https://github.com/google/atheris) para fuzzing de Python
- [OSS-Fuzz](https://google.github.io/oss-fuzz/) para integración continua

### 8. SAST (Static Analysis)
**Estado:** Hecho

- Bandit para código Python
- ESLint para frontend (TypeScript/React)

### 9. SBOM
**Estado:** Hecho

Generar con: `bash scripts/generate_sbom.sh`
Formato: CycloneDX JSON

---

## Aplicar al OpenSSF Best Practices Badge

1. Ir a https://www.bestpractices.dev/en
2. Click "Get Your Badge Now"
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
2. **Crear `SECURITY.md`** con proceso de reporte
3. **Pinnear actions por SHA** en workflows
4. **Firmar releases** con GPG o Sigstore
5. **Integrar fuzzing** con Atheris
