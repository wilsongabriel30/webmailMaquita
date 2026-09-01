"""API JSON de T-34 (prefijo /api/tareas; misma sesión que el resto del correo)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.dependencies import get_current_user, require_admin
from app.tareas.esquemas import (CambioEstado, ComentarioNuevo, ComentarioOut, EscalamientoConfig, Rechazo,
                                 TareaAsignar, TareaEditar, TareaOut)
from app.tareas.servicio import servicio_tareas as svc, a_salida

router = APIRouter()


def _db(r: Request):
    return r.app.state.db_pool


def _redis(r: Request):
    return r.app.state.redis


def _http(e):
    if isinstance(e, LookupError):
        return HTTPException(404, str(e))
    if isinstance(e, PermissionError):
        return HTTPException(403, str(e))
    return HTTPException(400, str(e))


@router.get('/mis', response_model=list[TareaOut])
async def mis(request: Request, completadas: bool = False, user: str = Depends(get_current_user)):
    return await svc.mis(_db(request), user, completadas)


@router.get('/asignadas-por-mi', response_model=list[TareaOut])
async def asignadas_por_mi(request: Request, completadas: bool = False, user: str = Depends(get_current_user)):
    return await svc.asignadas_por_mi(_db(request), user, completadas)


@router.get('/mi-dia', response_model=list[TareaOut])
async def mi_dia(request: Request, user: str = Depends(get_current_user)):
    return await svc.mi_dia(_db(request), user)


@router.get('/personas')
async def personas(request: Request, q: str = Query(''), user: str = Depends(get_current_user)):
    return [dict(r) for r in await svc.personas(_db(request), q)]


@router.get('/escalamiento')
async def escalamiento_listar(request: Request, user: str = Depends(get_current_user)):
    return [dict(r) for r in await svc.escalamiento_listar(_db(request))]


@router.put('/escalamiento')
async def escalamiento_guardar(cfg: EscalamientoConfig, request: Request, user: str = Depends(require_admin)):
    return dict(await svc.escalamiento_guardar(_db(request), user, cfg))


@router.delete('/escalamiento/{departamento}', status_code=204)
async def escalamiento_borrar(departamento: str, request: Request, user: str = Depends(require_admin)):
    await svc.escalamiento_borrar(_db(request), departamento)


@router.post('/asignar', response_model=TareaOut, status_code=201)
async def asignar(d: TareaAsignar, request: Request, user: str = Depends(get_current_user)):
    try:
        return await svc.asignar(_db(request), _redis(request), user, d)
    except Exception as e:
        raise _http(e)


@router.get('/{tarea_id}', response_model=TareaOut)
async def obtener(tarea_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return a_salida(await svc.obtener(_db(request), tarea_id, user))
    except Exception as e:
        raise _http(e)


@router.patch('/{tarea_id}', response_model=TareaOut)
async def editar(tarea_id: uuid.UUID, d: TareaEditar, request: Request, user: str = Depends(get_current_user)):
    try:
        return await svc.editar(_db(request), _redis(request), user, tarea_id, d)
    except Exception as e:
        raise _http(e)


@router.delete('/{tarea_id}', status_code=204)
async def eliminar(tarea_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        await svc.eliminar(_db(request), user, tarea_id)
    except Exception as e:
        raise _http(e)


@router.patch('/{tarea_id}/estado', response_model=TareaOut)
async def estado(tarea_id: uuid.UUID, d: CambioEstado, request: Request, user: str = Depends(get_current_user)):
    try:
        return await svc.cambiar_estado(_db(request), _redis(request), user, tarea_id, d.estado)
    except Exception as e:
        raise _http(e)


@router.post('/{tarea_id}/completar', response_model=TareaOut)
async def completar(tarea_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await svc.completar(_db(request), _redis(request), user, tarea_id)
    except Exception as e:
        raise _http(e)


@router.post('/{tarea_id}/aceptar', response_model=TareaOut)
async def aceptar(tarea_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await svc.aceptar(_db(request), user, tarea_id)
    except Exception as e:
        raise _http(e)


@router.post('/{tarea_id}/rechazar', response_model=TareaOut)
async def rechazar(tarea_id: uuid.UUID, d: Rechazo, request: Request, user: str = Depends(get_current_user)):
    try:
        return await svc.rechazar(_db(request), user, tarea_id, d.motivo)
    except Exception as e:
        raise _http(e)


@router.get('/{tarea_id}/comentarios', response_model=list[ComentarioOut])
async def comentarios(tarea_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return [_com(r) for r in await svc.comentarios(_db(request), user, tarea_id)]
    except Exception as e:
        raise _http(e)


@router.post('/{tarea_id}/comentarios', response_model=ComentarioOut, status_code=201)
async def comentar(tarea_id: uuid.UUID, d: ComentarioNuevo, request: Request, user: str = Depends(get_current_user)):
    try:
        return _com(await svc.comentar(_db(request), user, tarea_id, d.texto))
    except Exception as e:
        raise _http(e)


def _com(r):
    import json
    m = r['menciones']
    return ComentarioOut(id=r['id'], autor=r['autor'], texto=r['texto'], menciones=json.loads(m) if isinstance(m, str) else list(m or []),
                         creado_en=r['creado_en'])
