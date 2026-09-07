"""Receptor de informes CSP (`POST /api/csp-report`) acotado (N-4, auditoría del 03/09).

Antes: endpoint sin sesión que escribía en `security.log` TODO lo que llegara (hasta 2 KB por
informe, sin límite de ritmo). Como la cabecera `Report-To` manda al mismo sitio los informes de
red del navegador (NEL: `phase: application`, `elapsed_time`…), el log de seguridad recibía miles
de líneas diarias que no eran violaciones de CSP, y cualquiera podía inflarlo a voluntad.

Ahora:
- cuerpo de 16 KB como máximo (413 si es mayor);
- solo cuentan las violaciones de CSP (`csp-violation` del formato Reporting API o el objeto
  `csp-report` clásico); el resto (NEL, deprecation, intervention…) se descarta en silencio;
- límite por IP en Redis (30 informes/minuto → 429; sin Redis, fallo cerrado: se acepta pero no
  se registra);
- cada violación distinta (documento + directiva + recurso bloqueado) se registra una vez cada
  10 minutos; las repetidas solo suman en un contador;
- lo registrado es un resumen de campos conocidos, nunca el cuerpo crudo.
"""

import hashlib
import json
import logging

from fastapi import APIRouter, Request, Response

router = APIRouter(tags=["csp"])
log = logging.getLogger("security.csp")

MAX_BYTES = 16 * 1024
INFORMES_POR_MINUTO = 30
DEDUPE_SEG = 600
_CAMPOS = (
    "document-uri",
    "documentURL",
    "violated-directive",
    "effectiveDirective",
    "effective-directive",
    "blocked-uri",
    "blockedURL",
    "source-file",
    "sourceFile",
    "line-number",
    "lineNumber",
    "disposition",
)


def extraer_violaciones(cuerpo: bytes) -> list[dict]:
    """Devuelve solo las violaciones de CSP contenidas en `cuerpo` (0..n), normalizadas a un dict
    con los campos conocidos. Cualquier otro tipo de informe se ignora."""
    try:
        datos = json.loads(cuerpo.decode("utf-8", errors="replace") or "null")
    except ValueError:
        return []
    candidatos = datos if isinstance(datos, list) else [datos]
    salida = []
    for c in candidatos:
        if not isinstance(c, dict):
            continue
        if isinstance(c.get("csp-report"), dict):  # formato clásico
            cuerpo_v = c["csp-report"]
        elif c.get("type") == "csp-violation" and isinstance(c.get("body"), dict):
            cuerpo_v = c["body"]
        else:
            continue
        salida.append({k: str(cuerpo_v[k])[:300] for k in _CAMPOS if k in cuerpo_v})
    return salida


def huella(v: dict) -> str:
    """Identidad de una violación: documento + directiva + recurso bloqueado."""
    doc = v.get("document-uri") or v.get("documentURL") or ""
    dir_ = (
        v.get("violated-directive")
        or v.get("effectiveDirective")
        or v.get("effective-directive")
        or ""
    )
    blq = v.get("blocked-uri") or v.get("blockedURL") or ""
    return hashlib.sha256(f"{doc}|{dir_}|{blq}".encode()).hexdigest()[:24]


async def _permitido(redis, ip: str) -> bool:
    try:
        clave = f"csp:rl:{ip}"
        n = await redis.incr(clave)
        if n == 1:
            await redis.expire(clave, 60)
        return n <= INFORMES_POR_MINUTO
    except Exception:
        return False  # sin Redis no se registra nada: fallo cerrado


async def _nueva(redis, h: str) -> bool:
    try:
        return bool(await redis.set(f"csp:vista:{h}", "1", ex=DEDUPE_SEG, nx=True))
    except Exception:
        return False


@router.post("/api/csp-report")
async def csp_report(request: Request):
    content_type = request.headers.get("content-type", "")
    if (
        "csp-report" not in content_type
        and "json" not in content_type
        and "reports" not in content_type
    ):
        return Response(status_code=400)
    cuerpo = await request.body()
    if len(cuerpo) > MAX_BYTES:
        return Response(status_code=413)
    violaciones = extraer_violaciones(cuerpo)
    if not violaciones:
        return {"status": "ok"}
    redis = getattr(request.app.state, "redis", None)
    ip = request.headers.get("x-real-ip") or (
        request.client.host if request.client else "?"
    )
    if redis is None or not await _permitido(redis, ip):
        return Response(status_code=429) if redis is not None else {"status": "ok"}
    for v in violaciones:
        h = huella(v)
        if await _nueva(redis, h):
            log.warning(
                "CSP_VIOLACION huella=%s %s", h, json.dumps(v, ensure_ascii=False)
            )
        else:
            try:
                await redis.incr(f"csp:repetida:{h}")
                await redis.expire(f"csp:repetida:{h}", DEDUPE_SEG)
            except Exception:
                pass
    return {"status": "ok"}
