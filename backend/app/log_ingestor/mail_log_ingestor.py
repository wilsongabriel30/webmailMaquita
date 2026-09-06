"""Mail Log Ingestor v2 — Postfix + Rspamd + Dovecot correlation.

Tails /var/log/mail.log and parses:
- Postfix: queue_id, sender, recipient, size, status, relay, delay, dsn, message_id
- Rspamd: score, action, symbols
- Dovecot: LMTP delivery, user actions (expunge, copy, delete, save, append, flag_change)

Correlates Dovecot delivery with Postfix queue entries via message_id.
"""

import asyncio
import logging
import os
import re
import time
from datetime import datetime, timedelta

logger = logging.getLogger("compliance.ingestor")

MAIL_LOG = "/var/log/mail.log"

# --- Regex patterns ---


# Generic syslog prefix: "May 13 10:30:01 mail-maquita service[pid]:"
def _safe_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


RE_SYSLOG = re.compile(
    r"^(\w{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}|\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?)\s+\S+\s+(\S+?)(?:\[(\d+)\])?:\s+(.*)"
)

# Postfix smtpd client connect
RE_PF_CLIENT = re.compile(r"^([A-F0-9]+):\s+client=(\S+?)(?:\[([^\]]+)\])?,?\s*(.*)")

# Postfix cleanup message-id
RE_PF_MSGID = re.compile(r"^([A-F0-9]+):\s+message-id=<([^>]*)>")

# Postfix qmgr from
RE_PF_FROM = re.compile(r"^([A-F0-9]+):\s+from=<([^>]*)>,\s+size=(\d+),\s+nrcpt=(\d+)")

# Postfix smtp/lmtp delivery
RE_PF_DELIVERY = re.compile(
    r"^([A-F0-9]+):\s+to=<([^>]*)>,\s+"
    r"relay=([^,]+),\s+"
    r"(?:conn_use=\d+,\s+)?"
    r"delay=([^,]+),\s+"
    r"(?:delays=([^,]+),\s+)?"
    r"dsn=([^,]+),\s+"
    r"status=(\w+)\s*"
    r"(?:\((.+)\))?"
)

# Postfix qmgr removed
RE_PF_REMOVED = re.compile(r"^([A-F0-9]+):\s+removed$")

# Rspamd log line
RE_RSPAMD = re.compile(
    r"id:\s*<([^>]*)>.*?"
    r"score:\s*([\d.]+)\s*/\s*([\d.]+).*?"
    r"action:\s*(\S[^;]*?)(?:\s*;|$)"
)

# Rspamd symbols (between parentheses in the log)
RE_RSPAMD_SYMBOLS = re.compile(r"symbols:\s*(.+?)(?:\s*;|$)")

# Dovecot LMTP delivery
RE_DOVECOT_LMTP = re.compile(
    r"lmtp\(([^)<]+)\)<[^>]*>:\s+(?:\w+:\s+)?msgid=<([^>]*)>:\s+saved\s+mail\s+to\s+(\S+)"
)

# Dovecot LMTP with sieve (e.g., "saved mail to Junk" via sieve)
RE_DOVECOT_LMTP_SIEVE = re.compile(
    r"lmtp\(([^)<]+)\)<[^>]*>:\s+(?:\w+:\s+)?msgid=<([^>]*)>:\s+(?:sieve:\s+)?saved\s+mail\s+to\s+(\S+)"
)

# Dovecot imap actions
RE_DOVECOT_IMAP = re.compile(r"imap\(([^)<]+)\)<[^>]*>:\s+(.*)")

# Dovecot imap expunge
RE_DOVECOT_EXPUNGE = re.compile(
    r"[Ee]xpunged?\s+(?:message\s+)?(?:UID\s+)?(\d+)\s+from\s+(\S+)", re.IGNORECASE
)

# Dovecot imap copy
RE_DOVECOT_COPY = re.compile(r"[Cc]opy\s+.*?from\s+(\S+)\s+to\s+(\S+)", re.IGNORECASE)

# Dovecot imap delete mailbox
RE_DOVECOT_DELETE_MBOX = re.compile(r"[Dd]elete(?:d)?\s+mailbox\s+(\S+)", re.IGNORECASE)

# Dovecot imap rename mailbox
RE_DOVECOT_RENAME_MBOX = re.compile(
    r"[Rr]ename(?:d)?\s+(\S+)\s+to\s+(\S+)", re.IGNORECASE
)

# Dovecot imap save/append
RE_DOVECOT_SAVE = re.compile(
    r"(?:[Ss]ave|[Aa]ppend)(?:ed)?\s+.*?(?:to|in)\s+(\S+)", re.IGNORECASE
)

# Dovecot imap flag change
RE_DOVECOT_FLAGS = re.compile(
    r"[Ff]lag(?:s)?\s+(?:change|set|clear).*?UID\s+(\d+).*?(\S+)", re.IGNORECASE
)

# Queue map entry expiry (seconds)
QUEUE_MAP_TTL = 3600  # 1 hour
QUEUE_MAP_CLEANUP_INTERVAL = 300  # 5 minutes


class MailLogIngestor:
    """Ingests mail.log lines and correlates Postfix/Rspamd/Dovecot events."""

    def __init__(self, db_pool):
        self.db = db_pool
        self._task = None
        self._cleanup_task = None
        self._running = False
        # Track queue_id -> {message_id, sender, recipients, size, ...}
        self._queue_map: dict[str, dict] = {}

    async def start(self):
        """Start the log ingestor background tasks."""
        self._running = True
        self._task = asyncio.create_task(self._tail_loop())
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("Mail log ingestor v2 started")

    def stop(self):
        """Stop all background tasks."""
        self._running = False
        if self._task:
            self._task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        logger.info("Mail log ingestor v2 stopped")

    async def _cleanup_loop(self):
        """Periodically remove stale entries from _queue_map."""
        while self._running:
            try:
                await asyncio.sleep(QUEUE_MAP_CLEANUP_INTERVAL)
                self._expire_queue_map()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Error in queue_map cleanup loop")

    def _expire_queue_map(self):
        """Remove queue_map entries older than QUEUE_MAP_TTL."""
        now = time.monotonic()
        expired = [
            qid
            for qid, data in self._queue_map.items()
            if now - data.get("_ts", 0) > QUEUE_MAP_TTL
        ]
        for qid in expired:
            del self._queue_map[qid]
        if expired:
            logger.debug("Expired %d stale queue_map entries", len(expired))

    async def _tail_loop(self):
        """Tail /var/log/mail.log continuously, handling rotation."""
        while self._running:
            try:
                if not os.path.exists(MAIL_LOG):
                    logger.warning("Mail log not found: %s — waiting...", MAIL_LOG)
                    await asyncio.sleep(5)
                    continue

                stat = os.stat(MAIL_LOG)
                inode = stat.st_ino

                with open(MAIL_LOG, "r", encoding="utf-8", errors="replace") as f:
                    # Seek to end to only process new lines
                    f.seek(0, os.SEEK_END)
                    current_pos = f.tell()
                    logger.info(
                        "Tailing %s from position %d (inode %d)",
                        MAIL_LOG,
                        current_pos,
                        inode,
                    )

                    while self._running:
                        line = f.readline()
                        if line:
                            line = line.rstrip("\n")
                            if line:
                                try:
                                    await self._process_line(line)
                                except Exception:
                                    logger.exception(
                                        "Error processing line: %.200s", line
                                    )
                        else:
                            # No new data — check for rotation
                            try:
                                new_stat = os.stat(MAIL_LOG)
                                if new_stat.st_ino != inode:
                                    logger.info(
                                        "Log file rotated (inode changed), reopening"
                                    )
                                    break
                                if new_stat.st_size < f.tell():
                                    logger.info(
                                        "Log file truncated, seeking to beginning"
                                    )
                                    f.seek(0)
                                    continue
                            except FileNotFoundError:
                                logger.warning(
                                    "Log file disappeared, waiting for recreation"
                                )
                                break

                            await asyncio.sleep(0.2)

            except asyncio.CancelledError:
                logger.info("Tail loop cancelled")
                break
            except Exception:
                logger.exception("Unexpected error in tail loop, restarting in 5s")
                await asyncio.sleep(5)

    async def _process_line(self, line: str):
        """Parse syslog prefix and route to appropriate handler."""
        m = RE_SYSLOG.match(line)
        if not m:
            return

        timestamp_str, service, pid, payload = m.groups()

        # Route by service
        if service.startswith("postfix/"):
            component = service.split("/", 1)[1] if "/" in service else service
            await self._handle_postfix(payload, component, timestamp_str)
        elif service.startswith("rspamd"):
            await self._handle_rspamd(payload, timestamp_str)
        elif service.startswith("dovecot"):
            await self._handle_dovecot(payload, timestamp_str)

    # -------------------------------------------------------------------------
    # Postfix handlers
    # -------------------------------------------------------------------------

    async def _handle_postfix(self, payload: str, component: str, timestamp_str: str):
        """Handle Postfix log lines (smtpd, cleanup, qmgr, smtp, lmtp, etc.)."""

        # cleanup: message-id
        m = RE_PF_MSGID.match(payload)
        if m:
            queue_id, message_id = m.groups()
            entry = self._get_queue_entry(queue_id)
            entry["message_id"] = message_id
            return

        # qmgr: from=, size=, nrcpt=
        m = RE_PF_FROM.match(payload)
        if m:
            queue_id, sender, size, nrcpt = m.groups()
            entry = self._get_queue_entry(queue_id)
            entry["sender"] = sender
            entry["size"] = int(size)
            entry["nrcpt"] = int(nrcpt)
            return

        # smtpd: client connection
        m = RE_PF_CLIENT.match(payload)
        if m:
            queue_id, client_host, client_ip, extra = m.groups()
            entry = self._get_queue_entry(queue_id)
            entry["client_host"] = client_host
            entry["client_ip"] = client_ip or ""
            return

        # smtp/lmtp delivery
        m = RE_PF_DELIVERY.match(payload)
        if m:
            queue_id = m.group(1)
            recipient = m.group(2)
            relay = m.group(3)
            delay = m.group(4)
            delays = m.group(5) or ""
            dsn = m.group(6)
            status = m.group(7)
            status_detail = m.group(8) or ""

            entry = self._get_queue_entry(queue_id)

            await self._insert_mail_trace(
                queue_id=queue_id,
                message_id=entry.get("message_id", ""),
                sender=entry.get("sender", ""),
                recipient=recipient,
                size=entry.get("size", 0),
                status=status,
                relay=relay,
                delay=delay,
                dsn=dsn,
                status_detail=status_detail,
                client_ip=entry.get("client_ip", ""),
                rspamd_score=entry.get("rspamd_score"),
                rspamd_action=entry.get("rspamd_action"),
                rspamd_symbols=entry.get("rspamd_symbols"),
                timestamp_str=timestamp_str,
            )
            return

        # removed from queue
        m = RE_PF_REMOVED.match(payload)
        if m:
            queue_id = m.group(1)
            # Keep entry a bit longer for late Dovecot correlation, but mark done
            if queue_id in self._queue_map:
                self._queue_map[queue_id]["_removed"] = True
            return

    def _get_queue_entry(self, queue_id: str) -> dict:
        """Get or create a queue map entry, updating its timestamp."""
        if queue_id not in self._queue_map:
            self._queue_map[queue_id] = {"_ts": time.monotonic()}
        else:
            self._queue_map[queue_id]["_ts"] = time.monotonic()
        return self._queue_map[queue_id]

    async def _insert_mail_trace(
        self,
        *,
        queue_id,
        message_id,
        sender,
        recipient,
        size,
        status,
        relay,
        delay,
        dsn,
        status_detail,
        client_ip,
        rspamd_score,
        rspamd_action,
        rspamd_symbols,
        timestamp_str
    ):
        """Insert a record into mail_trace."""
        try:
            ts = self._parse_syslog_timestamp(timestamp_str)
            import ipaddress

            try:
                src_ip = str(ipaddress.ip_address(client_ip)) if client_ip else None
            except (ValueError, TypeError):
                src_ip = None
            await self.db.execute(
                """
                INSERT INTO mail_trace (
                    queue_id, message_id, sender, recipient, size_bytes,
                    status, relay, delay_seconds, dsn,
                    source_ip, rspamd_score, rspamd_action
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, $7, $8, $9,
                    $10, $11, $12
                )
            """,
                queue_id,
                message_id,
                sender,
                recipient,
                _safe_int(size),
                status,
                relay,
                _safe_float(delay),
                dsn,
                src_ip,
                _safe_float(rspamd_score),
                rspamd_action,
            )
        except Exception:
            logger.exception("Failed to insert mail_trace for queue_id=%s", queue_id)

    # -------------------------------------------------------------------------
    # Rspamd handler
    # -------------------------------------------------------------------------

    async def _handle_rspamd(self, payload: str, timestamp_str: str):
        """Handle Rspamd log lines — extract score, action, symbols."""
        m = RE_RSPAMD.search(payload)
        if not m:
            return

        message_id = m.group(1)
        score = float(m.group(2))
        threshold = float(m.group(3))
        action = m.group(4).strip()

        symbols = ""
        ms = RE_RSPAMD_SYMBOLS.search(payload)
        if ms:
            symbols = ms.group(1).strip()

        # Try to find the queue entry that has this message_id and enrich it
        for qid, entry in self._queue_map.items():
            if entry.get("message_id") == message_id:
                entry["rspamd_score"] = score
                entry["rspamd_action"] = action
                entry["rspamd_symbols"] = symbols
                break
        else:
            # No queue entry yet — update directly in DB if trace already exists
            try:
                await self.db.execute(
                    """
                    UPDATE mail_trace
                    SET rspamd_score = $1, rspamd_action = $2, rspamd_symbols = $3
                    WHERE message_id = $4
                      AND rspamd_score IS NULL
                """,
                    score,
                    action,
                    symbols,
                    message_id,
                )
            except Exception:
                logger.exception(
                    "Failed to update rspamd info for msgid=%s", message_id
                )

    # -------------------------------------------------------------------------
    # Dovecot handler
    # -------------------------------------------------------------------------

    async def _handle_dovecot(self, payload: str, timestamp_str: str):
        """Handle Dovecot log lines — LMTP delivery + IMAP actions."""

        # --- LMTP delivery ---
        m = RE_DOVECOT_LMTP.search(payload) or RE_DOVECOT_LMTP_SIEVE.search(payload)
        if m:
            dovecot_user = m.group(1)
            message_id = m.group(2)
            folder = m.group(3)
            await self._correlate_by_message_id(message_id, dovecot_user, folder)
            return

        # --- IMAP actions ---
        m = RE_DOVECOT_IMAP.search(payload)
        if not m:
            return

        username = m.group(1)
        action_text = m.group(2)

        # Expunge
        em = RE_DOVECOT_EXPUNGE.search(action_text)
        if em:
            uid = em.group(1)
            folder = em.group(2)
            await self._log_dovecot_action(
                username, "email_expunge", uid=uid, folder=folder, detail=action_text
            )
            return

        # Copy
        cm = RE_DOVECOT_COPY.search(action_text)
        if cm:
            src_folder = cm.group(1)
            dst_folder = cm.group(2)
            await self._log_dovecot_action(
                username,
                "email_copy",
                src_folder=src_folder,
                dst_folder=dst_folder,
                detail=action_text,
            )
            return

        # Delete mailbox
        dm = RE_DOVECOT_DELETE_MBOX.search(action_text)
        if dm:
            folder = dm.group(1)
            await self._log_dovecot_action(
                username, "mailbox_delete", folder=folder, detail=action_text
            )
            return

        # Rename mailbox
        rm = RE_DOVECOT_RENAME_MBOX.search(action_text)
        if rm:
            old_name = rm.group(1)
            new_name = rm.group(2)
            await self._log_dovecot_action(
                username,
                "mailbox_rename",
                old_name=old_name,
                new_name=new_name,
                detail=action_text,
            )
            return

        # Save / Append
        sm = RE_DOVECOT_SAVE.search(action_text)
        if sm:
            folder = sm.group(1)
            await self._log_dovecot_action(
                username, "email_save", folder=folder, detail=action_text
            )
            return

        # Flag change
        fm = RE_DOVECOT_FLAGS.search(action_text)
        if fm:
            uid = fm.group(1)
            flags_info = fm.group(2)
            await self._log_dovecot_action(
                username,
                "email_flag_change",
                uid=uid,
                flags=flags_info,
                detail=action_text,
            )
            return

        # Generic delete (non-mailbox)
        if re.search(r"\b[Dd]elete(?:d)?\b", action_text) and not dm:
            await self._log_dovecot_action(username, "email_delete", detail=action_text)
            return

    async def _correlate_by_message_id(
        self, message_id: str, dovecot_user: str, folder: str
    ):
        """Update mail_trace record with Dovecot delivery info."""
        try:
            result = await self.db.execute(
                """
                UPDATE mail_trace
                SET dovecot_user = $1,
                    dovecot_folder = $2,
                    delivered_at = NOW()
                WHERE message_id = $3
                  AND dovecot_user IS NULL
            """,
                dovecot_user,
                folder,
                message_id,
            )
            logger.debug(
                "Dovecot correlation: msgid=%s user=%s folder=%s result=%s",
                message_id,
                dovecot_user,
                folder,
                result,
            )
        except Exception:
            logger.exception(
                "Failed Dovecot correlation for msgid=%s user=%s",
                message_id,
                dovecot_user,
            )

    async def _log_dovecot_action(self, username: str, action: str, **kwargs):
        """Insert Dovecot action into user_activity_log."""
        detail = kwargs.pop("detail", "")
        metadata = {k: v for k, v in kwargs.items() if v is not None}

        try:
            await self.db.execute(
                """
                INSERT INTO user_activity_log (
                    username, action, detail, metadata, created_at
                ) VALUES ($1, $2, $3, $4, NOW())
            """,
                username,
                action,
                detail[:500],  # Truncate long detail strings
                str(metadata) if metadata else None,
            )
            logger.debug("Dovecot action logged: user=%s action=%s", username, action)
        except Exception:
            logger.exception(
                "Failed to log Dovecot action: user=%s action=%s",
                username,
                action,
            )

    # -------------------------------------------------------------------------
    # Utilities
    # -------------------------------------------------------------------------

    @staticmethod
    def _parse_syslog_timestamp(ts_str: str) -> datetime:
        """Parse syslog timestamp (no year) into a datetime using current year."""
        now = datetime.now()
        # ISO8601 (rsyslog RFC3339): 2026-06-09T19:37:11.984504-05:00
        if "T" in ts_str and ts_str[:4].isdigit():
            try:
                return datetime.fromisoformat(ts_str).replace(tzinfo=None)
            except ValueError:
                pass
        try:
            dt = datetime.strptime(ts_str, "%b %d %H:%M:%S")
            dt = dt.replace(year=now.year)
            # Handle December→January wrap-around
            if dt.month > now.month + 1:
                dt = dt.replace(year=now.year - 1)
            return dt
        except ValueError:
            return now


async def start_log_ingestor(db_pool) -> MailLogIngestor:
    """Create and start the mail log ingestor."""
    ingestor = MailLogIngestor(db_pool)
    await ingestor.start()
    return ingestor
