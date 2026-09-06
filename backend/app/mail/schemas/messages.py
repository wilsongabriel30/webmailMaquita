"""Mail schemas — request/response models with security validations."""
import re
from datetime import datetime, timezone
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

MAX_RECIPIENTS = 50  # Máximo total de destinatarios (to + cc + bcc)


def _sanitize_crlf(value: str) -> str:
    """Strip ALL line separators, control chars, and null bytes from SMTP header values."""
    # Remove header folding (CRLF/LF followed by space/tab)
    value = re.sub(r"\r?\n[\t ]", " ", value)
    # Remove ALL line-break and control characters including Unicode
    # CR, LF, NULL, VT, FF, NEL(U+0085), LS(U+2028), PS(U+2029)
    return re.sub(r"[\r\n\x00-\x08\x0b\x0c\x0e-\x1f\x7f\x85\u2028\u2029]", "", value).strip()
def _validate_email_addr(addr: str) -> str:
    """Sanitize and loosely validate an email address."""
    sanitized = _sanitize_crlf(addr)
    # Extract email from 'Name <email>' format
    m = re.search(r'<([^>]+)>', sanitized)
    email_part = m.group(1).strip() if m else sanitized.strip()
    if not re.match(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$', email_part):
        raise ValueError(f'Dirección de email inválida: {repr(addr)}')
    return sanitized


def _normalize_recipients(v):
    """Accept string or list, sanitize each address."""
    if isinstance(v, str):
        v = [s.strip() for s in v.split(',') if s.strip()]
    return [_validate_email_addr(a) for a in v]


class AttachmentUpload(BaseModel):
    filename: str
    content_b64: str
    content_type: str = 'application/octet-stream'
    is_inline: bool = False
    cid: str = ''

    @field_validator('filename', mode='before')
    @classmethod
    def sanitize_filename(cls, v):
        return _sanitize_crlf(v)


class ComposeRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    to: Union[list[str], str]
    subject: str
    html_body: str = ''
    text_body: str = ''
    cc: list[str] | None = None
    bcc: list[str] | None = None
    in_reply_to: str = ''
    references: str = ''
    draft_uid: int | None = None
    attachments: list[AttachmentUpload] | None = None
    request_read_receipt: bool = False
    request_delivery_receipt: bool = False
    identity_id: int | None = None
    reply_to: str | None = None
    dlp_override: bool = False
    dlp_reason: str | None = None

    @field_validator('to', mode='before')
    @classmethod
    def normalize_to(cls, v):
        return _normalize_recipients(v)

    @field_validator('cc', 'bcc', mode='before')
    @classmethod
    def normalize_cc_bcc(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = [s.strip() for s in v.split(',') if s.strip()]
        return [_validate_email_addr(a) for a in v]

    @field_validator('subject', 'in_reply_to', 'references', mode='before')
    @classmethod
    def sanitize_headers(cls, v):
        return _sanitize_crlf(v)

    @model_validator(mode='after')
    def check_total_recipients(self):
        total = len(self.to)
        if self.cc:
            total += len(self.cc)
        if self.bcc:
            total += len(self.bcc)
        if total > MAX_RECIPIENTS:
            raise ValueError(f'Máximo {MAX_RECIPIENTS} destinatarios totales, recibidos: {total}')
        if total == 0:
            raise ValueError('Se requiere al menos un destinatario')
        return self


class ScheduleRequest(BaseModel):
    to: Union[list[str], str]
    subject: str
    html_body: str = ''
    text_body: str = ''
    cc: list[str] | None = None
    bcc: list[str] | None = None
    in_reply_to: str = ''
    references: str = ''
    scheduled_at: str
    request_read_receipt: bool = False
    request_delivery_receipt: bool = False
    identity_id: int | None = None
    reply_to: str | None = None

    @field_validator('to', mode='before')
    @classmethod
    def normalize_to(cls, v):
        return _normalize_recipients(v)

    @field_validator('cc', 'bcc', mode='before')
    @classmethod
    def normalize_cc_bcc(cls, v):
        if v is None:
            return v
        if isinstance(v, str):
            v = [s.strip() for s in v.split(',') if s.strip()]
        return [_validate_email_addr(a) for a in v]

    @field_validator('subject', 'in_reply_to', 'references', mode='before')
    @classmethod
    def sanitize_headers(cls, v):
        return _sanitize_crlf(v)

    @field_validator('scheduled_at', mode='after')
    @classmethod
    def must_be_future(cls, v):
        try:
            dt = datetime.fromisoformat(v.replace('Z', '+00:00'))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt <= datetime.now(timezone.utc):
                raise ValueError('La fecha de programación debe ser futura')
            if dt.year > 2100:
                raise ValueError('Fecha demasiado lejana (máximo año 2100)')
        except (ValueError, TypeError) as e:
            if 'futura' in str(e) or 'lejana' in str(e):
                raise
            raise ValueError(f'Formato de fecha inválido: {v}')
        return v

    @model_validator(mode='after')
    def check_total_recipients(self):
        total = len(self.to)
        if self.cc:
            total += len(self.cc)
        if self.bcc:
            total += len(self.bcc)
        if total > MAX_RECIPIENTS:
            raise ValueError(f'Máximo {MAX_RECIPIENTS} destinatarios totales')
        return self


class MoveRequest(BaseModel):
    dest_folder: str

    @field_validator('dest_folder', mode='before')
    @classmethod
    def sanitize_folder(cls, v):
        return _sanitize_crlf(v)


class FlagRequest(BaseModel):
    flags: str
    add: bool = True

    @field_validator('flags', mode='before')
    @classmethod
    def sanitize_flags(cls, v):
        return _sanitize_crlf(v)


class BulkActionRequest(BaseModel):
    uids: list[int]
    action: str
    dest_folder: str = ''

    @field_validator('uids', mode='after')
    @classmethod
    def limit_uids(cls, v):
        if len(v) > 500:
            raise ValueError('Máximo 500 UIDs por operación masiva')
        return v

    @field_validator('action', mode='before')
    @classmethod
    def validate_action(cls, v):
        allowed = {'delete', 'move', 'mark_read', 'mark_unread', 'flag', 'unflag', 'archive'}
        if v not in allowed:
            raise ValueError(f'Acción no válida: {v}')
        return v


class DraftRequest(BaseModel):
    to: list[str] = []
    subject: str = ''
    html_body: str = ''
    text_body: str = ''
    cc: list[str] | None = None
    bcc: list[str] | None = None
    in_reply_to: str = ''
    references: str = ''
    existing_draft_uid: int | None = None

    @field_validator('subject', 'in_reply_to', 'references', mode='before')
    @classmethod
    def sanitize_headers(cls, v):
        return _sanitize_crlf(v)


class MessageSummaryResponse(BaseModel):
    uid: int
    folder: str
    message_id: str | None = None
    thread_id: str = ''
    from_: str = ''
    to: str = ''
    subject: str = ''
    date: str | None = None
    size: int = 0
    flags: list[str] = []
    seen: bool = False
    flagged: bool = False
    snippet: str = ''
    has_attachments: bool = False
    importance: str = 'normal'

    model_config = ConfigDict(populate_by_name=True)
