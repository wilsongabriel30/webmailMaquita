import json
import re
from fastapi import APIRouter, Request, HTTPException, Depends, Query
from app.auth.dependencies import get_current_admin, require_role

router = APIRouter(prefix="/api/groups", tags=["groups"])

# Dominios internos de la organización
INTERNAL_DOMAINS = {"maquita.com.ec", "mcch.com.ec", "fundmcch.com.ec", "maquitaturismo.com"}


def _db(r: Request):
    return r.app.state.db


def _is_internal(email: str) -> bool:
    """Verifica si un email pertenece a un dominio interno."""
    if "@" not in email:
        return False
    domain = email.split("@")[1].lower()
    return domain in INTERNAL_DOMAINS


async def _audit(r, a, action, target=None, details=None):
    await _db(r).execute(
        "INSERT INTO admin_audit (admin_id, admin_username, action, target, details, ip_address) VALUES ($1,$2,$3,$4,$5::jsonb,$6)",
        a["id"], a["username"], action, target, json.dumps(details) if details else None,
        r.headers.get("X-Real-IP", r.client.host if r.client else ""))


async def _ensure_tables(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS mail_groups (
            id SERIAL PRIMARY KEY,
            address VARCHAR(255) UNIQUE NOT NULL,
            name VARCHAR(255) NOT NULL DEFAULT '',
            description TEXT DEFAULT '',
            domain VARCHAR(255) NOT NULL,
            active BOOLEAN DEFAULT true,
            allow_external BOOLEAN DEFAULT false,
            allowed_senders TEXT DEFAULT '',
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS mail_group_members (
            id SERIAL PRIMARY KEY,
            group_id INT REFERENCES mail_groups(id) ON DELETE CASCADE,
            member_email VARCHAR(255) NOT NULL,
            member_name VARCHAR(255) DEFAULT '',
            can_send BOOLEAN DEFAULT true,
            receive BOOLEAN DEFAULT true,
            added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            UNIQUE(group_id, member_email)
        );
    """)


async def _get_member_analysis(db, group_id: int):
    """Analiza miembros de un grupo: externos, grupos anidados, etc."""
    members = await db.fetch(
        "SELECT m.*, (SELECT g.id FROM mail_groups g WHERE g.address = m.member_email) as is_group "
        "FROM mail_group_members m WHERE m.group_id = $1 ORDER BY m.member_email", group_id)

    external_members = []
    nested_groups = []
    internal_members = []

    for m in members:
        md = dict(m)
        email = md["member_email"]
        if md.get("is_group"):
            md["member_type"] = "group"
            nested_groups.append(md)
        elif not _is_internal(email):
            md["member_type"] = "external"
            external_members.append(md)
        else:
            md["member_type"] = "internal"
            internal_members.append(md)

    return {
        "members": [dict(m) for m in members],
        "external_count": len(external_members),
        "nested_group_count": len(nested_groups),
        "internal_count": len(internal_members),
        "external_members": [m["member_email"] for m in external_members],
        "nested_groups": [m["member_email"] for m in nested_groups],
        "all_enriched": internal_members + external_members + nested_groups,
    }


@router.get("")
async def list_groups(request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    await _ensure_tables(db)
    rows = await db.fetch("""
        SELECT g.*,
            (SELECT count(*) FROM mail_group_members m WHERE m.group_id = g.id) as member_count,
            (SELECT count(*) FROM mail_group_members m WHERE m.group_id = g.id
             AND m.member_email IN (SELECT address FROM mail_groups)) as nested_group_count,
            (SELECT count(*) FROM mail_group_members m WHERE m.group_id = g.id
             AND m.member_email NOT IN (SELECT address FROM mail_groups)
             AND split_part(m.member_email, '@', 2) NOT IN ('maquita.com.ec','mcch.com.ec','fundmcch.com.ec','maquitaturismo.com')
            ) as external_count
        FROM mail_groups g ORDER BY g.domain, g.address
    """)
    return [dict(r) for r in rows]


@router.get("/by-member")
async def groups_by_member(
    email: str = Query(..., min_length=3),
    request: Request = None,
    admin: dict = Depends(get_current_admin),
):
    """Retorna todos los grupos a los que pertenece un email."""
    db = _db(request)
    await _ensure_tables(db)
    rows = await db.fetch("""
        SELECT g.id, g.address, g.name, g.active, g.allow_external,
               m.can_send, m.receive, m.added_at
        FROM mail_groups g
        JOIN mail_group_members m ON m.group_id = g.id
        WHERE LOWER(m.member_email) = $1
        ORDER BY g.address
    """, email.strip().lower())
    return [dict(r) for r in rows]


@router.get("/audit")
async def audit_groups(request: Request, admin: dict = Depends(get_current_admin)):
    """Auditoría completa: grupos con miembros externos o grupos anidados."""
    db = _db(request)
    await _ensure_tables(db)

    # Grupos con miembros externos
    external_issues = await db.fetch("""
        SELECT g.id, g.address, g.name, g.allow_external,
               m.member_email, m.member_name
        FROM mail_groups g
        JOIN mail_group_members m ON m.group_id = g.id
        WHERE split_part(m.member_email, '@', 2) NOT IN ('maquita.com.ec','mcch.com.ec','fundmcch.com.ec','maquitaturismo.com')
        AND m.member_email NOT IN (SELECT address FROM mail_groups)
        ORDER BY g.address, m.member_email
    """)

    # Grupos anidados
    nested_issues = await db.fetch("""
        SELECT g.id as parent_id, g.address as parent_address, g.name as parent_name,
               m.member_email as nested_address,
               ng.name as nested_name,
               (SELECT count(*) FROM mail_group_members nm WHERE nm.group_id = ng.id) as nested_member_count
        FROM mail_groups g
        JOIN mail_group_members m ON m.group_id = g.id
        JOIN mail_groups ng ON ng.address = m.member_email
        ORDER BY g.address, m.member_email
    """)

    return {
        "external_issues": [dict(r) for r in external_issues],
        "nested_issues": [dict(r) for r in nested_issues],
        "total_external": len(external_issues),
        "total_nested": len(nested_issues),
        "groups_with_external": len(set(r["address"] for r in external_issues)),
        "groups_with_nested": len(set(r["parent_address"] for r in nested_issues)),
    }


@router.get("/{group_id}")
async def get_group(group_id: int, request: Request, admin: dict = Depends(get_current_admin)):
    db = _db(request)
    await _ensure_tables(db)
    group = await db.fetchrow("SELECT * FROM mail_groups WHERE id = $1", group_id)
    if not group:
        raise HTTPException(404, "Grupo no encontrado")

    analysis = await _get_member_analysis(db, group_id)

    # Enriquecer miembros con tipo
    enriched = []
    group_addresses = set(r["address"] for r in await db.fetch("SELECT address FROM mail_groups"))
    for m in analysis["members"]:
        md = dict(m)
        email = md["member_email"]
        if email in group_addresses:
            md["member_type"] = "group"
        elif not _is_internal(email):
            md["member_type"] = "external"
        else:
            md["member_type"] = "internal"
        # Limpiar campo is_group del query
        md.pop("is_group", None)
        enriched.append(md)

    warnings = []
    if analysis["external_count"] > 0:
        warnings.append({
            "type": "external_members",
            "severity": "high",
            "message": f"Este grupo tiene {analysis['external_count']} miembro(s) externo(s). "
                       f"Los correos enviados a este grupo llegarán a direcciones fuera de la organización.",
            "emails": analysis["external_members"],
        })
    if analysis["nested_group_count"] > 0:
        warnings.append({
            "type": "nested_groups",
            "severity": "medium",
            "message": f"Este grupo contiene {analysis['nested_group_count']} subgrupo(s) anidado(s). "
                       f"Los correos se expandirán recursivamente a todos los miembros de esos subgrupos.",
            "groups": analysis["nested_groups"],
        })

    return {
        "group": dict(group),
        "members": enriched,
        "warnings": warnings,
        "stats": {
            "total": len(enriched),
            "internal": analysis["internal_count"],
            "external": analysis["external_count"],
            "nested_groups": analysis["nested_group_count"],
        },
    }


@router.post("", status_code=201)
async def create_group(request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    address = data.get("address", "").strip().lower()
    name = data.get("name", "")
    description = data.get("description", "")
    allow_external = data.get("allow_external", False)
    allowed_senders = data.get("allowed_senders", "")

    if not address or "@" not in address:
        raise HTTPException(400, "Direccion en formato grupo@dominio requerida")

    domain = address.split("@")[1]
    db = _db(request)
    await _ensure_tables(db)

    try:
        row = await db.fetchrow("""
            INSERT INTO mail_groups (address, name, description, domain, allow_external, allowed_senders)
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING *
        """, address, name, description, domain, allow_external, allowed_senders)
    except Exception as e:
        raise HTTPException(400, f"Error al crear grupo: {e}")

    await _audit(request, admin, "group_create", address, {"name": name})
    return dict(row)


@router.put("/{group_id}")
async def update_group(group_id: int, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    db = _db(request)
    cur = await db.fetchrow("SELECT * FROM mail_groups WHERE id = $1", group_id)
    if not cur:
        raise HTTPException(404)

    new_allow_external = data.get("allow_external", cur["allow_external"])

    # Si se está desactivando allow_external, verificar que no haya externos
    if not new_allow_external and cur["allow_external"]:
        ext_count = await db.fetchval("""
            SELECT count(*) FROM mail_group_members m WHERE m.group_id = $1
            AND split_part(m.member_email, '@', 2) NOT IN ('maquita.com.ec','mcch.com.ec','fundmcch.com.ec','maquitaturismo.com')
            AND m.member_email NOT IN (SELECT address FROM mail_groups)
        """, group_id)
        if ext_count > 0:
            raise HTTPException(400,
                f"No se puede desactivar 'permitir externos' porque el grupo tiene {ext_count} miembro(s) externo(s). "
                f"Elimínelos primero.")

    row = await db.fetchrow("""
        UPDATE mail_groups SET name=$2, description=$3, active=$4, allow_external=$5,
            allowed_senders=$6, modified_at=NOW()
        WHERE id=$1 RETURNING *
    """, group_id,
        data.get("name", cur["name"]),
        data.get("description", cur["description"]),
        data.get("active", cur["active"]),
        new_allow_external,
        data.get("allowed_senders", cur["allowed_senders"]))

    await _sync_group_alias(db, cur["address"], group_id)
    await _audit(request, admin, "group_update", cur["address"], data)
    return dict(row)


@router.delete("/{group_id}")
async def delete_group(group_id: int, request: Request, admin: dict = Depends(require_role("superadmin"))):
    db = _db(request)
    group = await db.fetchrow("SELECT address FROM mail_groups WHERE id = $1", group_id)
    if not group:
        raise HTTPException(404)

    await db.execute("DELETE FROM alias WHERE address = $1", group["address"])
    await db.execute("DELETE FROM mail_groups WHERE id = $1", group_id)
    await _audit(request, admin, "group_delete", group["address"])
    return {"ok": True}


# ── Members ──

@router.post("/{group_id}/members")
async def add_member(group_id: int, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    email = data.get("email", "").strip().lower()
    name = data.get("name", "")
    can_send = data.get("can_send", True)
    receive = data.get("receive", True)
    force = data.get("force", False)  # Para confirmar adición de externos/grupos

    if not email:
        raise HTTPException(400, "Email requerido")

    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+$', email):
        raise HTTPException(400, "Formato de email inválido")

    db = _db(request)
    group = await db.fetchrow("SELECT * FROM mail_groups WHERE id = $1", group_id)
    if not group:
        raise HTTPException(404, "Grupo no encontrado")

    # Detectar si es un grupo anidado
    is_nested_group = await db.fetchval(
        "SELECT id FROM mail_groups WHERE address = $1", email)
    if is_nested_group and not force:
        # Contar miembros del subgrupo para informar
        sub_count = await db.fetchval(
            "SELECT count(*) FROM mail_group_members WHERE group_id = $1", is_nested_group)
        raise HTTPException(409, {
            "type": "nested_group_warning",
            "message": f"'{email}' es un grupo de distribución con {sub_count} miembros. "
                       f"Al agregarlo, todos los correos enviados a '{group['address']}' "
                       f"se expandirán recursivamente a esos {sub_count} miembros. "
                       f"¿Está seguro?",
            "sub_count": sub_count,
            "requires_confirmation": True,
        })

    # Detectar si es externo
    is_external = not _is_internal(email)
    if is_external:
        if not group["allow_external"]:
            raise HTTPException(403, {
                "type": "external_blocked",
                "message": f"El grupo '{group['address']}' no permite miembros externos. "
                           f"'{email}' no pertenece a los dominios internos "
                           f"({', '.join(sorted(INTERNAL_DOMAINS))}). "
                           f"Para agregar miembros externos, primero active la opción "
                           f"'Permitir miembros externos' en la configuración del grupo.",
            })
        if not force:
            raise HTTPException(409, {
                "type": "external_warning",
                "message": f"'{email}' es una dirección EXTERNA a la organización. "
                           f"Los correos enviados a '{group['address']}' llegarán a esta "
                           f"persona fuera de Maquita. ¿Está seguro?",
                "requires_confirmation": True,
            })

    try:
        row = await db.fetchrow("""
            INSERT INTO mail_group_members (group_id, member_email, member_name, can_send, receive)
            VALUES ($1, $2, $3, $4, $5) RETURNING *
        """, group_id, email, name, can_send, receive)
    except Exception:
        raise HTTPException(409, "El miembro ya existe en este grupo")

    # Enriquecer respuesta con tipo
    result = dict(row)
    if is_nested_group:
        result["member_type"] = "group"
    elif is_external:
        result["member_type"] = "external"
    else:
        result["member_type"] = "internal"

    await _sync_group_alias(db, group["address"], group_id)

    detail = {"member": email}
    if is_external:
        detail["warning"] = "MIEMBRO EXTERNO agregado"
    if is_nested_group:
        detail["warning"] = "GRUPO ANIDADO agregado"
    await _audit(request, admin, "group_member_add", group["address"], detail)

    return result


@router.put("/{group_id}/members/{member_id}")
async def update_member(group_id: int, member_id: int, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    data = await request.json()
    db = _db(request)
    await db.execute("""
        UPDATE mail_group_members SET can_send=$3, receive=$4
        WHERE id=$1 AND group_id=$2
    """, member_id, group_id, data.get("can_send", True), data.get("receive", True))

    group = await db.fetchrow("SELECT address FROM mail_groups WHERE id = $1", group_id)
    if group:
        await _sync_group_alias(db, group["address"], group_id)
    return {"ok": True}


@router.delete("/{group_id}/members/{member_id}")
async def remove_member(group_id: int, member_id: int, request: Request, admin: dict = Depends(require_role("superadmin", "admin"))):
    db = _db(request)
    member = await db.fetchrow("SELECT member_email FROM mail_group_members WHERE id=$1 AND group_id=$2", member_id, group_id)
    if not member:
        raise HTTPException(404)

    await db.execute("DELETE FROM mail_group_members WHERE id=$1 AND group_id=$2", member_id, group_id)

    group = await db.fetchrow("SELECT address FROM mail_groups WHERE id = $1", group_id)
    if group:
        await _sync_group_alias(db, group["address"], group_id)
        await _audit(request, admin, "group_member_remove", group["address"], {"member": member["member_email"]})
    return {"ok": True}


async def _sync_group_alias(db, group_address: str, group_id: int):
    """Sync group members to Postfix alias table for actual mail delivery."""
    members = await db.fetch(
        "SELECT member_email FROM mail_group_members WHERE group_id=$1 AND receive=true", group_id)
    if not members:
        await db.execute("DELETE FROM alias WHERE address=$1", group_address)
        return

    goto = ",".join(m["member_email"] for m in members)
    domain = group_address.split("@")[1]

    existing = await db.fetchrow("SELECT * FROM alias WHERE address=$1", group_address)
    if existing:
        await db.execute("UPDATE alias SET goto=$2, modified=NOW() WHERE address=$1", group_address, goto)
    else:
        await db.execute(
            "INSERT INTO alias (address, goto, domain, active) VALUES ($1,$2,$3,true)",
            group_address, goto, domain)
