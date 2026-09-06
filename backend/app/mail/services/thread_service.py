"""Thread service — group messages by conversation."""
import hashlib
import re


def compute_thread_id(message_id: str = "", references: str = "", in_reply_to: str = "", subject: str = "") -> str:
    """Derive thread_id using hybrid heuristic.

    Priority: References > In-Reply-To > normalized subject fallback.
    thread_id is a derived non-canonical identifier sufficient for visual grouping.
    """
    if references:
        ids = references.strip().split()
        if ids:
            return ids[0].strip("<>")
    if in_reply_to:
        return in_reply_to.strip("<>")
    # Mensaje raíz: su propio Message-ID (coincide con references[0] de las respuestas)
    if message_id:
        return message_id.strip("<>")
    # Fallback: normalized subject
    subj = re.sub(r"^(Re|Fwd|Fw)\s*:\s*", "", subject, flags=re.IGNORECASE).strip()
    if subj:
        return hashlib.md5(subj.lower().encode(), usedforsecurity=False).hexdigest()[:12]
    return ""


def group_by_thread(messages: list[dict]) -> dict[str, list[dict]]:
    """Group a list of message summaries by thread_id."""
    threads = {}
    for msg in messages:
        tid = msg.get("thread_id", "")
        if not tid:
            tid = msg.get("message_id", str(msg.get("uid", "")))
        threads.setdefault(tid, []).append(msg)
    return threads
