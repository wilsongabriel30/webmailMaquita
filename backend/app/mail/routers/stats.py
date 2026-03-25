"""Stats router — mailbox statistics for the sidebar widget."""
import re
import logging
from datetime import datetime, timedelta

from fastapi import APIRouter, Request, Depends

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password
from app.mail.clients.imap_client import get_imap_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mail", tags=["mail-stats"])


def _decode_lines(lines) -> list[str]:
    result = []
    for line in lines:
        if isinstance(line, (bytes, bytearray)):
            result.append(line.decode("utf-8", errors="replace"))
        elif isinstance(line, str):
            result.append(line)
    return result


async def _get_folder_status(imap, folder_name: str) -> dict:
    """Get MESSAGES and UNSEEN counts for a folder."""
    try:
        resp = await imap.status(folder_name, "(MESSAGES UNSEEN)")
        if resp.result == "OK":
            for line in _decode_lines(resp.lines):
                messages_m = re.search(r"MESSAGES\s+(\d+)", line)
                unseen_m = re.search(r"UNSEEN\s+(\d+)", line)
                return {
                    "messages": int(messages_m.group(1)) if messages_m else 0,
                    "unseen": int(unseen_m.group(1)) if unseen_m else 0,
                }
    except Exception as e:
        logger.debug(f"Status check failed for {folder_name}: {e}")
    return {"messages": 0, "unseen": 0}


async def _count_sent_since(imap, since_date: str) -> int:
    """Count messages in Sent folder since a given IMAP date string."""
    try:
        resp = await imap.select("Sent")
        if resp.result != "OK":
            return 0
        search_resp = await imap.uid_search("SINCE", since_date)
        if search_resp.result != "OK":
            return 0
        count = 0
        for line in _decode_lines(search_resp.lines):
            line = line.strip()
            if line and not line.endswith("completed."):
                count += len([x for x in line.split() if x.isdigit()])
        return count
    except Exception as e:
        logger.debug(f"Sent count failed: {e}")
        return 0


async def _get_top_senders(imap, limit: int = 5) -> list[dict]:
    """Get top senders from INBOX in last 30 days."""
    try:
        resp = await imap.select("INBOX")
        if resp.result != "OK":
            return []

        since = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
        search_resp = await imap.uid_search("SINCE", since)
        if search_resp.result != "OK":
            return []

        uids = []
        for line in _decode_lines(search_resp.lines):
            line = line.strip()
            if line and not line.endswith("completed."):
                uids.extend(int(x) for x in line.split() if x.isdigit())

        if not uids:
            return []

        # Limit to last 200 messages for performance
        uids.sort(reverse=True)
        uids = uids[:200]
        uid_set = ",".join(str(u) for u in uids)

        fetch_resp = await imap.uid("fetch", uid_set,
            "(BODY.PEEK[HEADER.FIELDS (FROM)])")
        if fetch_resp.result != "OK":
            return []

        sender_counts: dict[str, dict] = {}
        for line in _decode_lines(fetch_resp.lines):
            from_m = re.search(r"From:\s*(.+)", line, re.IGNORECASE)
            if from_m:
                raw_from = from_m.group(1).strip()
                # Parse "Name <email>" or just "email"
                addr_m = re.search(r"<([^>]+)>", raw_from)
                if addr_m:
                    email = addr_m.group(1).lower()
                    name = re.sub(r"\s*<[^>]+>\s*", "", raw_from).strip().strip('"').strip("'")
                else:
                    email = raw_from.lower().strip()
                    name = ""

                if email in sender_counts:
                    sender_counts[email]["count"] += 1
                else:
                    sender_counts[email] = {"email": email, "name": name, "count": 1}

        top = sorted(sender_counts.values(), key=lambda x: x["count"], reverse=True)
        return top[:limit]
    except Exception as e:
        logger.debug(f"Top senders failed: {e}")
        return []


@router.get("/stats")
async def get_mail_stats(request: Request, username: str = Depends(get_current_user)):
    password = await get_user_password(request, username)
    imap = await get_imap_connection(username, password)
    try:
        # Folder stats
        inbox_status = await _get_folder_status(imap, "INBOX")
        drafts_status = await _get_folder_status(imap, "Drafts")
        trash_status = await _get_folder_status(imap, "Trash")
        sent_status = await _get_folder_status(imap, "Sent")

        # Sent counts by date range
        today = datetime.now()
        today_str = today.strftime("%d-%b-%Y")
        week_ago = (today - timedelta(days=7)).strftime("%d-%b-%Y")
        month_ago = (today - timedelta(days=30)).strftime("%d-%b-%Y")

        sent_today = await _count_sent_since(imap, today_str)
        sent_week = await _count_sent_since(imap, week_ago)
        sent_month = await _count_sent_since(imap, month_ago)

        # Storage from quota2 table
        storage_used_mb = 0.0
        try:
            db = request.app.state.db_pool
            row = await db.fetchrow(
                "SELECT bytes FROM quota2 WHERE username = $1", username
            )
            if row and row["bytes"]:
                storage_used_mb = round(row["bytes"] / (1024 * 1024), 1)
        except Exception as e:
            logger.debug(f"Quota lookup failed: {e}")

        # Top senders
        top_senders = await _get_top_senders(imap, limit=5)

        return {
            "inbox_total": inbox_status["messages"],
            "inbox_unread": inbox_status["unseen"],
            "sent_total": sent_status["messages"],
            "sent_today": sent_today,
            "sent_week": sent_week,
            "sent_month": sent_month,
            "drafts": drafts_status["messages"],
            "trash": trash_status["messages"],
            "storage_used_mb": storage_used_mb,
            "top_senders": top_senders,
        }
    finally:
        try:
            await imap.logout()
        except Exception:
            pass
