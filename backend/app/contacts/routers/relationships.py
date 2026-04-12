"""Relaciones entre contactos."""
from fastapi import APIRouter, Request, Depends, HTTPException
from app.auth.dependencies import get_current_user
from .helpers import audit

router = APIRouter(prefix="/api/contacts", tags=["contacts"])

VALID_RELATION_TYPES = ["assistant", "manager", "spouse", "referral", "partner", "provider", "client"]

# Relaciones inversas para mostrar desde el otro lado
INVERSE_RELATIONS = {
    "assistant": "manager",
    "manager": "assistant",
    "spouse": "spouse",
    "referral": "referral",
    "partner": "partner",
    "provider": "client",
    "client": "provider",
}

RELATION_LABELS = {
    "assistant": "Asistente",
    "manager": "Gerente",
    "spouse": "Cónyuge",
    "referral": "Referido",
    "partner": "Socio",
    "provider": "Proveedor",
    "client": "Cliente",
}


@router.get("/{contact_id}/relationships")
async def get_relationships(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Obtiene relaciones de un contacto (desde ambos lados)."""
    db = request.app.state.db_pool
    exists = await db.fetchval(
        "SELECT id FROM user_contacts WHERE id=$1 AND owner=$2", contact_id, username
    )
    if not exists:
        raise HTTPException(404, "Contacto no encontrado")

    # Relaciones donde este contacto es from
    outgoing = await db.fetch(
        "SELECT cr.id, cr.relation_type, cr.to_contact_id AS related_id, "
        "uc.display_name, uc.email, uc.photo_url "
        "FROM contact_relationships cr "
        "JOIN user_contacts uc ON uc.id = cr.to_contact_id "
        "WHERE cr.from_contact_id=$1 AND cr.owner=$2",
        contact_id, username
    )

    # Relaciones donde este contacto es to (invertir tipo)
    incoming = await db.fetch(
        "SELECT cr.id, cr.relation_type, cr.from_contact_id AS related_id, "
        "uc.display_name, uc.email, uc.photo_url "
        "FROM contact_relationships cr "
        "JOIN user_contacts uc ON uc.id = cr.from_contact_id "
        "WHERE cr.to_contact_id=$1 AND cr.owner=$2",
        contact_id, username
    )

    result = []
    for r in outgoing:
        result.append({
            "id": r["id"],
            "relation_type": r["relation_type"],
            "relation_label": RELATION_LABELS.get(r["relation_type"], r["relation_type"]),
            "related_id": r["related_id"],
            "display_name": r["display_name"],
            "email": r["email"],
            "photo_url": r["photo_url"],
            "direction": "outgoing"
        })
    for r in incoming:
        inv_type = INVERSE_RELATIONS.get(r["relation_type"], r["relation_type"])
        result.append({
            "id": r["id"],
            "relation_type": inv_type,
            "relation_label": RELATION_LABELS.get(inv_type, inv_type),
            "related_id": r["related_id"],
            "display_name": r["display_name"],
            "email": r["email"],
            "photo_url": r["photo_url"],
            "direction": "incoming"
        })
    return result


@router.post("/{contact_id}/relationships")
async def add_relationship(contact_id: int, request: Request, username: str = Depends(get_current_user)):
    """Agrega una relación entre dos contactos."""
    body = await request.json()
    db = request.app.state.db_pool
    to_contact_id = body.get("to_contact_id")
    relation_type = body.get("relation_type", "").strip().lower()

    if not to_contact_id:
        raise HTTPException(400, "to_contact_id requerido")
    if contact_id == to_contact_id:
        raise HTTPException(400, "No se puede relacionar un contacto consigo mismo")
    if relation_type not in VALID_RELATION_TYPES:
        raise HTTPException(400, f"Tipo inválido. Opciones: {', '.join(VALID_RELATION_TYPES)}")

    # Verificar ambos contactos
    for cid in (contact_id, to_contact_id):
        exists = await db.fetchval(
            "SELECT id FROM user_contacts WHERE id=$1 AND owner=$2", cid, username
        )
        if not exists:
            raise HTTPException(404, f"Contacto {cid} no encontrado")

    try:
        row = await db.fetchrow(
            "INSERT INTO contact_relationships (owner, from_contact_id, to_contact_id, relation_type) "
            "VALUES ($1,$2,$3,$4) RETURNING id",
            username, contact_id, to_contact_id, relation_type
        )
    except Exception:
        raise HTTPException(409, "Esta relación ya existe")

    await audit(db, username, contact_id, "relationship_added", {
        "to_contact_id": to_contact_id, "type": relation_type
    })
    return {"status": "created", "id": row["id"]}


@router.delete("/relationships/{rel_id}")
async def delete_relationship(rel_id: int, request: Request, username: str = Depends(get_current_user)):
    """Elimina una relación."""
    db = request.app.state.db_pool
    existing = await db.fetchrow(
        "SELECT * FROM contact_relationships WHERE id=$1 AND owner=$2", rel_id, username
    )
    if not existing:
        raise HTTPException(404, "Relación no encontrada")

    await db.execute("DELETE FROM contact_relationships WHERE id=$1", rel_id)
    await audit(db, username, existing["from_contact_id"], "relationship_deleted", {
        "to_contact_id": existing["to_contact_id"], "type": existing["relation_type"]
    })
    return {"status": "deleted"}
