"""Entorno para los subprocesos del correo, sin leer los secretos del correo.

Fase 2 del hallazgo A-15, decisión del 2026-09-04.

EL PROBLEMA
El panel lanza cuatro procesos que son código del correo: AIR, los agentes, el
copiloto y RAG. Hasta hoy les construía el entorno abriendo entero
/opt/maquita-webmail/backend/.env, que tiene 46 variables: las claves de
OnlyOffice, las de Nextcloud, la del chat, la cadena de conexión de nómina, las
de notificaciones push y la contraseña maestra del correo.

Eso funcionaba porque el panel corría como root. Corriendo como root, dar el
archivo entero da igual: ya lo puede todo. Al dejar de ser root, mantener esa
lectura habría vaciado de sentido el confinamiento, porque el panel seguiría
teniendo delante todos los secretos del correo.

LA DECISIÓN
Copiar al archivo de configuración del panel SOLO los valores que esos cuatro
procesos necesitan, con el prefijo WEBMAIL_, y no dar acceso al archivo del
correo ni por permisos de grupo. Se copiaron 17 de 46 variables.

Las que NO se copian, a propósito: ONLYOFFICE_SECRET, ONLYOFFICE_DOWNLOAD_SECRET,
NC_ADMIN_PASS, NC_ADMIN_USER, CHAT_SSO_SECRET, NOMINA_DSN, NOTIF_SECRET,
SECURE_MSG_KEY, las tres VAPID, KC_CLIENT_SECRET, GNUPGHOME, SMTP_*, SIEVE_*,
TRUSTED_NETWORKS, COOKIE_DOMAIN, CORS_ORIGINS, MAIL_DOMAIN, REDIS_URL y las
PHISH_CLASSIFIER_*. Si algún día un subproceso necesita una de ellas, se añade
aquí y al archivo, de una en una y a conciencia.

LA DEPENDENCIA, QUE HAY QUE TENER PRESENTE
Ahora el mismo valor vive en dos archivos. Si cambia en el correo y no aquí, los
cuatro procesos fallarán o se comportarán raro. El panel NO puede detectarlo por
sí mismo: comparar exigiría leer el archivo del correo, que es justo lo que se
quiere evitar. La comprobación la hace un guion aparte que sí corre como root:
/usr/local/sbin/verificar-config-panel.sh

Lo que sí se valida aquí es que las obligatorias estén presentes, y se avisa en
el registro cuando falta alguna, que es el fallo más probable tras un despliegue.
"""

import logging
import os

_log = logging.getLogger(__name__)

# Sin estas, los procesos del correo abortan al arrancar: su comprobación de
# secretos obligatorios los rechaza y la conexión a la base queda vacía.
OBLIGATORIAS = ("SECRET_KEY", "ADMIN_JWT_SECRET", "MASTER_PASSWORD", "DATABASE_URL")

# Con valor por defecto en el correo. Si faltan, degrada pero no rompe.
OPCIONALES = (
    "IA_PROVIDER", "IA_BASE_URL", "IA_MODEL", "IA_API_KEY", "IA_TIMEOUT",
    "IA_EMBED_URL", "IA_EMBED_MODEL", "OLLAMA_URL",
    "IMAP_HOST", "IMAP_PORT", "ORG_NAME", "AI_ORG_CONTEXT", "RAG_INGEST_LIMIT",
)

# Directorio de trabajo de los subprocesos del correo.
#
# NO puede ser /opt/maquita-webmail/backend. La configuracion del correo declara
# su archivo .env con ruta RELATIVA, asi que pydantic lo busca en el directorio
# de trabajo; si el proceso trabaja alli, lo encuentra, no puede leerlo (es solo
# de root) y aborta con PermissionError. Comprobado el 2026-09-04: no lo ignora
# en silencio, falla.
#
# Trabajando en un directorio propio y vacio, el archivo no existe, pydantic no
# se queja, y la configuracion se resuelve con las variables que le pasamos. El
# codigo del correo se localiza por PYTHONPATH.
DIRECTORIO_EJECUCION = "/var/lib/maquita-admin/ejecucion"
RUTA_CODIGO_CORREO = "/opt/maquita-webmail/backend"

_avisado = False


def entorno_webmail() -> dict:
    """Entorno para un subproceso del correo, a partir de los valores prestados.

    Sustituye a la lectura directa del archivo de configuración del correo. Toma
    las variables con prefijo WEBMAIL_ del entorno del panel y se las entrega al
    hijo con su nombre original, que es el que su configuración espera.
    """
    global _avisado
    env = dict(os.environ)

    faltan = []
    for clave in OBLIGATORIAS + OPCIONALES:
        valor = os.environ.get("WEBMAIL_" + clave)
        if valor is not None:
            env[clave] = valor
        elif clave in OBLIGATORIAS:
            faltan.append(clave)

    if faltan and not _avisado:
        _avisado = True
        _log.error(
            "Faltan valores prestados de la configuracion del correo: %s. "
            "Los procesos de AIR, agentes, copiloto y RAG van a fallar. "
            "Anade WEBMAIL_<NOMBRE> al archivo de configuracion del panel "
            "copiando el valor del archivo del correo, y comprueba la "
            "alineacion con /usr/local/sbin/verificar-config-panel.sh",
            ", ".join(faltan))

    env["PYTHONPATH"] = RUTA_CODIGO_CORREO
    return env


def estado() -> dict:
    """Para la comprobación de salud del panel. No devuelve ningún valor."""
    return {
        "obligatorias_presentes": sorted(
            c for c in OBLIGATORIAS if os.environ.get("WEBMAIL_" + c)),
        "obligatorias_ausentes": sorted(
            c for c in OBLIGATORIAS if not os.environ.get("WEBMAIL_" + c)),
        "opcionales_presentes": sorted(
            c for c in OPCIONALES if os.environ.get("WEBMAIL_" + c)),
    }
