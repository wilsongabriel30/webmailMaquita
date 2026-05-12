"""
Importación multi-servicio — estructura para importar desde Google, Microsoft, LinkedIn.
Incluye importación vCard mejorada y placeholder para OAuth flows.
"""
from fastapi import APIRouter, Request, HTTPException, Depends, UploadFile, File
from pydantic import BaseModel
from typing import Optional
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


class GoogleImportRequest(BaseModel):
    access_token: str


class MicrosoftImportRequest(BaseModel):
    access_token: str


@router.post("/import/vcard")
async def import_vcard_file(request: Request, file: UploadFile = File(...), username: str = Depends(get_current_user)):
    """Importa contactos desde archivo vCard (.vcf)."""
    db = request.app.state.db_pool
    user = username

    if not file.filename or not file.filename.lower().endswith('.vcf'):
        raise HTTPException(422, "El archivo debe ser .vcf (vCard)")

    content = await file.read()
    if len(content) > 10_000_000:  # 10MB max
        raise HTTPException(413, "Archivo demasiado grande (max 10MB)")
    try:
        text = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            text = content.decode('latin-1')
        except Exception:
            raise HTTPException(422, "No se pudo leer el archivo")

    # Parsear vCards
    from .carddav import _parse_vcard

    vcards = []
    current_lines = []
    for line in text.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        current_lines.append(line)
        if line.strip().upper() == 'END:VCARD':
            vcards.append('\r\n'.join(current_lines))
            current_lines = []

    imported = 0
    updated = 0
    skipped = 0
    errors = []

    for i, vcard in enumerate(vcards, 1):
        try:
            data = _parse_vcard(vcard)
            if not data.get('email'):
                skipped += 1
                continue

            existing = await db.fetchrow(
                "SELECT id FROM user_contacts WHERE owner=$1 AND email=$2 AND deleted_at IS NULL",
                user, data['email'],
            )

            if existing:
                # Merge — actualizar solo campos vacíos
                contact = await db.fetchrow(
                    "SELECT * FROM user_contacts WHERE id=$1", existing['id']
                )
                updates = []
                params = [existing['id'], user]
                idx = 3
                for field in ['display_name', 'first_name', 'last_name', 'phone',
                              'phone_mobile', 'phone_work', 'phone_home', 'company',
                              'job_title', 'department', 'website', 'notes']:
                    if data.get(field) and not contact.get(field):
                        updates.append(f"{field}=${idx}")
                        params.append(data[field])
                        idx += 1

                if updates:
                    await db.execute(
                        f"UPDATE user_contacts SET {', '.join(updates)}, updated_at=NOW() WHERE id=$1 AND owner=$2",
                        *params,
                    )
                    updated += 1
                else:
                    skipped += 1
            else:
                dn = data.get('display_name') or \
                     f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or \
                     data['email']

                await db.execute(
                    """INSERT INTO user_contacts
                        (owner, display_name, first_name, last_name, email,
                         phone, phone_mobile, phone_work, phone_home,
                         company, organization, job_title, department,
                         website, notes, source)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10,$11,$12,$13,$14,'import')""",
                    user, dn, data.get('first_name', ''), data.get('last_name', ''),
                    data['email'], data.get('phone', ''), data.get('phone_mobile', ''),
                    data.get('phone_work', ''), data.get('phone_home', ''),
                    data.get('company', ''), data.get('job_title', ''),
                    data.get('department', ''), data.get('website', ''),
                    data.get('notes', ''),
                )
                imported += 1

        except Exception as e:
            errors.append(f"vCard #{i}: {str(e)}")

    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "total_parsed": len(vcards),
    }


@router.get("/import/services")
async def list_import_services(request: Request, username: str = Depends(get_current_user)):
    """Lista los servicios de importación disponibles."""
    return [
        {
            "id": "csv",
            "name": "Archivo CSV",
            "description": "Importar desde archivo CSV (Excel, LibreOffice, etc.)",
            "icon": "csv",
            "available": True,
        },
        {
            "id": "vcard",
            "name": "Archivo vCard",
            "description": "Importar desde archivo .vcf (vCard 3.0/4.0)",
            "icon": "vcard",
            "available": True,
        },
        {
            "id": "google",
            "name": "Google Contacts",
            "description": "Importar desde tu cuenta de Google",
            "icon": "google",
            "available": False,
            "setup_required": True,
            "setup_url": "/settings/integrations/google",
        },
        {
            "id": "microsoft",
            "name": "Microsoft 365 / Outlook",
            "description": "Importar desde tu cuenta de Microsoft",
            "icon": "microsoft",
            "available": False,
            "setup_required": True,
            "setup_url": "/settings/integrations/microsoft",
        },
        {
            "id": "linkedin",
            "name": "LinkedIn",
            "description": "Importar desde exportación de LinkedIn (CSV)",
            "icon": "linkedin",
            "available": True,
            "note": "Descarga tu exportación desde linkedin.com/mypreferences/d/download-my-data",
        },
    ]


@router.post("/import/linkedin")
async def import_linkedin(request: Request, file: UploadFile = File(...), username: str = Depends(get_current_user)):
    """Importa contactos desde exportación CSV de LinkedIn."""
    db = request.app.state.db_pool
    user = username

    import csv
    import io

    content = await file.read()
    if len(content) > 10_000_000:  # 10MB max
        raise HTTPException(413, "Archivo demasiado grande (max 10MB)")
    try:
        text = content.decode('utf-8-sig')
    except UnicodeDecodeError:
        text = content.decode('latin-1')

    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    updated = 0
    skipped = 0
    errors = []

    for i, row in enumerate(reader, 1):
        try:
            email = row.get('Email Address', '') or row.get('Email', '') or ''
            email = email.strip()
            if not email:
                skipped += 1
                continue

            first = row.get('First Name', '') or ''
            last = row.get('Last Name', '') or ''
            company = row.get('Company', '') or ''
            title = row.get('Position', '') or row.get('Title', '') or ''

            display_name = f"{first} {last}".strip() or email

            existing = await db.fetchrow(
                "SELECT id FROM user_contacts WHERE owner=$1 AND email=$2 AND deleted_at IS NULL",
                user, email,
            )

            if existing:
                updated += 1
            else:
                await db.execute(
                    """INSERT INTO user_contacts
                        (owner, display_name, first_name, last_name, email,
                         company, organization, job_title, source)
                       VALUES ($1,$2,$3,$4,$5,$6,$6,$7,'import')""",
                    user, display_name, first.strip(), last.strip(),
                    email, company.strip(), title.strip(),
                )
                imported += 1

        except Exception as e:
            errors.append(f"Fila #{i}: {str(e)}")

    return {
        "imported": imported,
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
    }
