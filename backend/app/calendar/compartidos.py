"""Permisos sobre calendarios compartidos (05/11/2026).

Hasta hoy «compartir con lectura y escritura» solo guardaba el permiso: el servicio seguía
exigiendo ser el dueño para ver, crear, editar o borrar. Estas condiciones SQL se añaden a
las consultas de `service.py` (la tabla `calendars` va con alias `c`; `$2` es el correo de
quien pide). Un calendario de equipo donde todos editan necesita exactamente esto.
"""

# Quien puede VER el calendario: el dueño o cualquiera con quien esté compartido.
VISIBLE_2 = (
    "(c.owner_email = $2 OR EXISTS (SELECT 1 FROM calendar_shares cs "
    "WHERE cs.calendar_id = c.id AND lower(cs.shared_with) = lower($2)))"
)

# Quien puede ESCRIBIR: el dueño o quien tenga permiso «read-write».
EDITABLE_2 = (
    "(c.owner_email = $2 OR EXISTS (SELECT 1 FROM calendar_shares cs "
    "WHERE cs.calendar_id = c.id AND lower(cs.shared_with) = lower($2) "
    "AND cs.permission = 'read-write'))"
)
