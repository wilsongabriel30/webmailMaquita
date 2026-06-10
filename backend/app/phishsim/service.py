"""Simulación de phishing — registro de eventos del objetivo (público)."""
import re as _re
import quopri as _quopri

_FIELDS = {"opened", "clicked", "submitted", "reported"}
_TOKEN_RE = _re.compile(rb"phishtest[/=]?(?:2[fF])?([A-Za-z0-9_\-]{12,})")


async def get_target(db, token: str):
    return await db.fetchrow("SELECT id, email, campaign_id FROM phish_targets WHERE token = $1", token)


async def mark(db, token: str, field: str) -> None:
    if field not in _FIELDS:
        return
    try:
        await db.execute(
            f"UPDATE phish_targets SET {field} = true, {field}_at = COALESCE({field}_at, now()) "
            f"WHERE token = $1", token)
    except Exception:
        pass


async def mark_reports_from_imap(imap, folder, uids, db) -> None:
    """Si un correo reportado como spam es un señuelo de simulación (su cuerpo
    contiene el enlace /api/phishtest/<token>), marca al objetivo como 'reportó'.
    Se busca en el cuerpo porque los encabezados X- se eliminan en la entrega."""
    try:
        mbox = "INBOX" if folder == "INBOX" else '"' + folder + '"'
        await imap.select(mbox)
        for uid in uids:
            try:
                resp = await imap.uid("fetch", str(uid), "(BODY.PEEK[])")
                if resp.result != "OK":
                    continue
                blob = b"".join(x if isinstance(x, bytes) else str(x).encode()
                                for x in (resp.lines or []))
                try:
                    decoded = _quopri.decodestring(blob)
                except Exception:
                    decoded = b""
                token = None
                for source in (blob, decoded):
                    m = _TOKEN_RE.search(source)
                    if m:
                        cand = m.group(1).decode("ascii", "ignore")
                        # validar que exista como objetivo
                        row = await db.fetchrow("SELECT 1 FROM phish_targets WHERE token = $1", cand)
                        if row:
                            token = cand
                            break
                if token:
                    await mark(db, token, "reported")
            except Exception:
                continue
    except Exception:
        pass
