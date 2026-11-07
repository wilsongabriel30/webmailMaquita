"""Directorio de buzones (05/11/2026): la capa GENÉRICA del directorio institucional.

Todos los buzones activos de los dominios institucionales de la organización, con lo que
`user_profiles` sepa de cada uno (nombre, cargo, departamento, área, teléfonos, foto).
Sirve a cualquier organización que use el webmail sin ningún sistema externo: el nombre sale
del buzón, la foto la sube cada persona (fotos.py) y el admin completa el resto desde el panel.
Donde hay un conector de nómina (en Maquita, Raíces: app/tareas/jefes.py), ese conector llena
`user_profiles` y aquí se ve sin hacer nada más.

Se combina con `org_contacts` (entradas manuales del admin) en directory.py. Los ids de buzón
son NEGATIVOS para no chocar con los de org_contacts.
"""

import zlib

from app import organizacion


def dominios_visibles(usuario: str) -> list[str]:
    """Un usuario institucional ve todos los dominios institucionales de la organización;
    otro, solo el suyo."""
    dominio = (usuario or "").rsplit("@", 1)[-1].lower()
    institucionales = organizacion.dominios("ORG_DOMINIOS_INSTITUCIONALES")
    if dominio in institucionales:
        return sorted(institucionales)
    return [dominio]


def id_buzon(email: str) -> int:
    return -(zlib.crc32(email.strip().lower().encode("utf-8")) % 2_000_000_000 + 1)


def _fila_a_contacto(r) -> dict:
    email = (r["email"] or "").strip()
    nombre = (
        (r["display_name"] or "").strip()
        or (r["name"] or "").strip()
        or email.split("@", 1)[0]
    )
    partes = nombre.split()
    return {
        "id": id_buzon(email),
        "display_name": nombre,
        "first_name": partes[0] if partes else "",
        "last_name": " ".join(partes[1:]) if len(partes) > 1 else "",
        "email": email,
        "phone": (r["phone"] or r["tel_buzon"] or "").strip(),
        "phone_mobile": (r["mobile"] or "").strip(),
        "job_title": (r["title"] or "").strip(),
        "department": (r["department"] or "").strip(),
        "company": organizacion.valor("ORG_NAME", ""),
        "address_street": "",
        "address_city": "",
        "address_state": "",
        "address_zip": "",
        "address_country": "",
        "photo_url": (r["photo_url"] or "").strip(),
        "notes": "",
        "created_by": "buzon",
        "created_at": None,
        "updated_at": r["updated_at"],
        "location": (r["office_location"] or "").strip(),
        "source": "mailbox",
        "is_active": True,
    }


_SQL = """
    SELECT m.username AS email, m.name, m.domain, m.phone AS tel_buzon,
           p.display_name, p.title, p.department, p.phone, p.mobile, p.office_location, p.photo_url, p.updated_at
    FROM mailbox m
    LEFT JOIN user_profiles p ON lower(p.user_email) = lower(m.username)
    WHERE m.active = true AND m.domain = ANY($1::text[])
"""


async def entradas_buzones(
    db, dominios: list[str], search: str = "", department: str = "", excluir=()
) -> list[dict]:
    sql = _SQL
    params: list = [dominios]
    if search:
        params.append(f"%{search}%")
        n = len(params)
        sql += (
            f" AND (m.username ILIKE ${n} OR m.name ILIKE ${n} OR COALESCE(p.display_name,'') ILIKE ${n}"
            f" OR COALESCE(p.department,'') ILIKE ${n} OR COALESCE(p.title,'') ILIKE ${n})"
        )
    if department:
        params.append(department)
        sql += f" AND COALESCE(p.department,'') = ${len(params)}"
    rows = await db.fetch(sql, *params)
    excluidos = {e.lower() for e in excluir}
    contactos = [
        _fila_a_contacto(r) for r in rows if (r["email"] or "").lower() not in excluidos
    ]
    contactos.sort(key=lambda c: c["display_name"].lower())
    return contactos


async def buzon_por_id(db, dominios: list[str], contacto_id: int) -> dict | None:
    """Los ids negativos son buzones: se resuelve por el mismo hash del correo."""
    rows = await db.fetch(_SQL, dominios)
    for r in rows:
        if id_buzon(r["email"] or "") == contacto_id:
            return _fila_a_contacto(r)
    return None


async def departamentos_buzones(db, dominios: list[str]) -> list[str]:
    rows = await db.fetch(
        """SELECT DISTINCT p.department FROM user_profiles p JOIN mailbox m ON lower(m.username) = lower(p.user_email)
           WHERE m.active AND m.domain = ANY($1::text[]) AND COALESCE(p.department,'') <> '' ORDER BY 1""",
        dominios,
    )
    return [r["department"] for r in rows]


async def ubicaciones_buzones(db, dominios: list[str]) -> list[str]:
    rows = await db.fetch(
        """SELECT DISTINCT p.office_location FROM user_profiles p JOIN mailbox m ON lower(m.username) = lower(p.user_email)
           WHERE m.active AND m.domain = ANY($1::text[]) AND COALESCE(p.office_location,'') <> '' ORDER BY 1""",
        dominios,
    )
    return [r["office_location"] for r in rows]
