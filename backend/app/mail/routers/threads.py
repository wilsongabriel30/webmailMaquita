"""Threads router — get messages grouped by thread."""
from fastapi import APIRouter, Request, Depends

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password
from app.mail.clients.imap_client import get_imap_connection
from app.mail.services.message_service import list_messages, get_message
from app.mail.services.thread_service import group_by_thread

router = APIRouter(prefix="/api/mail", tags=["mail-threads"])


@router.get("/threads/{folder}")
async def get_threads(
    folder: str,
    request: Request,
    page: int = 1,
    per_page: int = 50,
    username: str = Depends(get_current_user),
):
    password = await get_user_password(request, username)
    imap = await get_imap_connection(username, password)
    try:
        result = await list_messages(imap, folder, page, per_page)
        threads = group_by_thread(result["messages"])
        return {
            "threads": threads,
            "total": result["total"],
            "page": page,
            "per_page": per_page,
        }
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/threads/{folder}/{thread_id}")
async def get_thread_messages(
    folder: str,
    thread_id: str,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Get all messages in a thread by thread_id, sorted by date ascending."""
    password = await get_user_password(request, username)
    imap = await get_imap_connection(username, password)
    try:
        # Fetch a large window to find all thread messages
        result = await list_messages(imap, folder, 1, 500)
        thread_msgs = [
            m for m in result["messages"]
            if m.get("thread_id") == thread_id
        ]
        # Sort by date ascending (oldest first)
        thread_msgs.sort(key=lambda m: m.get("date") or "")

        # Fetch full content for each message in thread
        full_messages = []
        for summary in thread_msgs:
            full = await get_message(imap, folder, summary["uid"])
            if full:
                full_messages.append(full)

        return {
            "thread_id": thread_id,
            "messages": full_messages,
            "count": len(full_messages),
        }
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
