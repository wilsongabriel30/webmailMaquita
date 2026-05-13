# Release Process

This document describes how to prepare, test, and publish a new release of Maquita Webmail.

## Versioning Policy

This project follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html):

- **MAJOR** (X.0.0) -- breaking API changes, major architecture shifts
- **MINOR** (0.X.0) -- new features, backward-compatible
- **PATCH** (0.0.X) -- bug fixes, security patches, backward-compatible

Pre-release versions use suffixes: `1.2.0-rc.1`, `1.2.0-beta.1`.

## Branch Strategy

| Branch    | Purpose                                    |
|-----------|--------------------------------------------|
| `main`    | Stable release branch. Always deployable.  |
| `develop` | Integration branch for next release.       |
| `feature/*` | Feature branches, merged into `develop`. |
| `hotfix/*` | Urgent fixes, branched from and merged to `main` and `develop`. |
| `release/*` | Release preparation, branched from `develop`. |

### Flow

1. Features are developed in `feature/*` branches and merged to `develop` via pull request.
2. When `develop` is ready for release, create a `release/vX.Y.Z` branch.
3. Final testing and changelog updates happen on the release branch.
4. Merge release branch to `main` and tag.
5. Merge release branch back to `develop`.
6. For urgent fixes, branch `hotfix/*` from `main`, fix, merge to both `main` and `develop`.

## Release Checklist

Before tagging a release, verify every item:

### Code Quality

- [ ] All CI tests pass on the release branch
- [ ] No linting errors (`black --check`, `isort --check`, `npm run lint`)
- [ ] No type errors (`mypy app/`, `npx tsc --noEmit`)
- [ ] Code coverage meets minimum threshold (80%+)

### Security

- [ ] `gitleaks detect` reports no findings
- [ ] No new dependencies with known vulnerabilities (`pip audit`, `npm audit`)
- [ ] Secrets are not hardcoded anywhere in the codebase
- [ ] SBOM generated and included in release artifacts

### Documentation

- [ ] `CHANGELOG.md` updated with all changes under the new version
- [ ] Version number bumped in `backend/app/__init__.py` and `frontend/package.json`
- [ ] Migration guide written (if breaking changes)
- [ ] API documentation reflects any endpoint changes

### Database

- [ ] New migrations tested from a clean database (`createdb` + apply all)
- [ ] New migrations tested as upgrade from previous version
- [ ] Rollback migration exists (if applicable)
- [ ] No data loss in migration path

### Final Verification

- [ ] Fresh install tested on a clean Debian 12 VM
- [ ] Upgrade path tested from previous release
- [ ] All compliance features verified (legal hold, audit trail, export)
- [ ] Email send/receive tested end-to-end
- [ ] Calendar, contacts, and tasks functional

## How to Create a Release

### 1. Prepare the release branch

```bash
git checkout develop
git pull origin develop
git checkout -b release/v1.2.0
```

### 2. Update version and changelog

Edit version numbers:

```bash
# backend/app/__init__.py
__version__ = "1.2.0"

# frontend/package.json
# "version": "1.2.0"
```

Move `[Unreleased]` entries in `CHANGELOG.md` to the new version section.

### 3. Run the full test suite

```bash
cd backend && pytest --cov=app
cd frontend && npm test && npm run test:e2e
```

### 4. Security scan

```bash
gitleaks detect --source .
pip audit
cd frontend && npm audit
```

### 5. Generate SBOM

```bash
# Python
pip-licenses --format=json --output-file=sbom-backend.json

# Node
npx @cyclonedx/cyclonedx-npm --output-file sbom-frontend.json
```

### 6. Merge and tag

```bash
git checkout main
git merge --no-ff release/v1.2.0
git tag -s v1.2.0 -m "Release v1.2.0: <brief description>"
git push origin main --tags

# Merge back to develop
git checkout develop
git merge --no-ff release/v1.2.0
git push origin develop

# Clean up
git branch -d release/v1.2.0
```

### 7. Create GitHub release

```bash
# Generate checksums
sha256sum sbom-*.json > SHA256SUMS

gh release create v1.2.0 \
  --title "v1.2.0 - <Title>" \
  --notes-file release-notes-v1.2.0.md \
  sbom-backend.json \
  sbom-frontend.json \
  SHA256SUMS
```

### 8. Post-release

- [ ] Verify the release page on GitHub
- [ ] Deploy to staging and run smoke tests
- [ ] Deploy to production
- [ ] Announce the release (if applicable)
- [ ] Close the milestone on GitHub

## Hotfix Process

For critical fixes that cannot wait for the next regular release:

```bash
git checkout main
git checkout -b hotfix/v1.2.1

# Fix the issue, update CHANGELOG.md, bump patch version

git checkout main
git merge --no-ff hotfix/v1.2.1
git tag -s v1.2.1 -m "Hotfix v1.2.1: <description>"
git push origin main --tags

git checkout develop
git merge --no-ff hotfix/v1.2.1
git push origin develop
```

## Evidence Package

For compliance-relevant releases, create an evidence package:

```
evidence/
  v1.2.0/
    CHANGELOG.md          # Changes in this release
    test-results.xml      # CI test output
    coverage-report.html  # Code coverage
    gitleaks-report.json  # Secret scan results
    sbom-backend.json     # Backend dependencies
    sbom-frontend.json    # Frontend dependencies
    SHA256SUMS            # Checksums of all artifacts
    migration-test.log    # Database migration test output
```

This package should be archived and retained per the organization's compliance retention policy.
