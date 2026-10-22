"""«http2 on;» solo existe desde nginx 1.25.1 (Debian 12 trae la 1.22, Ubuntu 22.04 la 1.18): en un nginx anterior se
escribe la forma antigua («listen 443 ssl http2;»), que nginx -t sí acepta. Lo mismo hace
deploy/tools/nginx-http2-compatible.sh con los archivos que instalan los guiones."""

import functools
import re
import subprocess

MINIMA = (1, 25, 1)
_RE_VERSION = re.compile(r"nginx/(\d+)\.(\d+)\.(\d+)")
_RE_HTTP2 = re.compile(r"^[ \t]*http2[ \t]+on;[ \t]*\n", re.M)
_RE_LISTEN = re.compile(r"^([ \t]*listen[ \t]+(?:\[::\]:)?443[ \t]+ssl);", re.M)


@functools.lru_cache(maxsize=1)
def version():
    """La versión de nginx como tupla, o None si no se puede saber."""
    try:
        r = subprocess.run(["nginx", "-v"], capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    m = _RE_VERSION.search((r.stderr or "") + (r.stdout or ""))
    return tuple(int(x) for x in m.groups()) if m else None


def adaptar(texto, version_nginx=None):
    """El texto tal cual con nginx 1.25.1 o posterior (o si no se sabe); si no, con la forma antigua."""
    v = version_nginx if version_nginx is not None else version()
    if v is None or v >= MINIMA or not _RE_HTTP2.search(texto):
        return texto
    return _RE_LISTEN.sub(r"\1 http2;", _RE_HTTP2.sub("", texto))
