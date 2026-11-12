"""Crear contacto desde un correo recibido."""

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.contacts.services import alta_rapida

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


async def _poner_nombre(
    db, username: str, contacto_id: int, email: str, nombre: str
) -> None:
    nombre_pila, apellido = alta_rapida.partir(nombre)
    await db.execute(
        "UPDATE user_contacts SET display_name = $1, first_name = $2, last_name = $3, updated_at = now() "
        "WHERE id = $4 AND owner = $5",
        nombre,
        nombre_pila,
        apellido,
        contacto_id,
        username,
    )
    # El autocompletado al escribir un correo sale de los destinatarios recientes: mismo nombre allí.
    await db.execute(
        "UPDATE sent_recipients SET recipient_name = $1 WHERE sender = $2 AND LOWER(recipient_email) = LOWER($3)",
        nombre,
        username,
        email,
    )


@router.post("/from-email")
async def create_from_email(
    request: Request, username: str = Depends(get_current_user)
):
    """
    Crea contacto rápido desde MessageView. Body: {name, email, actualizar?}.

    Respuesta `status`:
      created   — no existía y se creó;
      updated   — existía sin nombre útil (o la persona confirmó el cambio) y se guardó el nombre;
      different — existe con OTRO nombre: se devuelve `nombre_guardado` para preguntar antes de cambiarlo;
      exists    — existe con ese mismo nombre.
    """
    body = await request.json()
    email = str(body.get("email") or "").strip()
    name = alta_rapida.nombre_util(str(body.get("name") or ""), email)
    if not email:
        raise HTTPException(400, "Email requerido")

    db = request.app.state.db_pool
    existente = await db.fetchrow(
        "SELECT id, display_name FROM user_contacts WHERE owner=$1 AND LOWER(email)=LOWER($2) AND deleted_at IS NULL",
        username,
        email,
    )
    if existente:
        guardado = existente["display_name"] or ""
        accion = alta_rapida.decidir(
            guardado, email, name, bool(body.get("actualizar"))
        )
        if accion in ("completar", "actualizar"):
            await _poner_nombre(db, username, existente["id"], email, name)
            return {
                "status": "updated",
                "id": existente["id"],
                "nombre": name,
                "nombre_anterior": guardado,
            }
        if accion == "distinto":
            return {
                "status": "different",
                "id": existente["id"],
                "nombre_guardado": guardado,
                "nombre": name,
            }
        return {"status": "exists", "id": existente["id"], "nombre": guardado}

    nombre_pila, apellido = alta_rapida.partir(name) if name else ("", "")
    row = await db.fetchrow(
        "INSERT INTO user_contacts (owner, display_name, first_name, last_name, email, source) "
        "VALUES ($1,$2,$3,$4,$5,'from_email') RETURNING id",
        username,
        name or email,
        nombre_pila,
        apellido,
        email,
    )
    return {"status": "created", "id": row["id"], "nombre": name or email}
