"""FastAPI router for Tasks — Microsoft To Do style + backward-compat Kanban."""
from __future__ import annotations

import uuid
from datetime import datetime
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.auth.dependencies import get_current_user
from app.tasks.schemas import (
    ActivityOut,
    BoardCreate, BoardFull, BoardOut, BoardUpdate,
    CardCreate, CardMove, CardOut, CardUpdate,
    LabelCreate, LabelOut,
    ListCreate, ListOut,
    MemberAdd, MemberOut,
    TaskListCreate, TaskListUpdate,
)
from app.tasks.service import task_service
from app.tasks.task_calendar_sync import sync_task_to_calendar, remove_task_from_calendar, notify_task_assignment

import logging
_sync_logger = logging.getLogger("task_sync")

router = APIRouter()


def _db(request: Request):
    return request.app.state.db_pool

def _redis(request: Request):
    return request.app.state.redis


# ════════════════════════════════════════════════
#  Microsoft To Do style endpoints
# ════════════════════════════════════════════════

# ── Lists ──

@router.get("/lists", response_model=list[ListOut])
async def todo_list_lists(request: Request, user: str = Depends(get_current_user)):
    return await task_service.list_user_lists(_db(request), user)

@router.post("/lists", response_model=ListOut, status_code=201)
async def todo_create_list(data: TaskListCreate, request: Request, user: str = Depends(get_current_user)):
    return await task_service.create_user_list(_db(request), user, data)

@router.patch("/lists/{list_id}", response_model=ListOut)
async def todo_rename_list(list_id: uuid.UUID, data: TaskListUpdate, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.rename_user_list(_db(request), user, list_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.delete("/lists/{list_id}", status_code=204)
async def todo_delete_list(list_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        await task_service.delete_user_list(_db(request), user, list_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# ── Tasks in lists ──

@router.get("/lists/{list_id}/tasks", response_model=list[CardOut])
async def todo_list_tasks(list_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.list_cards(_db(request), user, list_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/lists/{list_id}/tasks", response_model=CardOut, status_code=201)
async def todo_create_task_in_list(list_id: uuid.UUID, data: CardCreate, request: Request, user: str = Depends(get_current_user)):
    try:
        result = await task_service.create_task(_db(request), user, list_id, data)
        # Sincronizar con calendario y notificar
        try:
            rd = result.model_dump()
            await sync_task_to_calendar(_db(request), _redis(request), rd, user)
            if data.assigned_to:
                await notify_task_assignment(_redis(request), rd, data.assigned_to, "assigned", user)
        except Exception as e:
            _sync_logger.warning("Sync error (create_in_list): %s", e)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/tasks", response_model=CardOut, status_code=201)
async def todo_create_task_default(data: CardCreate, request: Request, user: str = Depends(get_current_user)):
    """Create task in default 'Tareas' list."""
    result = await task_service.create_task(_db(request), user, None, data)
    # Sincronizar con calendario y notificar
    try:
        rd = result.model_dump()
        await sync_task_to_calendar(_db(request), _redis(request), rd, user)
        if data.assigned_to:
            await notify_task_assignment(_redis(request), rd, data.assigned_to, "assigned", user)
    except Exception as e:
        _sync_logger.warning("Sync error (create_default): %s", e)
    return result

# ── Smart Views ──

@router.get("/views/my-day", response_model=list[CardOut])
async def todo_view_my_day(request: Request, user: str = Depends(get_current_user)):
    return await task_service.get_smart_view(_db(request), user, "my_day")

@router.get("/views/important", response_model=list[CardOut])
async def todo_view_important(request: Request, user: str = Depends(get_current_user)):
    return await task_service.get_smart_view(_db(request), user, "important")

@router.get("/views/planned", response_model=list[CardOut])
async def todo_view_planned(request: Request, user: str = Depends(get_current_user)):
    return await task_service.get_smart_view(_db(request), user, "planned")

@router.get("/views/assigned", response_model=list[CardOut])
async def todo_view_assigned(request: Request, user: str = Depends(get_current_user)):
    return await task_service.get_smart_view(_db(request), user, "assigned")

@router.get("/views/flagged")
async def todo_view_flagged(request: Request, user: str = Depends(get_current_user)):
    """Correo electrónico marcado — obtiene emails con bandera desde IMAP."""
    try:
        from app.core.session import get_user_password, get_imap_login_user
        from app.mail.clients.imap_client import get_imap_connection
        from app.mail.services.message_service import list_messages
        password = await get_user_password(request, user)
        login_user = await get_imap_login_user(request, user)
        imap = await get_imap_connection(login_user, password)
        try:
            result = await list_messages(imap, "INBOX", 1, 50, "is:flagged")
            if result and "messages" in result:
                flagged = []
                for msg in result["messages"]:
                    flagged.append({
                        "id": f"mail-{msg.get('uid', 0)}",
                        "list_id": "00000000-0000-0000-0000-000000000000",
                        "title": msg.get("subject", "(sin asunto)"),
                        "description": f"De: {msg.get('from', '')}",
                        "due_date": None,
                        "priority": "medium",
                        "labels": [],
                        "completed": False,
                        "position": 0,
                        "assigned_to": None,
                        "created_by": msg.get("from", ""),
                        "completed_by": None,
                        "completed_at": None,
                        "important": True,
                        "my_day": False,
                        "reminder": None,
                        "note": "",
                        "recurrence": None,
                        "created_at": msg.get("date", ""),
                        "updated_at": msg.get("date", ""),
                    })
                return flagged
        finally:
            try:
                await imap.logout()
            except Exception:
                pass
    except Exception:
        pass
    return []

# ── Task operations ──

@router.patch("/tasks/{card_id}", response_model=CardOut)
async def todo_update_task(card_id: uuid.UUID, data: CardUpdate, request: Request, user: str = Depends(get_current_user)):
    try:
        result = await task_service.update_card(_db(request), user, card_id, data)
        rd = result.model_dump()
        try:
            # Si se cambio fecha o asignado, sincronizar calendario
            date_changed = 'due_date' in data.model_fields_set
            assigned_changed = 'assigned_to' in data.model_fields_set
            if date_changed or assigned_changed:
                if rd.get("due_date"):
                    await sync_task_to_calendar(_db(request), _redis(request), rd, user)
                elif date_changed:
                    # Se quito la fecha — eliminar evento del calendario
                    assigned = rd.get("assigned_to") or user
                    await remove_task_from_calendar(_db(request), rd, assigned)
            if assigned_changed and data.assigned_to:
                await notify_task_assignment(_redis(request), rd, data.assigned_to, "updated", user)
        except Exception as e:
            _sync_logger.warning("Sync error (update): %s", e)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/tasks/{card_id}/toggle", response_model=CardOut)
async def todo_toggle_task(card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        result = await task_service.toggle_card(_db(request), user, card_id)
        # Si se completo, eliminar del calendario; si se reabrio, re-sincronizar
        try:
            rd = result.model_dump()
            assigned = rd.get("assigned_to") or rd.get("created_by", user)
            if rd.get("completed"):
                await remove_task_from_calendar(_db(request), rd, assigned)
                await notify_task_assignment(_redis(request), rd, assigned, "completed", user)
            else:
                await sync_task_to_calendar(_db(request), _redis(request), rd, user)
        except Exception as e:
            _sync_logger.warning("Sync error (toggle): %s", e)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/tasks/{card_id}/important", response_model=CardOut)
async def todo_toggle_important(card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.toggle_important(_db(request), user, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/tasks/{card_id}/my-day", response_model=CardOut)
async def todo_toggle_my_day(card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.toggle_my_day(_db(request), user, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/tasks/{card_id}", status_code=204)
async def todo_delete_task(card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        # Leer tarea antes de eliminar para poder limpiar calendario
        db = _db(request)
        task_row = await db.fetchrow("SELECT * FROM task_cards WHERE id = $1", card_id)
        await task_service.delete_card(db, user, card_id)
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
async def create_board(data: BoardCreate, request: Request, user: str = Depends(get_current_user)):
    return await task_service.create_board(_db(request), user, data)

@router.patch("/boards/{board_id}", response_model=BoardOut)
async def update_board(board_id: uuid.UUID, data: BoardUpdate, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.update_board(_db(request), user, board_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/boards/{board_id}", status_code=204)
async def delete_board(board_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        await task_service.delete_board(_db(request), user, board_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/boards/{board_id}/full", response_model=BoardFull)
async def get_board_full(board_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.get_board_full(_db(request), user, board_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Members

@router.get("/boards/{board_id}/members", response_model=list[MemberOut])
async def list_members(board_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.list_members(_db(request), user, board_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/boards/{board_id}/members", response_model=MemberOut, status_code=201)
async def add_member(board_id: uuid.UUID, data: MemberAdd, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.add_member(_db(request), user, board_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/boards/{board_id}/members/{member_email}", status_code=204)
async def remove_member(board_id: uuid.UUID, member_email: str, request: Request, user: str = Depends(get_current_user)):
    try:
        await task_service.remove_member(_db(request), user, board_id, member_email)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

# Activity

@router.get("/boards/{board_id}/activity", response_model=list[ActivityOut])
async def list_activity(board_id: uuid.UUID, request: Request, limit: int = Query(50, le=200), user: str = Depends(get_current_user)):
    try:
        return await task_service.list_activity(_db(request), user, board_id, limit)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Legacy Lists (under boards)

@router.get("/boards/{board_id}/lists", response_model=list[ListOut])
async def list_lists(board_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.list_lists(_db(request), user, board_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/boards/{board_id}/lists", response_model=ListOut, status_code=201)
async def create_list(board_id: uuid.UUID, data: ListCreate, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.create_list(_db(request), user, board_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Legacy Cards (under lists)

@router.get("/lists/{list_id}/cards", response_model=list[CardOut])
async def list_cards(list_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.list_cards(_db(request), user, list_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/lists/{list_id}/cards", response_model=CardOut, status_code=201)
async def create_card(list_id: uuid.UUID, data: CardCreate, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.create_card(_db(request), user, list_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/cards/{card_id}", response_model=CardOut)
async def update_card(card_id: uuid.UUID, data: CardUpdate, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.update_card(_db(request), user, card_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/cards/{card_id}/move", response_model=CardOut)
async def move_card(card_id: uuid.UUID, data: CardMove, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.move_card(_db(request), user, card_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/cards/{card_id}/toggle", response_model=CardOut)
async def toggle_card(card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.toggle_card(_db(request), user, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/cards/{card_id}", status_code=204)
async def delete_card(card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        await task_service.delete_card(_db(request), user, card_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

# Labels

@router.get("/boards/{board_id}/labels", response_model=list[LabelOut])
async def list_labels(board_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.list_labels(_db(request), user, board_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/boards/{board_id}/labels", response_model=LabelOut, status_code=201)
async def create_label(board_id: uuid.UUID, data: LabelCreate, request: Request, user: str = Depends(get_current_user)):
    try:
        return await task_service.create_label(_db(request), user, board_id, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.delete("/labels/{label_id}", status_code=204)
async def delete_label(label_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
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
    """Verify user has access to the card via board ownership or membership."""
    row = await db.fetchrow(
        """SELECT tc.board_id FROM task_cards tc
           JOIN task_boards tb ON tb.id = tc.board_id
           WHERE tc.id = $1 AND tb."user" = $2""",
        card_id, user
    )
    if not row:
        row = await db.fetchval(
            """SELECT 1 FROM task_cards tc
               JOIN task_board_members tbm ON tbm.board_id = tc.board_id
               WHERE tc.id = $1 AND tbm.user_email = $2""",
            card_id, user
        )
        if not row:
            from fastapi import HTTPException
            raise HTTPException(403, "No tiene acceso a esta tarea")


_steps_table_ready = False

async def _ensure_steps_table(db):
    global _steps_table_ready
    if _steps_table_ready:
        return
    try:
        # Use advisory lock to prevent deadlock with concurrent workers
        await db.execute("SELECT pg_advisory_lock(88888)")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS task_steps (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                card_id UUID NOT NULL REFERENCES task_cards(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                completed BOOLEAN NOT NULL DEFAULT FALSE,
                position INT NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """)
        await db.execute("SELECT pg_advisory_unlock(88888)")
        _steps_table_ready = True
    except Exception:
        try:
            await db.execute("SELECT pg_advisory_unlock(88888)")
        except Exception:
            pass
        _steps_table_ready = True  # Table likely exists already


@router.get("/cards/{card_id}/steps", response_model=list[StepOut])
async def list_steps(card_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    db = _db(request)
    await _ensure_steps_table(db)
    await _verify_card_access(db, card_id, user)
    rows = await db.fetch(
        "SELECT * FROM task_steps WHERE card_id = $1 ORDER BY position, created_at", card_id
    )
    return [StepOut(**dict(r)) for r in rows]


@router.post("/cards/{card_id}/steps", response_model=StepOut, status_code=201)
async def create_step(card_id: uuid.UUID, data: StepCreate, request: Request, user: str = Depends(get_current_user)):
    db = _db(request)
    await _ensure_steps_table(db)
    await _verify_card_access(db, card_id, user)
    max_pos = await db.fetchval("SELECT COALESCE(MAX(position), -1) FROM task_steps WHERE card_id = $1", card_id)
    row = await db.fetchrow(
        "INSERT INTO task_steps (card_id, title, position) VALUES ($1, $2, $3) RETURNING *",
        card_id, data.title.strip(), (max_pos or 0) + 1,
    )
    return StepOut(**dict(row))


@router.put("/steps/{step_id}", response_model=StepOut)
async def update_step(step_id: uuid.UUID, data: StepUpdate, request: Request, user: str = Depends(get_current_user)):
    db = _db(request)
    await _ensure_steps_table(db)
    sets, vals, idx = [], [], 1
    if data.title is not None:
        sets.append(f"title = ${idx}"); vals.append(data.title.strip()); idx += 1
    if data.completed is not None:
        sets.append(f"completed = ${idx}"); vals.append(data.completed); idx += 1
    if data.position is not None:
        sets.append(f"position = ${idx}"); vals.append(data.position); idx += 1
    if not sets:
        raise HTTPException(400, "Nada que actualizar")
    vals.append(step_id)
    row = await db.fetchrow(f"UPDATE task_steps SET {", ".join(sets)} WHERE id = ${idx} RETURNING *", *vals)
    if not row:
        raise HTTPException(404, "Paso no encontrado")
    return StepOut(**dict(row))


@router.delete("/steps/{step_id}", status_code=204)
async def delete_step(step_id: uuid.UUID, request: Request, user: str = Depends(get_current_user)):
    db = _db(request)
    await _ensure_steps_table(db)
    result = await db.execute("DELETE FROM task_steps WHERE id = $1", step_id)
    if result == "DELETE 0":
        raise HTTPException(404, "Paso no encontrado")
