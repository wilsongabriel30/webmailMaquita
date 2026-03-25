import aioimaplib
import asyncio


async def authenticate(username: str, password: str, host: str = "127.0.0.1", port: int = 143) -> bool:
    """Authenticate user via Dovecot IMAP LOGIN.

    Dovecot is the single authority for authentication.
    If the auth mechanism changes (LDAP, OAuth), only this file changes.
    """
    try:
        imap = aioimaplib.IMAP4(host=host, port=port, timeout=10)
        await imap.wait_hello_from_server()
        response = await imap.login(username, password)
        result = response.result == "OK"
        try:
            await imap.logout()
        except Exception:
            pass
        return result
    except (asyncio.TimeoutError, OSError, Exception):
        return False
