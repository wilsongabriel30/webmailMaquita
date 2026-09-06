"""Duplicados — detección y merge de contactos duplicados."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user

from .helpers import ALL_FIELDS, audit, enrich_contact, row_to_dict

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


@router.get("/duplicates")
async def find_duplicates(request: Request, username: str = Depends(get_current_user)):
    """Encuentra posibles contactos duplicados agrupados."""
    db = request.app.state.db_pool
    # Buscar contactos activos del usuario
    rows = await db.fetch(
        f"SELECT {ALL_FIELDS} FROM user_contacts WHERE owner=$1 AND deleted_at IS NULL ORDER BY display_name",
        username,
    )
    contacts = [row_to_dict(r) for r in rows]

    # Agrupar por dominio de email + primeros 3 chars de nombre
    groups_map = {}
    for c in contacts:
        email = (c.get("email") or "").strip().lower()
        if "@" not in email:
            continue
        domain = email.split("@")[1]
        fn = (c.get("first_name") or "").strip().lower()[:3]
        ln = (c.get("last_name") or "").strip().lower()[:3]
        dn = (c.get("display_name") or "").strip().lower()[:3]
        # Clave: dominio + prefijo del nombre
        key = f"{domain}|{fn or dn}|{ln}"
        if key not in groups_map:
            groups_map[key] = []
        groups_map[key].append(c)

    # También buscar emails exactamente iguales
    email_map = {}
    for c in contacts:
        email = (c.get("email") or "").strip().lower()
        if email:
            if email not in email_map:
                email_map[email] = []
            email_map[email].append(c)

    # Combinar: solo grupos con 2+ contactos
    seen_ids = set()
    result = []

    # Primero emails exactos (mayor prioridad)
    for email, group in email_map.items():
        if len(group) >= 2:
            ids = tuple(sorted(c["id"] for c in group))
            if ids not in seen_ids:
                seen_ids.add(ids)
                result.append({"reason": f"Email idéntico: {email}", "contacts": group})

    # Luego por dominio+nombre
    for key, group in groups_map.items():
        if len(group) >= 2:
            ids = tuple(sorted(c["id"] for c in group))
            if ids not in seen_ids:
                seen_ids.add(ids)
                domain = key.split("|")[0]
                result.append(
                    {"reason": f"Nombre similar en @{domain}", "contacts": group}
                )

    return result


@router.post("/merge")
async def merge_contacts(request: Request, username: str = Depends(get_current_user)):
    """Fusiona dos contactos. Mantiene keep_id, soft-deletes merge_id."""
    body = await request.json()
    db = request.app.state.db_pool
    keep_id = body.get("keep_id")
    merge_id = body.get("merge_id")

    if not keep_id or not merge_id or keep_id == merge_id:
        raise HTTPException(400, "Se requieren keep_id y merge_id distintos")

    # Verificar que ambos pertenecen al usuario
    keep = await db.fetchrow(
        f"SELECT {ALL_FIELDS} FROM user_contacts WHERE id=$1 AND owner=$2 AND deleted_at IS NULL",
        keep_id,
        username,
    )
    merge = await db.fetchrow(
        f"SELECT {ALL_FIELDS} FROM user_contacts WHERE id=$1 AND owner=$2 AND deleted_at IS NULL",
        merge_id,
        username,
    )
    if not keep or not merge:
        raise HTTPException(404, "Contacto no encontrado")

    # Copiar campos vacíos de merge a keep
    fillable = [
        "first_name",
        "last_name",
        "nickname",
        "email",
        "email2",
        "email3",
        "phone",
        "phone_mobile",
        "phone_work",
        "phone_home",
        "fax",
        "organization",
        "company",
        "job_title",
        "department",
        "address_street",
        "address_city",
        "address_state",
        "address_zip",
        "address_country",
        "birthday",
        "website",
        "im_address",
        "photo_url",
        "notes",
    ]
    updates = []
    values = [keep_id]
    idx = 2
    for field in fillable:
        keep_val = keep[field]
        merge_val = merge[field]
        if (
            not keep_val or (isinstance(keep_val, str) and not keep_val.strip())
        ) and merge_val:
            updates.append(f"{field}=${idx}")
            values.append(merge_val)
            idx += 1

    if updates:
        await db.execute(
            f"UPDATE user_contacts SET {', '.join(updates)}, updated_at=NOW() WHERE id=$1",
            *values,
        )

    # Transferir categorías
    await db.execute(
        "INSERT INTO contact_category_assignments (contact_id, category_id) "
        "SELECT $1, category_id FROM contact_category_assignments WHERE contact_id=$2 "
        "ON CONFLICT DO NOTHING",
        keep_id,
        merge_id,
    )

    # Transferir membresías de listas
    await db.execute(
        "INSERT INTO contact_list_members (list_id, contact_id) "
        "SELECT list_id, $1 FROM contact_list_members WHERE contact_id=$2 "
        "ON CONFLICT DO NOTHING",
        keep_id,
        merge_id,
    )

    # Transferir reminders
    await db.execute(
        "UPDATE contact_reminders SET contact_id=$1 WHERE contact_id=$2",
        keep_id,
        merge_id,
    )

    # Transferir custom values (sin duplicar)
    await db.execute(
        "INSERT INTO contact_custom_values (contact_id, field_id, value) "
        "SELECT $1, field_id, value FROM contact_custom_values WHERE contact_id=$2 "
        "ON CONFLICT (contact_id, field_id) DO NOTHING",
        keep_id,
        merge_id,
    )

    # Transferir relationships
    await db.execute(
        "UPDATE contact_relationships SET from_contact_id=$1 WHERE from_contact_id=$2",
        keep_id,
        merge_id,
    )
    await db.execute(
        "UPDATE contact_relationships SET to_contact_id=$1 WHERE to_contact_id=$2",
        keep_id,
        merge_id,
    )

    # Soft-delete merge_id
    await db.execute(
        "UPDATE user_contacts SET deleted_at=NOW(), updated_at=NOW() WHERE id=$1",
        merge_id,
    )

    # Audit
    await audit(db, username, keep_id, "merge", {"merged_from": merge_id})
    await audit(db, username, merge_id, "merged_into", {"merged_into": keep_id})

    # Retornar contacto actualizado
    updated = await db.fetchrow(
        f"SELECT {ALL_FIELDS} FROM user_contacts WHERE id=$1", keep_id
    )
    return {"status": "merged", "contact": await enrich_contact(db, updated)}
