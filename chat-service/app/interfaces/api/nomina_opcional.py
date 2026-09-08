# -*- coding: utf-8 -*-
"""El chat funciona con o sin nómina (aviso de Andes, 08/09/2026).

Varias consultas cruzan `usuarios` con `trabajadores` solo para la foto de perfil. En una
instalación sin nómina —ni la tabla, ni la columna `usuarios.trabajador_id`— esas consultas
revientan y la respuesta es un 500: mirar una conversación deja de funcionar por una foto.

Aquí se comprueba UNA vez si esa parte existe y se elige la consulta que toca. Si no hay
nómina, el chat sigue: se pierde la foto de respaldo, nada más.
"""

_hay_nomina = None


def reiniciar_cache():
    """Para las pruebas y para después de una migración."""
    global _hay_nomina
    _hay_nomina = None


def hay_nomina(ejecutar) -> bool:
    """¿Existen la tabla `trabajadores` y la columna `usuarios.trabajador_id`?

    `ejecutar(sql)` devuelve un valor escalar. Se pregunta una vez y se recuerda: es una
    propiedad del esquema, no algo que cambie entre peticiones.
    """
    global _hay_nomina
    if _hay_nomina is not None:
        return _hay_nomina
    try:
        _hay_nomina = bool(ejecutar(
            "SELECT (to_regclass('public.trabajadores') IS NOT NULL) AND EXISTS ("
            "  SELECT 1 FROM information_schema.columns"
            "  WHERE table_name = 'usuarios' AND column_name = 'trabajador_id')"
        ))
    except Exception:
        _hay_nomina = False
    return _hay_nomina


def consulta_remitentes(con_nomina: bool) -> str:
    """Datos de quienes escriben. Con nómina, además la foto de la ficha como respaldo."""
    if con_nomina:
        return """
            SELECT u.id, u.username, u.email, u.full_name, u.role,
                   u.profile_picture, t.foto_perfil as foto_trabajador
            FROM usuarios u
            LEFT JOIN trabajadores t ON u.trabajador_id = t.id
            WHERE u.id = ANY(:user_ids)
        """
    return """
        SELECT u.id, u.username, u.email, u.full_name, u.role,
               u.profile_picture, NULL as foto_trabajador
        FROM usuarios u
        WHERE u.id = ANY(:user_ids)
    """
