"""Import CSV / Export CSV+vCard de contactos."""
import csv
import io
from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.auth.dependencies import get_current_user
from .helpers import audit

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

# Mapeo de headers CSV → campo de BD (inglés y español)
_CSV_MAP = {
    "first name": "first_name", "nombre": "first_name",
    "last name": "last_name", "apellido": "last_name",
    "display name": "display_name", "nombre completo": "display_name",
    "e-mail address": "email", "email": "email", "correo": "email",
    "e-mail 2 address": "email2", "email 2": "email2",
    "e-mail 3 address": "email3", "email 3": "email3",
    "mobile phone": "phone_mobile", "celular": "phone_mobile",
    "business phone": "phone_work", "telefono trabajo": "phone_work", "teléfono trabajo": "phone_work",
    "home phone": "phone_home", "telefono casa": "phone_home", "teléfono casa": "phone_home",
    "business fax": "fax",
    "company": "company", "empresa": "company",
    "organizacion": "organization", "organización": "organization",
    "job title": "job_title", "cargo": "job_title",
    "department": "department", "departamento": "department",
    "notes": "notes", "notas": "notes",
    "birthday": "birthday", "cumpleaños": "birthday",
    "web page": "website", "website": "website", "sitio web": "website",
    "phone": "phone", "telefono": "phone", "teléfono": "phone",
    "street": "address_street", "direccion": "address_street", "dirección": "address_street",
    "city": "address_city", "ciudad": "address_city",
    "state": "address_state", "estado": "address_state", "provincia": "address_state",
    "zip": "address_zip", "codigo postal": "address_zip", "código postal": "address_zip",
    "country": "address_country", "pais": "address_country", "país": "address_country",
}

# Campos actualizables en merge (import sobre existente)
MAX_IMPORT_CONTACTS = 1000  # Max contacts per import

_MERGE_FIELDS = (
    "first_name", "last_name", "phone", "phone_mobile", "phone_work", "phone_home",
    "organization", "company", "job_title", "department", "notes",
    "address_street", "address_city", "address_state", "address_zip", "address_country",
    "website", "fax", "email2", "email3",
)


@router.post("/import")
async def import_contacts(request: Request, username: str = Depends(get_current_user)):
    """
    Importa contactos desde CSV.
    - Acepta multipart/form-data (campo 'file') o JSON (campo 'csv_data')
    - Detecta BOM, delimitador (,/;), y aliases de headers (EN/ES)
    - Si email ya existe: merge (solo actualiza campos vacíos)
    - Retorna: {imported, updated, skipped, errors}
    """
    db = request.app.state.db_pool
    content_type = request.headers.get("content-type", "")

    if "multipart" in content_type:
        form = await request.form()
        file_field = form.get("file")
        if not file_field:
            raise HTTPException(400, "No se encontró archivo")
        raw = await file_field.read()
    else:
        body = await request.json()
        raw = body.get("csv_data", "").encode("utf-8")

    # Decodificar con detección de BOM
    text = raw.decode("utf-8-sig")

    # Detectar delimitador
    first_line = text.split("\n")[0]
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","

    # Pre-check: count lines to enforce limit
    line_count = text.count("\n")
    if line_count > MAX_IMPORT_CONTACTS + 1:  # +1 for header
        raise HTTPException(400, f"Máximo {MAX_IMPORT_CONTACTS} contactos por importación (archivo tiene ~{line_count-1})")

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    imported = updated = skipped = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        mapped = _map_csv_row(row)
        email = mapped.get("email", "")
        if not email or "@" not in email:
            errors.append({"row": i, "error": f"Email inválido o faltante: '{email}'"})
            skipped += 1
            continue

        display_name = mapped.get("display_name", "")
        if not display_name:
            fn = mapped.get("first_name", "")
            ln = mapped.get("last_name", "")
            display_name = f"{fn} {ln}".strip() if (fn or ln) else email.split("@")[0]

        birthday = _parse_birthday_multi(mapped.get("birthday"))

        existing = await db.fetchrow(
            "SELECT id FROM user_contacts WHERE owner=$1 AND LOWER(email)=LOWER($2) AND deleted_at IS NULL",
            username, email
        )

        if existing:
            await _merge_existing(db, existing["id"], username, mapped, display_name)
            updated += 1
        else:
            await _insert_new(db, username, email, display_name, mapped, birthday)
            imported += 1

    ip = request.client.host if request.client else ""
    await audit(db, username, None, "import", {"imported": imported, "updated": updated, "skipped": skipped}, ip)
    return {"imported": imported, "updated": updated, "skipped": skipped, "errors": errors[:50]}


@router.get("/export")
async def export_contacts(
    request: Request, format: str = "csv", filter: str = "all",
    username: str = Depends(get_current_user),
):
    """
    Exporta contactos activos.
    - format: csv (UTF-8 con BOM para Excel) o vcf (vCard 3.0)
    - filter: all, favorites, list:{id}
    """
    db = request.app.state.db_pool

    if filter == "favorites":
        where, params = "owner = $1 AND deleted_at IS NULL AND is_favorite = true", [username]
    elif filter.startswith("list:"):
        list_id = int(filter.split(":")[1])
        where = "owner = $1 AND deleted_at IS NULL AND id IN (SELECT contact_id FROM contact_list_members WHERE list_id = $2)"
        params = [username, list_id]
    else:
        where, params = "owner = $1 AND deleted_at IS NULL", [username]

    rows = await db.fetch(f"SELECT * FROM user_contacts WHERE {where} ORDER BY display_name", *params)
    today = datetime.now().strftime("%Y%m%d")

    if format == "vcf":
        return _export_vcard(rows, today)
    return _export_csv(rows, today)


# ── Funciones internas ──────────────────────────────────────────────


def _map_csv_row(row: dict) -> dict:
    """Mapea headers CSV (cualquier idioma) a campos de BD."""
    mapped = {}
    for header, value in row.items():
        if not header:
            continue
        key = _CSV_MAP.get(header.strip().lower(), "")
        if key and value and value.strip():
            mapped[key] = value.strip()
    return mapped


def _parse_birthday_multi(value: str) -> "date | None":
    """Intenta parsear fecha en varios formatos comunes."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass
    return None


async def _merge_existing(db, contact_id: int, owner: str, mapped: dict, display_name: str):
    """Actualiza solo campos vacíos del contacto existente."""
    sets = []
    params = [contact_id, owner]
    pi = 3
    for field in _MERGE_FIELDS:
        if mapped.get(field):
            sets.append(f"{field} = CASE WHEN COALESCE({field}, '') = '' THEN ${pi} ELSE {field} END")
            params.append(mapped[field])
            pi += 1
    if display_name:
        sets.append(f"display_name = CASE WHEN COALESCE(display_name, '') = '' THEN ${pi} ELSE display_name END")
        params.append(display_name)
        pi += 1
    if sets:
        await db.execute(f"UPDATE user_contacts SET {', '.join(sets)} WHERE id=$1 AND owner=$2", *params)


async def _insert_new(db, owner: str, email: str, display_name: str, mapped: dict, birthday):
    """Inserta contacto nuevo desde CSV."""
    await db.execute("""
        INSERT INTO user_contacts (owner, display_name, email, first_name, last_name,
            phone, phone_mobile, phone_work, phone_home, fax,
            organization, company, job_title, department, notes,
            address_street, address_city, address_state, address_zip, address_country,
            birthday, website, email2, email3, source)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,'import')
    """,
        owner, display_name, email,
        mapped.get("first_name", ""), mapped.get("last_name", ""),
        mapped.get("phone", ""), mapped.get("phone_mobile", ""),
        mapped.get("phone_work", ""), mapped.get("phone_home", ""), mapped.get("fax", ""),
        mapped.get("organization", ""), mapped.get("company", ""),
        mapped.get("job_title", ""), mapped.get("department", ""), mapped.get("notes", ""),
        mapped.get("address_street", ""), mapped.get("address_city", ""),
        mapped.get("address_state", ""), mapped.get("address_zip", ""),
        mapped.get("address_country", ""),
        birthday, mapped.get("website", ""),
        mapped.get("email2", ""), mapped.get("email3", ""),
    )


def _export_vcard(rows, today: str) -> StreamingResponse:
    """Genera archivo vCard 3.0 con todos los contactos."""
    lines = []
    for r in rows:
        lines.append("BEGIN:VCARD")
        lines.append("VERSION:3.0")
        fn = r["display_name"] or f"{r['first_name']} {r['last_name']}".strip()
        lines.append(f"FN:{fn}")
        if r["last_name"] or r["first_name"]:
            lines.append(f"N:{r['last_name']};{r['first_name']};;;")
        if r["email"]:
            lines.append(f"EMAIL;TYPE=INTERNET:{r['email']}")
        if r.get("email2"):
            lines.append(f"EMAIL;TYPE=INTERNET:{r['email2']}")
        if r.get("email3"):
            lines.append(f"EMAIL;TYPE=INTERNET:{r['email3']}")
        if r.get("phone"):
            lines.append(f"TEL;TYPE=VOICE:{r['phone']}")
        if r.get("phone_mobile"):
            lines.append(f"TEL;TYPE=CELL:{r['phone_mobile']}")
        if r.get("phone_work"):
            lines.append(f"TEL;TYPE=WORK:{r['phone_work']}")
        if r.get("phone_home"):
            lines.append(f"TEL;TYPE=HOME:{r['phone_home']}")
        org = r.get("company") or r.get("organization") or ""
        if org:
            lines.append(f"ORG:{org}")
        if r.get("job_title"):
            lines.append(f"TITLE:{r['job_title']}")
        if r.get("birthday"):
            lines.append(f"BDAY:{r['birthday'].isoformat()}")
        if r.get("website"):
            lines.append(f"URL:{r['website']}")
        if r.get("notes"):
            lines.append(f"NOTE:{r['notes'].replace(chr(10), ' ')}")
        addr_parts = [
            "", "", r.get("address_street", ""), r.get("address_city", ""),
            r.get("address_state", ""), r.get("address_zip", ""), r.get("address_country", "")
        ]
        if any(addr_parts[2:]):
            lines.append(f"ADR;TYPE=WORK:{';'.join(addr_parts)}")
        lines.append("END:VCARD")
        lines.append("")

    content = "\r\n".join(lines)
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/vcard",
        headers={"Content-Disposition": f"attachment; filename=contactos_maquita_{today}.vcf"}
    )


def _export_csv(rows, today: str) -> StreamingResponse:
    """Genera CSV con BOM UTF-8 (compatible con Excel)."""
    output = io.StringIO()
    output.write("\ufeff")  # BOM para Excel
    headers = [
        "First Name", "Last Name", "Display Name", "E-mail Address", "E-mail 2 Address", "E-mail 3 Address",
        "Mobile Phone", "Business Phone", "Home Phone", "Company", "Job Title", "Department",
        "Notes", "Birthday", "Web Page", "Business Fax",
        "Street", "City", "State", "Zip", "Country",
    ]
    writer = csv.DictWriter(output, fieldnames=headers)
    writer.writeheader()
    for r in rows:
        writer.writerow({
            "First Name": r.get("first_name", ""), "Last Name": r.get("last_name", ""),
            "Display Name": r.get("display_name", ""),
            "E-mail Address": r.get("email", ""), "E-mail 2 Address": r.get("email2", ""),
            "E-mail 3 Address": r.get("email3", ""),
            "Mobile Phone": r.get("phone_mobile", ""), "Business Phone": r.get("phone_work", ""),
            "Home Phone": r.get("phone_home", ""),
            "Company": r.get("company", "") or r.get("organization", ""),
            "Job Title": r.get("job_title", ""), "Department": r.get("department", ""),
            "Notes": r.get("notes", ""),
            "Birthday": r["birthday"].isoformat() if r.get("birthday") else "",
            "Web Page": r.get("website", ""), "Business Fax": r.get("fax", ""),
            "Street": r.get("address_street", ""), "City": r.get("address_city", ""),
            "State": r.get("address_state", ""), "Zip": r.get("address_zip", ""),
            "Country": r.get("address_country", ""),
        })
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=contactos_maquita_{today}.csv"}
    )
