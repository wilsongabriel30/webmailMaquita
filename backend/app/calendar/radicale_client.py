"""Async HTTP client for Radicale CalDAV server."""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("calendar.radicale")

RADICALE_BASE = os.getenv("RADICALE_URL", "http://127.0.0.1:5232")


class RadicaleClient:
    """Async client that talks to Radicale via HTTP, using X-Remote-User auth."""

    def __init__(self):
        self._timeout = httpx.Timeout(10.0)

    def _headers(self, user: str) -> dict:
        # Radicale owner_only needs local part matching URL prefix
        local_part = user.split("@")[0] if "@" in user else user
        return {"X-Remote-User": local_part}

    async def ensure_calendar(
        self, user: str, calendar_path: str, display_name: str, color: str
    ) -> bool:
        """Create a calendar collection via MKCALENDAR if it doesn't exist."""
        url = f"{RADICALE_BASE}/{calendar_path}/"
        body = f"""<?xml version="1.0" encoding="UTF-8"?>
<mkcalendar xmlns="urn:ietf:params:xml:ns:caldav"
            xmlns:D="DAV:"
            xmlns:C="urn:ietf:params:xml:ns:caldav"
            xmlns:ICAL="http://apple.com/ns/ical/">
  <D:set>
    <D:prop>
      <D:displayname>{display_name}</D:displayname>
      <ICAL:calendar-color>{color}</ICAL:calendar-color>
    </D:prop>
  </D:set>
</mkcalendar>"""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(
                "MKCALENDAR",
                url,
                headers={**self._headers(user), "Content-Type": "application/xml"},
                content=body,
            )
            if resp.status_code in (201, 301):
                logger.info("Calendar created: %s", calendar_path)
                return True
            if resp.status_code == 405:
                # Already exists
                return True
            logger.warning(
                "MKCALENDAR %s returned %s: %s",
                calendar_path,
                resp.status_code,
                resp.text[:200],
            )
            return resp.status_code < 400

    async def put_event(
        self, user: str, calendar_path: str, uid: str, vcalendar_str: str
    ) -> bool:
        """PUT an .ics event into a Radicale calendar."""
        url = f"{RADICALE_BASE}/{calendar_path}/{uid}.ics"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.put(
                url,
                headers={
                    **self._headers(user),
                    "Content-Type": "text/calendar; charset=utf-8",
                },
                content=vcalendar_str,
            )
            ok = resp.status_code in (200, 201, 204)
            if not ok:
                logger.warning("PUT event %s returned %s", uid, resp.status_code)
            return ok

    async def delete_event(self, user: str, calendar_path: str, uid: str) -> bool:
        """DELETE an .ics event from Radicale."""
        url = f"{RADICALE_BASE}/{calendar_path}/{uid}.ics"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.delete(url, headers=self._headers(user))
            ok = resp.status_code in (200, 204, 404)
            if not ok:
                logger.warning("DELETE event %s returned %s", uid, resp.status_code)
            return ok

    async def list_events(self, user: str, calendar_path: str) -> str:
        """PROPFIND to list events in a calendar. Returns XML body."""
        url = f"{RADICALE_BASE}/{calendar_path}/"
        body = """<?xml version="1.0" encoding="UTF-8"?>
<D:propfind xmlns:D="DAV:">
  <D:prop>
    <D:getetag/>
    <D:getcontenttype/>
  </D:prop>
</D:propfind>"""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.request(
                "PROPFIND",
                url,
                headers={
                    **self._headers(user),
                    "Content-Type": "application/xml",
                    "Depth": "1",
                },
                content=body,
            )
            return resp.text


radicale_client = RadicaleClient()
