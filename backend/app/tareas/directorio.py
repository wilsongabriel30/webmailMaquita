"""Directorio de «Asignar tarea a», «Compartir lista» y Seguimiento (04/11/2026).

Antes salía solo de la nómina de Raíces, y eso fallaba de dos maneras:
- ofrecía correos personales (gmail, hotmail…) que la nómina guarda como «institucionales»; al elegirlos, el servidor
  respondía 400 «Solo se puede asignar a personas de la organización»;
- no traía a nadie de las empresas de la casa que no están en esa nómina: sus personas no encontraban a sus
  compañeros.

Ahora se unen la nómina y los buzones activos del correo (los mismos que ya muestra el directorio de Contactos), y solo
quedan los dominios de la casa (`organizacion.dominios_propios`), que son los que el servidor acepta al asignar.
"""

from __future__ import annotations

from app import organizacion

BUZONES_SQL = """
SELECT LOWER(m.username) AS email,
       COALESCE(NULLIF(p.display_name, ''), NULLIF(m.name, ''), SPLIT_PART(m.username, '@', 1)) AS nombre,
       COALESCE(p.title, '') AS cargo,
       COALESCE(p.department, '') AS departamento
  FROM mailbox m
  LEFT JOIN user_profiles p ON LOWER(p.user_email) = LOWER(m.username)
 WHERE m.active
"""


def de_la_casa(email: str) -> bool:
    email = (email or "").strip().lower()
    return "@" in email and email.rsplit("@", 1)[-1] in organizacion.dominios_propios()


def unir(nomina: list[dict], buzones: list[dict]) -> list[dict]:
    """Nómina primero (trae nombre, cargo y departamento reales); los buzones completan a quien no está en ella.

    Solo quedan correos de la casa, sin repetidos, ordenados por nombre.
    """
    vistos: dict[str, dict] = {}
    for fuente in (nomina, buzones):
        for p in fuente:
            email = (p.get("email") or "").strip().lower()
            if not de_la_casa(email) or email in vistos:
                continue
            vistos[email] = {
                "email": email,
                "nombre": p.get("nombre") or email.split("@")[0],
                "cargo": p.get("cargo") or "",
                "departamento": p.get("departamento") or "",
            }
    return sorted(vistos.values(), key=lambda p: (p["nombre"] or "").lower())


async def buzones(db) -> list[dict]:
    """Buzones activos del correo. Si la consulta falla, el directorio sigue con la nómina."""
    try:
        return [dict(f) for f in await db.fetch(BUZONES_SQL)]
    except Exception:  # p. ej. una instalación sin perfiles de usuario
        import logging

        logging.getLogger(__name__).warning(
            "directorio de tareas sin buzones", exc_info=True
        )
        return []
