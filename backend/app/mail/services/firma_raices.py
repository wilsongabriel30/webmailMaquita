"""Cliente del servicio de firma de PDF de Raíces (09/11/2026).

El correo no firma PDF por su cuenta: los certificados .p12 de cada persona viven en Raíces
(Herramientas → Editor PDF → Firma digital). Este módulo llama a las rutas de servicio
`/api/pdf/firma-servicio/*` de Raíces con un token propio y el correo de la persona, y
devuelve lo que Raíces conteste. Variables del .env:

  RAICES_FIRMA_URL    base de Raíces (obligatoria en producción; por defecto https://raices.example.org)
  RAICES_FIRMA_TOKEN  el mismo valor que CORREO_FIRMA_SERVICIO_TOKEN en el .env de Raíces
                      (mínimo 32 caracteres; sin él la función se declara no configurada)
"""

from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("maquita.webmail.firma_pdf")

TIEMPO_SEGUNDOS = 90.0
LARGO_MINIMO_TOKEN = 32


class FirmaNoConfigurada(Exception):
    """Falta RAICES_FIRMA_TOKEN (o es demasiado corto)."""


class ErrorFirma(Exception):
    """Raíces respondió con un error: `status` y `cuerpo` (dict con exito/mensaje/codigo…)."""

    def __init__(self, status: int, cuerpo: dict):
        super().__init__(cuerpo.get("mensaje") or f"HTTP {status}")
        self.status = status
        self.cuerpo = cuerpo


def url_base() -> str:
    return (
        (os.getenv("RAICES_FIRMA_URL") or "https://raices.example.org")
        .strip()
        .rstrip("/")
    )


def _token() -> str:
    tok = (os.getenv("RAICES_FIRMA_TOKEN") or "").strip()
    return tok if len(tok) >= LARGO_MINIMO_TOKEN else ""


def configurado() -> bool:
    return bool(_token())


def _cabeceras() -> dict:
    tok = _token()
    if not tok:
        raise FirmaNoConfigurada()
    return {
        "Authorization": f"Bearer {tok}",
        "Accept": "application/json, application/pdf",
    }


def _cuerpo_error(r: httpx.Response) -> dict:
    try:
        d = r.json()
        return d if isinstance(d, dict) else {"mensaje": str(d)}
    except ValueError:
        return {"mensaje": (r.text or f"HTTP {r.status_code}")[:200]}


async def certificados(correo: str) -> dict:
    """Estado de la persona en Raíces: usuario, consentimiento y certificados guardados."""
    async with httpx.AsyncClient(timeout=20.0) as cliente:
        r = await cliente.get(
            f"{url_base()}/api/pdf/firma-servicio/certificados",
            params={"correo": correo},
            headers=_cabeceras(),
        )
    if r.status_code != 200:
        raise ErrorFirma(r.status_code, _cuerpo_error(r))
    return r.json()


async def aceptar_consentimiento(correo: str, version: str, ip: str) -> dict:
    """La persona acepta desde el correo el aviso de privacidad / términos de la firma (queda en Raíces)."""
    async with httpx.AsyncClient(timeout=20.0) as cliente:
        r = await cliente.post(
            f"{url_base()}/api/pdf/firma-servicio/consentimiento",
            data={
                "correo": correo,
                "version": version or "",
                "ip": ip or "",
                "acepta": "1",
            },
            headers=_cabeceras(),
        )
    if r.status_code != 200:
        raise ErrorFirma(r.status_code, _cuerpo_error(r))
    return r.json()


async def firmar(
    correo: str,
    nombre_pdf: str,
    pdf: bytes,
    campos: dict,
    p12: tuple[str, bytes] | None = None,
) -> tuple[bytes, str, dict]:
    """Firma `pdf` en Raíces y devuelve (bytes firmados, nombre sugerido, extras).

    `extras` trae `certificado_guardado` (id) y `password_guardada` cuando se pidió guardar el .p12 subido.

    `campos`: certificado_id, password, pagina, posicion, razon, ubicacion, guardar, guardar_password
    (cadenas; vacías se omiten).
    `p12`: (nombre, bytes) de un certificado subido en el momento, en vez de uno guardado.
    """
    datos = {"correo": correo}
    datos.update({k: str(v) for k, v in campos.items() if v not in (None, "")})
    archivos = {"archivo": (nombre_pdf or "documento.pdf", pdf, "application/pdf")}
    if p12:
        archivos["certificado"] = (
            p12[0] or "certificado.p12",
            p12[1],
            "application/x-pkcs12",
        )
    async with httpx.AsyncClient(timeout=TIEMPO_SEGUNDOS) as cliente:
        r = await cliente.post(
            f"{url_base()}/api/pdf/firma-servicio/firmar",
            data=datos,
            files=archivos,
            headers=_cabeceras(),
        )
    if r.status_code != 200 or not r.content.startswith(b"%PDF"):
        raise ErrorFirma(
            r.status_code if r.status_code != 200 else 502, _cuerpo_error(r)
        )
    base = (nombre_pdf or "documento.pdf").rsplit(".", 1)[0] or "documento"
    extras = {
        "certificado_guardado": r.headers.get("X-Certificado-Guardado", ""),
        "password_guardada": r.headers.get("X-Certificado-Password-Guardada", "")
        == "1",
    }
    return r.content, base + "_firmado.pdf", extras
