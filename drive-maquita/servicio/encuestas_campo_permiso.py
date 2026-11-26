"""
Formularios del Almacén — quién puede publicar una encuesta de campo (11/11/2026)
================================================================================
Publicar (o retirar) una encuesta de campo la pone en los teléfonos de los
encuestadores, así que no basta con poder editar el formulario: hace falta el
perfil «Publicador» (o «Administrador») de Datos de campo. Los usuarios master
entran siempre como administradores.

Falla cerrado: si no se puede leer el perfil, no se publica.

Autoría: Equipo de Tecnología Maquita — 2026-11-11
"""
import logging

log = logging.getLogger('almacen.encuestas.campo.permiso')

MENSAJE = ('Solo quien tiene el perfil «Publicador» de Datos de campo puede publicar encuestas de campo. '
           'Pídelo en Administración → Módulos y permisos, o pide a un publicador que la publique.')


def puede_publicar(usuario_id, ruta=None):
    """Con `ruta`, también la Gestoría territorial si la encuesta es de su territorio (12/11/2026)."""
    try:
        from modulos.campo_app.social import perfil
        if perfil.puede(usuario_id, 'publicar'):
            return True
        if not ruta:
            return False
        from modulos.campo_app.social import territorio_encuestas
        return bool(territorio_encuestas.es_suya(ruta, usuario_id))
    except Exception as e:
        log.warning('No se pudo comprobar el perfil de campo del usuario %s: %s', usuario_id, e)
        return False
