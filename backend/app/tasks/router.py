"""FastAPI router for Tasks — Microsoft To Do style + backward-compat Kanban."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user
from app.tasks import acceso, adjuntos, correo_marcado, repeticion
from app.tasks.rutas_listas import router as listas_router
from app.tasks.rutas_tareas import router as f3_router
from app.tasks.rutas_vistas import router as vistas_router
from app.tasks.schemas import (
    ActivityOut,
    BoardCreate,
    BoardFull,
    BoardOut,
    BoardUpdate,
    CardCreate,
    CardMove,
    CardOut,
    CardUpdate,
    LabelCreate,
    LabelOut,
    ListCreate,
    ListOut,
    MemberAdd,
    MemberOut,
)
from app.tasks.service import task_service
from app.tasks.task_calendar_sync import (
    notify_task_assignment,
    remove_task_from_calendar,
    sync_task_to_calendar,
)

_sync_logger = logging.getLogger("task_sync")

router = APIRouter()
router.include_router(listas_router)  # listas propias, grupos y orden
router.include_router(vistas_router)  # listas inteligentes, «Mi día» y conteos
router.include_router(f3_router)  # buscar, mover a otra lista y adjuntos


def _db(request: Request):
    return request.app.state.db_pool


def _redis(request: Request):
    return request.app.state.redis


# ════════════════════════════════════════════════
#  Microsoft To Do style endpoints
# ════════════════════════════════════════════════

# Listas propias, grupos y orden: rutas_listas.py.


# ── Tasks in lists ──


@router.post("/lists/{list_id}/tasks", response_model=CardOut, status_code=201)
async def todo_create_task_in_list(
    list_id: uuid.UUID,
    data: CardCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        result = await task_service.create_task(_db(request), user, list_id, data)
        # Sincronizar con calendario y notificar
        try:
            rd = result.model_dump()
            await sync_task_to_calendar(_db(request), _redis(request), rd, user)
            if data.assigned_to:
                await notify_task_assignment(
                    _redis(request), rd, data.assigned_to, "assigned", user
                )
        except Exception as e:
            _sync_logger.warning("Sync error (create_in_list): %s", e)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/tasks", response_model=CardOut, status_code=201)
async def todo_create_task_default(
    data: CardCreate, request: Request, user: str = Depends(get_current_user)
):
    """Create task in default 'Tareas' list."""
    result = await task_service.create_task(_db(request), user, None, data)
    # Sincronizar con calendario y notificar
    try:
        rd = result.model_dump()
        await sync_task_to_calendar(_db(request), _redis(request), rd, user)
        if data.assigned_to:
            await notify_task_assignment(
                _redis(request), rd, data.assigned_to, "assigned", user
            )
    except Exception as e:
        _sync_logger.warning("Sync error (create_default): %s", e)
    return result


# ── Task operations ──


@router.patch("/tasks/{card_id}", response_model=CardOut)
async def todo_update_task(
    card_id: uuid.UUID,
    data: CardUpdate,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        result = await task_service.update_card(_db(request), user, card_id, data)
        if result.completed and data.completed:
            await repeticion.tras_completar(_db(request), user, card_id)
        if data.completed is not None:
            enlace = await correo_marcado.vinculo(_db(request), card_id, user)
            await correo_marcado.poner_bandera(
                request, user, enlace, not result.completed
            )
        rd = result.model_dump()
        try:
            # Si se cambio fecha o asignado, sincronizar calendario
            date_changed = "due_date" in data.model_fields_set
            assigned_changed = "assigned_to" in data.model_fields_set
            if date_changed or assigned_changed:
                if rd.get("due_date"):
                    await sync_task_to_calendar(_db(request), _redis(request), rd, user)
                elif date_changed:
                    # Se quito la fecha — eliminar evento del calendario
                    assigned = rd.get("assigned_to") or user
                    await remove_task_from_calendar(_db(request), rd, assigned)
            if assigned_changed and data.assigned_to:
                await notify_task_assignment(
                    _redis(request), rd, data.assigned_to, "updated", user
                )
        except Exception as e:
            _sync_logger.warning("Sync error (update): %s", e)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/tasks/{card_id}/toggle", response_model=CardOut)
async def todo_toggle_task(
    card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        result = await task_service.toggle_card(_db(request), user, card_id)
        if result.completed:
            await repeticion.tras_completar(_db(request), user, card_id)
        enlace = await correo_marcado.vinculo(_db(request), card_id, user)
        await correo_marcado.poner_bandera(request, user, enlace, not result.completed)
        # Si se completo, eliminar del calendario; si se reabrio, re-sincronizar
        try:
            rd = result.model_dump()
            assigned = rd.get("assigned_to") or rd.get("created_by", user)
            if rd.get("completed"):
                await remove_task_from_calendar(_db(request), rd, assigned)
                await notify_task_assignment(
                    _redis(request), rd, assigned, "completed", user
                )
            else:
                await sync_task_to_calendar(_db(request), _redis(request), rd, user)
        except Exception as e:
            _sync_logger.warning("Sync error (toggle): %s", e)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/tasks/{card_id}/important", response_model=CardOut)
async def todo_toggle_important(
    card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        return await task_service.toggle_important(_db(request), user, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/tasks/{card_id}", status_code=204)
async def todo_delete_task(
    card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        # Leer tarea antes de eliminar para poder limpiar calendario
        db = _db(request)
        task_row = await db.fetchrow("SELECT * FROM task_cards WHERE id = $1", card_id)
        enlace = await correo_marcado.vinculo(db, card_id, user)
        carpetas = await adjuntos.con_adjuntos(db, card_id=card_id)
        await task_service.delete_card(db, user, card_id)
        await adjuntos.borrar_carpetas(carpetas)
        await correo_marcado.poner_bandera(request, user, enlace, False)
        # Limpiar calendario
        if task_row and task_row.get("due_date"):
            try:
                assigned = task_row.get("assigned_to") or user
                await remove_task_from_calendar(db, dict(task_row), assigned)
            except Exception as e:
                _sync_logger.warning("Sync error (delete): %s", e)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ════════════════════════════════════════════════
#  Legacy Kanban endpoints (backward compat)
# ════════════════════════════════════════════════

# Boards


@router.get("/boards", response_model=list[BoardOut])
async def list_boards(request: Request, user: str = Depends(get_current_user)):
    return await task_service.list_boards(_db(request), user)


@router.post("/boards", response_model=BoardOut, status_code=201)
async def create_board(
    data: BoardCreate, request: Request, user: str = Depends(get_current_user)
):
    return await task_service.create_board(_db(request), user, data)


@router.patch("/boards/{board_id}", response_model=BoardOut)
async def update_board(
    board_id: uuid.UUID,
    data: BoardUpdate,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        return await task_service.update_board(_db(request), user, board_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/boards/{board_id}", status_code=204)
async def delete_board(
    board_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        await task_service.delete_board(_db(request), user, board_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/boards/{board_id}/full", response_model=BoardFull)
async def get_board_full(
    board_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        return await task_service.get_board_full(_db(request), user, board_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Members


@router.get("/boards/{board_id}/members", response_model=list[MemberOut])
async def list_members(
    board_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        return await task_service.list_members(_db(request), user, board_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/boards/{board_id}/members", response_model=MemberOut, status_code=201)
async def add_member(
    board_id: uuid.UUID,
    data: MemberAdd,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        return await task_service.add_member(_db(request), user, board_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/boards/{board_id}/members/{member_email}", status_code=204)
async def remove_member(
    board_id: uuid.UUID,
    member_email: str,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        await task_service.remove_member(_db(request), user, board_id, member_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# Activity


@router.get("/boards/{board_id}/activity", response_model=list[ActivityOut])
async def list_activity(
    board_id: uuid.UUID,
    request: Request,
    limit: int = Query(50, le=200),
    user: str = Depends(get_current_user),
):
    try:
        return await task_service.list_activity(_db(request), user, board_id, limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Legacy Lists (under boards)


@router.get("/boards/{board_id}/lists", response_model=list[ListOut])
async def list_lists(
    board_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        return await task_service.list_lists(_db(request), user, board_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/boards/{board_id}/lists", response_model=ListOut, status_code=201)
async def create_list(
    board_id: uuid.UUID,
    data: ListCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        return await task_service.create_list(_db(request), user, board_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Legacy Cards (under lists)


@router.get("/lists/{list_id}/cards", response_model=list[CardOut])
async def list_cards(
    list_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        return await task_service.list_cards(_db(request), user, list_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/lists/{list_id}/cards", response_model=CardOut, status_code=201)
async def create_card(
    list_id: uuid.UUID,
    data: CardCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        return await task_service.create_card(_db(request), user, list_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/cards/{card_id}", response_model=CardOut)
async def update_card(
    card_id: uuid.UUID,
    data: CardUpdate,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        return await task_service.update_card(_db(request), user, card_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/cards/{card_id}/move", response_model=CardOut)
async def move_card(
    card_id: uuid.UUID,
    data: CardMove,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        return await task_service.move_card(_db(request), user, card_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.patch("/cards/{card_id}/toggle", response_model=CardOut)
async def toggle_card(
    card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        return await task_service.toggle_card(_db(request), user, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/cards/{card_id}", status_code=204)
async def delete_card(
    card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        await task_service.delete_card(_db(request), user, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# Labels


@router.get("/boards/{board_id}/labels", response_model=list[LabelOut])
async def list_labels(
    board_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        return await task_service.list_labels(_db(request), user, board_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/boards/{board_id}/labels", response_model=LabelOut, status_code=201)
async def create_label(
    board_id: uuid.UUID,
    data: LabelCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    try:
        return await task_service.create_label(_db(request), user, board_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/labels/{label_id}", status_code=204)
async def delete_label(
    label_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    try:
        await task_service.delete_label(_db(request), user, label_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ── Subtasks / Checklist Steps ────────────────────────────


class StepCreate(BaseModel):
    title: str


class StepUpdate(BaseModel):
    title: str | None = None
    completed: bool | None = None
    position: int | None = None


class StepOut(BaseModel):
    id: uuid.UUID
    card_id: uuid.UUID
    title: str
    completed: bool
    position: int
    created_at: datetime


StepCreate.model_rebuild()
StepUpdate.model_rebuild()
StepOut.model_rebuild()


async def _verify_card_access(db, card_id, user: str):
    """La persona ve la lista de la tarea (propia o compartida)."""
    if not await acceso.puede_ver_tarea(db, card_id, user):
        raise HTTPException(403, "No tiene acceso a esta tarea")


async def _verify_step_access(db, step_id, user: str):
    """Antes no se comprobaba: con el id de un paso se podía editar o borrar el de otra persona."""
    card_id = await db.fetchval("SELECT card_id FROM task_steps WHERE id = $1", step_id)
    if card_id is None:
        raise HTTPException(404, "Paso no encontrado")
    await _verify_card_access(db, card_id, user)


_steps_table_ready = False


async def _ensure_steps_table(db):
    global _steps_table_ready
    if _steps_table_ready:
        return
    try:
        # Serializado entre workers con un bloqueo de transacción: el de sesión pedido con
        # pool.execute() podía quedar prendido de otra conexión del pool (y con PgBouncer,
        # de otra conexión del servidor) y no soltarse nunca.
        from app.escala.ddl import ddl_serializado

        async with ddl_serializado(db, 88888) as con:
            await con.execute("""
                CREATE TABLE IF NOT EXISTS task_steps (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    card_id UUID NOT NULL REFERENCES task_cards(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    completed BOOLEAN NOT NULL DEFAULT FALSE,
                    position INT NOT NULL DEFAULT 0,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
        _steps_table_ready = True
    except Exception:
        _steps_table_ready = True  # Table likely exists already


@router.get("/cards/{card_id}/steps", response_model=list[StepOut])
async def list_steps(
    card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    await _ensure_steps_table(db)
    await _verify_card_access(db, card_id, user)
    rows = await db.fetch(
        "SELECT * FROM task_steps WHERE card_id = $1 ORDER BY position, created_at",
        card_id,
    )
    return [StepOut(**dict(r)) for r in rows]


@router.post("/cards/{card_id}/steps", response_model=StepOut, status_code=201)
async def create_step(
    card_id: uuid.UUID,
    data: StepCreate,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    await _ensure_steps_table(db)
    await _verify_card_access(db, card_id, user)
    max_pos = await db.fetchval(
        "SELECT COALESCE(MAX(position), -1) FROM task_steps WHERE card_id = $1", card_id
    )
    row = await db.fetchrow(
        "INSERT INTO task_steps (card_id, title, position) VALUES ($1, $2, $3) RETURNING *",
        card_id,
        data.title.strip(),
        (max_pos or 0) + 1,
    )
    return StepOut(**dict(row))


@router.put("/steps/{step_id}", response_model=StepOut)
async def update_step(
    step_id: uuid.UUID,
    data: StepUpdate,
    request: Request,
    user: str = Depends(get_current_user),
):
    db = _db(request)
    await _ensure_steps_table(db)
    await _verify_step_access(db, step_id, user)
    sets, vals, idx = [], [], 1
    if data.title is not None:
        sets.append(f"title = ${idx}")
        vals.append(data.title.strip())
        idx += 1
    if data.completed is not None:
        sets.append(f"completed = ${idx}")
        vals.append(data.completed)
        idx += 1
    if data.position is not None:
        sets.append(f"position = ${idx}")
        vals.append(data.position)
        idx += 1
    if not sets:
        raise HTTPException(400, "Nada que actualizar")
    vals.append(step_id)
    row = await db.fetchrow(
        f"UPDATE task_steps SET {", ".join(sets)} WHERE id = ${idx} RETURNING *", *vals
    )
    if not row:
        raise HTTPException(404, "Paso no encontrado")
    return StepOut(**dict(row))


@router.delete("/steps/{step_id}", status_code=204)
async def delete_step(
    step_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)
):
    db = _db(request)
    await _ensure_steps_table(db)
    await _verify_step_access(db, step_id, user)
    result = await db.execute("DELETE FROM task_steps WHERE id = $1", step_id)
    if result == "DELETE 0":
        raise HTTPException(404, "Paso no encontrado")
