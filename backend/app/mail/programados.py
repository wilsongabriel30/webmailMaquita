"""Envío de los correos programados («enviar más tarde»).

Bucle de fondo que corre en cada worker. Es seguro con varios workers y varias
máquinas: cada correo se reclama con un UPDATE atómico (status pending → sending)
y solo el worker que gana el reclamo lo envía. Salió de main.py para que el
arranque no siga creciendo.
"""

import asyncio
import json
import logging

logger = logging.getLogger("scheduler")


async def procesar_programados(db_pool, redis):
    """Background task: check and send scheduled emails every 30s."""
    while True:
        try:
            await asyncio.sleep(30)
            # Check if table exists
            try:
                rows = await db_pool.fetch("""
                    SELECT id, username, to_list, cc_list, bcc_list, subject,
                           html_body, text_body, in_reply_to, "references",
                           request_read_receipt, request_delivery_receipt, importance
                    FROM scheduled_emails
                    WHERE status = 'pending' AND scheduled_at <= NOW()
                    ORDER BY scheduled_at ASC
                    LIMIT 10
                """)
            except Exception:
                # Table might not exist yet
                continue

            for row in rows:
                try:
                    # Reclamo atómico: solo UN worker envía cada correo programado
                    claimed = await db_pool.fetchrow(
                        "UPDATE scheduled_emails SET status = 'sending' "
                        "WHERE id = $1 AND status = 'pending' RETURNING id",
                        row["id"],
                    )
                    if not claimed:
                        continue
                    username = row["username"]
                    # F-01: la credencial está cifrada POR SESIÓN; vale cualquiera viva.
                    from app.auth.sesiones import credencial_de_alguna_sesion

                    cred = await credencial_de_alguna_sesion(redis, username)
                    if not cred:
                        logger.warning(
                            f"Scheduled email {row['id']}: no session for {username}"
                        )
                        await db_pool.execute(
                            "UPDATE scheduled_emails SET status = 'pending' WHERE id = $1",
                            row["id"],
                        )
                        continue
                    _sid, password, login_user = cred

                    from app.mail.clients.imap_client import get_imap_connection
                    from app.mail.services.send_service import send_and_save

                    imap = await get_imap_connection(login_user, password)
                    try:
                        # Get display name
                        display_name = ""
                        pref = await db_pool.fetchrow(
                            "SELECT display_name FROM user_preferences WHERE username = $1",
                            username,
                        )
                        if pref and pref["display_name"]:
                            display_name = pref["display_name"]

                        to_list = (
                            json.loads(row["to_list"])
                            if isinstance(row["to_list"], str)
                            else row["to_list"]
                        )
                        cc_list = (
                            json.loads(row["cc_list"])
                            if isinstance(row["cc_list"], str)
                            else row["cc_list"]
                        )
                        bcc_list = (
                            json.loads(row["bcc_list"])
                            if isinstance(row["bcc_list"], str)
                            else row["bcc_list"]
                        )

                        from app.mail.firmas import preparar_envio

                        html_body, inline_firma, _ = await asyncio.to_thread(
                            preparar_envio, row["html_body"] or ""
                        )
                        await send_and_save(
                            imap=imap,
                            password=password,
                            from_addr=username,
                            to=to_list,
                            subject=row["subject"],
                            text_body=row["text_body"],
                            html_body=html_body,
                            attachments=inline_firma or None,
                            cc=cc_list,
                            bcc=bcc_list,
                            in_reply_to=row["in_reply_to"],
                            references=row["references"],
                            display_name=display_name,
                            request_read_receipt=row["request_read_receipt"],
                            request_delivery_receipt=row["request_delivery_receipt"],
                            importance=row["importance"],
                        )

                        await db_pool.execute(
                            "UPDATE scheduled_emails SET status = 'sent' WHERE id = $1",
                            row["id"],
                        )
                        logger.info(f"Scheduled email {row['id']} sent successfully")
                    finally:
                        try:
                            await imap.logout()
                        except Exception:
                            pass

                except Exception as exc:
                    logger.error(f"Scheduled email {row['id']} failed: {exc}")
                    await db_pool.execute(
                        "UPDATE scheduled_emails SET status = 'failed' WHERE id = $1",
                        row["id"],
                    )

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.error(f"Scheduler loop error: {exc}")
            await asyncio.sleep(30)
