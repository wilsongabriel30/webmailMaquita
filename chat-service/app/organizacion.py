"""Direcciones de la organización que instala el chat.

El repositorio es público: aquí solo hay valores de ejemplo. Lo real va en el .env del servicio.

  CHAT_URL_PUBLICA   dirección pública por la que la gente entra al chat y al correo
  FARO_PUBLIC_URL    intranet: perfiles, fotos y archivos
  JITSI_URL          servidor de reuniones
"""
import os


def _url(clave, defecto):
    return (os.getenv(clave) or defecto).rstrip('/')


def url_correo():
    return _url('CHAT_URL_PUBLICA', 'https://mail.example.org')


def url_intranet():
    return _url('FARO_PUBLIC_URL', 'https://intranet.example.org')


def url_reuniones():
    return _url('JITSI_URL', 'https://reuniones.example.org')


def url_foto(foto):
    """Dirección completa de una foto de perfil guardada en la intranet."""
    if not foto:
        return ''
    if foto.startswith('http') or foto.startswith('/'):
        return foto
    if foto.startswith('uploads/'):
        return url_intranet() + '/static/' + foto
    return url_intranet() + '/static/uploads/profiles/' + foto


# --- Identidad del asistente de IA del chat (16/10/2026) ---------------------------------------
#   CHAT_ORG_NOMBRE      nombre de la organización (p. ej. «Fundación Ejemplo»)
#   CHAT_IA_NOMBRE       nombre del asistente (p. ej. «IA Ejemplo»)
#   CHAT_IA_INSTITUCION  fichero de texto con los datos de la institución que el asistente no debe
#                        olvidar (país, fundación, misión, redes…). Si no existe, el asistente no
#                        afirma nada sobre la institución que no venga en el contexto.

def nombre_organizacion():
    return (os.getenv('CHAT_ORG_NOMBRE') or 'la organización').strip()


def nombre_asistente():
    return (os.getenv('CHAT_IA_NOMBRE') or 'Asistente IA').strip()


def conocimiento_institucional():
    ruta = os.getenv('CHAT_IA_INSTITUCION') or '/etc/maquita-mail/ia-institucion.txt'
    try:
        with open(ruta, encoding='utf-8') as f:
            return f.read().strip()[:4000]
    except OSError:
        return ''
