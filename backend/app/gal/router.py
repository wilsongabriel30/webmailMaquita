"""GAL (Global Address List) — Directorio unificado enterprise.

Combina: mailbox + user_profiles + org_contacts + meeting_rooms + mail_groups
Reescrito: 2026-04-12
Actualizado: 2026-04-13 — Agregadas listas de distribucion (mail_groups) al directorio
"""
from __future__ import annotations

import csv
import io
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/gal", tags=["gal"])


# --- Modelos ---

class GALEntry(BaseModel):
    email: str
    display_name: str | None = None
    name: str | None = None
    title: str | None = None
    department: str | None = None
    phone: str | None = None
    mobile: str | None = None
    office_location: str | None = None
    photo_url: str | None = None
    company: str | None = None
    source: str = "mailbox"  # mailbox | directory | room | group
    active: bool = True


class GALDetailEntry(GALEntry):
    first_name: str | None = None
    last_name: str | None = None
    quota: str | None = None
    last_login: str | None = None
    notes: str | None = None


class GALListResponse(BaseModel):
    items: list[GALEntry]
    total: int
    page: int
    page_size: int


class ProfileUpdate(BaseModel):
    display_name: str | None = None
    title: str | None = None
    department: str | None = None
    phone: str | None = None
    mobile: str | None = None
    office_location: str | None = None
    photo_url: str | None = None


class StatsResponse(BaseModel):
    total_mailbox: int
    total_directory: int
    total_rooms: int
    total_groups: int = 0
    total_combined: int
    by_department: list[dict]
    active_mailbox: int


class OrgChartDepartment(BaseModel):
    department: str
    members: list[dict]


# --- Helpers ---

def _db(request: Request):
    return request.app.state.db_pool


def _get_domain(user: str) -> str:
    return user.split("@")[1] if "@" in user else user


async def _is_admin(db, user: str) -> bool:
    if user.startswith("postmaster@") or user.startswith("admin@"):
        return True
    try:
        row = await db.fetchval(
            "SELECT 1 FROM domain_admins WHERE domain=$1 AND username=$2 AND is_active=true",
            _get_domain(user), user
        )
        if row:
            return True
    except Exception:
        pass
    return False


def _row_to_entry(r, source: str = "mailbox") -> GALEntry:
    return GALEntry(
        email=r["email"],
        name=r.get("name") or r.get("display_name") or "",
        display_name=r.get("display_name") or r.get("name") or "",
        title=r.get("title") or "",
        department=r.get("department") or "",
        phone=r.get("phone") or "",
        mobile=r.get("mobile") or "",
        office_location=r.get("office_location") or r.get("location") or "",
        photo_url=r.get("photo_url") or "",
        company=r.get("company") or "",
        source=source,
        active=r.get("active", True),
    )


# --- Busqueda unificada ---

async def unified_search(db, query: str, domain: str, limit: int = 15, include_rooms: bool = True):
    results = []
    q = f"%{query}%"
    seen_emails: set[str] = set()

    # 1. Mailbox users (prioridad alta)
    mailbox_rows = await db.fetch("""
        SELECT m.username AS email, m.name, m.active,
               COALESCE(p.display_name, m.name) AS display_name,
               COALESCE(p.title, '') AS title,
               COALESCE(p.department, '') AS department,
               COALESCE(p.phone, m.phone, '') AS phone,
               COALESCE(p.mobile, '') AS mobile,
               COALESCE(p.office_location, '') AS office_location,
               COALESCE(p.photo_url, '') AS photo_url,
               '' AS company
        FROM mailbox m
        LEFT JOIN user_profiles p ON p.user_email = m.username
        WHERE m.active = true AND (
            m.username ILIKE $1 OR m.name ILIKE $1 OR
            COALESCE(p.display_name, '') ILIKE $1 OR
            COALESCE(p.department, '') ILIKE $1 OR
            COALESCE(p.title, '') ILIKE $1
        )
        ORDER BY m.name
        LIMIT $2
    """, q, limit)
    for r in mailbox_rows:
        if r["email"] not in seen_emails:
            results.append(_row_to_entry(r, "mailbox"))
            seen_emails.add(r["email"])

    # 2. Org contacts (directorio institucional)
    remaining = limit - len(results)
    if remaining > 0:
        org_rows = await db.fetch("""
            SELECT email, display_name, first_name, last_name,
                   job_title AS title, department,
                   COALESCE(phone, phone_mobile) AS phone,
                   phone_mobile AS mobile,
                   '' AS office_location,
                   photo_url, company,
                   COALESCE(display_name, first_name || ' ' || last_name) AS name,
                   true AS active
            FROM org_contacts
            WHERE domain = $3 AND (
                email ILIKE $1 OR display_name ILIKE $1 OR
                first_name ILIKE $1 OR last_name ILIKE $1 OR
                department ILIKE $1 OR job_title ILIKE $1
            )
            LIMIT $2
        """, q, remaining, domain)
        for r in org_rows:
            if r["email"] not in seen_emails:
                results.append(_row_to_entry(r, "directory"))
                seen_emails.add(r["email"])

    # 3. Meeting rooms
    if include_rooms:
        remaining = limit - len(results)
        if remaining > 0:
            room_rows = await db.fetch("""
                SELECT email, name AS display_name, name,
                       'Sala de reuniones' AS title,
                       COALESCE(location, '') AS department,
                       '' AS phone, '' AS mobile,
                       COALESCE(location, '') AS office_location,
                       '' AS photo_url, '' AS company,
                       true AS active
                FROM meeting_rooms
                WHERE is_active = true AND (
                    name ILIKE $1 OR email ILIKE $1 OR COALESCE(location, '') ILIKE $1
                )
                LIMIT $2
            """, q, remaining)
            for r in room_rows:
                if r["email"] and r["email"] not in seen_emails:
                    results.append(_row_to_entry(r, "room"))
                    seen_emails.add(r["email"])

    # 4. Listas de distribucion (mail_groups)
    remaining = limit - len(results)
    if remaining > 0:
        group_rows = await db.fetch("""
            SELECT g.address AS email, g.name AS display_name, g.name,
                   'Lista de distribucion' AS title,
                   COALESCE(g.description, '') AS department,
                   '' AS phone, '' AS mobile,
                   '' AS office_location, '' AS photo_url, '' AS company,
                   g.active,
                   (SELECT count(*) FROM mail_group_members gm WHERE gm.group_id = g.id) AS member_count
            FROM mail_groups g
            WHERE g.active = true AND (
                g.address ILIKE $1 OR g.name ILIKE $1 OR
                COALESCE(g.description, '') ILIKE $1
            )
            LIMIT $2
        """, q, remaining)
        for r in group_rows:
            if r["email"] not in seen_emails:
                results.append(_row_to_entry(r, "group"))
                seen_emails.add(r["email"])

    return results


# --- GET /api/gal --- Directorio completo paginado ---

@router.get("", response_model=GALListResponse)
async def list_gal(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str = Query("", description="Texto de busqueda"),
    department: str = Query("", description="Filtrar por departamento"),
    location: str = Query("", description="Filtrar por ubicacion"),
    active_only: bool = Query(True, description="Solo activos"),
    user: str = Depends(get_current_user),
):
    """Directorio completo paginado con filtros. Combina mailbox + org_contacts."""
    db = _db(request)
    domain = _get_domain(user)
    offset = (page - 1) * per_page
    pattern = f"%{search}%" if search else "%"

    all_items: list[GALEntry] = []

    # Build mailbox query dynamically
    where_clauses = []
    params = []
    idx = 1

    if active_only:
        where_clauses.append("m.active = true")

    if search:
        where_clauses.append(f"""(
            m.username ILIKE ${idx} OR m.name ILIKE ${idx} OR
            COALESCE(p.display_name, '') ILIKE ${idx} OR
            COALESCE(p.department, '') ILIKE ${idx} OR
            COALESCE(p.title, '') ILIKE ${idx}
        )""")
        params.append(pattern)
        idx += 1

    if department:
        where_clauses.append(f"COALESCE(p.department, '') ILIKE ${idx}")
        params.append(f"%{department}%")
        idx += 1

    if location:
        where_clauses.append(f"COALESCE(p.office_location, '') ILIKE ${idx}")
        params.append(f"%{location}%")
        idx += 1

    where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

    mb_rows = await db.fetch(f"""
        SELECT m.username AS email, m.name, m.active,
               COALESCE(p.display_name, m.name) AS display_name,
               COALESCE(p.title, '') AS title,
               COALESCE(p.department, '') AS department,
               COALESCE(p.phone, m.phone, '') AS phone,
               COALESCE(p.mobile, '') AS mobile,
               COALESCE(p.office_location, '') AS office_location,
               COALESCE(p.photo_url, '') AS photo_url,
               '' AS company
        FROM mailbox m
        LEFT JOIN user_profiles p ON p.user_email = m.username
        WHERE {where_sql}
        ORDER BY COALESCE(p.display_name, m.name)
    """, *params)
    for r in mb_rows:
        all_items.append(_row_to_entry(r, "mailbox"))

    # Org contacts
    oc_clauses = [f"domain = ${1}"]
    oc_params = [domain]
    oc_idx = 2

    if search:
        oc_clauses.append(f"""(
            email ILIKE ${oc_idx} OR display_name ILIKE ${oc_idx} OR
            first_name ILIKE ${oc_idx} OR last_name ILIKE ${oc_idx} OR
            department ILIKE ${oc_idx} OR job_title ILIKE ${oc_idx}
        )""")
        oc_params.append(pattern)
        oc_idx += 1

    if department:
        oc_clauses.append(f"department ILIKE ${oc_idx}")
        oc_params.append(f"%{department}%")
        oc_idx += 1

    oc_where = " AND ".join(oc_clauses)

    oc_rows = await db.fetch(f"""
        SELECT email, display_name,
               COALESCE(display_name, first_name || ' ' || last_name) AS name,
               job_title AS title, department,
               COALESCE(phone, phone_mobile) AS phone,
               phone_mobile AS mobile,
               '' AS office_location,
               photo_url, company, true AS active
        FROM org_contacts
        WHERE {oc_where}
        ORDER BY display_name
    """, *oc_params)

    seen = {item.email for item in all_items}
    for r in oc_rows:
        if r["email"] not in seen:
            all_items.append(_row_to_entry(r, "directory"))
            seen.add(r["email"])

    # Listas de distribucion (mail_groups)
    gr_clauses = ["g.active = true"]
    gr_params = []
    gr_idx = 1

    if search:
        gr_clauses.append(f"""(
            g.address ILIKE ${gr_idx} OR g.name ILIKE ${gr_idx} OR
            COALESCE(g.description, '') ILIKE ${gr_idx}
        )""")
        gr_params.append(pattern)
        gr_idx += 1

    gr_where = " AND ".join(gr_clauses)

    gr_rows = await db.fetch(f"""
        SELECT g.address AS email, g.name AS display_name, g.name,
               'Lista de distribucion' AS title,
               COALESCE(g.description, '') AS department,
               '' AS phone, '' AS mobile,
               '' AS office_location, '' AS photo_url, '' AS company,
               g.active
        FROM mail_groups g
        WHERE {gr_where}
        ORDER BY g.name
    """, *gr_params)

    for r in gr_rows:
        if r["email"] not in seen:
            all_items.append(_row_to_entry(r, "group"))
            seen.add(r["email"])

    total = len(all_items)
    page_items = all_items[offset:offset + per_page]
    return GALListResponse(items=page_items, total=total, page=page, page_size=per_page)


# --- GET /api/gal/search --- Busqueda rapida unificada ---

@router.get("/search")
async def search_gal(
    request: Request,
    q: str = Query(..., min_length=2, description="Texto de busqueda (min 2 caracteres)"),
    limit: int = Query(15, ge=1, le=50),
    include_rooms: bool = Query(True),
    user: str = Depends(get_current_user),
):
    """Busqueda rapida unificada para autocomplete y directorio."""
    db = _db(request)
    domain = _get_domain(user)
    results = await unified_search(db, q, domain, limit, include_rooms)
    return {"results": [r.model_dump() for r in results], "total": len(results)}


# --- GET /api/gal/departments --- Lista departamentos ---

@router.get("/departments")
async def list_departments(
    request: Request,
    user: str = Depends(get_current_user),
):
    """Lista de departamentos unicos (para filtros)."""
    db = _db(request)
    domain = _get_domain(user)
    departments: set[str] = set()

    # De user_profiles
    rows = await db.fetch(
        "SELECT DISTINCT department FROM user_profiles WHERE department IS NOT NULL AND department != ''"
    )
    for r in rows:
        departments.add(r["department"])

    # De org_contacts
    rows = await db.fetch(
        "SELECT DISTINCT department FROM org_contacts WHERE domain = $1 AND department != ''",
        domain
    )
    for r in rows:
        departments.add(r["department"])

    return sorted(departments)


# --- GET /api/gal/org-chart --- Arbol organizacional ---

@router.get("/org-chart")
async def org_chart(
    request: Request,
    user: str = Depends(get_current_user),
):
    """Arbol organizacional: departamentos con sus miembros."""
    db = _db(request)
    domain = _get_domain(user)
    dept_map: dict[str, list] = {}

    # Mailbox users con perfil
    rows = await db.fetch("""
        SELECT m.username AS email, COALESCE(p.display_name, m.name) AS name,
               COALESCE(p.title, '') AS title,
               COALESCE(p.department, 'Sin departamento') AS department
        FROM mailbox m
        LEFT JOIN user_profiles p ON p.user_email = m.username
        WHERE m.active = true
        ORDER BY department, name
    """)
    for r in rows:
        dept = r["department"] or "Sin departamento"
        dept_map.setdefault(dept, []).append({
            "email": r["email"], "name": r["name"], "title": r["title"], "source": "mailbox"
        })

    # Org contacts
    rows = await db.fetch("""
        SELECT email, COALESCE(display_name, first_name || ' ' || last_name) AS name,
               job_title AS title,
               COALESCE(department, 'Sin departamento') AS department
        FROM org_contacts WHERE domain = $1
        ORDER BY department, display_name
    """, domain)
    seen: set[str] = set()
    for r in rows:
        if r["email"] not in seen:
            dept = r["department"] or "Sin departamento"
            dept_map.setdefault(dept, []).append({
                "email": r["email"], "name": r["name"], "title": r["title"], "source": "directory"
            })
            seen.add(r["email"])

    result = [
        {"department": dept, "members": members}
        for dept, members in sorted(dept_map.items())
    ]
    return result


# --- GET /api/gal/stats --- Estadisticas ---

@router.get("/stats", response_model=StatsResponse)
async def gal_stats(
    request: Request,
    user: str = Depends(get_current_user),
):
    """Estadisticas del directorio."""
    db = _db(request)
    domain = _get_domain(user)

    total_mb = await db.fetchval("SELECT COUNT(*) FROM mailbox")
    active_mb = await db.fetchval("SELECT COUNT(*) FROM mailbox WHERE active = true")
    total_dir = await db.fetchval("SELECT COUNT(*) FROM org_contacts WHERE domain = $1", domain)
    total_rooms = await db.fetchval("SELECT COUNT(*) FROM meeting_rooms WHERE is_active = true")
    total_groups = await db.fetchval("SELECT COUNT(*) FROM mail_groups WHERE active = true")

    # Por departamento
    dept_rows = await db.fetch("""
        SELECT COALESCE(p.department, 'Sin departamento') AS department, COUNT(*) AS count
        FROM mailbox m LEFT JOIN user_profiles p ON p.user_email = m.username
        WHERE m.active = true
        GROUP BY COALESCE(p.department, 'Sin departamento')
        ORDER BY count DESC
    """)
    by_dept = [{"department": r["department"], "count": r["count"]} for r in dept_rows]

    return StatsResponse(
        total_mailbox=total_mb,
        total_directory=total_dir,
        total_rooms=total_rooms,
        total_groups=total_groups,
        total_combined=total_mb + total_dir + total_rooms + total_groups,
        by_department=by_dept,
        active_mailbox=active_mb,
    )


# --- GET /api/gal/export --- Exportar directorio ---

@router.get("/export")
async def export_gal(
    request: Request,
    format: str = Query("csv", description="csv o vcard"),
    user: str = Depends(get_current_user),
):
    """Exportar directorio completo como CSV o vCard."""
    db = _db(request)
    domain = _get_domain(user)

    mb_rows = await db.fetch("""
        SELECT m.username AS email, COALESCE(p.display_name, m.name) AS display_name,
               COALESCE(p.title, '') AS title, COALESCE(p.department, '') AS department,
               COALESCE(p.phone, m.phone, '') AS phone, COALESCE(p.mobile, '') AS mobile,
               COALESCE(p.office_location, '') AS office_location, 'mailbox' AS source
        FROM mailbox m LEFT JOIN user_profiles p ON p.user_email = m.username
        WHERE m.active = true ORDER BY display_name
    """)
    oc_rows = await db.fetch("""
        SELECT email, display_name, job_title AS title, department,
               COALESCE(phone, '') AS phone, COALESCE(phone_mobile, '') AS mobile,
               '' AS office_location, 'directory' AS source
        FROM org_contacts WHERE domain = $1 ORDER BY display_name
    """, domain)

    gr_rows = await db.fetch("""
        SELECT address AS email, name AS display_name,
               'Lista de distribucion' AS title,
               COALESCE(description, '') AS department,
               '' AS phone, '' AS mobile,
               '' AS office_location, 'group' AS source
        FROM mail_groups WHERE active = true ORDER BY name
    """)

    all_rows = list(mb_rows) + list(oc_rows) + list(gr_rows)

    if format == "vcard":
        vcards = []
        for r in all_rows:
            vcard = (
                "BEGIN:VCARD\n"
                "VERSION:3.0\n"
                f"FN:{r['display_name']}\n"
                f"EMAIL:{r['email']}\n"
                f"TITLE:{r['title']}\n"
                f"ORG:{r.get('department', '')}\n"
                f"TEL;TYPE=WORK:{r['phone']}\n"
                f"TEL;TYPE=CELL:{r['mobile']}\n"
                "END:VCARD"
            )
            vcards.append(vcard)
        content = "\n".join(vcards)
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="text/vcard",
            headers={"Content-Disposition": "attachment; filename=directorio.vcf"}
        )
    else:
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Email", "Nombre", "Cargo", "Departamento", "Telefono", "Movil", "Ubicacion", "Fuente"])
        for r in all_rows:
            writer.writerow([r["email"], r["display_name"], r["title"], r["department"],
                             r["phone"], r["mobile"], r.get("office_location", ""), r["source"]])
        content = output.getvalue()
        return StreamingResponse(
            io.BytesIO(content.encode("utf-8")),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=directorio.csv"}
        )


# --- GET /api/gal/{email} --- Perfil detallado ---

@router.get("/{email}")
async def get_user_detail(
    email: str,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Perfil detallado de un usuario/contacto del directorio."""
    db = _db(request)
    domain = _get_domain(user)

    # Try mailbox first
    row = await db.fetchrow("""
        SELECT m.username AS email, m.name, m.active, m.phone,
               m.quota, m.modified AS last_login,
               p.display_name, p.title, p.department, p.mobile,
               p.office_location, p.photo_url
        FROM mailbox m
        LEFT JOIN user_profiles p ON p.user_email = m.username
        WHERE m.username = $1
    """, email)
    if row:
        return GALDetailEntry(
            email=row["email"],
            name=row["name"],
            display_name=row["display_name"] or row["name"],
            title=row["title"] or "",
            department=row["department"] or "",
            phone=row["phone"] or "",
            mobile=row["mobile"] or "",
            office_location=row["office_location"] or "",
            photo_url=row["photo_url"] or "",
            source="mailbox",
            active=row["active"],
            quota=str(row["quota"]) if row["quota"] else "",
            last_login=str(row["last_login"]) if row["last_login"] else "",
        )

    # Try org_contacts
    row = await db.fetchrow(
        "SELECT * FROM org_contacts WHERE email = $1 AND domain = $2",
        email, domain
    )
    if row:
        return GALDetailEntry(
            email=row["email"],
            name=row["display_name"],
            display_name=row["display_name"],
            first_name=row["first_name"],
            last_name=row["last_name"],
            title=row["job_title"] or "",
            department=row["department"] or "",
            phone=row["phone"] or "",
            mobile=row["phone_mobile"] or "",
            company=row["company"] or "",
            photo_url=row["photo_url"] or "",
            notes=row["notes"] or "",
            source="directory",
        )

    # Try meeting rooms
    row = await db.fetchrow("SELECT * FROM meeting_rooms WHERE email = $1", email)
    if row:
        return GALDetailEntry(
            email=row["email"],
            name=row["name"],
            display_name=row["name"],
            title="Sala de reuniones",
            office_location=row["location"] or "",
            source="room",
        )

    # Try mail_groups (listas de distribucion)
    row = await db.fetchrow("""
        SELECT g.address AS email, g.name, g.description, g.active, g.domain,
               (SELECT count(*) FROM mail_group_members gm WHERE gm.group_id = g.id) AS member_count
        FROM mail_groups g WHERE g.address = $1
    """, email)
    if row:
        return GALDetailEntry(
            email=row["email"],
            name=row["name"],
            display_name=row["name"],
            title="Lista de distribucion",
            department=row["description"] or "",
            notes=f"Miembros: {row['member_count']}",
            source="group",
            active=row["active"],
        )

    raise HTTPException(status_code=404, detail="Entrada no encontrada en el directorio")


# --- PUT /api/gal/{email}/profile --- Actualizar perfil ---

@router.put("/{email}/profile")
async def update_profile(
    email: str,
    body: ProfileUpdate,
    request: Request,
    user: str = Depends(get_current_user),
):
    """Actualizar perfil propio (o admin puede editar cualquiera)."""
    db = _db(request)

    if user != email and not await _is_admin(db, user):
        raise HTTPException(403, "Solo puedes editar tu propio perfil")

    exists = await db.fetchval("SELECT 1 FROM mailbox WHERE username = $1", email)
    if not exists:
        raise HTTPException(404, "Usuario no encontrado")

    row = await db.fetchrow("""
        INSERT INTO user_profiles (user_email, display_name, title, department, phone, mobile, office_location, photo_url)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (user_email) DO UPDATE SET
            display_name = COALESCE(NULLIF($2, ''), user_profiles.display_name),
            title = COALESCE(NULLIF($3, ''), user_profiles.title),
            department = COALESCE(NULLIF($4, ''), user_profiles.department),
            phone = COALESCE(NULLIF($5, ''), user_profiles.phone),
            mobile = COALESCE(NULLIF($6, ''), user_profiles.mobile),
            office_location = COALESCE(NULLIF($7, ''), user_profiles.office_location),
            photo_url = COALESCE(NULLIF($8, ''), user_profiles.photo_url),
            updated_at = NOW()
        RETURNING *
    """, email,
        body.display_name or "",
        body.title or "",
        body.department or "",
        body.phone or "",
        body.mobile or "",
        body.office_location or "",
        body.photo_url or "",
    )
    return {"status": "updated", "profile": dict(row)}


# --- POST /api/gal/bulk-update --- Actualizacion masiva (admin) ---

@router.post("/bulk-update")
async def bulk_update(
    request: Request,
    user: str = Depends(get_current_user),
):
    """Actualizacion masiva de perfiles (admin). Acepta JSON array."""
    db = _db(request)
    if not await _is_admin(db, user):
        raise HTTPException(403, "Solo administradores pueden hacer actualizaciones masivas")

    body = await request.json()
    if not isinstance(body, list):
        raise HTTPException(422, "Se espera un JSON array de objetos con campo email")

    updated = 0
    errors = []
    for entry in body:
        email = entry.get("email")
        if not email:
            errors.append({"error": "Falta campo email", "entry": entry})
            continue
        try:
            await db.execute("""
                INSERT INTO user_profiles (user_email, display_name, title, department, phone, mobile, office_location)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (user_email) DO UPDATE SET
                    display_name = COALESCE(NULLIF($2, ''), user_profiles.display_name),
                    title = COALESCE(NULLIF($3, ''), user_profiles.title),
                    department = COALESCE(NULLIF($4, ''), user_profiles.department),
                    phone = COALESCE(NULLIF($5, ''), user_profiles.phone),
                    mobile = COALESCE(NULLIF($6, ''), user_profiles.mobile),
                    office_location = COALESCE(NULLIF($7, ''), user_profiles.office_location),
                    updated_at = NOW()
            """, email,
                entry.get("display_name", ""),
                entry.get("title", ""),
                entry.get("department", ""),
                entry.get("phone", ""),
                entry.get("mobile", ""),
                entry.get("office_location", ""),
            )
            updated += 1
        except Exception as e:
            errors.append({"email": email, "error": str(e)})

    return {"updated": updated, "errors": errors}
