import json

"""Stats router — mailbox statistics for the sidebar widget."""
import logging
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user
from app.core.session import get_imap_login_user, get_user_password
from app.mail.clients.imap_client import _quote_folder, get_imap_connection
from app.mail.clients.imap_pool import get_pooled_imap

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
        resp = await imap.status(_quote_folder(folder_name), "(MESSAGES UNSEEN)")
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


async def _get_quota(imap) -> dict:
    """Get storage used/limit via IMAP GETQUOTAROOT."""
    storage_kb = 0
    storage_limit_kb = 0
    message_count = 0
    message_limit = 0
    try:
        import aioimaplib
        cmd = aioimaplib.Command(
            "GETQUOTAROOT", imap.protocol.new_tag(), "INBOX",
            untagged_resp_name="QUOTA",
        )
        resp = await imap.protocol.execute(cmd)
        if resp.result == "OK":
            for line in _decode_lines(resp.lines):
                # QUOTA "" (STORAGE 19923876 0) or (STORAGE 19923876)
                storage_m = re.search(r"STORAGE\s+(\d+)\s+(\d+)", line)
                if storage_m:
                    storage_kb = int(storage_m.group(1))
                    storage_limit_kb = int(storage_m.group(2))
                elif not storage_kb:
                    storage_m2 = re.search(r"STORAGE\s+(\d+)", line)
                    if storage_m2:
                        storage_kb = int(storage_m2.group(1))
                msg_m = re.search(r"MESSAGE\s+(\d+)\s+(\d+)", line)
                if msg_m:
                    message_count = int(msg_m.group(1))
                    message_limit = int(msg_m.group(2))
                elif not message_count:
                    msg_m2 = re.search(r"MESSAGE\s+(\d+)", line)
                    if msg_m2:
                        message_count = int(msg_m2.group(1))
    except Exception as e:
        logger.debug(f"GETQUOTAROOT failed: {e}")
    return {
        "storage_kb": storage_kb,
        "storage_limit_kb": storage_limit_kb,
        "message_count": message_count,
        "message_limit": message_limit,
    }


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
    # Cache en Redis (60s TTL) — stats no cambian segundo a segundo
    redis = request.app.state.redis
    cache_key = f"stats:{username}"
    cached = await redis.get(cache_key)
    if cached:
        return json.loads(cached)

    password = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)
    async with get_pooled_imap(login_user, password) as imap:
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

        # Storage from IMAP GETQUOTAROOT
        quota = await _get_quota(imap)
        storage_used_mb = round(quota["storage_kb"] / 1024, 1)
        storage_limit_mb = round(quota["storage_limit_kb"] / 1024, 1) if quota["storage_limit_kb"] else 0

        # Top senders
        top_senders = await _get_top_senders(imap, limit=5)

        result = {
            "inbox_total": inbox_status["messages"],
            "inbox_unread": inbox_status["unseen"],
            "sent_total": sent_status["messages"],
            "sent_today": sent_today,
            "sent_week": sent_week,
            "sent_month": sent_month,
            "drafts": drafts_status["messages"],
            "trash": trash_status["messages"],
            "storage_used_mb": storage_used_mb,
            "storage_limit_mb": storage_limit_mb,
            "top_senders": top_senders,
        }
        await redis.set(cache_key, json.dumps(result), ex=60)
        return result
