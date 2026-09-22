"""Panel · Dispositivos: códigos de enrolamiento (la «contraseña de instalación»).

Desde el 22/09/2026 (decisión de dirección) el código lo crea SOLO Tecnología aquí, y puede asignarse a
una persona (`custodio_email`): esa persona queda como custodia al enrolar, ve el código en solo lectura
en su Configuración del correo y la app 1.2.8 lo recibe para activar con un toque. Para que pueda
volver a verlo, el código asignado se guarda cifrado (`codigo_cifrado`, clave DISP_CODIGO_CLAVE del .env)
mientras esté vigente; los códigos sin persona siguen mostrándose una sola vez. Cada lectura del código
en claro por un administrador queda en `admin_audit` (`dispositivo_codigo_ver`).
"""

import hashlib
import json
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_admin, require_role
from app.dispositivos import codigo_cifrado
from app.dispositivos.comun import auditar, db, texto

router = APIRouter(prefix="/api/dispositivos/codigos", tags=["dispositivos"])
_ADMIN = require_role("superadmin", "admin")
_ALFABETO = "abcdefghjkmnpqrstuvwxyz23456789"   # sin 0/o/1/l/i: se teclea en un teléfono

_VIGENTE = "c.revocado_en IS NULL AND c.usos < c.usos_max AND (c.caduca_en IS NULL OR c.caduca_en > NOW())"


@router.get("")
async def listar(request: Request, admin: dict = Depends(get_current_admin)):
    filas = await db(request).fetch(
        f"""SELECT c.id, c.prefijo, c.etiqueta, c.modo, c.usos_max, c.usos, c.creado_por, c.creado_en, c.caduca_en,
                   c.revocado_en, c.custodio_email, c.autoservicio,
                   (c.codigo_cifrado IS NOT NULL AND {_VIGENTE}) AS recuperable,
                   COALESCE((SELECT json_agg(json_build_object('id', e.id, 'nombre', e.nombre, 'modelo', e.modelo,
                                                               'fabricante', e.fabricante, 'enrolado_en', e.enrolado_en) ORDER BY e.enrolado_en)
                              FROM disp_equipos e WHERE e.codigo_id = c.id), '[]'::json) AS usado_por
            FROM disp_codigos c ORDER BY c.creado_en DESC LIMIT 200""")
    codigos = []
    for f in filas:
        d = dict(f)
        d["usado_por"] = json.loads(d["usado_por"]) if isinstance(d["usado_por"], str) else d["usado_por"]
        codigos.append(d)
    return {"codigos": codigos, "cifrado_disponible": codigo_cifrado.disponible()}


@router.post("")
async def crear(request: Request, admin: dict = Depends(_ADMIN)):
    b = await request.json()
    modo = b.get("modo") if b.get("modo") in ("propietario", "limitado") else "propietario"
    usos = int(b.get("usos_max") or 1)
    horas = int(b.get("horas_validez") or 72)
    if not 1 <= usos <= 500 or not 1 <= horas <= 24 * 90:
        raise HTTPException(400, "Usos (1-500) u horas de validez (1-2160) fuera de rango")
    custodio = (texto(b.get("custodio_email"), 255) or "").lower() or None
    if custodio:
        if "@" not in custodio:
            raise HTTPException(400, "El correo de la persona no es válido")
        existe = await db(request).fetchval("SELECT 1 FROM mailbox WHERE username = $1 AND active", custodio)
        if not existe:
            raise HTTPException(400, "Ese buzón no existe o está inactivo")
    grupos = ["".join(secrets.choice(_ALFABETO) for _ in range(4)) for _ in range(3)]
    codigo = "-".join(grupos)
    cifrado = codigo_cifrado.cifrar(codigo) if custodio else None
    async with db(request).acquire() as con, con.transaction():
        if custodio:
            # Una persona tiene un solo código vigente: el anterior se anula al asignar el nuevo.
            await con.execute("UPDATE disp_codigos SET revocado_en = NOW(), codigo_cifrado = NULL "
                              "WHERE custodio_email = $1 AND revocado_en IS NULL AND usos < usos_max", custodio)
        fila = await con.fetchrow(
            "INSERT INTO disp_codigos (codigo_hash, prefijo, etiqueta, modo, usos_max, creado_por, caduca_en, custodio_email, codigo_cifrado) "
            "VALUES ($1,$2,$3,$4,$5,$6, NOW() + make_interval(hours => $7), $8, $9) RETURNING id, caduca_en",
            hashlib.sha256("".join(grupos).encode()).hexdigest(), grupos[0], texto(b.get("etiqueta"), 120) or "",
            modo, usos, admin["username"], horas, custodio, cifrado)
    await auditar(request, admin, "dispositivo_codigo_crear", str(fila["id"]),
                  {"modo": modo, "usos_max": usos, "horas": horas, "custodio_email": custodio, "recuperable": cifrado is not None})
    return {"id": fila["id"], "codigo": codigo, "caduca_en": fila["caduca_en"], "modo": modo, "usos_max": usos,
            "custodio_email": custodio, "recuperable": cifrado is not None,
            "aviso": None if (cifrado or not custodio) else
            "No hay DISP_CODIGO_CLAVE en el .env: el código no queda recuperable; la persona no lo verá en su Configuración."}


@router.get("/{codigo_id}/ver")
async def ver(codigo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    """Código en claro de un código asignado y vigente. Cada lectura queda en la auditoría."""
    c = await db(request).fetchrow(
        f"SELECT c.id, c.codigo_cifrado, c.custodio_email, c.caduca_en FROM disp_codigos c WHERE c.id = $1 AND {_VIGENTE}", codigo_id)
    claro = codigo_cifrado.descifrar(c["codigo_cifrado"]) if c else None
    if not claro:
        raise HTTPException(404, "Este código no es recuperable (no está asignado a una persona, ya se usó, caducó o se anuló)")
    await auditar(request, admin, "dispositivo_codigo_ver", str(codigo_id), {"custodio_email": c["custodio_email"]})
    return {"id": c["id"], "codigo": claro, "custodio_email": c["custodio_email"], "caduca_en": c["caduca_en"]}


@router.delete("/{codigo_id}")
async def revocar(codigo_id: int, request: Request, admin: dict = Depends(_ADMIN)):
    await db(request).execute("UPDATE disp_codigos SET revocado_en = NOW(), codigo_cifrado = NULL WHERE id = $1 AND revocado_en IS NULL", codigo_id)
    await auditar(request, admin, "dispositivo_codigo_revocar", str(codigo_id))
    return {"ok": True}
