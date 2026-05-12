"""CRUD — listar, crear, actualizar, eliminar (soft delete) contactos."""
from datetime import datetime
from fastapi import APIRouter, Request, Depends, HTTPException
from app.auth.dependencies import get_current_user
from app.core.sanitize import strip_html
from .helpers import ALL_FIELDS, compute_display_name, audit, enrich_contact

# Campos de texto que deben sanitizarse antes de guardar
_TEXT_FIELDS = (
    "first_name", "last_name", "nickname", "phone", "organization", "notes",
    "job_title", "department", "company", "email2", "email3",
    "phone_mobile", "phone_work", "phone_home", "fax",
    "address_street", "address_city", "address_state", "address_zip", "address_country",
    "website", "im_address",
)


def _sanitize_body(body: dict) -> dict:
    """Aplica strip_html a todos los campos de texto del contacto."""
    for field in _TEXT_FIELDS:
        if field in body and isinstance(body[field], str):
            body[field] = strip_html(body[field])
    # display_name se computa despues, pero sanitizamos si viene explicito
    if "display_name" in body and isinstance(body["display_name"], str):
        body["display_name"] = strip_html(body["display_name"])
    return body

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("")
async def list_contacts(
    request: Request, page: int = 1, per_page: int = 50,
    search: str = "", filter: str = "all", sort: str = "name",
    username: str = Depends(get_current_user),
):
    """Lista contactos con filtros, búsqueda, ordenamiento y paginación."""
    db = request.app.state.db_pool
    offset = (page - 1) * per_page
    params = [username]
    pi = 2  # índice de parámetro

    # WHERE según filtro
    if filter == "deleted":
        where = "owner = $1 AND deleted_at IS NOT NULL"
    elif filter == "favorites":
        where = "owner = $1 AND deleted_at IS NULL AND is_favorite = true"
    elif filter.startswith("category:"):
        cat_id = int(filter.split(":")[1])
        where = f"owner = $1 AND deleted_at IS NULL AND id IN (SELECT contact_id FROM contact_category_assignments WHERE category_id = ${pi})"
        params.append(cat_id)
        pi += 1
    elif filter.startswith("list:"):
        list_id = int(filter.split(":")[1])
        where = f"owner = $1 AND deleted_at IS NULL AND id IN (SELECT contact_id FROM contact_list_members WHERE list_id = ${pi})"
        params.append(list_id)
        pi += 1
    else:
        where = "owner = $1 AND deleted_at IS NULL"

    # Búsqueda por texto
    if search:
        where += (
            f" AND (LOWER(display_name) LIKE LOWER(${pi})"
            f" OR LOWER(email) LIKE LOWER(${pi})"
            f" OR LOWER(COALESCE(organization,'')) LIKE LOWER(${pi})"
            f" OR LOWER(COALESCE(company,'')) LIKE LOWER(${pi})"
            f" OR LOWER(COALESCE(first_name,'')) LIKE LOWER(${pi})"
            f" OR LOWER(COALESCE(last_name,'')) LIKE LOWER(${pi}))"
        )
        params.append(f"%{search}%")
        pi += 1

    # Ordenamiento
    sort_map = {
        "name": "display_name", "email": "email",
        "company": "COALESCE(company, organization)",
        "created": "created_at DESC",
        "last_contacted": "last_contacted_at DESC NULLS LAST",
    }
    order = sort_map.get(sort, "display_name")

    # Total para paginación
    count = await db.fetchval(f"SELECT COUNT(*) FROM user_contacts WHERE {where}", *params)

    # Contactos + categorías
    params_fetch = params + [per_page, offset]
    rows = await db.fetch(
        f"SELECT {ALL_FIELDS} FROM user_contacts WHERE {where} ORDER BY {order} LIMIT ${pi} OFFSET ${pi+1}",
        *params_fetch
    )
    contacts = [await enrich_contact(db, row) for row in rows]

    # FQA-007: When searching, also include org_contacts (directory) results
    org_contacts_list = []
    org_total = 0
    if search:
        domain = username.split("@")[1] if "@" in username else username
        org_rows = await db.fetch(
            """SELECT id, display_name, email, COALESCE(phone, ) as phone,
                   department, job_title, directory as source
            FROM org_contacts
            WHERE domain = $1 AND (
                LOWER(display_name) LIKE LOWER($2)
                OR LOWER(email) LIKE LOWER($2)
                OR LOWER(COALESCE(department, )) LIKE LOWER($2)
                OR LOWER(COALESCE(first_name, )) LIKE LOWER($2)
                OR LOWER(COALESCE(last_name, )) LIKE LOWER($2)
            )
            ORDER BY display_name
            LIMIT $3""",
            domain, f"%{search}%", per_page
        )
        seen_emails = {c.get("email", "").lower() for c in contacts}
        for row in org_rows:
            if row["email"].lower() not in seen_emails:
                org_contacts_list.append({
                    "id": row["id"],
                    "display_name": row["display_name"],
                    "email": row["email"],
                    "phone": row["phone"],
                    "department": row["department"],
                    "job_title": row["job_title"],
                    "source": "directory",
                    "is_favorite": False,
                    "categories": [],
                })
                seen_emails.add(row["email"].lower())
        org_total = len(org_contacts_list)

    all_contacts = contacts + org_contacts_list
    return {"contacts": all_contacts, "total": count + org_total, "page": page, "per_page": per_page}


@router.post("")
async def create_contact(request: Request, username: str = Depends(get_current_user)):
    """Crea un contacto nuevo. Requiere email. Verifica deduplicación."""
    body = await request.json()
    body = _sanitize_body(body)
    db = request.app.state.db_pool
    email = body.get("email", "").strip()
    if not email:
        raise HTTPException(400, "Email es requerido")

    # Verificar duplicado
    existing = await db.fetchval(
        "SELECT id FROM user_contacts WHERE owner=$1 AND LOWER(email)=LOWER($2) AND deleted_at IS NULL",
        username, email
    )
    if existing:
        raise HTTPException(409, f"Ya existe un contacto con el email {email}")

    display_name = compute_display_name(body)
    birthday = _parse_birthday(body.get("birthday"))

    row = await db.fetchrow("""
        INSERT INTO user_contacts (
            owner, display_name, email, phone, organization, notes,
            first_name, last_name, nickname, job_title, department, company,
            email2, email3, phone_mobile, phone_work, phone_home, fax,
            address_street, address_city, address_state, address_zip, address_country,
            birthday, website, im_address, photo_url, source
        ) VALUES (
            $1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23,$24,$25,$26,$27,$28
        ) RETURNING id
    """,
        username, display_name, email,
        body.get("phone", ""), body.get("organization", ""), body.get("notes", ""),
        body.get("first_name", ""), body.get("last_name", ""), body.get("nickname", ""),
        body.get("job_title", ""), body.get("department", ""), body.get("company", ""),
        body.get("email2", ""), body.get("email3", ""),
        body.get("phone_mobile", ""), body.get("phone_work", ""), body.get("phone_home", ""), body.get("fax", ""),
        body.get("address_street", ""), body.get("address_city", ""), body.get("address_state", ""),
        body.get("address_zip", ""), body.get("address_country", ""),
        birthday, body.get("website", ""), body.get("im_address", ""), body.get("photo_url", ""),
        body.get("source", "manual"),
    )
    ip = request.client.host if request.client else ""
    await audit(db, username, row["id"], "create", {"email": email}, ip)
    return {"status": "created", "id": row["id"]}


@router.put("/{contact_id}")
async def update_contact(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Actualiza campos de un contacto existente."""
    body = await request.json()
    body = _sanitize_body(body)
    db = request.app.state.db_pool

    existing = await db.fetchrow("SELECT * FROM user_contacts WHERE id=$1 AND owner=$2", contact_id, username)
    if not existing:
        raise HTTPException(404, "Contacto no encontrado")

    display_name = compute_display_name(body) or existing["display_name"]
    birthday = existing["birthday"]
    if "birthday" in body:
        birthday = _parse_birthday(body["birthday"]) if body["birthday"] else None

    await db.execute("""
        UPDATE user_contacts SET
            display_name=$3, email=$4, phone=$5, organization=$6, notes=$7,
            first_name=$8, last_name=$9, nickname=$10, job_title=$11, department=$12, company=$13,
            email2=$14, email3=$15, phone_mobile=$16, phone_work=$17, phone_home=$18, fax=$19,
            address_street=$20, address_city=$21, address_state=$22, address_zip=$23, address_country=$24,
            birthday=$25, website=$26, im_address=$27, photo_url=$28
        WHERE id=$1 AND owner=$2
    """,
        contact_id, username, display_name,
        body.get("email", existing["email"]), body.get("phone", existing["phone"]),
        body.get("organization", existing["organization"]), body.get("notes", existing["notes"]),
        body.get("first_name", existing["first_name"]), body.get("last_name", existing["last_name"]),
        body.get("nickname", existing["nickname"]), body.get("job_title", existing["job_title"]),
        body.get("department", existing["department"]), body.get("company", existing["company"]),
        body.get("email2", existing["email2"]), body.get("email3", existing["email3"]),
        body.get("phone_mobile", existing["phone_mobile"]), body.get("phone_work", existing["phone_work"]),
        body.get("phone_home", existing["phone_home"]), body.get("fax", existing["fax"]),
        body.get("address_street", existing["address_street"]), body.get("address_city", existing["address_city"]),
        body.get("address_state", existing["address_state"]), body.get("address_zip", existing["address_zip"]),
        body.get("address_country", existing["address_country"]),
        birthday, body.get("website", existing["website"]),
        body.get("im_address", existing["im_address"]), body.get("photo_url", existing["photo_url"]),
    )
    ip = request.client.host if request.client else ""
    await audit(db, username, contact_id, "update", {"fields": list(body.keys())}, ip)
    return {"status": "updated"}


@router.delete("/{contact_id}")
async def delete_contact(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Soft delete — mueve a papelera."""
    db = request.app.state.db_pool
    r = await db.execute(
        "UPDATE user_contacts SET deleted_at = NOW() WHERE id=$1 AND owner=$2 AND deleted_at IS NULL",
        contact_id, username
    )
    if r == "UPDATE 0":
        raise HTTPException(404, "Contacto no encontrado")
    ip = request.client.host if request.client else ""
    await audit(db, username, contact_id, "soft_delete", {}, ip)
    return {"status": "deleted"}


def _parse_birthday(value) -> "date | None":
    """Parsea birthday string a date, retorna None si falla."""
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
