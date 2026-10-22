"""`/api/v1/...` como alias estable de `/api/...`.

Las rutas de siempre (`/api/mail/...`, `/api/auth/...`) no cambian. Quien integre algo
nuevo puede fijarse a `/api/v1/...`: es la misma API, con la promesa de que no se rompe
sin pasar antes por una v2 anunciada (ver docs/SOPORTE-Y-VERSIONES.md). Las respuestas
servidas por el alias llevan la cabecera `API-Version: 1`.

Es un middleware ASGI puro (sin BaseHTTPMiddleware): reescribe la ruta antes de que la
vean los demás middlewares y el enrutador, y vale también para WebSocket.
"""

PREFIJO_V1 = "/api/v1"
PREFIJO_V1_B = PREFIJO_V1.encode()


def ruta_sin_version(ruta: str) -> str | None:
    """'/api/v1/mail/x' → '/api/mail/x'; None si la ruta no es del alias."""
    if ruta == PREFIJO_V1 or ruta.startswith(PREFIJO_V1 + "/"):
        return "/api" + ruta[len(PREFIJO_V1) :]
    return None


class AliasApiV1:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") not in ("http", "websocket"):
            return await self.app(scope, receive, send)
        nueva = ruta_sin_version(scope.get("path", ""))
        if nueva is None:
            return await self.app(scope, receive, send)
        scope = dict(scope)
        scope["path"] = nueva
        raw = scope.get("raw_path")
        if isinstance(raw, (bytes, bytearray)) and raw.startswith(PREFIJO_V1_B):
            scope["raw_path"] = b"/api" + bytes(raw[len(PREFIJO_V1_B) :])

        async def enviar(mensaje):
            if mensaje.get("type") == "http.response.start":
                cabeceras = list(mensaje.get("headers", []))
                cabeceras.append((b"api-version", b"1"))
                mensaje = {**mensaje, "headers": cabeceras}
            await send(mensaje)

        return await self.app(scope, receive, enviar)
