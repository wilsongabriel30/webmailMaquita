# -*- coding: utf-8 -*-
"""Nombre de la organización para textos de cara al usuario (pantallas de seguridad,
avisos, prompt de IA). Sale de branding_settings['org_name']; si no está configurado,
usa un fallback neutro para que una réplica NO muestre la marca de otra organización
(un aviso de seguridad a nombre ajeno parece phishing)."""

ORG_NAME_FALLBACK = 'Tu organización'


async def get_org_name(db) -> str:
    try:
        row = await db.fetchrow("SELECT value FROM branding_settings WHERE key = 'org_name'")
        if row and (row['value'] or '').strip():
            return row['value'].strip()
    except Exception:
        pass
    return ORG_NAME_FALLBACK
