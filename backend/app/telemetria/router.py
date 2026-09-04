"""Telemetría del cliente Windows Raíces (28/08/2026).
Cada instalación envía eventos (inicio de sesión, versión, módulos que abre, errores) y Tecnología los ve antes de que
la persona reporte. Sin sesión también se acepta (p. ej. fallo de login), identificando por `usuario` + `equipo`.
    POST /api/telemetria/app            {version, equipo, usuario?, evento, nivel?, detalle?, modulo?, url?, extra?}  (lote: {eventos:[…]})
    GET  /api/telemetria/app/recientes  ?horas=24&nivel=error&usuario=…   (solo administradores)
    GET  /api/telemetria/app/resumen    ?horas=24                          (solo administradores: por versión, por equipo, errores)
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.auth.dependencies import require_admin
from app.auth.jwt import decode_access_token

router = APIRouter()
DDL = """
CREATE TABLE IF NOT EXISTS app_telemetria (
    id         BIGSERIAL PRIMARY KEY,
    recibido   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ocurrido   TIMESTAMPTZ,
    usuario    TEXT NOT NULL DEFAULT '',
    equipo     TEXT NOT NULL DEFAULT '',
    version    TEXT NOT NULL DEFAULT '',
    ip         TEXT NOT NULL DEFAULT '',
    evento     TEXT NOT NULL,
    nivel      TEXT NOT NULL DEFAULT 'info',
    modulo     TEXT NOT NULL DEFAULT '',
    url        TEXT NOT NULL DEFAULT '',
    detalle    TEXT NOT NULL DEFAULT '',
    extra      JSONB
);
CREATE INDEX IF NOT EXISTS ix_app_telemetria_recibido ON app_telemetria (recibido DESC);
CREATE INDEX IF NOT EXISTS ix_app_telemetria_usuario ON app_telemetria (usuario, recibido DESC);
CREATE INDEX IF NOT EXISTS ix_app_telemetria_nivel ON app_telemetria (nivel, recibido DESC);
"""
NIVELES = ('debug', 'info', 'aviso', 'error', 'critico')


class Evento(BaseModel):
    evento: str = Field(..., max_length=80)          # p. ej. app_inicio, login_ok, login_fallo, sesion_sembrada, modulo_abierto, error_js, sin_conexion, actualizacion
    nivel: str = 'info'
    version: str = ''
    equipo: str = ''                                 # nombre del PC de Windows
    usuario: Optional[str] = None                    # correo (si no hay sesión aún)
    modulo: str = ''
    url: str = ''
    detalle: str = ''
    ocurrido: Optional[datetime] = None
    extra: Optional[dict[str, Any]] = None


class Lote(BaseModel):
    eventos: list[Evento]
    version: str = ''
    equipo: str = ''
    usuario: Optional[str] = None


async def asegurar_tabla(pool):
    await pool.execute(DDL)


def _usuario_de_cookie(request: Request) -> str:
    tok = request.cookies.get('access_token')
    if not tok:
        return ''
    try:
        d = decode_access_token(tok) or {}
        return (d.get('sub') or '').lower()
    except Exception:
        return ''


def _txt(v, n=4000) -> str:
    if v is None:
        return ''
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)
    return str(v)[:n]


def _fecha(v):
    if not v:
        return None
    try:
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v / (1000 if v > 1e11 else 1), tz=timezone.utc)
        return datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except Exception:
        return None


@router.post('/app', status_code=202)
async def recibir(request: Request):
    """Acepta un evento o un lote con CUALQUIER forma razonable. Nunca responde 500: lo que no se entiende se guarda
    como evento `telemetria_invalida` con el cuerpo crudo, para poder corregir el cliente."""
    try:
        cuerpo = await request.json()
    except Exception:
        crudo = (await request.body())[:4000]
        cuerpo = {'evento': 'telemetria_invalida', 'nivel': 'aviso', 'detalle': crudo.decode('utf-8', 'replace')}
    if isinstance(cuerpo, list):
        cuerpo = {'eventos': cuerpo}
    if not isinstance(cuerpo, dict):
        cuerpo = {'evento': 'telemetria_invalida', 'nivel': 'aviso', 'detalle': _txt(cuerpo)}
    eventos = cuerpo.get('eventos') if isinstance(cuerpo.get('eventos'), list) else [cuerpo]
    base = {k: cuerpo.get(k) for k in ('version', 'equipo', 'usuario', 'ip')}
    ip = request.headers.get('x-forwarded-for', request.client.host if request.client else '').split(',')[0].strip()
    u_cookie = _usuario_de_cookie(request)
    n = 0
    async with request.app.state.db_pool.acquire() as db:
        for e in eventos[:200]:
            if not isinstance(e, dict):
                e = {'evento': 'telemetria_invalida', 'nivel': 'aviso', 'detalle': _txt(e)}
            nivel = _txt(e.get('nivel') or 'info', 20).lower()
            if nivel not in NIVELES:
                nivel = 'info'
            usuario = _txt(e.get('usuario') or base.get('usuario') or u_cookie or '', 120).lower()
            extra = e.get('extra')
            if extra is not None and not isinstance(extra, dict):
                extra = {'valor': extra}
            try:
                await db.execute(
                    """INSERT INTO app_telemetria (ocurrido, usuario, equipo, version, ip, evento, nivel, modulo, url, detalle, extra)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb)""",
                    _fecha(e.get('ocurrido') or e.get('fecha') or e.get('ts')), usuario, _txt(e.get('equipo') or base.get('equipo'), 80),
                    _txt(e.get('version') or base.get('version'), 20), ip[:45], _txt(e.get('evento') or e.get('tipo') or 'sin_nombre', 80),
                    nivel, _txt(e.get('modulo'), 60), _txt(e.get('url'), 300), _txt(e.get('detalle') or e.get('mensaje') or e.get('message')),
                    json.dumps(extra, ensure_ascii=False, default=str) if extra else None)
                n += 1
            except Exception as ex:   # jamás tumbar al cliente por un evento raro
                logging.getLogger(__name__).warning('telemetria: evento no guardado: %s', ex)
    return {'ok': True, 'recibidos': n}


@router.get('/app/recientes')
async def recientes(request: Request, horas: int = Query(24, ge=1, le=720), nivel: str = Query(''), usuario: str = Query(''),
                    limite: int = Query(200, le=1000), user: str = Depends(require_admin)):
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    cond, params = ['recibido >= $1'], [desde]
    if nivel:
        params.append(nivel); cond.append(f'nivel = ${len(params)}')
    if usuario:
        params.append(f'%{usuario.lower()}%'); cond.append(f'usuario ILIKE ${len(params)}')
    params.append(limite)
    async with request.app.state.db_pool.acquire() as db:
        rows = await db.fetch(f"SELECT * FROM app_telemetria WHERE {' AND '.join(cond)} ORDER BY recibido DESC LIMIT ${len(params)}", *params)
    return [dict(r) | {'extra': (json.loads(r['extra']) if isinstance(r['extra'], str) else r['extra'])} for r in rows]


@router.get('/app/resumen')
async def resumen(request: Request, horas: int = Query(24, ge=1, le=720), user: str = Depends(require_admin)):
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    async with request.app.state.db_pool.acquire() as db:
        por_version = await db.fetch("SELECT version, count(DISTINCT equipo) equipos, count(DISTINCT usuario) usuarios, count(*) eventos FROM app_telemetria WHERE recibido >= $1 GROUP BY 1 ORDER BY 1 DESC", desde)
        errores = await db.fetch("SELECT usuario, equipo, version, evento, modulo, left(detalle, 200) detalle, max(recibido) ultimo, count(*) veces FROM app_telemetria WHERE recibido >= $1 AND nivel IN ('error','critico') GROUP BY 1,2,3,4,5,6 ORDER BY ultimo DESC LIMIT 100", desde)
        logins = await db.fetch("SELECT evento, count(*) FROM app_telemetria WHERE recibido >= $1 AND evento IN ('login_ok','login_fallo','sesion_sembrada','sesion_fallo') GROUP BY 1", desde)
        equipos = await db.fetch("SELECT equipo, usuario, max(version) version, max(recibido) ultimo FROM app_telemetria WHERE recibido >= $1 GROUP BY 1,2 ORDER BY ultimo DESC LIMIT 300", desde)
    return {'horas': horas, 'por_version': [dict(r) for r in por_version], 'errores': [dict(r) for r in errores],
            'logins': {r['evento']: r['count'] for r in logins}, 'equipos': [dict(r) for r in equipos]}


@router.get('/app/resumen-interno')
async def resumen_interno(request: Request, horas: int = Query(24, ge=1, le=720)):
    """Mismo resumen que /app/resumen, para el panel de soporte de Raices.

    Autenticacion server-to-server con el secreto compartido; nunca expone
    contenido de correos ni de chats: solo datos tecnicos de las apps.
    """
    import os
    secreto = os.getenv('NOTIF_SECRET', '')
    if not secreto or request.headers.get('X-Notif-Secret') != secreto:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Secreto invalido')
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    async with request.app.state.db_pool.acquire() as db:
        por_version = await db.fetch("SELECT version, count(DISTINCT equipo) equipos, count(DISTINCT usuario) usuarios, count(*) eventos FROM app_telemetria WHERE recibido >= $1 GROUP BY 1 ORDER BY 1 DESC", desde)
        errores = await db.fetch("SELECT usuario, equipo, version, evento, modulo, left(detalle, 200) detalle, max(recibido) ultimo, count(*) veces FROM app_telemetria WHERE recibido >= $1 AND nivel IN ('error','critico') GROUP BY 1,2,3,4,5,6 ORDER BY ultimo DESC LIMIT 100", desde)
        logins = await db.fetch("SELECT evento, count(*) FROM app_telemetria WHERE recibido >= $1 AND evento IN ('login_ok','login_fallo','sesion_sembrada','sesion_fallo') GROUP BY 1", desde)
        equipos = await db.fetch("SELECT equipo, usuario, max(version) version, max(recibido) ultimo FROM app_telemetria WHERE recibido >= $1 GROUP BY 1,2 ORDER BY ultimo DESC LIMIT 300", desde)
        socket_chat = await db.fetch("""
            SELECT equipo, max(usuario) usuario, count(*) veces,
                   max(left(detalle, 120)) motivo, max(recibido) ultimo
            FROM app_telemetria
            WHERE recibido >= $1 AND evento IN ('socket_chat_perdido', 'socket_chat_error',
                                     'socket_sin_chat_session')
            GROUP BY equipo ORDER BY veces DESC LIMIT 50
        """, desde)
        reconstrucciones = await db.fetch("""
            SELECT equipo, max(usuario) usuario, count(*) veces,
                   max(COALESCE(NULLIF(modulo, ''), 'la app')) modulo,
                   max(left(detalle, 120)) motivo, max(recibido) ultimo
            FROM app_telemetria
            WHERE recibido >= $1 AND evento = 'webview_reconstruido'
            GROUP BY equipo ORDER BY veces DESC LIMIT 50
        """, desde)
        # Equipos que dejaron de reportar (vistos alguna vez, callados desde hace >= 2 dias)
        callados = await db.fetch("""
            SELECT equipo, max(usuario) usuario, max(version) version, max(recibido) ultimo
            FROM app_telemetria GROUP BY equipo
            HAVING max(recibido) < NOW() - INTERVAL '2 days'
            ORDER BY ultimo DESC LIMIT 100
        """)
    def _fila(r):
        d = dict(r)
        for k, v in d.items():
            if isinstance(v, datetime):
                d[k] = v.isoformat()
        return d
    return {'horas': horas,
            'por_version': [_fila(r) for r in por_version],
            'errores': [_fila(r) for r in errores],
            'logins': {r['evento']: r['count'] for r in logins},
            'equipos': [_fila(r) for r in equipos],
            'callados': [_fila(r) for r in callados],
            'reconstrucciones': [_fila(r) for r in reconstrucciones],
            'socket_chat': [_fila(r) for r in socket_chat]}
