"""Mail Log Ingestor — Parsea /var/log/mail.log y lo ingesta en tabla mail_trace.

Se ejecuta como tarea en background del backend, leyendo el archivo de log
continuamente (estilo tail -f) y parseando líneas de Postfix/Rspamd/Dovecot.
"""
import asyncio
import hashlib
import logging
import os
import re
from datetime import datetime

logger = logging.getLogger("log_ingestor")

MAIL_LOG = "/var/log/mail.log"
POSITION_FILE = "/tmp/mail_log_ingestor.pos"

# Regex patterns para Postfix
RE_QUEUEID = re.compile(r"postfix/\w+\[\d+\]: ([A-F0-9]{10,14}): ")
RE_FROM = re.compile(r"from=<([^>]*)>")
RE_TO = re.compile(r"to=<([^>]*)>")
RE_STATUS = re.compile(r"status=(\w+)")
RE_DSN = re.compile(r"dsn=([0-9.]+)")
RE_SIZE = re.compile(r"size=(\d+)")
RE_DELAY = re.compile(r"delay=([0-9.]+)")
RE_RELAY = re.compile(r"relay=([^\s,]+)")
RE_MSGID = re.compile(r"message-id=<([^>]+)>")
RE_CLIENT = re.compile(r"client=\S+\[([0-9.]+)\]")
RE_HELO = re.compile(r"helo=<([^>]*)>")

# Rspamd headers en mail.log
RE_RSPAMD_SCORE = re.compile(r"X-Spamd-Result:.*\[(-?[0-9.]+)\s*/")
RE_RSPAMD_ACTION = re.compile(r"rspamd.*action\s*=\s*(\w+)")

# Dovecot LMTP
RE_DOVECOT_LMTP = re.compile(r"lmtp\(\d+,\s*([^)]+)\).*msgid=<([^>]+)>.*saved mail to (\S+)")


class MailLogIngestor:
    def __init__(self, db_pool):
        self.db = db_pool
        self.queue_data = {}  # queue_id → accumulated data
        self._running = False

    async def start(self):
        """Inicia el ingestor en background."""
        self._running = True
        logger.info("Mail log ingestor starting — watching %s", MAIL_LOG)

        # Leer posición previa
        position = self._read_position()

        while self._running:
            try:
                if not os.path.exists(MAIL_LOG):
                    await asyncio.sleep(5)
                    continue

                with open(MAIL_LOG, "r") as f:
                    # Seek a posición previa
                    file_size = os.path.getsize(MAIL_LOG)
                    if position > file_size:
                        position = 0  # Log fue rotado
                    f.seek(position)

                    lines_processed = 0
                    for line in f:
                        await self._process_line(line.strip())
                        lines_processed += 1

                        if lines_processed % 100 == 0:
                            await asyncio.sleep(0)  # Yield control

                    position = f.tell()
                    self._save_position(position)

            except Exception as exc:
                logger.error("Ingestor error: %s", exc)

            await asyncio.sleep(5)  # Poll cada 5 segundos

    def stop(self):
        self._running = False

    def _read_position(self) -> int:
        try:
            with open(POSITION_FILE, "r") as f:
                return int(f.read().strip())
        except (FileNotFoundError, ValueError):
            return 0

    def _save_position(self, pos: int):
        try:
            with open(POSITION_FILE, "w") as f:
                f.write(str(pos))
        except Exception:
            pass

    async def _process_line(self, line: str):
        """Procesa una línea de mail.log."""
        if not line:
            return

        # Detectar programa (postfix/smtpd, postfix/cleanup, postfix/smtp, dovecot, rspamd)
        qid_match = RE_QUEUEID.search(line)
        if not qid_match:
            # Líneas de Dovecot LMTP
            lmtp_match = RE_DOVECOT_LMTP.search(line)
            if lmtp_match:
                user = lmtp_match.group(1)
                msgid = lmtp_match.group(2)
                folder = lmtp_match.group(3)
                await self._update_by_msgid(msgid, {"dovecot_user": user, "dovecot_folder": folder})
            return

        qid = qid_match.group(1)

        if qid not in self.queue_data:
            self.queue_data[qid] = {
                "queue_id": qid,
                "raw_lines": [],
                "created_at": self._parse_timestamp(line),
            }

        data = self.queue_data[qid]
        data["raw_lines"].append(line[-300:])  # Limitar tamaño

        # Extraer campos
        from_match = RE_FROM.search(line)
        if from_match:
            data["sender"] = from_match.group(1)

        to_match = RE_TO.search(line)
        if to_match:
            data["recipient"] = to_match.group(1)

        status_match = RE_STATUS.search(line)
        if status_match:
            data["status"] = status_match.group(1)

        dsn_match = RE_DSN.search(line)
        if dsn_match:
            data["dsn"] = dsn_match.group(1)

        size_match = RE_SIZE.search(line)
        if size_match:
            data["size_bytes"] = int(size_match.group(1))

        delay_match = RE_DELAY.search(line)
        if delay_match:
            data["delay_seconds"] = float(delay_match.group(1))

        relay_match = RE_RELAY.search(line)
        if relay_match:
            data["relay"] = relay_match.group(1)

        msgid_match = RE_MSGID.search(line)
        if msgid_match:
            data["message_id"] = msgid_match.group(1)

        client_match = RE_CLIENT.search(line)
        if client_match:
            data["source_ip"] = client_match.group(1)

        helo_match = RE_HELO.search(line)
        if helo_match:
            data["helo_name"] = helo_match.group(1)

        # Si tiene status, está completa → insertar
        if "status" in data and "recipient" in data:
            await self._insert_trace(data)
            del self.queue_data[qid]

        # Limpiar entries viejos (>5 min sin completar)
        if len(self.queue_data) > 1000:
            to_remove = list(self.queue_data.keys())[:500]
            for k in to_remove:
                del self.queue_data[k]

    async def _insert_trace(self, data: dict):
        """Inserta un registro completo en mail_trace."""
        try:
            sender = data.get("sender", "")
            recipient = data.get("recipient", "")
            source_ip = data.get("source_ip")

            # Determinar dirección
            direction = "outbound"
            if recipient and ("@maquita.org" in recipient or "@maquita.com.ec" in recipient):
                direction = "inbound"
            if sender and ("@maquita.org" in sender or "@maquita.com.ec" in sender):
                if direction == "inbound":
                    direction = "internal"
                else:
                    direction = "outbound"

            raw_log = "\n".join(data.get("raw_lines", []))[:2000]

            await self.db.execute(
                """INSERT INTO mail_trace
                   (queue_id, message_id, direction, sender, recipient,
                    source_ip, helo_name, size_bytes, status, dsn,
                    delay_seconds, relay, raw_log, created_at)
                   VALUES ($1, $2, $3, $4, $5, $6::inet, $7, $8, $9, $10, $11, $12, $13,
                           COALESCE($14, NOW()))""",
                data.get("queue_id"),
                data.get("message_id"),
                direction,
                sender,
                recipient,
                source_ip if source_ip and re.match(r"^\d+\.\d+\.\d+\.\d+$", source_ip) else None,
                data.get("helo_name"),
                data.get("size_bytes"),
                data.get("status"),
                data.get("dsn"),
                data.get("delay_seconds"),
                data.get("relay"),
                raw_log,
                data.get("created_at"),
            )
        except Exception as exc:
            logger.debug("Insert trace error: %s", exc)

    async def _update_by_msgid(self, msgid: str, updates: dict):
        """Actualiza registro de mail_trace con info de Dovecot."""
        pass  # Fase 2: correlación Dovecot

    def _parse_timestamp(self, line: str) -> datetime:
        """Parsea timestamp de syslog format."""
        try:
            match = re.match(r"^(\w{3}\s+\d+\s+\d+:\d+:\d+)", line)
            if match:
                ts_str = match.group(1)
                year = datetime.now().year
                return datetime.strptime(f"{year} {ts_str}", "%Y %b %d %H:%M:%S")
        except Exception:
            pass
        return datetime.now()


async def start_log_ingestor(db_pool) -> MailLogIngestor:
    """Inicia el ingestor como tarea background."""
    ingestor = MailLogIngestor(db_pool)
    asyncio.create_task(ingestor.start())
    return ingestor
