"""TaskService — all DB operations with Microsoft To Do style + backward compat."""
from __future__ import annotations
from app.core.sanitize import strip_html, sanitize_html

import json
import uuid
from datetime import datetime
from typing import Optional

import asyncpg

from app.tasks.schemas import (
    ActivityOut,
    BoardCreate, BoardOut, BoardUpdate,
    CardCreate, CardMove, CardOut, CardUpdate,
    LabelCreate, LabelOut,
    ListCreate, ListFull, ListOut, ListUpdate,
    MemberAdd, MemberOut,
    BoardFull,
    TaskListCreate, TaskListUpdate,
)


def _row_to_board(row):
    return BoardOut(id=row["id"], name=row["name"], color=row["color"],
                    position=row["position"], created_at=row["created_at"], updated_at=row["updated_at"])

def _row_to_list(row, task_count=0):
    return ListOut(id=row["id"], board_id=row["board_id"], name=row["name"],
                   position=row["position"], color=row["color"],
                   list_type=row.get("list_type", "custom"),
                   icon=row.get("icon", ""),
                   task_count=task_count)

def _row_to_card(row):
    labels = row["labels"]
    if isinstance(labels, str):
        labels = json.loads(labels)
    if labels is None:
        labels = []
    return CardOut(
        id=row["id"], list_id=row["list_id"], title=row["title"],
        description=row["description"], due_date=row["due_date"],
        priority=row["priority"], labels=labels, completed=row["completed"],
        position=row["position"], assigned_to=row.get("assigned_to"),
        created_by=row.get("created_by", ""), completed_by=row.get("completed_by"),
        completed_at=row.get("completed_at"),
        important=row.get("important", False),
        my_day=row.get("my_day", False),
        reminder=row.get("reminder"),
        note=row.get("note", ""),
        recurrence=row.get("recurrence"),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )

def _row_to_label(row):
    return LabelOut(id=row["id"], board_id=row["board_id"], name=row["name"], color=row["color"])

def _row_to_member(row):
    return MemberOut(id=row["id"], board_id=row["board_id"], user_email=row["user_email"],
                     role=row["role"], invited_by=row["invited_by"], joined_at=row["joined_at"])

def _row_to_activity(row):
    return ActivityOut(id=row["id"], board_id=row["board_id"], card_id=row.get("card_id"),
                       user_email=row["user_email"], action=row["action"],
                       details=row["details"], created_at=row["created_at"])


class TaskService:

    async def _user_has_access(self, db, board_id, user):
        val = await db.fetchval(
            'SELECT 1 FROM task_boards WHERE id = $1 AND "user" = $2', board_id, user)
        if val:
            return True
        val = await db.fetchval(
            'SELECT 1 FROM task_board_members WHERE board_id = $1 AND user_email = $2', board_id, user)
        return val is not None

    async def _list_belongs_to_user(self, db, list_id, user):
        row = await db.fetchrow('SELECT board_id FROM task_lists WHERE id = $1', list_id)
        if not row:
            return False
        return await self._user_has_access(db, row["board_id"], user)

    async def _card_belongs_to_user(self, db, card_id, user):
        row = await db.fetchrow(
            'SELECT tl.board_id FROM task_cards tc JOIN task_lists tl ON tl.id = tc.list_id WHERE tc.id = $1',
            card_id)
        if not row:
            return False
        return await self._user_has_access(db, row["board_id"], user)

    async def _get_board_id_for_card(self, db, card_id):
        return await db.fetchval(
            'SELECT tl.board_id FROM task_cards tc JOIN task_lists tl ON tl.id = tc.list_id WHERE tc.id = $1',
            card_id)

    async def _get_board_id_for_list(self, db, list_id):
        return await db.fetchval('SELECT board_id FROM task_lists WHERE id = $1', list_id)

    async def _log_activity(self, db, board_id, user, action, details="", card_id=None):
        await db.execute(
            'INSERT INTO task_activity (board_id, card_id, user_email, action, details) VALUES ($1, $2, $3, $4, $5)',
            board_id, card_id, user, action, details)

    # ── Microsoft To Do style: ensure default board + list ──

    async def ensure_default_board(self, db, user):
        """Auto-create implicit board + default 'Tareas' list for a user if none exists.
        Returns the board_id."""
        row = await db.fetchrow(
            'SELECT id FROM task_boards WHERE "user" = $1 ORDER BY created_at LIMIT 1', user)
        if row:
            board_id = row["id"]
        else:
            board_row = await db.fetchrow(
                'INSERT INTO task_boards ("user", name, color, position) VALUES ($1, $2, $3, 0) RETURNING id',
                user, "Mi To Do", "#0078d4")
            board_id = board_row["id"]
            await db.execute(
                "INSERT INTO task_board_members (board_id, user_email, role, invited_by) VALUES ($1, $2, 'owner', $2) ON CONFLICT DO NOTHING",
                board_id, user)
        # Ensure default list exists
        default_list = await db.fetchrow(
            "SELECT id FROM task_lists WHERE board_id = $1 AND list_type = 'default'", board_id)
        if not default_list:
            await db.execute(
                "INSERT INTO task_lists (board_id, name, position, color, list_type, icon, owner) VALUES ($1, 'Tareas', 0, '#e0e0e0', 'default', '', $2)",
                board_id, user)
        return board_id

    async def _get_default_list_id(self, db, user):
        """Get the default 'Tareas' list for the user, ensuring it exists."""
        board_id = await self.ensure_default_board(db, user)
        list_id = await db.fetchval(
            "SELECT id FROM task_lists WHERE board_id = $1 AND list_type = 'default' LIMIT 1", board_id)
        return list_id

    # ── To Do style: Lists ──

    async def list_user_lists(self, db, user):
        """Return all lists for the user with task counts."""
        board_id = await self.ensure_default_board(db, user)
        rows = await db.fetch(
            """SELECT tl.*, COALESCE(cnt.c, 0) as task_count
               FROM task_lists tl
               LEFT JOIN (SELECT list_id, COUNT(*) as c FROM task_cards WHERE completed = FALSE GROUP BY list_id) cnt
               ON cnt.list_id = tl.id
               WHERE tl.board_id = $1
               ORDER BY tl.list_type DESC, tl.position, tl.name""",
            board_id)
        return [_row_to_list(r, task_count=r["task_count"]) for r in rows]

    async def create_user_list(self, db, user, data: TaskListCreate):
        """Create a custom list for the user."""
        board_id = await self.ensure_default_board(db, user)
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM task_lists WHERE board_id = $1", board_id)
        row = await db.fetchrow(
            "INSERT INTO task_lists (board_id, name, position, color, list_type, icon, owner) VALUES ($1, $2, $3, '#e0e0e0', 'custom', $4, $5) RETURNING *",
            board_id, data.name, max_pos + 1, data.icon, user)
        # get task_count (0 for new list)
        await self._log_activity(db, board_id, user, "list_created", f"Lista '{data.name}' creada")
        return _row_to_list(row, task_count=0)

    async def rename_user_list(self, db, user, list_id, data: TaskListUpdate):
        """Rename/update a user list."""
        if not await self._list_belongs_to_user(db, list_id, user):
            raise ValueError("List not found")
        # Don't allow renaming default list
        row = await db.fetchrow("SELECT list_type FROM task_lists WHERE id = $1", list_id)
        if row and row["list_type"] == "default":
            raise ValueError("Cannot rename default list")
        sets, params, idx = [], [], 1
        if data.name is not None:
            idx += 1
            sets.append(f"name = ${idx}")
            params.append(data.name)
        if data.icon is not None:
            idx += 1
            sets.append(f"icon = ${idx}")
            params.append(data.icon)
        if not sets:
            raise ValueError("Nothing to update")
        sql = f"UPDATE task_lists SET {', '.join(sets)} WHERE id = $1 RETURNING *"
        row = await db.fetchrow(sql, list_id, *params)
        cnt = await db.fetchval("SELECT COUNT(*) FROM task_cards WHERE list_id = $1 AND completed = FALSE", list_id)
        return _row_to_list(row, task_count=cnt or 0)

    async def delete_user_list(self, db, user, list_id):
        """Delete a custom list (not the default one)."""
        if not await self._list_belongs_to_user(db, list_id, user):
            raise ValueError("List not found")
        row = await db.fetchrow("SELECT list_type, name FROM task_lists WHERE id = $1", list_id)
        if row and row["list_type"] == "default":
            raise ValueError("Cannot delete default list")
        board_id = await self._get_board_id_for_list(db, list_id)
        await db.execute("DELETE FROM task_lists WHERE id = $1", list_id)
        if board_id:
            await self._log_activity(db, board_id, user, "list_deleted", f"Lista '{row['name']}' eliminada")

    # ── To Do style: Smart Views ──

    async def get_smart_view(self, db, user, view):
        """Return tasks filtered by smart view type."""
        board_id = await self.ensure_default_board(db, user)
        if view == "my_day":
            rows = await db.fetch(
                """SELECT tc.* FROM task_cards tc
                   JOIN task_lists tl ON tl.id = tc.list_id
                   WHERE tl.board_id = $1 AND tc.my_day = TRUE
                   ORDER BY tc.completed, tc.position""", board_id)
        elif view == "important":
            rows = await db.fetch(
                """SELECT tc.* FROM task_cards tc
                   JOIN task_lists tl ON tl.id = tc.list_id
                   WHERE tl.board_id = $1 AND tc.important = TRUE
                   ORDER BY tc.completed, tc.position""", board_id)
        elif view == "planned":
            rows = await db.fetch(
                """SELECT tc.* FROM task_cards tc
                   JOIN task_lists tl ON tl.id = tc.list_id
                   WHERE tl.board_id = $1 AND tc.due_date IS NOT NULL
                   ORDER BY tc.completed, tc.due_date, tc.position""", board_id)
        elif view == "assigned":
            rows = await db.fetch(
                """SELECT tc.* FROM task_cards tc
                   JOIN task_lists tl ON tl.id = tc.list_id
                   WHERE tl.board_id = $1 AND tc.assigned_to = $2
                   ORDER BY tc.completed, tc.position""", board_id, user)
        else:
            raise ValueError(f"Unknown view: {view}")
        return [_row_to_card(r) for r in rows]

    # ── To Do style: Tasks ──

    async def create_task(self, db, user, list_id, data: CardCreate):
        """Create a task. If list_id is None, use default list."""
        if list_id is None:
            list_id = await self._get_default_list_id(db, user)
        if not await self._list_belongs_to_user(db, list_id, user):
            raise ValueError("List not found")
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM task_cards WHERE list_id = $1", list_id)
        row = await db.fetchrow(
            """INSERT INTO task_cards (list_id, title, description, due_date, priority, labels, position,
               assigned_to, created_by, important, my_day, reminder, note, recurrence)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13, $14) RETURNING *""",
            list_id, strip_html(data.title), sanitize_html(data.description or ''), data.due_date,
            data.priority, json.dumps(data.labels), max_pos + 1,
            data.assigned_to, user, data.important, data.my_day, data.reminder, sanitize_html(data.note or ''),
            getattr(data, "recurrence", None))
        board_id = await self._get_board_id_for_list(db, list_id)
        if board_id:
            await self._log_activity(db, board_id, user, "card_created", f"Tarea '{data.title}' creada", row["id"])
        return _row_to_card(row)

    async def toggle_important(self, db, user, card_id):
        """Toggle important flag on a task."""
        if not await self._card_belongs_to_user(db, card_id, user):
            raise ValueError("Card not found")
        row = await db.fetchrow(
            "UPDATE task_cards SET important = NOT important, updated_at = NOW() WHERE id = $1 RETURNING *",
            card_id)
        return _row_to_card(row)

    async def toggle_my_day(self, db, user, card_id):
        """Toggle my_day flag on a task."""
        if not await self._card_belongs_to_user(db, card_id, user):
            raise ValueError("Card not found")
        row = await db.fetchrow(
            "UPDATE task_cards SET my_day = NOT my_day, updated_at = NOW() WHERE id = $1 RETURNING *",
            card_id)
        return _row_to_card(row)

    # ── Original Kanban endpoints (backward compat) ──

    # Boards

    async def list_boards(self, db, user):
        rows = await db.fetch(
            'SELECT DISTINCT tb.* FROM task_boards tb LEFT JOIN task_board_members tbm ON tbm.board_id = tb.id WHERE tb."user" = $1 OR tbm.user_email = $1 ORDER BY tb.position, tb.created_at',
            user)
        return [_row_to_board(r) for r in rows]

    async def create_board(self, db, user, data):
        max_pos = await db.fetchval(
            'SELECT COALESCE(MAX(position), -1) FROM task_boards WHERE "user" = $1', user)
        row = await db.fetchrow(
            'INSERT INTO task_boards ("user", name, color, position) VALUES ($1, $2, $3, $4) RETURNING *',
            user, data.name, data.color, max_pos + 1)
        board = _row_to_board(row)
        await db.execute(
            "INSERT INTO task_board_members (board_id, user_email, role, invited_by) VALUES ($1, $2, 'owner', $2) ON CONFLICT DO NOTHING",
            board.id, user)
        for name, pos, color in [("Por hacer", 0, "#e0e0e0"), ("En progreso", 1, "#fff3cd"), ("Completado", 2, "#d4edda")]:
            await db.execute(
                'INSERT INTO task_lists (board_id, name, position, color) VALUES ($1, $2, $3, $4)',
                board.id, name, pos, color)
        await self._log_activity(db, board.id, user, "board_created", "Tablero creado")
        return board

    async def update_board(self, db, user, board_id, data):
        if not await self._user_has_access(db, board_id, user):
            raise ValueError("Board not found")
        sets, params, idx = [], [], 1
        for field in ("name", "color", "position"):
            val = getattr(data, field, None)
            if val is not None:
                idx += 1
                sets.append(f"{field} = ${idx}")
                params.append(val)
        if not sets:
            raise ValueError("Nothing to update")
        sets.append("updated_at = NOW()")
        sql = f"UPDATE task_boards SET {', '.join(sets)} WHERE id = $1 RETURNING *"
        row = await db.fetchrow(sql, board_id, *params)
        return _row_to_board(row)

    async def delete_board(self, db, user, board_id):
        val = await db.fetchval('SELECT 1 FROM task_boards WHERE id = $1 AND "user" = $2', board_id, user)
        if not val:
            raise ValueError("Board not found or not owner")
        await db.execute("DELETE FROM task_boards WHERE id = $1", board_id)

    # Members

    async def list_members(self, db, user, board_id):
        if not await self._user_has_access(db, board_id, user):
            raise ValueError("Board not found")
        rows = await db.fetch(
            "SELECT * FROM task_board_members WHERE board_id = $1 ORDER BY joined_at", board_id)
        return [_row_to_member(r) for r in rows]

    async def add_member(self, db, user, board_id, data):
        if not await self._user_has_access(db, board_id, user):
            raise ValueError("Board not found")
        caller_role = await db.fetchval(
            "SELECT role FROM task_board_members WHERE board_id = $1 AND user_email = $2", board_id, user)
        if caller_role not in ('owner', 'admin'):
            raise ValueError("Solo el propietario o admin puede agregar miembros")
        row = await db.fetchrow(
            "INSERT INTO task_board_members (board_id, user_email, role, invited_by) VALUES ($1, $2, $3, $4) ON CONFLICT (board_id, user_email) DO UPDATE SET role = $3 RETURNING *",
            board_id, data.user_email, data.role, user)
        await self._log_activity(db, board_id, user, "member_added", f"{data.user_email} agregado como {data.role}")
        return _row_to_member(row)

    async def remove_member(self, db, user, board_id, member_email):
        if not await self._user_has_access(db, board_id, user):
            raise ValueError("Board not found")
        caller_role = await db.fetchval(
            "SELECT role FROM task_board_members WHERE board_id = $1 AND user_email = $2", board_id, user)
        if caller_role not in ('owner', 'admin'):
            raise ValueError("Solo el propietario o admin puede remover miembros")
        is_owner = await db.fetchval('SELECT 1 FROM task_boards WHERE id = $1 AND "user" = $2', board_id, member_email)
        if is_owner:
            raise ValueError("Cannot remove board owner")
        await db.execute(
            "DELETE FROM task_board_members WHERE board_id = $1 AND user_email = $2", board_id, member_email)
        await self._log_activity(db, board_id, user, "member_removed", f"{member_email} removido")

    # Lists (legacy kanban)

    async def list_lists(self, db, user, board_id):
        if not await self._user_has_access(db, board_id, user):
            raise ValueError("Board not found")
        rows = await db.fetch("SELECT * FROM task_lists WHERE board_id = $1 ORDER BY position", board_id)
        return [_row_to_list(r) for r in rows]

    async def create_list(self, db, user, board_id, data):
        if not await self._user_has_access(db, board_id, user):
            raise ValueError("Board not found")
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM task_lists WHERE board_id = $1", board_id)
        row = await db.fetchrow(
            'INSERT INTO task_lists (board_id, name, position, color) VALUES ($1, $2, $3, $4) RETURNING *',
            board_id, data.name, max_pos + 1, data.color)
        await self._log_activity(db, board_id, user, "list_created", f"Lista '{data.name}' creada")
        return _row_to_list(row)

    async def update_list(self, db, user, list_id, data):
        if not await self._list_belongs_to_user(db, list_id, user):
            raise ValueError("List not found")
        sets, params, idx = [], [], 1
        for field in ("name", "color", "position"):
            val = getattr(data, field, None)
            if val is not None:
                idx += 1
                sets.append(f"{field} = ${idx}")
                params.append(val)
        if not sets:
            raise ValueError("Nothing to update")
        sql = f"UPDATE task_lists SET {', '.join(sets)} WHERE id = $1 RETURNING *"
        row = await db.fetchrow(sql, list_id, *params)
        return _row_to_list(row)

    async def delete_list(self, db, user, list_id):
        if not await self._list_belongs_to_user(db, list_id, user):
            raise ValueError("List not found")
        await db.execute("DELETE FROM task_lists WHERE id = $1", list_id)

    # Cards (legacy + updated with new fields)

    async def list_cards(self, db, user, list_id):
        if not await self._list_belongs_to_user(db, list_id, user):
            raise ValueError("List not found")
        rows = await db.fetch("SELECT * FROM task_cards WHERE list_id = $1 ORDER BY position", list_id)
        return [_row_to_card(r) for r in rows]

    async def create_card(self, db, user, list_id, data):
        if not await self._list_belongs_to_user(db, list_id, user):
            raise ValueError("List not found")
        max_pos = await db.fetchval(
            "SELECT COALESCE(MAX(position), -1) FROM task_cards WHERE list_id = $1", list_id)
        important = getattr(data, 'important', False) or False
        my_day = getattr(data, 'my_day', False) or False
        reminder = getattr(data, 'reminder', None)
        note = getattr(data, 'note', '') or ''
        row = await db.fetchrow(
            """INSERT INTO task_cards (list_id, title, description, due_date, priority, labels, position,
               assigned_to, created_by, important, my_day, reminder, note, recurrence)
               VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10, $11, $12, $13, $14) RETURNING *""",
            list_id, data.title, data.description, data.due_date,
            data.priority, json.dumps(data.labels), max_pos + 1,
            data.assigned_to, user, important, my_day, reminder, note,
            getattr(data, "recurrence", None))
        board_id = await self._get_board_id_for_list(db, list_id)
        if board_id:
            details = f"Tarea '{data.title}' creada"
            if data.assigned_to:
                details += f" y asignada a {data.assigned_to}"
            await self._log_activity(db, board_id, user, "card_created", details, row["id"])
        return _row_to_card(row)

    async def update_card(self, db, user, card_id, data):
        if not await self._card_belongs_to_user(db, card_id, user):
            raise ValueError("Card not found")
        old_row = await db.fetchrow("SELECT * FROM task_cards WHERE id = $1", card_id)
        sets, params, idx = [], [], 1
        # Fields that can be explicitly set to null (clearable)
        clearable = {"due_date", "assigned_to", "note", "reminder"}
        for field in ("title", "description", "due_date", "priority", "position", "assigned_to", "note"):
            if field in data.model_fields_set:
                val = getattr(data, field, None)
                if val is None and field not in clearable:
                    continue
                idx += 1
                sets.append(f"{field} = ${idx}")
                params.append(val)
        if data.labels is not None:
            idx += 1
            sets.append(f"labels = ${idx}::jsonb")
            params.append(json.dumps(data.labels))
        if data.completed is not None:
            idx += 1
            sets.append(f"completed = ${idx}")
            params.append(data.completed)
            if data.completed and not old_row["completed"]:
                idx += 1
                sets.append(f"completed_by = ${idx}")
                params.append(user)
                sets.append("completed_at = NOW()")
            elif not data.completed and old_row["completed"]:
                sets.append("completed_by = NULL")
                sets.append("completed_at = NULL")
        if data.important is not None:
            idx += 1
            sets.append(f"important = ${idx}")
            params.append(data.important)
        if data.my_day is not None:
            idx += 1
            sets.append(f"my_day = ${idx}")
            params.append(data.my_day)
        if 'recurrence' in data.model_fields_set:
            idx += 1
            sets.append(f"recurrence = ${idx}")
            params.append(data.recurrence)
        if 'reminder' in data.model_fields_set:
            idx += 1
            sets.append(f"reminder = ${idx}")
            params.append(data.reminder)
        if not sets:
            raise ValueError("Nothing to update")
        sets.append("updated_at = NOW()")
        sql = f"UPDATE task_cards SET {', '.join(sets)} WHERE id = $1 RETURNING *"
        row = await db.fetchrow(sql, card_id, *params)
        board_id = await self._get_board_id_for_card(db, card_id)
        if board_id:
            changes = []
            if data.completed is not None and data.completed != old_row["completed"]:
                changes.append("completada" if data.completed else "reabierta")
            if data.assigned_to is not None and data.assigned_to != old_row.get("assigned_to"):
                changes.append(f"asignada a {data.assigned_to}")
            if data.title is not None and data.title != old_row["title"]:
                changes.append(f"renombrada a '{data.title}'")
            if data.priority is not None and data.priority != old_row["priority"]:
                changes.append(f"prioridad: {data.priority}")
            if data.important is not None and data.important != old_row.get("important"):
                changes.append("importante" if data.important else "no importante")
            if data.my_day is not None and data.my_day != old_row.get("my_day"):
                changes.append("agregada a Mi Dia" if data.my_day else "removida de Mi Dia")
            if changes:
                await self._log_activity(db, board_id, user, "card_updated",
                                         f"Tarea '{old_row['title']}': {', '.join(changes)}", card_id)
        return _row_to_card(row)

    async def move_card(self, db, user, card_id, data):
        if not await self._card_belongs_to_user(db, card_id, user):
            raise ValueError("Card not found")
        if not await self._list_belongs_to_user(db, data.list_id, user):
            raise ValueError("Target list not found")
        old_row = await db.fetchrow(
            "SELECT tc.title, tl.name as old_list FROM task_cards tc JOIN task_lists tl ON tl.id = tc.list_id WHERE tc.id = $1", card_id)
        new_list = await db.fetchrow("SELECT name FROM task_lists WHERE id = $1", data.list_id)
        row = await db.fetchrow(
            'UPDATE task_cards SET list_id = $2, position = $3, updated_at = NOW() WHERE id = $1 RETURNING *',
            card_id, data.list_id, data.position)
        board_id = await self._get_board_id_for_card(db, card_id)
        if board_id and old_row and new_list:
            await self._log_activity(db, board_id, user, "card_moved",
                f"'{old_row['title']}' de '{old_row['old_list']}' a '{new_list['name']}'", card_id)
        return _row_to_card(row)

    async def toggle_card(self, db, user, card_id):
        if not await self._card_belongs_to_user(db, card_id, user):
            raise ValueError("Card not found")
        old_row = await db.fetchrow("SELECT * FROM task_cards WHERE id = $1", card_id)
        new_completed = not old_row["completed"]
        if new_completed:
            row = await db.fetchrow(
                'UPDATE task_cards SET completed = TRUE, completed_by = $2, completed_at = NOW(), updated_at = NOW() WHERE id = $1 RETURNING *',
                card_id, user)
        else:
            row = await db.fetchrow(
                'UPDATE task_cards SET completed = FALSE, completed_by = NULL, completed_at = NULL, updated_at = NOW() WHERE id = $1 RETURNING *',
                card_id)
        board_id = await self._get_board_id_for_card(db, card_id)
        if board_id:
            action = "completada" if new_completed else "reabierta"
            await self._log_activity(db, board_id, user, "card_toggled",
                f"'{old_row['title']}' {action}", card_id)
        return _row_to_card(row)

    async def delete_card(self, db, user, card_id):
        if not await self._card_belongs_to_user(db, card_id, user):
            raise ValueError("Card not found")
        old_row = await db.fetchrow("SELECT title FROM task_cards WHERE id = $1", card_id)
        board_id = await self._get_board_id_for_card(db, card_id)
        await db.execute("DELETE FROM task_cards WHERE id = $1", card_id)
        if board_id and old_row:
            await self._log_activity(db, board_id, user, "card_deleted", f"'{old_row['title']}' eliminada")

    # Labels

    async def list_labels(self, db, user, board_id):
        if not await self._user_has_access(db, board_id, user):
            raise ValueError("Board not found")
        rows = await db.fetch("SELECT * FROM task_labels WHERE board_id = $1 ORDER BY name", board_id)
        return [_row_to_label(r) for r in rows]

    async def create_label(self, db, user, board_id, data):
        if not await self._user_has_access(db, board_id, user):
            raise ValueError("Board not found")
        row = await db.fetchrow(
            'INSERT INTO task_labels (board_id, name, color) VALUES ($1, $2, $3) RETURNING *',
            board_id, data.name, data.color)
        return _row_to_label(row)

    async def delete_label(self, db, user, label_id):
        row = await db.fetchrow("SELECT board_id FROM task_labels WHERE id = $1", label_id)
        if not row:
            raise ValueError("Label not found")
        if not await self._user_has_access(db, row["board_id"], user):
            raise ValueError("Label not found")
        await db.execute("DELETE FROM task_labels WHERE id = $1", label_id)

    # Activity

    async def list_activity(self, db, user, board_id, limit=50):
        if not await self._user_has_access(db, board_id, user):
            raise ValueError("Board not found")
        rows = await db.fetch(
            "SELECT * FROM task_activity WHERE board_id = $1 ORDER BY created_at DESC LIMIT $2",
            board_id, limit)
        return [_row_to_activity(r) for r in rows]

    # Full board (kanban view - backward compat)

    async def get_board_full(self, db, user, board_id):
        if not await self._user_has_access(db, board_id, user):
            raise ValueError("Board not found")
        board_row = await db.fetchrow("SELECT * FROM task_boards WHERE id = $1", board_id)
        board = _row_to_board(board_row)
        list_rows = await db.fetch(
            "SELECT * FROM task_lists WHERE board_id = $1 ORDER BY position", board_id)
        lists_full = []
        for lr in list_rows:
            card_rows = await db.fetch(
                "SELECT * FROM task_cards WHERE list_id = $1 ORDER BY position", lr["id"])
            cards = [_row_to_card(cr) for cr in card_rows]
            lists_full.append(ListFull(
                id=lr["id"], board_id=lr["board_id"], name=lr["name"],
                position=lr["position"], color=lr["color"],
                list_type=lr.get("list_type", "custom"),
                icon=lr.get("icon", ""),
                task_count=len(cards),
                cards=cards))
        label_rows = await db.fetch(
            "SELECT * FROM task_labels WHERE board_id = $1 ORDER BY name", board_id)
        labels = [_row_to_label(r) for r in label_rows]
        member_rows = await db.fetch(
            "SELECT * FROM task_board_members WHERE board_id = $1 ORDER BY joined_at", board_id)
        members = [_row_to_member(r) for r in member_rows]
        return BoardFull(
            id=board.id, name=board.name, color=board.color,
            position=board.position, created_at=board.created_at,
            updated_at=board.updated_at, lists=lists_full,
            labels=labels, members=members)


task_service = TaskService()
