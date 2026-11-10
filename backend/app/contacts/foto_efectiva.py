"""Decisión de la foto de perfil EFECTIVA (09/11/2026). Función pura, sin BD ni red.

Regla «la foto de Raíces manda» (REGLA-WEBMAIL-FOTO-PERFIL-RAICES-MANDA):
  - La foto de Raíces (nómina) es la base institucional.
  - La persona puede poner una propia desde el correo; se ve para todos MIENTRAS Raíces
    no cambie la suya.
  - Cuando la foto de Raíces cambia (huella distinta a la guardada), pisa la propia.

Columnas de `user_profiles` implicadas:
  photo_url          foto efectiva (la que leen todas las vistas)
  foto_raices_url    última URL conocida de Raíces
  foto_raices_huella huella (ETag / tamaño+fecha) de esa imagen, para detectar cambios
  foto_propia_url    foto subida desde el correo (vacío = ninguna)
  foto_origen        'nomina' | 'propio' | ''
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class EstadoFoto:
    """Lo que hay hoy en la fila de la persona (cadenas vacías = sin dato)."""

    photo_url: str = ""
    foto_raices_url: str = ""
    foto_raices_huella: str = ""
    foto_propia_url: str = ""
    foto_origen: str = ""


@dataclass(frozen=True)
class Cambios:
    """Valores que hay que escribir. `vacio()` → nada que hacer."""

    photo_url: str = ""
    foto_raices_url: str = ""
    foto_raices_huella: str = ""
    foto_propia_url: str = ""
    foto_origen: str = ""
    # True cuando la foto efectiva cambia: hay que invalidar la caché `avatar:<correo>`.
    invalidar_cache: bool = False
    motivo: str = field(default="", compare=False)

    def vacio(self) -> bool:
        return self.motivo == ""


def _limpia(s: str | None) -> str:
    return (s or "").strip()


def decidir(estado: EstadoFoto, raices_url: str, raices_huella: str) -> Cambios:
    """Decide la foto efectiva tras una sincronización con Raíces.

    `raices_url` vacío significa que la persona ya no tiene foto en Raíces.
    Devuelve los campos a escribir; si no hay nada que cambiar, `Cambios()` vacío.
    """
    raices_url = _limpia(raices_url)
    raices_huella = _limpia(raices_huella) or raices_url
    propia = _limpia(estado.foto_propia_url)
    actual = _limpia(estado.photo_url)

    # --- Raíces ya no tiene foto ---
    if not raices_url:
        if not _limpia(estado.foto_raices_url) and not _limpia(
            estado.foto_raices_huella
        ):
            return (
                Cambios()
            )  # nunca la tuvo: nada que tocar (la propia, si hay, se queda)
        efectiva = propia
        return Cambios(
            photo_url=efectiva,
            foto_raices_url="",
            foto_raices_huella="",
            foto_propia_url=propia,
            foto_origen="propio" if propia else "",
            invalidar_cache=efectiva != actual,
            motivo="raices_sin_foto",
        )

    huella_guardada = _limpia(estado.foto_raices_huella)
    misma_url = _limpia(estado.foto_raices_url) == raices_url
    # Una huella provisional («url:…», cuando el HEAD falló o viene de la migración) que se sustituye por la
    # definitiva de la MISMA URL no es un cambio de foto: se adopta la nueva huella sin pisar la propia.
    provisional = huella_guardada in ("", "url:" + raices_url, raices_url) and misma_url
    cambio_raices = raices_huella != huella_guardada and not provisional

    # --- Raíces cambió (o es la primera vez que la vemos): manda y termina la propia ---
    if cambio_raices:
        return Cambios(
            photo_url=raices_url,
            foto_raices_url=raices_url,
            foto_raices_huella=raices_huella,
            foto_propia_url="",
            foto_origen="nomina",
            invalidar_cache=raices_url != actual,
            motivo="raices_cambio",
        )

    # --- Raíces igual que la última vez ---
    if propia:
        # La propia sigue vigente. Solo se corrige si la fila está incoherente.
        if (
            actual == propia
            and estado.foto_origen == "propio"
            and misma_url
            and huella_guardada == raices_huella
        ):
            return Cambios()
        return Cambios(
            photo_url=propia,
            foto_raices_url=raices_url,
            foto_raices_huella=raices_huella,
            foto_propia_url=propia,
            foto_origen="propio",
            invalidar_cache=propia != actual,
            motivo="propia_vigente",
        )

    if (
        actual == raices_url
        and estado.foto_origen == "nomina"
        and misma_url
        and huella_guardada == raices_huella
    ):
        return Cambios()
    return Cambios(
        photo_url=raices_url,
        foto_raices_url=raices_url,
        foto_raices_huella=raices_huella,
        foto_propia_url="",
        foto_origen="nomina",
        invalidar_cache=raices_url != actual,
        motivo="raices_vigente",
    )


def al_subir_propia(estado: EstadoFoto, url_propia: str) -> Cambios:
    """La persona sube una foto desde el correo: pasa a ser la efectiva hasta que Raíces cambie."""
    url_propia = _limpia(url_propia)
    return Cambios(
        photo_url=url_propia,
        foto_raices_url=_limpia(estado.foto_raices_url),
        foto_raices_huella=_limpia(estado.foto_raices_huella),
        foto_propia_url=url_propia,
        foto_origen="propio",
        invalidar_cache=url_propia != _limpia(estado.photo_url),
        motivo="subida_propia",
    )


def al_quitar_propia(estado: EstadoFoto) -> Cambios:
    """Quita la propia y vuelve a la de Raíces si existe (si no, sin foto)."""
    raices = _limpia(estado.foto_raices_url)
    return Cambios(
        photo_url=raices,
        foto_raices_url=raices,
        foto_raices_huella=_limpia(estado.foto_raices_huella),
        foto_propia_url="",
        foto_origen="nomina" if raices else "",
        invalidar_cache=raices != _limpia(estado.photo_url),
        motivo="quitar_propia",
    )


def huella_desde_cabeceras(cabeceras: dict, url: str) -> str:
    """Huella de la imagen a partir de las cabeceras HTTP de un HEAD (ETag; si no, tamaño+fecha; si no, la URL)."""
    bajas = {str(k).lower(): str(v).strip() for k, v in (cabeceras or {}).items()}
    etag = bajas.get("etag", "").strip('"W/ ')
    if etag:
        return "etag:" + etag
    tam = bajas.get("content-length", "")
    fecha = bajas.get("last-modified", "")
    if tam or fecha:
        return f"len:{tam}|mod:{fecha}"
    return "url:" + _limpia(url)
