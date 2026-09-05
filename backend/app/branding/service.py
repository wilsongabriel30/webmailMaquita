# -*- coding: utf-8 -*-
"""Nombre de la organización y del producto para textos de cara al usuario
(pantallas de seguridad, avisos, correos automáticos, prompt de IA).

Salen de `branding_settings`; si no están configurados se usan valores por
defecto. Son DOS cosas distintas y conviene no mezclarlas:

  org_name  — la organización. Aquí: «Fundación Maquita Cushunchic MCCH».
              Fallback NEUTRO a propósito: una réplica no debe mostrar la marca
              de otra organización, porque un aviso de seguridad a nombre ajeno
              parece phishing.

  app_name  — el producto de correo. Aquí: «Maquita Mail». Es lo que ve quien
              usa el sistema: el emisor de su segundo factor, el pie de los
              recordatorios, el título de los avisos del navegador.

Sustituir un literal «Maquita Mail» por `org_name` NO es equivalente: cambiaría
lo que la gente ya tiene registrado en su aplicación de autenticación y el pie
de los correos automáticos. Por eso existe `app_name`.

Para los puntos que no tienen la base de datos a mano (el cliente SMTP, por
ejemplo) hay una caché de proceso que se rellena al arrancar. Si no se ha
rellenado todavía, se devuelven los valores por defecto: nunca se bloquea el
envío de un correo por consultar la marca.
"""

ORG_NAME_FALLBACK = 'Tu organización'
APP_NAME_FALLBACK = 'Maquita Mail'

# Caché de proceso. La rellena `precargar()` al arrancar y la refrescan las
# funciones asíncronas cada vez que consultan.
_cache = {'org_name': None, 'app_name': None}


async def _leer(db, clave: str):
    try:
        row = await db.fetchrow(
            "SELECT value FROM branding_settings WHERE key = $1", clave)
        if row and (row['value'] or '').strip():
            return row['value'].strip()
    except Exception:
        pass
    return None


async def get_org_name(db) -> str:
    """Nombre de la organización, con fallback neutro."""
    valor = await _leer(db, 'org_name')
    if valor:
        _cache['org_name'] = valor
        return valor
    return _cache['org_name'] or ORG_NAME_FALLBACK


async def get_app_name(db) -> str:
    """Nombre del producto de correo, con «Maquita Mail» por defecto."""
    valor = await _leer(db, 'app_name')
    if valor:
        _cache['app_name'] = valor
        return valor
    return _cache['app_name'] or APP_NAME_FALLBACK


def org_name_cacheado() -> str:
    """Versión sin base de datos, para puntos que no la tienen a mano."""
    return _cache['org_name'] or ORG_NAME_FALLBACK


def app_name_cacheado() -> str:
    """Versión sin base de datos, para puntos que no la tienen a mano."""
    return _cache['app_name'] or APP_NAME_FALLBACK


async def precargar(db) -> None:
    """Rellena la caché al arrancar. Si falla, se sigue con los valores por
    defecto: la marca nunca debe impedir que el sistema levante."""
    try:
        _cache['org_name'] = await _leer(db, 'org_name')
        _cache['app_name'] = await _leer(db, 'app_name')
    except Exception:
        pass
