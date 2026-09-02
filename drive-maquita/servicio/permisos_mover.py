# -*- coding: utf-8 -*-
"""
¿Quién puede MOVER dentro de una unidad compartida?
===================================================
Regla del 31/08/2026, en una frase: **cada quien mueve dentro de lo suyo.**

    · Administrador de la unidad (`manager`) → mueve en toda la unidad.
    · Con un rol concedido sobre una CARPETA (editor o manager de esa carpeta)
      → mueve dentro de esa carpeta, y solo ahí.
    · `editor` de la unidad entera, sin carpeta asignada → NO mueve. Puede
      crear, subir y editar, pero no reorganizar la unidad de los demás.
    · `viewer` → no mueve (ni escribe).
    · Master del Drive → mueve en cualquier sitio: es quien recupera lo que se
      pierde, y para eso tiene que poder colocarlo donde iba.

Ejemplo real de la unidad «Procesos Formativos»: quien tiene editor sobre
«1 Esmeraldas…» mueve, edita, copia y borra dentro de Esmeraldas; no puede
tocar «3 Guayas-El Oro…» ni la raíz de la unidad.

Como se pregunta por el ORIGEN y por el DESTINO, sacar algo de Esmeraldas para
llevarlo a Guayas falla por el destino, que es lo que se busca.

### Por qué mover se trata aparte de editar

Editar un archivo es un cambio *dentro* de algo, y queda en el historial de
versiones. Mover es un cambio en la **estructura que todos comparten**, y a
quien no encuentra su archivo el historial no le sirve de nada.

Autoría: Equipo de Tecnología Maquita — 2026-08-31
"""
import logging

from seguridad_rutas import unidad_de_ruta

log = logging.getLogger('almacen.permisos_mover')

# Roles que, sobre una carpeta concedida, permiten reorganizarla.
ROLES_QUE_MUEVEN = ('editor', 'manager')
# Rol de unidad que permite mover en TODA la unidad.
ROL_DE_UNIDAD_QUE_MUEVE = 'manager'


def puede_mover(usuario_id: int, ruta: str) -> bool:
    """¿Puede esta persona mover algo en esta ruta?

    Fuera de las unidades compartidas devuelve True: ahí manda el permiso de
    escritura de siempre, que ya se comprueba aparte. Ante cualquier duda
    responde que NO: es preferible que alguien pida ayuda a que la estructura
    de una unidad se reorganice sola.
    """
    try:
        unidad_id, subruta = unidad_de_ruta(ruta)
    except Exception:
        return False
    if unidad_id is None:
        return True

    try:
        from almacen_bd import es_master
        if es_master(usuario_id):
            return True
    except Exception:
        pass

    try:
        from permisos_unidad_carpeta import rol_en_carpeta
        from api_unidades import rol_en_unidad
    except Exception as excepcion:
        log.warning('no se pudieron leer los roles (%s): no se permite mover', excepcion)
        return False

    try:
        # Primero la carpeta: es lo que acota el ámbito. rol_en_carpeta busca la
        # concesión de esta carpeta o de una superior, así que vale también en
        # las subcarpetas de la que se concedió.
        if rol_en_carpeta(usuario_id, unidad_id, subruta) in ROLES_QUE_MUEVEN:
            return True
        return rol_en_unidad(usuario_id, unidad_id) == ROL_DE_UNIDAD_QUE_MUEVE
    except Exception as excepcion:
        log.warning('fallo comprobando el rol (%s): no se permite mover', excepcion)
        return False


def error_no_puede_mover():
    """El mensaje que se le da a quien no puede. Dice QUIÉN sí puede."""
    return ('Solo puedes mover dentro de las carpetas donde tienes permiso para '
            'hacerlo. Pide a un administrador de la unidad que lo mueva, o que '
            'te dé acceso a esa carpeta.')
