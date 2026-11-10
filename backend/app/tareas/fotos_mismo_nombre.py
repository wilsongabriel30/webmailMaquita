"""Misma foto de Raíces para TODOS los buzones de una persona (09/11/2026).

Raíces guarda un solo correo por persona; sus otros buzones (p. ej. logisticaproductos@ de Thalia Vega) se
emparejan solo por nombre (`fuente='nomina-nombre'`, jefes.nombres_por_coincidencia) y hasta hoy recibían el
nombre pero no la foto. Regla «la foto de Raíces manda / misma foto para todos»: a esos buzones se les copia la
foto de Raíces del perfil principal (único perfil `fuente='nomina'` con el mismo nombre). Si la persona puso una
foto propia en ese buzón, se respeta hasta que la de Raíces cambie (misma lógica que foto_efectiva). Si el
principal pierde la foto, el secundario también.
"""

import logging

from app.contacts.foto_efectiva import Cambios, EstadoFoto, decidir

log = logging.getLogger("tareas.fotos_mismo_nombre")

SQL_PARES = """
SELECT lower(s.user_email) AS email,
       COALESCE(s.photo_url,'') AS photo_url, COALESCE(s.foto_raices_url,'') AS foto_raices_url,
       COALESCE(s.foto_raices_huella,'') AS foto_raices_huella, COALESCE(s.foto_propia_url,'') AS foto_propia_url,
       COALESCE(s.foto_origen,'') AS foto_origen,
       COALESCE(p.foto_raices_url,'') AS p_url, COALESCE(p.foto_raices_huella,'') AS p_huella
  FROM user_profiles s
  JOIN LATERAL (
        SELECT q.foto_raices_url, q.foto_raices_huella
          FROM user_profiles q
         WHERE q.fuente = 'nomina' AND q.display_name = s.display_name
           AND lower(q.user_email) <> lower(s.user_email)
         ORDER BY (COALESCE(q.foto_raices_url,'') <> '') DESC, q.updated_at DESC
         LIMIT 1
       ) p ON TRUE
 WHERE s.fuente = 'nomina-nombre' AND COALESCE(s.display_name,'') <> ''
   AND (SELECT count(*) FROM user_profiles q2
         WHERE q2.fuente = 'nomina' AND q2.display_name = s.display_name) = 1
"""

SQL_ESCRIBIR = """UPDATE user_profiles
                     SET photo_url = $2, foto_raices_url = $3, foto_raices_huella = $4,
                         foto_propia_url = $5, foto_origen = $6, updated_at = NOW()
                   WHERE lower(user_email) = $1 AND fuente = 'nomina-nombre'"""


def _estado(f) -> EstadoFoto:
    return EstadoFoto(
        photo_url=f["photo_url"],
        foto_raices_url=f["foto_raices_url"],
        foto_raices_huella=f["foto_raices_huella"],
        foto_propia_url=f["foto_propia_url"],
        foto_origen=f["foto_origen"],
    )


def decidir_copia(f) -> Cambios | None:
    """Qué escribir en el buzón secundario para que lleve la foto de Raíces de su principal; None si ya está."""
    c = decidir(_estado(f), f["p_url"], f["p_huella"])
    return None if c.vacio() else c


async def propagar(db) -> set[str]:
    """Copia la foto de Raíces del perfil principal a los buzones emparejados por nombre. Devuelve los cambiados."""
    cambiados: set[str] = set()
    for f in await db.fetch(SQL_PARES):
        c = decidir_copia(f)
        if c is None:
            continue
        await db.execute(
            SQL_ESCRIBIR,
            f["email"],
            c.photo_url,
            c.foto_raices_url,
            c.foto_raices_huella,
            c.foto_propia_url,
            c.foto_origen,
        )
        cambiados.add(f["email"])
    if cambiados:
        log.info(
            "foto de Raíces copiada a %d buzones emparejados por nombre", len(cambiados)
        )
    return cambiados
