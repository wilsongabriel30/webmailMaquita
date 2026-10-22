"""Una pasada completa del recolector con registros sintéticos y una base simulada."""

import asyncio
import json
from contextlib import asynccontextmanager

from app.seguridad import avisos, exportar, fuentes, recolector

CORREO = [
    "Oct 21 10:00:01 mail postfix/lmtp[9]: 4F3A1B2C: to=<ana@example.org>, relay=mail[private/dovecot-lmtp], delay=0.2, dsn=2.0.0, status=sent (250 Saved)",
    "Oct 21 10:00:02 mail postfix/smtpd[7]: NOQUEUE: reject: RCPT from x[203.0.113.9]: 554 5.7.1 rechazado",
] + [
    f"Oct 21 10:01:0{i} mail dovecot: imap-login: Disconnected (auth failed, 1 attempts in 2 secs): user=<ana@example.org>, method=PLAIN, rip=203.0.113.50, lip=192.0.2.1"
    for i in range(6)
] + [
    "Oct 21 10:02:00 mail dovecot: imap-login: Login: user=<ana@example.org>, method=PLAIN, rip=203.0.113.50, lip=192.0.2.1, TLS",
    # El webmail entrando a IMAP con la clave de la persona: no cuenta (ya se cuenta en el webmail)
    "Oct 21 10:02:01 mail dovecot: imap-login: Login: user=<ana@example.org>, method=PLAIN, rip=127.0.0.1, lip=127.0.0.1",
]


class Conexion:
    def __init__(self, base):
        self.b = base

    @asynccontextmanager
    async def transaction(self):
        yield

    async def fetchval(self, sql, *a):
        self.b.sql.append(sql)
        if "FROM seg_estado" in sql:
            v = self.b.estado.get(a[0])
            return None if v is None else json.dumps(v)
        if "pg_try_advisory_lock" in sql:
            return True
        return 0

    async def fetch(self, sql, *a):
        self.b.sql.append(sql)
        return []

    async def fetchrow(self, sql, *a):
        self.b.sql.append(sql)
        if "INSERT INTO seg_alertas" in sql:
            self.b.alertas.append(a)
            return {"id": len(self.b.alertas), "nueva": True}
        return None

    async def execute(self, sql, *a):
        self.b.sql.append(sql)
        if "INSERT INTO seg_estado" in sql:
            self.b.estado[a[0]] = json.loads(a[1])
        if "INSERT INTO seg_flujo_hora" in sql and "en_cola" not in sql:
            self.b.flujo.append(a)
        return "DELETE 0"

    async def executemany(self, sql, filas):
        self.b.sql.append(sql)
        if "seg_accesos_detalle" in sql:
            self.b.detalle.extend(filas)


class Pool:
    def __init__(self):
        self.estado, self.sql, self.alertas, self.flujo, self.detalle = {}, [], [], [], []

    @asynccontextmanager
    async def acquire(self):
        yield Conexion(self)

    async def fetchrow(self, sql, *a):
        return None  # seg_config sin fila: valores por omisión


def test_pasada_completa(tmp_path, monkeypatch):
    log = tmp_path / "mail.log"
    log.write_text("\n".join(CORREO) + "\n")
    monkeypatch.setattr(recolector, "LOG_CORREO", str(log))
    monkeypatch.setattr(recolector, "LOG_ACTIVESYNC", str(tmp_path / "no-existe.log"))
    stats = iter([{"scanned": 100, "actions": {"reject": 4}}, {"scanned": 110, "actions": {"reject": 6}}])

    async def rspamd():
        return next(stats)

    monkeypatch.setattr(recolector, "_rspamd", rspamd)
    monkeypatch.setattr(fuentes, "tamano_cola", lambda: 3)
    enviados = []
    monkeypatch.setattr(avisos, "enviar", lambda asunto, cuerpo, destinos: enviados.append((asunto, cuerpo)) or True)
    monkeypatch.setattr(exportar, "activo", lambda: False)

    base = Pool()
    r = asyncio.run(recolector.pasada(base))
    assert r["fuentes"]["correo"]["lineas"] == len(CORREO)
    assert r["eventos_acceso"] == 7  # 6 fallos + 1 acceso (el de 127.0.0.1 no)
    assert r["alertas_nuevas"] == 1 and base.alertas[0][0] == "fallos_y_exito"
    assert enviados and "[ALTA]" in enviados[0][1]
    imap = [f for f in base.detalle if f[1] == "imap"]
    assert imap == [(imap[0][0], "imap", "ana@example.org", "203.0.113.50", imap[0][4], 1, 6)]
    assert base.estado["pos_correo"]["pos"] == log.stat().st_size
    assert base.estado["rspamd"]["scanned"] == 100
    assert "ultima_pasada" in base.estado

    # Segunda pasada: no relee nada y cuenta la diferencia de Rspamd
    r2 = asyncio.run(recolector.pasada(base))
    assert r2["fuentes"]["correo"]["lineas"] == 0 and r2["alertas_nuevas"] == 0
    assert any(10 in f and 2 in f for f in base.flujo[-1:])  # analizados +10, rechazados como spam +2
