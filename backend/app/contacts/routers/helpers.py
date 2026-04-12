"""Funciones compartidas para el módulo de contactos."""
import json

# Todos los campos de user_contacts para SELECT
ALL_FIELDS = (
    "id, owner, display_name, email, phone, organization, notes, "
    "first_name, last_name, nickname, job_title, department, company, "
    "email2, email3, phone_mobile, phone_work, phone_home, fax, "
    "address_street, address_city, address_state, address_zip, address_country, "
    "birthday, website, im_address, photo_url, "
    "is_favorite, deleted_at, source, last_contacted_at, usage_count, "
    "created_at, updated_at"
)


def compute_initials(name: str) -> str:
    """Genera iniciales para avatar: 'Wilson Arguello' → 'WA'."""
    if not name or not name.strip():
        return "?"
    parts = name.strip().split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[-1][0]).upper()
    return parts[0][0].upper()


def row_to_dict(row) -> dict:
    """Convierte un asyncpg Record a dict con fechas en ISO."""
    d = dict(row)
    for k in ("created_at", "updated_at", "deleted_at", "last_contacted_at"):
        if d.get(k):
            d[k] = d[k].isoformat()
    if d.get("birthday"):
        d["birthday"] = d["birthday"].isoformat()
    return d


def compute_display_name(body: dict) -> str:
    """Calcula display_name desde first+last o lo usa directo."""
    dn = body.get("display_name", "").strip()
    if dn:
        return dn
    fn = body.get("first_name", "").strip()
    ln = body.get("last_name", "").strip()
    if fn and ln:
        return f"{fn} {ln}"
    return fn or ln or body.get("name", "").strip() or ""


async def audit(db, owner: str, contact_id, action: str, details: dict = None, ip: str = ""):
    """Registra acción en contact_audit_log. No lanza excepciones."""
    try:
        await db.execute(
            "INSERT INTO contact_audit_log (owner, contact_id, action, details, ip_address) "
            "VALUES ($1,$2,$3,$4,$5)",
            owner, contact_id, action, json.dumps(details or {}), ip
        )
    except Exception:
        pass


async def get_categories_for_contact(db, contact_id: int) -> list:
    """Retorna categorías asignadas a un contacto."""
    rows = await db.fetch(
        "SELECT cc.id, cc.name, cc.color FROM contact_category_assignments cca "
        "JOIN contact_categories cc ON cc.id = cca.category_id "
        "WHERE cca.contact_id = $1 ORDER BY cc.name", contact_id
    )
    return [{"id": r["id"], "name": r["name"], "color": r["color"]} for r in rows]


async def enrich_contact(db, row) -> dict:
    """Convierte row a dict + agrega categorías."""
    d = row_to_dict(row)
    d["categories"] = await get_categories_for_contact(db, d["id"])
    return d
