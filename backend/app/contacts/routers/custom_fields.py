"""Campos personalizados — definiciones y valores por contacto."""
from fastapi import APIRouter, Request, Depends, HTTPException
from app.auth.dependencies import get_current_user
from .helpers import audit

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def field_to_dict(row) -> dict:
    d = dict(row)
    if d.get("created_at"):
        d["created_at"] = d["created_at"].isoformat()
    return d


@router.get("/custom-fields")
async def list_custom_fields(request: Request, username: str = Depends(get_current_user)):
    """Lista definiciones de campos personalizados del usuario."""
    db = request.app.state.db_pool
    rows = await db.fetch(
        "SELECT * FROM contact_custom_fields WHERE owner=$1 ORDER BY field_name",
        username
    )
    return [field_to_dict(r) for r in rows]


@router.post("/custom-fields")
async def create_custom_field(request: Request, username: str = Depends(get_current_user)):
    """Crea un campo personalizado."""
    body = await request.json()
    db = request.app.state.db_pool
    field_name = body.get("field_name", "").strip()
    field_type = body.get("field_type", "text").strip()

    if not field_name:
        raise HTTPException(400, "Nombre del campo requerido")

    valid_types = ["text", "number", "date", "url", "email"]
    if field_type not in valid_types:
        raise HTTPException(400, f"Tipo inválido. Opciones: {', '.join(valid_types)}")

    try:
        row = await db.fetchrow(
            "INSERT INTO contact_custom_fields (owner, field_name, field_type) "
            "VALUES ($1,$2,$3) RETURNING *",
            username, field_name, field_type
        )
    except Exception:
        raise HTTPException(409, "Ya existe un campo con ese nombre")

    return field_to_dict(row)


@router.delete("/custom-fields/{field_id}")
async def delete_custom_field(field_id: int, request: Request, username: str = Depends(get_current_user)):
    """Elimina un campo personalizado y todos sus valores."""
    db = request.app.state.db_pool
    existing = await db.fetchval(
        "SELECT id FROM contact_custom_fields WHERE id=$1 AND owner=$2", field_id, username
    )
    if not existing:
        raise HTTPException(404, "Campo no encontrado")

    # CASCADE borrará los valores automáticamente
    await db.execute("DELETE FROM contact_custom_fields WHERE id=$1", field_id)
    return {"status": "deleted"}


@router.get("/{contact_id}/custom-values")
async def get_custom_values(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Obtiene valores de campos personalizados para un contacto."""
    db = request.app.state.db_pool
    exists = await db.fetchval(
        "SELECT id FROM user_contacts WHERE id=$1 AND owner=$2", contact_id, username
    )
    if not exists:
        raise HTTPException(404, "Contacto no encontrado")

    rows = await db.fetch(
        "SELECT cv.id, cv.field_id, cf.field_name, cf.field_type, cv.value "
        "FROM contact_custom_values cv "
        "JOIN contact_custom_fields cf ON cf.id = cv.field_id "
        "WHERE cv.contact_id=$1 AND cf.owner=$2 "
        "ORDER BY cf.field_name",
        contact_id, username
    )
    return [{"id": r["id"], "field_id": r["field_id"], "field_name": r["field_name"],
             "field_type": r["field_type"], "value": r["value"]} for r in rows]


@router.put("/{contact_id}/custom-values")
async def set_custom_values(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Establece valores de campos personalizados. Body: {field_id: value, ...}"""
    body = await request.json()
    db = request.app.state.db_pool

    exists = await db.fetchval(
        "SELECT id FROM user_contacts WHERE id=$1 AND owner=$2", contact_id, username
    )
    if not exists:
        raise HTTPException(404, "Contacto no encontrado")

    for field_id_str, value in body.items():
        try:
            field_id = int(field_id_str)
        except ValueError:
            continue

        # Verificar que el campo pertenece al usuario
        field_exists = await db.fetchval(
            "SELECT id FROM contact_custom_fields WHERE id=$1 AND owner=$2", field_id, username
        )
        if not field_exists:
            continue

        if value is None or (isinstance(value, str) and not value.strip()):
            # Borrar valor vacío
            await db.execute(
                "DELETE FROM contact_custom_values WHERE contact_id=$1 AND field_id=$2",
                contact_id, field_id
            )
        else:
            await db.execute(
                "INSERT INTO contact_custom_values (contact_id, field_id, value) "
                "VALUES ($1,$2,$3) ON CONFLICT (contact_id, field_id) DO UPDATE SET value=$3",
                contact_id, field_id, str(value)
            )

    await audit(db, username, contact_id, "custom_values_updated", {"fields": list(body.keys())})

    # Retornar valores actualizados
    rows = await db.fetch(
        "SELECT cv.id, cv.field_id, cf.field_name, cf.field_type, cv.value "
        "FROM contact_custom_values cv "
        "JOIN contact_custom_fields cf ON cf.id = cv.field_id "
        "WHERE cv.contact_id=$1 AND cf.owner=$2 "
        "ORDER BY cf.field_name",
        contact_id, username
    )
    return [{"id": r["id"], "field_id": r["field_id"], "field_name": r["field_name"],
             "field_type": r["field_type"], "value": r["value"]} for r in rows]
