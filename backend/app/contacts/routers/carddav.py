"""
CardDAV — exportar/importar contactos en formato vCard para sincronización.
Provee endpoints para que clientes CardDAV puedan sincronizar.
Implementa un subset simplificado de CardDAV via REST.
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import hashlib
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def _contact_to_vcard(c: dict) -> str:
    """Convierte un contacto a formato vCard 3.0."""
    lines = ["BEGIN:VCARD", "VERSION:3.0"]

    fn = c.get("display_name") or ""
    if fn:
        lines.append(f"FN:{fn}")

    ln = c.get("last_name", "")
    gn = c.get("first_name", "")
    if ln or gn:
        lines.append(f"N:{ln};{gn};;;")

    email = c.get("email", "")
    if email:
        lines.append(f"EMAIL;TYPE=INTERNET;TYPE=WORK:{email}")
    email2 = c.get("email2", "")
    if email2:
        lines.append(f"EMAIL;TYPE=INTERNET;TYPE=HOME:{email2}")
    email3 = c.get("email3", "")
    if email3:
        lines.append(f"EMAIL;TYPE=INTERNET:{email3}")

    phone = c.get("phone", "")
    if phone:
        lines.append(f"TEL;TYPE=VOICE:{phone}")
    pm = c.get("phone_mobile", "")
    if pm:
        lines.append(f"TEL;TYPE=CELL:{pm}")
    pw = c.get("phone_work", "")
    if pw:
        lines.append(f"TEL;TYPE=WORK:{pw}")
    ph = c.get("phone_home", "")
    if ph:
        lines.append(f"TEL;TYPE=HOME:{ph}")

    org = c.get("company", "") or c.get("organization", "")
    if org:
        lines.append(f"ORG:{org}")

    title = c.get("job_title", "")
    if title:
        lines.append(f"TITLE:{title}")

    dept = c.get("department", "")
    if dept:
        lines.append(f"X-DEPARTMENT:{dept}")

    # Address
    street = c.get("address_street", "")
    city = c.get("address_city", "")
    state = c.get("address_state", "")
    zip_code = c.get("address_zip", "")
    country = c.get("address_country", "")
    if any([street, city, state, zip_code, country]):
        lines.append(f"ADR;TYPE=WORK:;;{street};{city};{state};{zip_code};{country}")

    bday = c.get("birthday")
    if bday:
        if isinstance(bday, datetime):
            bday = bday.strftime("%Y-%m-%d")
        lines.append(f"BDAY:{bday}")

    url = c.get("website", "")
    if url:
        lines.append(f"URL:{url}")

    note = c.get("notes", "")
    if note:
        lines.append(f"NOTE:{note.replace(chr(10), '\\n')}")

    photo = c.get("photo_url", "")
    if photo:
        lines.append(f"PHOTO;VALUE=URI:{photo}")

    # UID basado en id del contacto
    uid = c.get("vcard_uid") or f"contact-{c['id']}@maquita"
    lines.append(f"UID:{uid}")

    # REV
    updated = c.get("updated_at")
    if updated:
        if isinstance(updated, datetime):
            rev = updated.strftime("%Y%m%dT%H%M%SZ")
        else:
            rev = str(updated).replace("-", "").replace(":", "").replace(" ", "T")[:15] + "Z"
        lines.append(f"REV:{rev}")

    lines.append("END:VCARD")
    return "\r\n".join(lines)


def _parse_vcard(vcard_text: str) -> dict:
    """Parsea un vCard 3.0 a diccionario de campos."""
    data = {}
    for line in vcard_text.replace("\r\n ", "").replace("\r\n\t", "").split("\r\n"):
        if not line or line.startswith("BEGIN:") or line.startswith("END:") or line.startswith("VERSION:"):
            continue

        # Separar tipo y valor
        if ":" not in line:
            continue
        field_part, value = line.split(":", 1)
        field_name = field_part.split(";")[0].upper()

        if field_name == "FN":
            data["display_name"] = value
        elif field_name == "N":
            parts = value.split(";")
            data["last_name"] = parts[0] if len(parts) > 0 else ""
            data["first_name"] = parts[1] if len(parts) > 1 else ""
        elif field_name == "EMAIL":
            if "email" not in data:
                data["email"] = value
            elif "email2" not in data:
                data["email2"] = value
            else:
                data["email3"] = value
        elif field_name == "TEL":
            type_info = field_part.upper()
            if "CELL" in type_info:
                data["phone_mobile"] = value
            elif "WORK" in type_info:
                data["phone_work"] = value
            elif "HOME" in type_info:
                data["phone_home"] = value
            elif "phone" not in data:
                data["phone"] = value
        elif field_name == "ORG":
            data["company"] = value
        elif field_name == "TITLE":
            data["job_title"] = value
        elif field_name == "ADR":
            parts = value.split(";")
            if len(parts) >= 7:
                data["address_street"] = parts[2]
                data["address_city"] = parts[3]
                data["address_state"] = parts[4]
                data["address_zip"] = parts[5]
                data["address_country"] = parts[6]
        elif field_name == "BDAY":
            data["birthday"] = value
        elif field_name == "URL":
            data["website"] = value
        elif field_name == "NOTE":
            data["notes"] = value.replace("\\n", "\n")
        elif field_name == "PHOTO":
            data["photo_url"] = value
        elif field_name == "UID":
            data["vcard_uid"] = value
        elif field_name == "X-DEPARTMENT":
            data["department"] = value

    return data


@router.get("/carddav/addressbook.vcf")
async def export_all_vcards(request: Request, username: str = Depends(get_current_user)):
    """Exporta todos los contactos como un archivo multi-vCard."""
    db = request.app.state.db_pool
    user = username

    rows = await db.fetch(
        """SELECT uc.*, cs.vcard_uid, cs.etag
           FROM user_contacts uc
           LEFT JOIN contact_sync_state cs ON cs.contact_id = uc.id AND cs.owner = uc.owner
           WHERE uc.owner = $1 AND uc.deleted_at IS NULL
           ORDER BY uc.display_name""",
        user,
    )

    vcards = []
    for row in rows:
        c = dict(row)
        vcards.append(_contact_to_vcard(c))

    content = "\r\n".join(vcards)
    return PlainTextResponse(
        content=content,
        media_type="text/vcard; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="contacts.vcf"'},
    )


@router.get("/carddav/sync")
async def get_sync_state(request: Request, username: str = Depends(get_current_user)):
    """Retorna el estado de sincronización para detectar cambios."""
    db = request.app.state.db_pool
    user = username

    rows = await db.fetch(
        """SELECT cs.contact_id, cs.etag, cs.vcard_uid, cs.last_synced,
                  uc.updated_at
           FROM contact_sync_state cs
           JOIN user_contacts uc ON uc.id = cs.contact_id
           WHERE cs.owner = $1 AND uc.deleted_at IS NULL""",
        user,
    )

    # También incluir contactos sin estado de sync (nuevos)
    all_contacts = await db.fetch(
        """SELECT id, updated_at FROM user_contacts
           WHERE owner = $1 AND deleted_at IS NULL""",
        user,
    )

    synced_ids = {r["contact_id"] for r in rows}
    result = []

    for r in rows:
        etag = hashlib.md5(str(r["updated_at"]).encode()).hexdigest()
        result.append({
            "contact_id": r["contact_id"],
            "etag": etag,
            "vcard_uid": r["vcard_uid"],
            "needs_sync": etag != r["etag"],
        })

    for c in all_contacts:
        if c["id"] not in synced_ids:
            etag = hashlib.md5(str(c["updated_at"]).encode()).hexdigest()
            result.append({
                "contact_id": c["id"],
                "etag": etag,
                "vcard_uid": None,
                "needs_sync": True,
            })

    return result


@router.post("/carddav/import-vcard")
async def import_vcard(request: Request, username: str = Depends(get_current_user)):
    """Importa uno o más vCards y crea/actualiza contactos."""
    db = request.app.state.db_pool
    user = username

    body = await request.body()
    vcard_text = body.decode("utf-8")

    # Split multiple vcards
    vcards = []
    current = []
    for line in vcard_text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        current.append(line)
        if line.strip().upper() == "END:VCARD":
            vcards.append("\r\n".join(current))
            current = []

    imported = 0
    updated = 0
    errors = []

    for vcard in vcards:
        try:
            data = _parse_vcard(vcard)
            if not data.get("email"):
                errors.append("vCard sin email — saltado")
                continue

            # Check if exists
            existing = await db.fetchrow(
                "SELECT id FROM user_contacts WHERE owner=$1 AND email=$2 AND deleted_at IS NULL",
                user, data["email"],
            )

            if existing:
                # Update non-empty fields
                sets = []
                params = [existing["id"], user]
                idx = 3
                for field in ["display_name", "first_name", "last_name", "phone", "phone_mobile",
                              "phone_work", "phone_home", "company", "job_title", "department",
                              "address_street", "address_city", "address_state", "address_zip",
                              "address_country", "website", "notes", "photo_url"]:
                    if data.get(field):
                        sets.append(f"{field}=${idx}")
                        params.append(data[field])
                        idx += 1

                if sets:
                    await db.execute(
                        f"UPDATE user_contacts SET {', '.join(sets)}, updated_at=NOW() WHERE id=$1 AND owner=$2",
                        *params,
                    )
                updated += 1
            else:
                display_name = data.get("display_name") or f"{data.get('first_name', '')} {data.get('last_name', '')}".strip() or data["email"]
                await db.execute(
                    """INSERT INTO user_contacts
                        (owner, display_name, first_name, last_name, email, phone, phone_mobile,
                         phone_work, phone_home, company, organization, job_title, department,
                         address_street, address_city, address_state, address_zip, address_country,
                         website, notes, photo_url, source)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,'import')""",
                    user, display_name, data.get("first_name", ""), data.get("last_name", ""),
                    data["email"], data.get("phone", ""), data.get("phone_mobile", ""),
                    data.get("phone_work", ""), data.get("phone_home", ""),
                    data.get("company", ""), data.get("job_title", ""), data.get("department", ""),
                    data.get("address_street", ""), data.get("address_city", ""),
                    data.get("address_state", ""), data.get("address_zip", ""),
                    data.get("address_country", ""), data.get("website", ""),
                    data.get("notes", ""), data.get("photo_url", ""),
                )
                imported += 1

        except Exception as e:
            errors.append(str(e))

    return {"imported": imported, "updated": updated, "errors": errors}
