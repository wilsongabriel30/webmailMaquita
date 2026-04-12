import aioimaplib
import asyncio
import logging

logger = logging.getLogger("auth")


async def authenticate(username: str, password: str, host: str = "127.0.0.1", port: int = 143) -> bool:
    """Authenticate user via Dovecot IMAP LOGIN."""
    try:
        logger.info("auth_attempt | user=%s | pass_len=%d | host=%s:%d", username, len(password), host, port)
        imap = aioimaplib.IMAP4(host=host, port=port, timeout=10)
        await imap.wait_hello_from_server()
        response = await imap.login(username, password)
        result = response.result == "OK"
        logger.info("auth_result | user=%s | result=%s | response=%s", username, result, response.result)
        try:
            await imap.logout()
        except Exception:
            pass
        return result
    except asyncio.TimeoutError:
        logger.error("auth_timeout | user=%s", username)
        return False
    except OSError as e:
        logger.error("auth_os_error | user=%s | error=%s", username, e)
        return False
    except Exception as e:
        logger.error("auth_exception | user=%s | error=%s | type=%s", username, e, type(e).__name__)
        return False
