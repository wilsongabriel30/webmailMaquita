"""Labels router — user label/tag system for messages."""
import logging
from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException, Query
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mail", tags=["mail-labels"])

DEFAULT_LABELS = [
    ("Importante", "#d13438"),
    ("Trabajo", "#0078d4"),
    ("Personal", "#107c10"),
    ("Seguimiento", "#ca5010"),
    ("Proyecto", "#8764b8"),
]


async def ensure_tables(db):
    await db.execute("""
        CREATE TABLE IF NOT EXISTS user_labels (
            id SERIAL PRIMARY KEY,
            owner VARCHAR(255) NOT NULL,
            name VARCHAR(100) NOT NULL,
            color VARCHAR(7) NOT NULL DEFAULT '#0078d4',
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(owner, name)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_labels_owner ON user_labels(owner)")
    await db.execute("""
        CREATE TABLE IF NOT EXISTS message_labels (
            id SERIAL PRIMARY KEY,
            owner VARCHAR(255) NOT NULL,
            folder VARCHAR(255) NOT NULL,
            message_uid INTEGER NOT NULL,
            label_id INTEGER NOT NULL REFERENCES user_labels(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(owner, folder, message_uid, label_id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_mlabels_owner_folder ON message_labels(owner, folder)")


async def seed_defaults(db, owner: str):
    """Seed default labels for a user if they have none."""
    count = await db.fetchval("SELECT COUNT(*) FROM user_labels WHERE owner = $1", owner)
    if count == 0:
        for name, color in DEFAULT_LABELS:
            await db.execute(
                "INSERT INTO user_labels (owner, name, color) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
                owner, name, color,
            )


class LabelCreate(BaseModel):
    name: str
    color: str = "#0078d4"


class LabelUpdate(BaseModel):
    name: Optional[str] = None
    color: Optional[str] = None


class AssignBody(BaseModel):
    folder: str
    uids: list[int]


@router.get("/labels")
async def list_labels(request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    await ensure_tables(db)
    await seed_defaults(db, username)
    rows = await db.fetch(
        "SELECT id, name, color, created_at FROM user_labels WHERE owner = $1 ORDER BY id",
        username,
    )
    # Get counts for each label
    labels = []
    for r in rows:
        count = await db.fetchval(
            "SELECT COUNT(*) FROM message_labels WHERE label_id = $1 AND owner = $2",
            r["id"], username,
        )
        labels.append({
            "id": r["id"], "name": r["name"], "color": r["color"],
            "count": count,
        })
    return {"labels": labels}


@router.post("/labels")
async def create_label(body: LabelCreate, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    await ensure_tables(db)
    try:
        row = await db.fetchrow(
            "INSERT INTO user_labels (owner, name, color) VALUES ($1, $2, $3) RETURNING id, name, color",
            username, body.name.strip(), body.color,
        )
        return {"id": row["id"], "name": row["name"], "color": row["color"]}
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail="Label already exists")
        raise


@router.put("/labels/{label_id}")
async def update_label(label_id: int, body: LabelUpdate, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    await ensure_tables(db)
    existing = await db.fetchrow(
        "SELECT id FROM user_labels WHERE id = $1 AND owner = $2", label_id, username,
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Label not found")
    if body.name is not None:
        await db.execute("UPDATE user_labels SET name = $1 WHERE id = $2", body.name.strip(), label_id)
    if body.color is not None:
        await db.execute("UPDATE user_labels SET color = $1 WHERE id = $2", body.color, label_id)
    row = await db.fetchrow("SELECT id, name, color FROM user_labels WHERE id = $1", label_id)
    return {"id": row["id"], "name": row["name"], "color": row["color"]}


@router.delete("/labels/{label_id}")
async def delete_label(label_id: int, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    await ensure_tables(db)
    result = await db.execute(
        "DELETE FROM user_labels WHERE id = $1 AND owner = $2", label_id, username,
    )
    if result == "DELETE 0":
        raise HTTPException(status_code=404, detail="Label not found")
    return {"ok": True}


@router.post("/labels/{label_id}/assign")
async def assign_label(label_id: int, body: AssignBody, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    await ensure_tables(db)
    # Verify label belongs to user
    lbl = await db.fetchrow("SELECT id FROM user_labels WHERE id = $1 AND owner = $2", label_id, username)
    if not lbl:
        raise HTTPException(status_code=404, detail="Label not found")
    count = 0
    for uid in body.uids:
        try:
            await db.execute(
                "INSERT INTO message_labels (owner, folder, message_uid, label_id) VALUES ($1, $2, $3, $4) ON CONFLICT DO NOTHING",
                username, body.folder, uid, label_id,
            )
            count += 1
        except Exception:
            pass
    return {"assigned": count}


@router.post("/labels/{label_id}/unassign")
async def unassign_label(label_id: int, body: AssignBody, request: Request, username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    await ensure_tables(db)
    count = 0
    for uid in body.uids:
        result = await db.execute(
            "DELETE FROM message_labels WHERE owner = $1 AND folder = $2 AND message_uid = $3 AND label_id = $4",
            username, body.folder, uid, label_id,
        )
        if result != "DELETE 0":
            count += 1
    return {"unassigned": count}


@router.get("/labels/messages/{folder}")
async def get_message_labels(folder: str, request: Request, uids: str = Query(...), username: str = Depends(get_current_user)):
    db = request.app.state.db_pool
    await ensure_tables(db)
    uid_list = [int(u.strip()) for u in uids.split(",") if u.strip().isdigit()]
    if not uid_list:
        return {"message_labels": {}}
    rows = await db.fetch("""
        SELECT ml.message_uid, ml.label_id, ul.name, ul.color
        FROM message_labels ml
        JOIN user_labels ul ON ul.id = ml.label_id
        WHERE ml.owner = $1 AND ml.folder = $2 AND ml.message_uid = ANY($3::int[])
    """, username, folder, uid_list)
    result: dict = {}
    for r in rows:
        uid_key = str(r["message_uid"])
        if uid_key not in result:
            result[uid_key] = []
        result[uid_key].append({"id": r["label_id"], "name": r["name"], "color": r["color"]})
    return {"message_labels": result}


@router.get("/labels/{label_id}/messages")
async def get_label_messages(label_id: int, request: Request, username: str = Depends(get_current_user), page: int = 1, per_page: int = 50):
    """Get messages that have a specific label (for sidebar label click)."""
    db = request.app.state.db_pool
    await ensure_tables(db)
    lbl = await db.fetchrow("SELECT id, name, color FROM user_labels WHERE id = $1 AND owner = $2", label_id, username)
    if not lbl:
        raise HTTPException(status_code=404, detail="Label not found")
    total = await db.fetchval(
        "SELECT COUNT(*) FROM message_labels WHERE label_id = $1 AND owner = $2",
        label_id, username,
    )
    offset = (page - 1) * per_page
    rows = await db.fetch(
        "SELECT folder, message_uid FROM message_labels WHERE label_id = $1 AND owner = $2 ORDER BY created_at DESC LIMIT $3 OFFSET $4",
        label_id, username, per_page, offset,
    )
    return {
        "label": {"id": lbl["id"], "name": lbl["name"], "color": lbl["color"]},
        "total": total,
        "messages": [{"folder": r["folder"], "uid": r["message_uid"]} for r in rows],
    }
