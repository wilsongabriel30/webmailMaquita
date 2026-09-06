"""
Enriquecimiento desde firma de correo — parsea firmas de emails recibidos
para extraer cargo, empresa, teléfono, dirección, sitio web.
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


class ParseRequest(BaseModel):
    contact_id: int
    email_body: str
    message_id: str = ""


class ApplyField(BaseModel):
    field_name: str
    field_value: str


# Patrones para extraer datos de firmas
PHONE_PATTERNS = [
    r'(?:tel|phone|teléfono|celular|móvil|cell|fax)[\s.:]+([+\d\s\-().]{7,20})',
    r'(?:^|\s)(\+?\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4})(?:\s|$)',
]

URL_PATTERNS = [
    r'(?:web|website|sitio|www)[\s.:]+(\S+)',
    r'(https?://\S+)',
    r'(www\.\S+)',
]

ADDRESS_PATTERNS = [
    r'(?:dirección|address|dir)[\s.:]+(.+?)(?:\n|$)',
    r'(?:calle|av\.|avenida|carrera|transversal)\s+.+?(?:\n|$)',
]

TITLE_PATTERNS = [
    r'(?:^|\n)\s*([A-ZÁ-Ú][a-zá-ú]+(?:\s+[A-ZÁ-Ú][a-zá-ú]+)*)\s*(?:\n|$)',
]

# Cargos comunes en español e inglés
KNOWN_TITLES = {
    'gerente', 'director', 'jefe', 'coordinador', 'analista', 'asistente',
    'presidente', 'vicepresidente', 'secretario', 'contador', 'abogado',
    'ingeniero', 'arquitecto', 'diseñador', 'desarrollador', 'consultor',
    'manager', 'director', 'head', 'chief', 'officer', 'lead', 'senior',
    'junior', 'associate', 'specialist', 'coordinator', 'assistant',
    'ceo', 'cto', 'cfo', 'coo', 'vp', 'svp', 'evp',
}


def _extract_signature(body: str) -> str:
    """Intenta extraer la firma del final del correo."""
    lines = body.strip().split('\n')

    # Buscar separadores de firma comunes
    sig_start = len(lines)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped in ['--', '---', '- -', '____', '————', '━━━━']:
            sig_start = i + 1
            break
        # Buscar la última ocurrencia de línea vacía seguida de nombre
        if i > len(lines) * 0.6 and stripped == '' and i + 1 < len(lines):
            # Posible inicio de firma
            remaining = '\n'.join(lines[i+1:])
            if len(remaining.strip().split('\n')) <= 10:
                sig_start = i + 1
                break

    # Si no encontramos separador, tomar las últimas 8 líneas
    if sig_start >= len(lines):
        sig_start = max(0, len(lines) - 8)

    return '\n'.join(lines[sig_start:])


def _parse_signature(signature: str) -> list[dict]:
    """Parsea la firma y extrae campos con confianza."""
    results = []
    text = signature.strip()
    if not text:
        return results

    lines = [l.strip() for l in text.split('\n') if l.strip()]

    # Teléfonos
    for pattern in PHONE_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            phone = match.group(1).strip() if match.lastindex else match.group(0).strip()
            phone_clean = re.sub(r'[^\d+]', '', phone)
            if len(phone_clean) >= 7:
                results.append({
                    'field_name': 'phone',
                    'field_value': phone,
                    'confidence': 0.8,
                })

    # URLs/sitios web
    for pattern in URL_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            url = match.group(1) if match.lastindex else match.group(0)
            url = url.rstrip('.,;)')
            if '.' in url and len(url) > 5:
                results.append({
                    'field_name': 'website',
                    'field_value': url if url.startswith('http') else f'https://{url}',
                    'confidence': 0.85,
                })

    # Cargo — buscar líneas con palabras clave de cargo
    for line in lines:
        words_lower = line.lower().split()
        for word in words_lower:
            clean = re.sub(r'[^a-záéíóúñ]', '', word)
            if clean in KNOWN_TITLES:
                results.append({
                    'field_name': 'job_title',
                    'field_value': line.strip(' |-–—'),
                    'confidence': 0.7,
                })
                break

    # Empresa — línea después del nombre (primera línea) que no es teléfono ni email
    if len(lines) >= 2:
        for line in lines[1:4]:
            if '@' in line or re.match(r'^[+\d\s\-().]+$', line):
                continue
            if any(line.lower().startswith(p) for p in ['tel', 'phone', 'cel', 'dir', 'web', 'http']):
                continue
            # Posible empresa
            if len(line) > 2 and len(line) < 80:
                results.append({
                    'field_name': 'company',
                    'field_value': line.strip(' |-–—'),
                    'confidence': 0.5,
                })
                break

    # Dirección
    for pattern in ADDRESS_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            addr = match.group(1) if match.lastindex else match.group(0)
            if len(addr.strip()) > 5:
                results.append({
                    'field_name': 'address',
                    'field_value': addr.strip(),
                    'confidence': 0.6,
                })

    # Dedup por field_name (quedarse con mayor confianza)
    seen = {}
    for r in results:
        key = r['field_name']
        if key not in seen or r['confidence'] > seen[key]['confidence']:
            seen[key] = r
    return list(seen.values())


@router.post("/signature/parse")
async def parse_signature(request: Request, body: ParseRequest, username: str = Depends(get_current_user)):
    """Parsea la firma de un correo y guarda sugerencias."""
    db = request.app.state.db_pool
    user = username

    # Verificar que el contacto existe
    contact = await db.fetchrow(
        "SELECT id FROM user_contacts WHERE id=$1 AND owner=$2 AND deleted_at IS NULL",
        body.contact_id, user,
    )
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")

    signature = _extract_signature(body.email_body)
    fields = _parse_signature(signature)

    saved = []
    for f in fields:
        try:
            row = await db.fetchrow(
                """INSERT INTO contact_signature_data
                    (contact_id, field_name, field_value, confidence, source_message_id)
                   VALUES ($1, $2, $3, $4, $5)
                   ON CONFLICT (contact_id, field_name, field_value) DO UPDATE
                   SET confidence = GREATEST(contact_signature_data.confidence, $4),
                       source_message_id = $5
                   RETURNING *""",
                body.contact_id, f['field_name'], f['field_value'],
                f['confidence'], body.message_id,
            )
            saved.append(dict(row))
        except Exception:
            pass

    return {"parsed_fields": len(fields), "saved": saved, "signature_text": signature}


@router.get("/{contact_id}/signature-suggestions")
async def get_suggestions(request: Request, contact_id: int, username: str = Depends(get_current_user)):
    """Obtener sugerencias de enriquecimiento pendientes para un contacto."""
    db = request.app.state.db_pool
    user = username

    contact = await db.fetchrow(
        "SELECT id FROM user_contacts WHERE id=$1 AND owner=$2",
        contact_id, user,
    )
    if not contact:
        raise HTTPException(404, "Contacto no encontrado")

    rows = await db.fetch(
        """SELECT id, field_name, field_value, confidence, status, created_at
           FROM contact_signature_data
           WHERE contact_id = $1 AND status = 'pending'
           ORDER BY confidence DESC""",
        contact_id,
    )
    return [dict(r) for r in rows]


@router.post("/{contact_id}/signature-suggestions/{suggestion_id}/apply")
async def apply_suggestion(request: Request, contact_id: int, suggestion_id: int, username: str = Depends(get_current_user)):
    """Aplica una sugerencia de firma al contacto."""
    db = request.app.state.db_pool
    user = username

    # Verificar ownership del contacto
    owns = await db.fetchval(
        "SELECT 1 FROM user_contacts WHERE id = $1 AND owner = $2",
        contact_id, user
    )
    if not owns:
        raise HTTPException(403, "No tiene acceso a este contacto")

    sug = await db.fetchrow(
        """SELECT * FROM contact_signature_data
           WHERE id=$1 AND contact_id=$2""",
        suggestion_id, contact_id,
    )
    if not sug:
        raise HTTPException(404, "Sugerencia no encontrada")

    # Mapear field_name a columna real
    field_map = {
        'phone': 'phone',
        'phone_mobile': 'phone_mobile',
        'website': 'website',
        'job_title': 'job_title',
        'company': 'company',
        'address': 'address_street',
    }

    column = field_map.get(sug["field_name"])
    if column:
        await db.execute(
            f"UPDATE user_contacts SET {column}=$3, updated_at=NOW() WHERE id=$1 AND owner=$2",
            contact_id, user, sug["field_value"],
        )

    await db.execute(
        "UPDATE contact_signature_data SET status='applied' WHERE id=$1",
        suggestion_id,
    )
    return {"status": "applied"}


@router.post("/{contact_id}/signature-suggestions/{suggestion_id}/dismiss")
async def dismiss_suggestion(request: Request, contact_id: int, suggestion_id: int, username: str = Depends(get_current_user)):
    """Descartar una sugerencia."""
    db = request.app.state.db_pool
    user = username

    # Verificar ownership del contacto
    owns = await db.fetchval(
        "SELECT 1 FROM user_contacts WHERE id = $1 AND owner = $2",
        contact_id, user
    )
    if not owns:
        raise HTTPException(403, "No tiene acceso a este contacto")

    await db.execute(
        "UPDATE contact_signature_data SET status='dismissed' WHERE id=$1 AND contact_id=$2",
        suggestion_id, contact_id,
    )
    return {"status": "dismissed"}
