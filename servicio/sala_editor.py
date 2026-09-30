"""¿Hay alguien dentro de la sala de OnlyOffice de un documento? (17/09/2026)

PROBLEMA QUE RESUELVE
    Renovar la sala (subir su versión → key nueva) mientras hay gente editando
    parte el documento en DOS salas: quien ya estaba sigue en la vieja y quien
    abre después entra en la nueva. Cada una guarda encima de la otra y lo que
    se escribe en una «no se guarda» visto desde la otra.
    Caso real: «IBI 2025/prueba IFO (respuestas).xlsx», con tres salas abiertas
    a la vez; las pestañas de provincias desaparecían en cada guardado.

CÓMO
    Se pregunta al CommandService (`info`) por la key ACTUAL de la sala, que es
    en la que entraría quien abre ahora. Si hay usuarios conectados, quien llama
    no debe renovar la sala ni escribir el archivo por fuera del editor.

Si el Document Server no responde se devuelve None («no se sabe»): abrir el
editor sigue como antes, pero quien iba a ESCRIBIR el archivo por fuera debe
tratarlo como ocupado. El `info` a veces tarda 7-8 s (17/09/2026).
"""

import hashlib
import logging

log = logging.getLogger(__name__)


def key_actual(doc_base: str) -> str:
    from api_onlyoffice import _version_sesion
    version = _version_sesion(doc_base)
    return hashlib.sha1(f'{doc_base}:v{version}'.encode()).hexdigest()[:20]


def usuarios_conectados(doc_base: str) -> list:
    """Ids de los usuarios dentro de la sala actual; None si no se sabe."""
    try:
        import requests
        from api_onlyoffice import firmar_jwt, url_interna_ds

        cuerpo = {'c': 'info', 'key': key_actual(doc_base)}
        cuerpo['token'] = firmar_jwt(dict(cuerpo))
        respuesta = requests.post(
            url_interna_ds().rstrip('/') + '/coauthoring/CommandService.ashx',
            json=cuerpo, timeout=(3, 15),
            headers={'Authorization': 'Bearer ' + firmar_jwt({'payload': cuerpo})})
        respuesta.raise_for_status()
        datos = respuesta.json() or {}
        return list(datos.get('users') or []) if datos.get('error') == 0 else []
    except Exception as excepcion:
        log.warning('OnlyOffice: no se pudo consultar la sala de %s: %s', doc_base, excepcion)
        return None
