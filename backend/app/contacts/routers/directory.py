"""
Directorio institucional — contactos compartidos por dominio.
Solo admins del dominio pueden crear/editar/eliminar.
Todos los usuarios del dominio pueden leer.
"""
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


class OrgContactCreate(BaseModel):
    display_name: str = ""
    first_name: str = ""
    last_name: str = ""
    email: str
    phone: str = ""
    phone_mobile: str = ""
    job_title: str = ""
    department: str = ""
    company: str = ""
    address_street: str = ""
    address_city: str = ""
    address_state: str = ""
    address_zip: str = ""
    address_country: str = ""
    photo_url: str = ""
    notes: str = ""


class OrgContactUpdate(OrgContactCreate):
    pass


def _get_domain(user: str) -> str:
    """Extrae dominio del email del usuario."""
    if "@" in user:
        return user.split("@")[1]
    return user


async def _is_admin(db, user: str) -> bool:
    """Verifica si el usuario es admin del dominio.
    Solo permite: superadmins de tabla admin, domain_admins activos,
    o postmaster@/admin@ del dominio.
    """
    domain = _get_domain(user)
    # 1. Verificar superadmin en tabla admin (PostfixAdmin)
    try:
        is_super = await db.fetchval(
            "SELECT 1 FROM admin WHERE username=$1 AND active=true",
            user
        )
        if is_super:
            return True
    except Exception:
        pass
    # 2. Verificar domain_admins
    try:
        row = await db.fetchval(
            "SELECT 1 FROM domain_admins WHERE domain=$1 AND username=$2 AND is_active=true",
            domain, user
        )
        if row:
            return True
    except Exception:
        pass
    # 3. Solo postmaster@ y admin@ del dominio
    if user.startswith("postmaster@") or user.startswith("admin@"):
        return True
    return False


@router.get("/directory")
async def list_directory(request: Request, search: str = "", department: str = "", username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    user = username
    domain = _get_domain(user)

    query = """
        SELECT id, display_name, first_name, last_name, email, phone, phone_mobile,
               job_title, department, company, address_street, address_city,
               address_state, address_zip, address_country, photo_url, notes,
               created_by, created_at, updated_at
        FROM org_contacts
        WHERE domain = $1
    """
    params = [domain]
    idx = 2

    if search:
        query += f" AND (display_name ILIKE ${idx} OR email ILIKE ${idx} OR department ILIKE ${idx})"
        params.append(f"%{search}%")
        idx += 1

    if department:
        query += f" AND department = ${idx}"
        params.append(department)
        idx += 1

    query += " ORDER BY display_name ASC"

    rows = await db.fetch(query, *params)
    return [dict(r) for r in rows]


@router.get("/directory/departments")
async def list_departments(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    user = username
    domain = _get_domain(user)

    rows = await db.fetch(
        "SELECT DISTINCT department FROM org_contacts WHERE domain = $1 AND department != '' ORDER BY department",
        domain,
    )
    return [r["department"] for r in rows]


@router.get("/directory/{contact_id}")
async def get_directory_contact(request: Request, contact_id: int, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    user = username
    domain = _get_domain(user)

    row = await db.fetchrow(
        "SELECT * FROM org_contacts WHERE id = $1 AND domain = $2",
        contact_id, domain,
    )
    if not row:
        raise HTTPException(404, "Contacto no encontrado en directorio")
    return dict(row)


@router.post("/directory")
async def create_directory_contact(request: Request, body: OrgContactCreate, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    user = username
    domain = _get_domain(user)

    if not await _is_admin(db, user):
        raise HTTPException(403, "Solo administradores pueden gestionar el directorio")

    if not body.email:
        raise HTTPException(422, "Email es requerido")

    display_name = body.display_name or f"{body.first_name} {body.last_name}".strip() or body.email

    try:
        row = await db.fetchrow(
            """INSERT INTO org_contacts
                (domain, display_name, first_name, last_name, email, phone, phone_mobile,
                 job_title, department, company, address_street, address_city,
                 address_state, address_zip, address_country, photo_url, notes, created_by)
               VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18)
               RETURNING *""",
            domain, display_name, body.first_name, body.last_name, body.email,
            body.phone, body.phone_mobile, body.job_title, body.department, body.company,
            body.address_street, body.address_city, body.address_state, body.address_zip,
            body.address_country, body.photo_url, body.notes, user,
        )
        return dict(row)
    except Exception as e:
        if "unique" in str(e).lower() or "duplicate" in str(e).lower():
            raise HTTPException(409, f"Ya existe un contacto con email {body.email} en el directorio")
        raise


@router.put("/directory/{contact_id}")
async def update_directory_contact(request: Request, contact_id: int, body: OrgContactUpdate, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    user = username
    domain = _get_domain(user)

    if not await _is_admin(db, user):
        raise HTTPException(403, "Solo administradores pueden gestionar el directorio")

    display_name = body.display_name or f"{body.first_name} {body.last_name}".strip() or body.email

    row = await db.fetchrow(
        """UPDATE org_contacts SET
            display_name=$3, first_name=$4, last_name=$5, email=$6,
            phone=$7, phone_mobile=$8, job_title=$9, department=$10,
            company=$11, address_street=$12, address_city=$13, address_state=$14,
            address_zip=$15, address_country=$16, photo_url=$17, notes=$18,
            updated_at=NOW()
           WHERE id=$1 AND domain=$2 RETURNING *""",
        contact_id, domain, display_name, body.first_name, body.last_name, body.email,
        body.phone, body.phone_mobile, body.job_title, body.department, body.company,
        body.address_street, body.address_city, body.address_state, body.address_zip,
        body.address_country, body.photo_url, body.notes,
    )
    if not row:
        raise HTTPException(404, "Contacto no encontrado")
    return dict(row)


@router.delete("/directory/{contact_id}")
async def delete_directory_contact(request: Request, contact_id: int, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    user = username
    domain = _get_domain(user)

    if not await _is_admin(db, user):
        raise HTTPException(403, "Solo administradores pueden gestionar el directorio")

    result = await db.execute(
        "DELETE FROM org_contacts WHERE id = $1 AND domain = $2",
        contact_id, domain,
    )
    if result == "DELETE 0":
        raise HTTPException(404, "Contacto no encontrado")
    return {"status": "deleted"}


@router.post("/directory/{contact_id}/copy-to-personal")
async def copy_to_personal(request: Request, contact_id: int, username: str = Depends(get_current_user)):
    """Copia un contacto del directorio a la libreta personal del usuario."""
    db = request.app.state.db_pool
    user = username
    domain = _get_domain(user)

    org = await db.fetchrow(
        "SELECT * FROM org_contacts WHERE id = $1 AND domain = $2",
        contact_id, domain,
    )
    if not org:
        raise HTTPException(404, "Contacto no encontrado en directorio")

    # Verificar si ya existe en personales
    existing = await db.fetchrow(
        "SELECT id FROM user_contacts WHERE owner=$1 AND email=$2 AND deleted_at IS NULL",
        user, org["email"],
    )
    if existing:
        return {"status": "exists", "id": existing["id"]}

    row = await db.fetchrow(
        """INSERT INTO user_contacts
            (owner, display_name, first_name, last_name, email, phone, phone_mobile,
             job_title, department, company, organization, address_street, address_city,
             address_state, address_zip, address_country, photo_url, notes, source)
           VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$10,$11,$12,$13,$14,$15,$16,$17,'directory')
           RETURNING id""",
        user, org["display_name"], org["first_name"], org["last_name"], org["email"],
        org["phone"], org["phone_mobile"], org["job_title"], org["department"],
        org["company"], org["address_street"], org["address_city"],
        org["address_state"], org["address_zip"], org["address_country"],
        org["photo_url"], org["notes"],
    )
    return {"status": "created", "id": row["id"]}
