"""
ManageSieve router for vacation auto-reply and mail filter rules.
Connects to Dovecot ManageSieve on localhost:4190.
"""

import asyncio
import base64
import re
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth.dependencies import get_current_user
from app.core.session import get_user_password


# ---------------------------------------------------------------------------
# Input sanitization — prevent sieve code injection
# ---------------------------------------------------------------------------

_SIEVE_DANGEROUS_RE = re.compile(r"[\r\n\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x85\u2028\u2029]")


def _sanitize_sieve_value(v: str) -> str:
    """Strip newlines and control chars from sieve values to prevent injection."""
    return _SIEVE_DANGEROUS_RE.sub("", v).strip()


def _validate_forward_email(addr: str) -> str:
    """Validate that a forward address is a proper email."""
    addr = _sanitize_sieve_value(addr)
    if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", addr):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dirección de reenvío inválida: {addr}",
        )
    return addr


router = APIRouter(prefix="/api/sieve", tags=["sieve"])

SIEVE_HOST = "127.0.0.1"
SIEVE_PORT = 4190
SCRIPT_NAME = "webmail"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------

class VacationSettings(BaseModel):
    enabled: bool = False
    subject: str = ""
    body: str = ""
    start_date: Optional[str] = None  # ISO date YYYY-MM-DD
    end_date: Optional[str] = None


class FilterCondition(BaseModel):
    field: str = Field(..., pattern="^(from|to|subject)$")
    operator: str = Field(..., pattern="^(contains|is|matches)$")
    value: str


class FilterAction(BaseModel):
    type: str = Field(..., pattern="^(move|flag|delete|forward)$")
    value: Optional[str] = None


class FilterRule(BaseModel):
    name: str
    condition: FilterCondition
    action: FilterAction


class FilterRuleOut(FilterRule):
    index: int


# ---------------------------------------------------------------------------
# ManageSieve low-level protocol helpers
# ---------------------------------------------------------------------------

async def _read_response(reader: asyncio.StreamReader) -> str:
    """Read lines until we get an OK or NO terminal response."""
    lines: list[str] = []
    while True:
        raw = await asyncio.wait_for(reader.readline(), timeout=10)
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        lines.append(line)
        if line.startswith("OK") or line.startswith("NO") or line.startswith("BYE"):
            break
    return "\n".join(lines)


async def _read_until_ok(reader: asyncio.StreamReader) -> str:
    """Read all data until an OK or NO line, return full text."""
    buf: list[str] = []
    while True:
        raw = await asyncio.wait_for(reader.readline(), timeout=10)
        line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
        buf.append(line)
        if line.startswith("OK") or line.startswith("NO") or line.startswith("BYE"):
            break
    return "\n".join(buf)


async def sieve_connect(username: str, password: str) -> tuple:
    """
    Open a ManageSieve connection and authenticate with PLAIN.
    Returns (reader, writer) on success; raises HTTPException on failure.
    """
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(SIEVE_HOST, SIEVE_PORT), timeout=10
        )
    except (OSError, asyncio.TimeoutError) as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Cannot connect to ManageSieve server: {exc}",
        )

    # Read server greeting (may be multiple lines ending with OK)
    greeting = await _read_until_ok(reader)
    if "OK" not in greeting:
        writer.close()
        await writer.wait_closed()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="ManageSieve greeting did not contain OK",
        )

    # AUTHENTICATE PLAIN
    auth_plain = base64.b64encode(f"\0{username}\0{password}".encode()).decode()
    writer.write(f'AUTHENTICATE "PLAIN" "{auth_plain}"\r\n'.encode())
    await writer.drain()

    auth_resp = await _read_until_ok(reader)
    if not auth_resp.strip().startswith("OK"):
        writer.close()
        await writer.wait_closed()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="ManageSieve authentication failed",
        )

    return reader, writer


async def sieve_disconnect(writer: asyncio.StreamWriter) -> None:
    """Send LOGOUT and close the connection."""
    try:
        writer.write(b"LOGOUT\r\n")
        await writer.drain()
    except Exception:
        pass
    try:
        writer.close()
        await writer.wait_closed()
    except Exception:
        pass


async def sieve_listscripts(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter
) -> list[tuple[str, bool]]:
    """Return list of (script_name, is_active) tuples."""
    writer.write(b"LISTSCRIPTS\r\n")
    await writer.drain()
    resp = await _read_until_ok(reader)
    scripts: list[tuple[str, bool]] = []
    for line in resp.splitlines():
        if line.startswith("OK") or line.startswith("NO"):
            continue
        # Format: "scriptname" or "scriptname" ACTIVE
        m = re.match(r'"([^"]+)"(\s+ACTIVE)?', line)
        if m:
            scripts.append((m.group(1), bool(m.group(2))))
    return scripts


async def sieve_getscript(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, name: str
) -> str:
    """Download a named sieve script. Returns empty string if not found."""
    writer.write(f'GETSCRIPT "{name}"\r\n'.encode())
    await writer.drain()

    # First line is the octet-count or NO
    first_line_raw = await asyncio.wait_for(reader.readline(), timeout=10)
    first_line = first_line_raw.decode("utf-8", errors="replace").rstrip("\r\n")

    if first_line.startswith("NO"):
        return ""

    # The first line is {<size>+} or {<size>}
    size_match = re.match(r"\{(\d+)\+?\}", first_line)
    if size_match:
        size = int(size_match.group(1))
        script_data = await asyncio.wait_for(reader.readexactly(size), timeout=10)
        script_text = script_data.decode("utf-8", errors="replace")
    else:
        # Some servers send the script as quoted string
        script_text = first_line.strip('"')

    # Read trailing OK
    await _read_until_ok(reader)
    return script_text


async def sieve_putscript(
    reader: asyncio.StreamReader,
    writer: asyncio.StreamWriter,
    name: str,
    script: str,
) -> None:
    """Upload a sieve script."""
    encoded = script.encode("utf-8")
    size = len(encoded)
    cmd = f'PUTSCRIPT "{name}" {{{size}+}}\r\n'.encode() + encoded + b"\r\n"
    writer.write(cmd)
    await writer.drain()

    resp = await _read_until_ok(reader)
    if not resp.strip().split("\n")[-1].startswith("OK"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"PUTSCRIPT failed: {resp}",
        )


async def sieve_setactive(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, name: str
) -> None:
    """Activate a sieve script (pass empty string to deactivate all)."""
    writer.write(f'SETACTIVE "{name}"\r\n'.encode())
    await writer.drain()
    resp = await _read_until_ok(reader)
    if not resp.strip().split("\n")[-1].startswith("OK"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"SETACTIVE failed: {resp}",
        )


async def sieve_deletescript(
    reader: asyncio.StreamReader, writer: asyncio.StreamWriter, name: str
) -> None:
    """Delete a sieve script from the server."""
    writer.write(f'DELETESCRIPT "{name}"\r\n'.encode())
    await writer.drain()
    resp = await _read_until_ok(reader)
    if not resp.strip().split("\n")[-1].startswith("OK"):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"DELETESCRIPT failed: {resp}",
        )


# ---------------------------------------------------------------------------
# Sieve script generation / parsing
# ---------------------------------------------------------------------------

def _build_requires(vacation: Optional[VacationSettings], filters: list[FilterRule]) -> list[str]:
    """Compute the list of require strings needed."""
    reqs: set[str] = set()
    if vacation and vacation.enabled:
        reqs.add("vacation")
        if vacation.start_date or vacation.end_date:
            reqs.add("date")
            reqs.add("relational")
    for f in filters:
        if f.action.type == "move":
            reqs.add("fileinto")
        elif f.action.type == "flag":
            reqs.update({"imap4flags"})
        elif f.action.type == "forward":
            reqs.add("redirect")  # redirect is implicit, but include for clarity
    return sorted(reqs)


def _sieve_match_type(operator: str) -> str:
    if operator == "contains":
        return ":contains"
    elif operator == "is":
        return ":is"
    elif operator == "matches":
        return ":matches"
    return ":contains"


def _sieve_header_name(field: str) -> str:
    return {"from": "From", "to": "To", "subject": "Subject"}.get(field, field)


def generate_sieve_script(
    vacation: Optional[VacationSettings], filters: list[FilterRule]
) -> str:
    """Build a complete sieve script from vacation + filter rules."""
    parts: list[str] = []

    requires = _build_requires(vacation, filters)
    if requires:
        req_str = ", ".join(f'"{r}"' for r in requires)
        parts.append(f"require [{req_str}];")
    parts.append("")

    # Vacation block
    parts.append("# --- VACATION ---")
    if vacation and vacation.enabled:
        subject_escaped = _sanitize_sieve_value(vacation.subject).replace('"', '\\"')
        body_escaped = _sanitize_sieve_value(vacation.body).replace('"', '\\"')

        date_conditions: list[str] = []
        if vacation.start_date:
            date_conditions.append(
                f'currentdate :value "ge" "date" "{vacation.start_date}"'
            )
        if vacation.end_date:
            date_conditions.append(
                f'currentdate :value "le" "date" "{vacation.end_date}"'
            )

        vacation_cmd = f'vacation :days 7 :subject "{subject_escaped}" "{body_escaped}";'

        if date_conditions:
            cond_str = ", ".join(date_conditions)
            parts.append(f"if allof ({cond_str}) {{")
            parts.append(f"    {vacation_cmd}")
            parts.append("}")
        else:
            parts.append(vacation_cmd)
    else:
        parts.append("# vacation disabled")
    parts.append("")

    # Filter rules block
    parts.append("# --- FILTERS ---")
    for idx, f in enumerate(filters):
        header = _sieve_header_name(f.condition.field)
        match = _sieve_match_type(f.condition.operator)
        value_escaped = _sanitize_sieve_value(f.condition.value).replace('"', '\\"')
        name_escaped = _sanitize_sieve_value(f.name).replace('"', '\\"')

        parts.append(f'# filter[{idx}]: {name_escaped}')
        condition_line = f'if header {match} "{header}" "{value_escaped}"'

        if f.action.type == "move":
            folder = _sanitize_sieve_value(f.action.value or "INBOX").replace('"', '\\"')
            parts.append(f'{condition_line} {{')
            parts.append(f'    fileinto "{folder}";')
            parts.append("}")
        elif f.action.type == "flag":
            flag_val = _sanitize_sieve_value(f.action.value or "\\\\Flagged").replace('"', '\\"')
            parts.append(f'{condition_line} {{')
            parts.append(f'    setflag "{flag_val}";')
            parts.append("}")
        elif f.action.type == "delete":
            parts.append(f'{condition_line} {{')
            parts.append("    discard;")
            parts.append("}")
        elif f.action.type == "forward":
            addr = _validate_forward_email(f.action.value or "")
            parts.append(f'{condition_line} {{')
            parts.append(f'    redirect "{addr}";')
            parts.append("}")

    parts.append("")
    return "\n".join(parts)


def parse_vacation_from_script(script: str) -> VacationSettings:
    """Parse vacation settings from a sieve script."""
    if not script:
        return VacationSettings(enabled=False)

    # Check if vacation command exists and is not commented out
    # Match: vacation :days N :subject "..." "body";
    vac_pattern = re.compile(
        r'vacation\s+:days\s+\d+\s+:subject\s+"([^"]*?)"\s+"([^"]*?)"\s*;',
        re.DOTALL,
    )
    m = vac_pattern.search(script)
    if not m:
        return VacationSettings(enabled=False)

    subject = m.group(1).replace('\\"', '"')
    body = m.group(2).replace('\\"', '"')

    # Check if vacation is inside a disabled comment block
    # Find the line position of the match
    before_match = script[: m.start()]
    if "# vacation disabled" in before_match.split("\n")[-1] if before_match else "":
        return VacationSettings(enabled=False)

    # Parse date constraints
    start_date = None
    end_date = None
    ge_match = re.search(r'currentdate\s+:value\s+"ge"\s+"date"\s+"([^"]+)"', script)
    le_match = re.search(r'currentdate\s+:value\s+"le"\s+"date"\s+"([^"]+)"', script)
    if ge_match:
        start_date = ge_match.group(1)
    if le_match:
        end_date = le_match.group(1)

    return VacationSettings(
        enabled=True,
        subject=subject,
        body=body,
        start_date=start_date,
        end_date=end_date,
    )


def parse_filters_from_script(script: str) -> list[FilterRule]:
    """Parse filter rules from a sieve script."""
    if not script:
        return []

    filters: list[FilterRule] = []

    # Pattern for: # filter[N]: name
    # followed by: if header :op "Header" "value" { action; }
    block_pattern = re.compile(
        r'#\s*filter\[\d+\]:\s*(.+?)\n'
        r'if\s+header\s+(:contains|:is|:matches)\s+"(From|To|Subject)"\s+"([^"]*?)"\s*\{\s*\n'
        r'\s+(.+?);\s*\n'
        r'\}',
        re.MULTILINE,
    )

    for m in block_pattern.finditer(script):
        name = m.group(1).strip().replace('\\"', '"')
        sieve_op = m.group(2)
        header = m.group(3)
        value = m.group(4).replace('\\"', '"')
        action_line = m.group(5).strip()

        # Map sieve match type back to operator
        op_map = {":contains": "contains", ":is": "is", ":matches": "matches"}
        operator = op_map.get(sieve_op, "contains")

        # Map header back to field
        field_map = {"From": "from", "To": "to", "Subject": "subject"}
        field = field_map.get(header, "from")

        # Parse action
        if action_line.startswith("fileinto"):
            folder_m = re.match(r'fileinto\s+"([^"]*)"', action_line)
            action = FilterAction(
                type="move", value=folder_m.group(1) if folder_m else "INBOX"
            )
        elif action_line.startswith("setflag"):
            flag_m = re.match(r'setflag\s+"([^"]*)"', action_line)
            action = FilterAction(
                type="flag", value=flag_m.group(1) if flag_m else "\\Flagged"
            )
        elif action_line == "discard":
            action = FilterAction(type="delete")
        elif action_line.startswith("redirect"):
            addr_m = re.match(r'redirect\s+"([^"]*)"', action_line)
            action = FilterAction(
                type="forward", value=addr_m.group(1) if addr_m else ""
            )
        else:
            continue

        filters.append(
            FilterRule(
                name=name,
                condition=FilterCondition(field=field, operator=operator, value=value),
                action=action,
            )
        )

    return filters


# ---------------------------------------------------------------------------
# Helper: get / save the combined webmail script
# ---------------------------------------------------------------------------

async def _get_current_script(username: str, password: str) -> str:
    """Fetch the current 'webmail' sieve script, or empty string."""
    reader, writer = await sieve_connect(username, password)
    try:
        script = await sieve_getscript(reader, writer, SCRIPT_NAME)
        return script
    finally:
        await sieve_disconnect(writer)


async def _save_script(username: str, password: str, script: str) -> None:
    """Upload and activate the 'webmail' sieve script."""
    reader, writer = await sieve_connect(username, password)
    try:
        await sieve_putscript(reader, writer, SCRIPT_NAME, script)
        await sieve_setactive(reader, writer, SCRIPT_NAME)
    finally:
        await sieve_disconnect(writer)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/vacation")
async def get_vacation(
    request: Request,
    username: str = Depends(get_current_user),
):
    """Get current vacation auto-reply settings."""
    # username from Depends
    password: str = await get_user_password(request, username)

    script = await _get_current_script(username, password)
    vacation = parse_vacation_from_script(script)
    return vacation.model_dump()


@router.put("/vacation")
async def set_vacation(
    request: Request,
    settings: VacationSettings,
    username: str = Depends(get_current_user),
):
    """Set vacation auto-reply (generates sieve script, uploads via ManageSieve)."""
    # username from Depends
    password: str = await get_user_password(request, username)

    # Get existing script to preserve filters
    current_script = await _get_current_script(username, password)
    existing_filters = parse_filters_from_script(current_script)

    # Generate new combined script
    new_script = generate_sieve_script(settings, existing_filters)
    await _save_script(username, password, new_script)

    return {"status": "updated", "vacation": settings.model_dump()}


@router.get("/filters")
async def list_filters(
    request: Request,
    username: str = Depends(get_current_user),
):
    """List all mail filter rules."""
    # username from Depends
    password: str = await get_user_password(request, username)

    script = await _get_current_script(username, password)
    filters = parse_filters_from_script(script)
    return [
        FilterRuleOut(index=idx, **f.model_dump()) for idx, f in enumerate(filters)
    ]


@router.post("/filters", status_code=status.HTTP_201_CREATED)
async def create_filter(
    request: Request,
    rule: FilterRule,
    username: str = Depends(get_current_user),
):
    """Create a new filter rule."""
    MAX_FILTERS = 20
    password: str = await get_user_password(request, username)

    current_script = await _get_current_script(username, password)
    vacation = parse_vacation_from_script(current_script)
    filters = parse_filters_from_script(current_script)

    if len(filters) >= MAX_FILTERS:
        raise HTTPException(status_code=400, detail=f"Máximo {MAX_FILTERS} filtros por usuario")

    filters.append(rule)

    new_script = generate_sieve_script(vacation, filters)
    await _save_script(username, password, new_script)

    return FilterRuleOut(index=len(filters) - 1, **rule.model_dump())


@router.put("/filters/{index}")
async def update_filter(
    index: int,
    request: Request,
    rule: FilterRule,
    username: str = Depends(get_current_user),
):
    """Update a filter rule by index."""
    # username from Depends
    password: str = await get_user_password(request, username)

    current_script = await _get_current_script(username, password)
    vacation = parse_vacation_from_script(current_script)
    filters = parse_filters_from_script(current_script)

    if index < 0 or index >= len(filters):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filter index {index} not found (total: {len(filters)})",
        )

    filters[index] = rule

    new_script = generate_sieve_script(vacation, filters)
    await _save_script(username, password, new_script)

    return FilterRuleOut(index=index, **rule.model_dump())


@router.delete("/filters/{index}")
async def delete_filter(
    index: int,
    request: Request,
    username: str = Depends(get_current_user),
):
    """Delete a filter rule by index."""
    # username from Depends
    password: str = await get_user_password(request, username)

    current_script = await _get_current_script(username, password)
    vacation = parse_vacation_from_script(current_script)
    filters = parse_filters_from_script(current_script)

    if index < 0 or index >= len(filters):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Filter index {index} not found (total: {len(filters)})",
        )

    removed = filters.pop(index)

    new_script = generate_sieve_script(vacation, filters)
    await _save_script(username, password, new_script)

    return {"status": "deleted", "removed": removed.model_dump()}


# ---------------------------------------------------------------------------
# BRECHA 6 — Additional Sieve endpoints: from-message, preview, templates
# ---------------------------------------------------------------------------

from app.core.session import get_imap_login_user
from app.mail.clients.imap_client import get_imap_connection


class FilterFromMessage(BaseModel):
    folder: str = Field(default="INBOX")
    uid: int = Field(..., gt=0)
    action_type: str = Field(..., pattern="^(move|flag|delete|forward)$")
    action_value: Optional[str] = None


class FilterPreviewOut(BaseModel):
    matching_count: int
    sample_subjects: list[str]


# Static filter templates
_FILTER_TEMPLATES = [
    {
        "id": "newsletters",
        "name": "Newsletters a carpeta",
        "description": "Mueve correos de newsletters a una carpeta dedicada",
        "condition": {"field": "from", "operator": "contains", "value": "newsletter"},
        "action": {"type": "move", "value": "Newsletter"},
    },
    {
        "id": "notifications",
        "name": "Notificaciones a carpeta",
        "description": "Mueve correos de noreply a una carpeta de notificaciones",
        "condition": {"field": "from", "operator": "contains", "value": "noreply"},
        "action": {"type": "move", "value": "Notificaciones"},
    },
    {
        "id": "boss_important",
        "name": "Correo de jefe como importante",
        "description": "Marca como importante los correos del jefe",
        "condition": {"field": "from", "operator": "is", "value": "jefe@maquita.org"},
        "action": {"type": "flag", "value": "\\\\Flagged"},
    },
    {
        "id": "spam_recurrent",
        "name": "Eliminar spam recurrente",
        "description": "Elimina correos con asuntos sospechosos de spam",
        "condition": {"field": "subject", "operator": "matches", "value": "*viagra*|*casino*|*lottery*"},
        "action": {"type": "delete", "value": None},
    },
]


@router.post("/filters/from-message", status_code=status.HTTP_201_CREATED)
async def create_filter_from_message(
    request: Request,
    body: FilterFromMessage,
    username: str = Depends(get_current_user),
):
    """Create a filter based on an existing message's From/Subject headers."""
    MAX_FILTERS = 20
    password: str = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)

    # Fetch message headers via IMAP
    imap = await get_imap_connection(login_user, password)
    try:
        resp = await imap.select(body.folder)
        if resp.result != "OK":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se pudo abrir la carpeta: {body.folder}",
            )

        # Fetch From and Subject headers
        fetch_resp = await imap.uid("fetch", str(body.uid), "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT)])")
        if fetch_resp.result != "OK":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Mensaje UID {body.uid} no encontrado en {body.folder}",
            )

        # Parse headers from response
        from_addr = ""
        subject = ""
        for line in fetch_resp.lines:
            if isinstance(line, (bytes, bytearray)):
                line = line.decode("utf-8", errors="replace")
            line = str(line)
            line_lower = line.lower().strip()
            if line_lower.startswith("from:"):
                from_addr = line[5:].strip()
                # Extract email from "Name <email>" format
                email_match = re.search(r"<([^>]+)>", from_addr)
                if email_match:
                    from_addr = email_match.group(1)
            elif line_lower.startswith("subject:"):
                subject = line[8:].strip()
    finally:
        try:
            await imap.logout()
        except Exception:
            pass

    if not from_addr:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No se pudo extraer el remitente del mensaje",
        )

    # Auto-generate filter name
    filter_name = f"Auto: {from_addr[:40]}"

    # Build filter rule based on the message
    condition = FilterCondition(field="from", operator="contains", value=from_addr)
    action = FilterAction(type=body.action_type, value=body.action_value)
    rule = FilterRule(name=filter_name, condition=condition, action=action)

    # Get current script and add filter
    current_script = await _get_current_script(username, password)
    vacation = parse_vacation_from_script(current_script)
    filters = parse_filters_from_script(current_script)

    if len(filters) >= MAX_FILTERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Máximo {MAX_FILTERS} filtros por usuario",
        )

    filters.append(rule)
    new_script = generate_sieve_script(vacation, filters)
    await _save_script(username, password, new_script)

    return {
        "index": len(filters) - 1,
        "filter": rule.model_dump(),
        "source_from": from_addr,
        "source_subject": subject,
    }


@router.get("/filters/preview")
async def preview_filter(
    request: Request,
    field: str,
    operator: str,
    value: str,
    username: str = Depends(get_current_user),
):
    """Preview how many INBOX messages would match a filter rule.
    
    Uses IMAP SEARCH to count matching messages and returns sample subjects.
    """
    # Validate params
    if field not in ("from", "to", "subject"):
        raise HTTPException(status_code=422, detail="field debe ser from, to o subject")
    if operator not in ("contains", "is", "matches"):
        raise HTTPException(status_code=422, detail="operator debe ser contains, is o matches")

    password: str = await get_user_password(request, username)
    login_user = await get_imap_login_user(request, username)

    imap = await get_imap_connection(login_user, password)
    try:
        resp = await imap.select("INBOX")
        if resp.result != "OK":
            raise HTTPException(status_code=500, detail="No se pudo abrir INBOX")

        # Build IMAP SEARCH command
        # IMAP SEARCH supports: HEADER <field> <string> for contains-like matching
        header_map = {"from": "FROM", "to": "TO", "subject": "SUBJECT"}
        imap_header = header_map[field]

        if operator == "is":
            # Exact match — use HEADER which does substring, then we'll filter
            search_cmd = f'HEADER {imap_header} "{value}"'
        else:
            # contains / matches — use HEADER search (substring match)
            search_cmd = f'HEADER {imap_header} "{value}"'

        search_resp = await imap.uid("search", search_cmd)
        matching_uids = []
        if search_resp.result == "OK":
            for line in search_resp.lines:
                if isinstance(line, (bytes, bytearray)):
                    line = line.decode("utf-8", errors="replace")
                line = str(line).strip()
                if line and not line.endswith("completed."):
                    matching_uids.extend(line.split())

        matching_count = len(matching_uids)

        # Fetch sample subjects (up to 5 most recent)
        sample_subjects = []
        if matching_uids:
            sample_uids = matching_uids[-5:]  # Last 5 (most recent)
            uid_str = ",".join(sample_uids)
            fetch_resp = await imap.uid(
                "fetch", uid_str, "(BODY.PEEK[HEADER.FIELDS (SUBJECT)])"
            )
            if fetch_resp.result == "OK":
                for line in fetch_resp.lines:
                    if isinstance(line, (bytes, bytearray)):
                        line = line.decode("utf-8", errors="replace")
                    line = str(line).strip()
                    if line.lower().startswith("subject:"):
                        subj = line[8:].strip()
                        if subj:
                            sample_subjects.append(subj[:100])

        return {
            "matching_count": matching_count,
            "sample_subjects": sample_subjects,
        }
    finally:
        try:
            await imap.logout()
        except Exception:
            pass


@router.get("/filter-templates")
async def list_filter_templates():
    """Return a list of predefined filter templates."""
    return _FILTER_TEMPLATES
