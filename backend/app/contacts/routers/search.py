"""Search — autocomplete para compose y busqueda global.

Actualizado 2026-04-12: incluye org_contacts y meeting_rooms como fuentes.
"""

from fastapi import APIRouter, Depends, Request

from app.auth.dependencies import get_current_user

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


def _get_domain(user: str) -> str:
    return user.split("@")[1] if "@" in user else user


@router.get("/search")
async def search_contacts(
    q: str = "",
    limit: int = 15,
    request: Request = None,
    username: str = Depends(get_current_user),
):
    """
    Autocomplete unificado: busca en contactos personales, listas, directorio institucional,
    mailbox, historial de envios y salas de reuniones.
    Prioridad: favoritos -> usage_count -> last_contacted -> nombre.
    """
    if not q or len(q) < 1:
        return {"contacts": []}
    if limit > 50:
        limit = 50

    db = request.app.state.db_pool
    domain = _get_domain(username)
    query_like = f"%{q}%"
    contacts = []
    seen_emails: set[str] = set()

    # Fuente 1: Contactos personales (favoritos primero, luego uso frecuente)
    rows = await db.fetch(
        """
        SELECT display_name, email, 'personal' AS source, is_favorite, usage_count
        FROM user_contacts
        WHERE owner = $1 AND deleted_at IS NULL AND (
            LOWER(display_name) LIKE LOWER($2) OR LOWER(email) LIKE LOWER($2)
            OR LOWER(COALESCE(organization, '')) LIKE LOWER($2)
            OR LOWER(COALESCE(company, '')) LIKE LOWER($2)
            OR LOWER(COALESCE(first_name, '')) LIKE LOWER($2)
            OR LOWER(COALESCE(last_name, '')) LIKE LOWER($2)
        )
        ORDER BY is_favorite DESC, usage_count DESC, last_contacted_at DESC NULLS LAST, display_name
        LIMIT $3
    """,
        username,
        query_like,
        limit,
    )
    for row in rows:
        if row["email"] not in seen_emails:
            contacts.append(
                {
                    "name": row["display_name"] or "",
                    "email": row["email"],
                    "source": "personal",
                    "is_favorite": row["is_favorite"],
                }
            )
            seen_emails.add(row["email"])

    # Fuente 2: Listas de contactos (por nombre de lista)
    remaining = limit - len(contacts)
    if remaining > 0:
        list_rows = await db.fetch(
            """
            SELECT cl.id, cl.name, COUNT(clm.contact_id) AS member_count
            FROM contact_lists cl
            LEFT JOIN contact_list_members clm ON clm.list_id = cl.id
            LEFT JOIN user_contacts uc ON uc.id = clm.contact_id AND uc.deleted_at IS NULL
            WHERE cl.owner = $1 AND LOWER(cl.name) LIKE LOWER($2)
            GROUP BY cl.id, cl.name LIMIT $3
        """,
            username,
            query_like,
            remaining,
        )
        for row in list_rows:
            list_key = f"list:{row['id']}"
            if list_key not in seen_emails:
                contacts.append(
                    {
                        "name": row["name"],
                        "email": f"[Lista: {row['member_count']} miembros]",
                        "source": "list",
                        "list_id": row["id"],
                        "member_count": row["member_count"],
                    }
                )
                seen_emails.add(list_key)

    # Fuente 3: Directorio institucional (org_contacts)
    remaining = limit - len(contacts)
    if remaining > 0:
        org_rows = await db.fetch(
            """
            SELECT display_name, email, job_title, department, company,
                   'org_directory' AS source
            FROM org_contacts
            WHERE domain = $1 AND (
                LOWER(email) LIKE LOWER($2)
                OR LOWER(display_name) LIKE LOWER($2)
                OR LOWER(COALESCE(first_name, '')) LIKE LOWER($2)
                OR LOWER(COALESCE(last_name, '')) LIKE LOWER($2)
                OR LOWER(COALESCE(department, '')) LIKE LOWER($2)
                OR LOWER(COALESCE(job_title, '')) LIKE LOWER($2)
            )
            ORDER BY display_name
            LIMIT $3
        """,
            domain,
            query_like,
            remaining,
        )
        for row in org_rows:
            if row["email"] not in seen_emails:
                subtitle_parts = [p for p in [row["job_title"], row["department"]] if p]
                contacts.append(
                    {
                        "name": row["display_name"] or "",
                        "email": row["email"],
                        "source": "org_directory",
                        "subtitle": (
                            " - ".join(subtitle_parts) if subtitle_parts else ""
                        ),
                    }
                )
                seen_emails.add(row["email"])

    # Fuente 4: Directorio global (mailbox activos)
    remaining = limit - len(contacts)
    if remaining > 0:
        rows = await db.fetch(
            """
            SELECT COALESCE(p.display_name, m.name, SPLIT_PART(m.username, '@', 1)) AS display_name,
                   m.username AS email, 'directory' AS source,
                   COALESCE(p.title, '') AS title,
                   COALESCE(p.department, '') AS department
            FROM mailbox m
            LEFT JOIN user_profiles p ON p.user_email = m.username
            WHERE m.active = true AND (
                LOWER(m.username) LIKE LOWER($1)
                OR LOWER(COALESCE(m.name, '')) LIKE LOWER($1)
                OR LOWER(COALESCE(p.display_name, '')) LIKE LOWER($1)
                OR LOWER(COALESCE(p.department, '')) LIKE LOWER($1)
                OR LOWER(COALESCE(p.title, '')) LIKE LOWER($1)
            ) ORDER BY display_name LIMIT $2
        """,
            query_like,
            remaining,
        )
        for row in rows:
            if row["email"] not in seen_emails:
                subtitle_parts = [p for p in [row["title"], row["department"]] if p]
                contacts.append(
                    {
                        "name": row["display_name"] or "",
                        "email": row["email"],
                        "source": "directory",
                        "subtitle": (
                            " - ".join(subtitle_parts) if subtitle_parts else ""
                        ),
                    }
                )
                seen_emails.add(row["email"])

    # Fuente 5: Historial de envios
    remaining = limit - len(contacts)
    if remaining > 0:
        rows = await db.fetch(
            """
            SELECT DISTINCT recipient_email AS email, COALESCE(recipient_name, '') AS display_name, 'history' AS source
            FROM sent_recipients WHERE sender = $1 AND (
                LOWER(recipient_email) LIKE LOWER($2) OR LOWER(COALESCE(recipient_name, '')) LIKE LOWER($2)
            ) ORDER BY recipient_email LIMIT $3
        """,
            username,
            query_like,
            remaining,
        )
        for row in rows:
            if row["email"] not in seen_emails:
                contacts.append(
                    {
                        "name": row["display_name"] or "",
                        "email": row["email"],
                        "source": "history",
                    }
                )
                seen_emails.add(row["email"])

    # Fuente 6: Salas de reuniones
    remaining = limit - len(contacts)
    if remaining > 0:
        room_rows = await db.fetch(
            """
            SELECT name, email, COALESCE(location, '') AS location,
                   capacity, 'room' AS source
            FROM meeting_rooms
            WHERE is_active = true AND email IS NOT NULL AND (
                LOWER(name) LIKE LOWER($1)
                OR LOWER(COALESCE(email, '')) LIKE LOWER($1)
                OR LOWER(COALESCE(location, '')) LIKE LOWER($1)
            )
            ORDER BY name LIMIT $2
        """,
            query_like,
            remaining,
        )
        for row in room_rows:
            if row["email"] not in seen_emails:
                loc_info = f" ({row['location']})" if row["location"] else ""
                contacts.append(
                    {
                        "name": row["name"] or "",
                        "email": row["email"],
                        "source": "room",
                        "subtitle": f"Sala de reuniones{loc_info} - Cap. {row['capacity']}",
                    }
                )
                seen_emails.add(row["email"])

    return {"contacts": contacts}
