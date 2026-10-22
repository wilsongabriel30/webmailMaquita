"""Seguridad → Tableros: lectura de líneas de Postfix, Dovecot y ActiveSync y agregación por hora."""

from datetime import datetime, timedelta, timezone

from app.seguridad import agregador, parseo
from app.seguridad.parseo import EventoAcceso, EventoCorreo

ZONA = timezone(timedelta(hours=-5))
AHORA = datetime(2026, 10, 21, 12, 0, tzinfo=ZONA)


def _uno(linea):
    ev = parseo.analizar_linea(linea, AHORA, ZONA)
    assert len(ev) == 1, ev
    return ev[0]


def test_fechas_syslog_iso_y_diario():
    a = _uno("Oct 21 10:30:01 mail postfix/smtpd[123]: NOQUEUE: reject: RCPT from x[203.0.113.5]: 554 5.7.1 rechazado")
    assert a.momento == datetime(2026, 10, 21, 10, 30, 1, tzinfo=ZONA)
    b = _uno("2026-10-21T10:30:01.123456-05:00 mail postfix/smtpd[123]: NOQUEUE: reject: RCPT from x[203.0.113.5]: 554")
    c = _uno("2026-10-21T10:30:01-0500 mail postfix/smtpd[123]: NOQUEUE: reject: RCPT from x[203.0.113.5]: 554")
    assert b.momento.replace(microsecond=0) == c.momento == a.momento
    # Diciembre leído en enero: año anterior
    enero = datetime(2027, 1, 1, 0, 5, tzinfo=ZONA)
    ev = parseo.analizar_linea("Dec 31 23:59:59 mail postfix/smtpd[1]: NOQUEUE: reject: x", enero, ZONA)
    assert ev[0].momento.year == 2026


def test_flujo_de_postfix():
    lineas = [
        "Oct 21 10:00:01 mail postfix/lmtp[9]: 4F3A1B2C: to=<ana@example.org>, relay=mail[private/dovecot-lmtp], delay=0.2, delays=0/0/0/0.1, dsn=2.0.0, status=sent (250 2.0.0 Saved)",
        "Oct 21 10:00:02 mail postfix/smtp[9]: 4F3A1B2D: to=<x@example.com>, relay=mx.example.com[198.51.100.7]:25, delay=1, delays=0/0/0.5/0.5, dsn=2.0.0, status=sent (250 ok)",
        "Oct 21 10:00:03 mail postfix/smtp[9]: 4F3A1B2E: to=<x@example.com>, relay=none, delay=30, delays=0/0/30/0, dsn=4.4.1, status=deferred (connect timed out)",
        "Oct 21 10:00:04 mail postfix/smtp[9]: 4F3A1B2F: to=<y@example.com>, relay=mx.example.com[198.51.100.7]:25, delay=1, dsn=5.1.1, status=bounced (user unknown)",
        "Oct 21 10:00:05 mail postfix/cleanup[9]: 4F3A1B30: milter-reject: END-OF-MESSAGE from x[203.0.113.9]: 5.7.1 Spam message rejected",
        "Oct 21 11:00:06 mail postfix/postscreen[9]: NOQUEUE: reject: RCPT from [203.0.113.9]:4000: 550 5.7.1 Service unavailable",
        # Reinyección local (filtro de contenido en 127.0.0.1): no es un envío
        "Oct 21 11:00:07 mail postfix/smtp[9]: 4F3A1B31: to=<z@example.com>, relay=127.0.0.1[127.0.0.1]:10025, delay=0.1, dsn=2.0.0, status=sent (250 ok)",
        "Oct 21 11:00:08 mail postfix/qmgr[9]: 4F3A1B31: removed",
    ]
    eventos = [e for linea in lineas for e in parseo.analizar_linea(linea, AHORA, ZONA)]
    assert [e.tipo for e in eventos] == ["recibido", "enviado", "diferido", "rebotado", "rechazado_filtro", "rechazado"]
    por_hora = agregador.agregar_correo(eventos)
    h10 = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)  # 10:00 en UTC-5
    assert por_hora[h10]["recibidos"] == 1 and por_hora[h10]["enviados"] == 1
    assert por_hora[h10]["rechazados_filtro"] == 1 and por_hora[h10]["rebotados"] == 1
    assert por_hora[h10 + timedelta(hours=1)]["rechazados"] == 1


def test_accesos_smtp_y_dovecot():
    ok = _uno("Oct 21 10:00:01 mail postfix/submission/smtpd[7]: 4F3A1B2C: client=unknown[203.0.113.5], sasl_method=PLAIN, sasl_username=Ana@Example.org")
    assert (ok.servicio, ok.resultado, ok.cuenta, ok.ip) == ("smtp", "ok", "ana@example.org", "203.0.113.5")
    f1 = _uno("Oct 21 10:00:02 mail postfix/smtpd[7]: warning: unknown[203.0.113.6]: SASL LOGIN authentication failed: UGFzc3dvcmQ6")
    assert (f1.resultado, f1.cuenta, f1.ip) == ("fallo", "", "203.0.113.6")
    f2 = _uno("Oct 21 10:00:02 mail postfix/smtpd[7]: warning: unknown[203.0.113.6]: SASL PLAIN authentication failed: , sasl_username=ana@example.org")
    assert f2.cuenta == "ana@example.org"
    d = _uno("Oct 21 10:00:03 mail dovecot: imap-login: Login: user=<ana@example.org>, method=PLAIN, rip=198.51.100.20, lip=192.0.2.1, mpid=1, TLS, session=<abc>")
    assert (d.servicio, d.resultado, d.ip) == ("imap", "ok", "198.51.100.20")
    df = _uno("2026-10-21T10:00:04-0500 mail dovecot[5]: pop3-login: Disconnected: Connection closed (auth failed, 3 attempts in 15 secs): user=<ana@example.org>, method=PLAIN, rip=203.0.113.7, lip=192.0.2.1, TLS")
    assert (df.servicio, df.resultado, df.veces, df.ip) == ("pop3", "fallo", 3, "203.0.113.7")
    sin_usuario = _uno("Oct 21 10:00:05 mail dovecot: imap-login: Aborted login (auth failed, 1 attempts in 2 secs): method=PLAIN, rip=203.0.113.8, lip=192.0.2.1")
    assert sin_usuario.cuenta == "" and sin_usuario.ip == "203.0.113.8"
    assert parseo.analizar_linea("Oct 21 10:00:05 mail sshd[1]: Accepted password for root", AHORA, ZONA) == []
    assert parseo.analizar_linea("línea que no es de syslog", AHORA, ZONA) == []


def test_activesync():
    base = '203.0.113.30 - {u} [21/Oct/2026:10:15:00 -0500] "POST /Microsoft-Server-ActiveSync?Cmd=Ping&User=ana%40example.org&DeviceId=X HTTP/1.1" {c} 12 "-" "Android/14"'
    ok = parseo.analizar_activesync(base.format(u="ana%40example.org", c=200))
    assert ok[0].resultado == "ok" and ok[0].cuenta == "ana@example.org"
    assert ok[0].momento == datetime(2026, 10, 21, 10, 15, tzinfo=ZONA)
    # El saludo sin credenciales (401 sin usuario) no es un fallo
    assert parseo.analizar_activesync(base.format(u="-", c=401)) == []
    fallo = parseo.analizar_activesync(base.format(u="ana@example.org", c=401))
    assert fallo[0].resultado == "fallo"
    assert parseo.analizar_activesync('203.0.113.30 - - [21/Oct/2026:10:15:00 -0500] "GET /index.html HTTP/1.1" 200 1 "-" "x"') == []


def test_auditoria_webmail_y_panel():
    m = datetime(2026, 10, 21, 15, 0, tzinfo=timezone.utc)
    assert parseo.evento_auditoria("webmail", "login_failed", "(login_attempt)", "203.0.113.4", m).cuenta == ""
    assert parseo.evento_auditoria("webmail", "login_success", "ana@example.org", None, m).resultado == "ok"
    assert parseo.evento_auditoria("panel", "login_failed", "admin", "192.0.2.10", m).resultado == "fallo"
    assert parseo.evento_auditoria("panel", "respaldo_manual", "admin", "", m) is None


def test_agregar_accesos_activesync_una_vez_por_hora():
    m = datetime(2026, 10, 21, 15, 5, tzinfo=timezone.utc)
    eventos = [EventoAcceso(m + timedelta(minutes=i), "activesync", "ok", "ana@example.org", "203.0.113.30", pais="EC") for i in range(10)]
    eventos += [EventoAcceso(m, "imap", "ok", "ana@example.org", "203.0.113.30", pais="EC")] * 3
    eventos += [EventoAcceso(m, "imap", "fallo", "ana@example.org", "203.0.113.30", veces=4, pais="EC")]
    filas = agregador.agregar_accesos(eventos)
    hora = m.replace(minute=0)
    assert filas[(hora, "activesync", "ana@example.org", "203.0.113.30")]["ok"] == 1
    assert filas[(hora, "imap", "ana@example.org", "203.0.113.30")] == {"pais": "EC", "ok": 3, "fallos": 4}
    assert all(isinstance(e, (EventoAcceso, EventoCorreo)) for e in eventos)


def test_pasarela_no_cuenta_dos_veces():
    es = agregador.filtro_pasarela()
    m = datetime(2026, 10, 21, 15, 5, tzinfo=timezone.utc)
    assert es(EventoAcceso(m, "imap", "ok", "a@example.org", "127.0.0.1"))
    assert agregador.filtro_pasarela(["192.0.2.0/24"])(EventoAcceso(m, "imap", "ok", "a@example.org", "192.0.2.7"))
    assert not es(EventoAcceso(m, "imap", "ok", "a@example.org", "203.0.113.5"))
    assert not es(EventoAcceso(m, "webmail", "ok", "a@example.org", "127.0.0.1"))


def test_delta_rspamd():
    antes = {"scanned": 100, "actions": {"reject": 10, "add header": 5, "greylist": 2, "no action": 83}}
    ahora = {"scanned": 130, "actions": {"reject": 12, "add header": 9, "rewrite subject": 1, "greylist": 2, "no action": 106}}
    assert agregador.delta_rspamd(None, ahora) == {}
    d = agregador.delta_rspamd(antes, ahora)
    assert d == {"analizados": 30, "spam_rechazado": 2, "spam_marcado": 5, "spam_aplazado": 0}
    # Rspamd reiniciado: los contadores empiezan de cero y todo lo de ahora es nuevo
    reinicio = agregador.delta_rspamd(ahora, {"scanned": 7, "actions": {"reject": 1}})
    assert reinicio["analizados"] == 7 and reinicio["spam_rechazado"] == 1
