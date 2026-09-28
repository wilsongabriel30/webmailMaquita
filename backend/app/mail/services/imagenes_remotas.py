"""Imágenes remotas: cuándo se muestran solas y cuándo se bloquean.

Desde el 28/09/2026 las imágenes remotas se muestran sin pulsar nada (las firmas de la
contraparte suelen ser imágenes remotas y la gente se quedaba sin verlas). Se bloquean solo:

- si la persona activó «Bloquear imágenes remotas» en Configuración, o
- si el correo está en la carpeta de no deseado: ahí una imagen puede avisar al remitente
  de que la dirección existe y se lee.

En ambos casos queda el botón «Cargar imágenes» para verlas a mano.
"""

CARPETAS_NO_DESEADO = {"junk", "spam", "correo no deseado"}


def es_no_deseado(folder: str) -> bool:
    # Las carpetas de cuentas delegadas llegan como «Compartidos,<cuenta>,<carpeta>».
    real = (folder or "").split(",")[-1].strip().lower()
    return real in CARPETAS_NO_DESEADO


async def debe_bloquear(db, username: str, folder: str) -> bool:
    if es_no_deseado(folder):
        return True
    try:
        valor = await db.fetchval(
            "SELECT block_remote_images FROM user_preferences WHERE username = $1",
            username,
        )
    except Exception:
        return False
    return bool(valor)
