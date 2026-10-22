"""Configuración de Redis: `redis://` simple (lo de serie) o Redis Sentinel.

Formas aceptadas:

1. REDIS_URL=redis://:clave@127.0.0.1:6379/0 (o rediss://, unix://): un solo Redis.
2. REDIS_URL=redis+sentinel://:clave@centinela1:26379,centinela2:26379/mymaster/0
   La clave de la URL es la del Redis principal; la de los centinelas, si la tienen,
   va en `?sentinel_password=...` o en REDIS_SENTINEL_PASSWORD.
3. REDIS_SENTINELS=centinela1:26379,centinela2:26379 (+ REDIS_SENTINEL_MASTER y
   REDIS_SENTINEL_PASSWORD). La clave y la base del Redis principal se toman de REDIS_URL
   si está definida (su host se ignora).

Con Sentinel el cliente pregunta a los centinelas quién es el principal y, si cambia
(conmutación por error), se reconecta al nuevo sin reiniciar el servicio.
"""

from dataclasses import dataclass, field
from urllib.parse import parse_qs, unquote, urlsplit


@dataclass
class ConfigRedis:
    modo: str = "simple"  # simple | sentinel
    url: str = ""
    centinelas: list[tuple[str, int]] = field(default_factory=list)
    principal: str = "mymaster"
    db: int = 0
    clave: str | None = None
    clave_centinela: str | None = None


def _hosts(texto: str, puerto_defecto: int = 26379) -> list[tuple[str, int]]:
    hosts = []
    for parte in (texto or "").split(","):
        parte = parte.strip()
        if not parte:
            continue
        if parte.startswith("["):  # IPv6 entre corchetes: [::1]:26379
            host, _, resto = parte[1:].partition("]")
            puerto = resto.lstrip(":")
        else:
            host, _, puerto = parte.rpartition(":") if ":" in parte else (parte, "", "")
        hosts.append((host, int(puerto) if puerto else puerto_defecto))
    return hosts


def _clave_y_db(url: str) -> tuple[str | None, int]:
    """Clave y número de base de una URL redis:// (el host no importa aquí)."""
    if not url:
        return None, 0
    p = urlsplit(url)
    clave = unquote(p.password) if p.password else None
    ruta = (p.path or "").strip("/")
    return clave, int(ruta) if ruta.isdigit() else 0


def leer_config(settings) -> ConfigRedis:
    url = (settings.redis_url or "").strip()
    centinelas_txt = (getattr(settings, "redis_sentinels", "") or "").strip()
    clave_cent = (
        getattr(settings, "redis_sentinel_password", "") or ""
    ).strip() or None

    if url.startswith("redis+sentinel://"):
        resto = url[len("redis+sentinel://") :]
        resto, _, consulta = resto.partition("?")
        auth, arroba, resto_hosts = resto.rpartition("@")
        if not arroba:
            auth, resto_hosts = "", resto
        hosts_txt, _, ruta = resto_hosts.partition("/")
        partes = [x for x in ruta.split("/") if x]
        principal = (
            partes[0] if partes else (settings.redis_sentinel_master or "mymaster")
        )
        db = int(partes[1]) if len(partes) > 1 and partes[1].isdigit() else 0
        clave = (
            unquote(auth.partition(":")[2]) if ":" in auth else (unquote(auth) or None)
        )
        q = parse_qs(consulta)
        if q.get("sentinel_password"):
            clave_cent = q["sentinel_password"][0]
        cfg = ConfigRedis(
            modo="sentinel",
            centinelas=_hosts(hosts_txt),
            principal=principal,
            db=db,
            clave=clave or None,
            clave_centinela=clave_cent,
        )
    elif centinelas_txt:
        clave, db = _clave_y_db(url)
        cfg = ConfigRedis(
            modo="sentinel",
            centinelas=_hosts(centinelas_txt),
            principal=(settings.redis_sentinel_master or "mymaster").strip(),
            db=db,
            clave=clave,
            clave_centinela=clave_cent,
        )
    else:
        return ConfigRedis(modo="simple", url=url)

    if not cfg.centinelas:
        raise ValueError(
            "Redis Sentinel configurado sin ningún centinela (host:puerto)."
        )
    return cfg


def crear_cliente(cfg: ConfigRedis, **kw):
    """Cliente asíncrono de redis-py para la configuración dada."""
    import redis.asyncio as aioredis

    kw.setdefault("decode_responses", True)
    if cfg.modo == "simple":
        return aioredis.from_url(cfg.url, **kw)
    from redis.asyncio.sentinel import Sentinel

    centinela = Sentinel(
        cfg.centinelas,
        sentinel_kwargs=(
            {"password": cfg.clave_centinela} if cfg.clave_centinela else None
        ),
        socket_timeout=kw.pop("socket_timeout", 5),
    )
    return centinela.master_for(cfg.principal, db=cfg.db, password=cfg.clave, **kw)
