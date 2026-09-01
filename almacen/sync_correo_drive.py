#!/opt/maquita-webmail/almacen/venv/bin/python3
# -*- coding: utf-8 -*-
"""
«Archivos del correo» en el Drive (T-21).
==========================================
Refleja los adjuntos del correo de cada persona en su Drive, carpeta del sistema
`/Archivos del correo/<Recibidos|Enviados>/<AAAA-MM>/`, sin pedir contraseñas: lee los buzones con
`doveadm` (Dovecot, como root) y escribe en el Almacén en proceso (nucleo_archivos → dedup por hash).
Cada adjunto queda vinculado a su correo (buzón, carpeta, UID) en la tabla `correo_adjuntos`; cuando el
correo deja de existir (eliminado definitivamente), el adjunto se manda a la papelera del Drive.
Corre por cron cada 5 min. Idempotente. Primera vez: solo los últimos DIAS_INICIALES días.
Uso: sync_correo_drive.py [--dry-run] [--usuario correo] [--dias N]
"""
import email
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from email import policy

BASE = '/opt/maquita-webmail/almacen'
sys.path.insert(0, os.path.join(BASE, 'servicio'))
for l in open(os.path.join(BASE, '.env'), encoding='utf-8'):
    l = l.strip()
    if l and not l.startswith('#') and '=' in l:
        k, v = l.split('=', 1)
        os.environ.setdefault(k.strip(), v.strip())

import psycopg2
import psycopg2.extras

DRY = '--dry-run' in sys.argv
SOLO = sys.argv[sys.argv.index('--usuario') + 1] if '--usuario' in sys.argv else None
DIAS_INICIALES = int(sys.argv[sys.argv.index('--dias') + 1]) if '--dias' in sys.argv else 30
CARPETA = '/Archivos del correo'
CARPETAS_CORREO = {'INBOX': 'Recibidos', 'Sent': 'Enviados'}
DOMINIOS = ('maquita.org', 'maquita.com.ec', 'fundacionmaquita.org')
TAM_MAX = 50 * 1024 * 1024
INLINE_MIN = 8 * 1024   # imágenes incrustadas pequeñas (firmas) no se reflejan


def log(m):
    print(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] {m}", flush=True)


def db_almacen():
    return psycopg2.connect(host=os.environ['ALMACEN_DB_HOST'], dbname=os.environ['ALMACEN_DB_NAME'],
                            user=os.environ['ALMACEN_DB_USER'], password=os.environ['ALMACEN_DB_PASSWORD'])


def asegurar_tablas(con):
    with con.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS correo_adjuntos (
                           id SERIAL PRIMARY KEY, usuario_id INTEGER NOT NULL, buzon VARCHAR(200) NOT NULL,
                           carpeta_correo VARCHAR(100) NOT NULL, uid BIGINT NOT NULL, message_id TEXT, asunto TEXT,
                           remitente TEXT, fecha_correo TIMESTAMP, nombre VARCHAR(300) NOT NULL, ruta_drive TEXT NOT NULL,
                           estado VARCHAR(20) NOT NULL DEFAULT 'activo', creado_en TIMESTAMP NOT NULL DEFAULT NOW(),
                           actualizado_en TIMESTAMP NOT NULL DEFAULT NOW());
                       CREATE INDEX IF NOT EXISTS ix_ca_usuario_ruta ON correo_adjuntos (usuario_id, ruta_drive);
                       CREATE INDEX IF NOT EXISTS ix_ca_correo ON correo_adjuntos (buzon, carpeta_correo, uid);
                       CREATE TABLE IF NOT EXISTS correo_sync_estado (
                           buzon VARCHAR(200) NOT NULL, carpeta_correo VARCHAR(100) NOT NULL,
                           ultimo_uid BIGINT NOT NULL DEFAULT 0, ultima_vez TIMESTAMP NOT NULL DEFAULT NOW(),
                           PRIMARY KEY (buzon, carpeta_correo));""")
    con.commit()


def buzones_enlazados():
    """[(buzon, usuario_id)] — buzones activos con usuario en el directorio (exacto o dominio equivalente)."""
    con_mail = psycopg2.connect(os.environ.get('MAILDB_DSN', 'dbname=maildb user=mailserver host=localhost'))
    try:
        with con_mail.cursor() as cur:
            cur.execute("SELECT lower(username) FROM mailbox WHERE active = TRUE")
            buzones = [r[0] for r in cur.fetchall()]
    finally:
        con_mail.close()
    con_nom = psycopg2.connect(host='193.16.0.132', dbname='nomina', user='sistemas', password=os.environ['ALMACEN_DB_PASSWORD'])
    try:
        with con_nom.cursor() as cur:
            cur.execute("SELECT id, lower(email) FROM usuarios WHERE active = TRUE AND email IS NOT NULL")
            por_correo = {e: i for i, e in cur.fetchall()}
    finally:
        con_nom.close()
    salida = []
    for b in buzones:
        if SOLO and b != SOLO:
            continue
        loc, _, dom = b.partition('@')
        uid = por_correo.get(b)
        if not uid and dom in DOMINIOS:
            for o in DOMINIOS:
                uid = por_correo.get(f'{loc}@{o}')
                if uid:
                    break
        if uid:
            salida.append((b, uid))
    return salida


def doveadm(*args):
    r = subprocess.run(['doveadm'] + list(args), capture_output=True, timeout=120)
    return r.returncode, r.stdout, r.stderr.decode(errors='replace')


def uids_desde(buzon, carpeta, ultimo_uid):
    if ultimo_uid > 0:
        rc, out, _ = doveadm('search', '-u', buzon, 'mailbox', carpeta, 'UID', f'{ultimo_uid + 1}:*')
    else:
        desde = (datetime.now() - timedelta(days=DIAS_INICIALES)).strftime('%Y-%m-%d')
        rc, out, _ = doveadm('search', '-u', buzon, 'mailbox', carpeta, 'SINCE', desde)
    if rc != 0:
        return []
    uids = []
    for linea in out.decode(errors='replace').splitlines():
        partes = linea.split()
        if len(partes) == 2 and partes[1].isdigit():
            uids.append(int(partes[1]))
    return sorted(uids)


def uid_existe(buzon, carpeta, uid):
    rc, out, _ = doveadm('search', '-u', buzon, 'mailbox', carpeta, 'UID', str(uid))
    return rc == 0 and bool(out.strip())


def mensaje_crudo(buzon, carpeta, uid):
    rc, out, _ = doveadm('fetch', '-u', buzon, 'text', 'mailbox', carpeta, 'uid', str(uid))
    if rc != 0 or not out:
        return None
    # doveadm antepone "text:\n" y termina con una línea vacía
    if out.startswith(b'text:'):
        out = out.split(b'\n', 1)[1] if b'\n' in out else b''
    return out


def adjuntos_de(crudo):
    msg = email.message_from_bytes(crudo, policy=policy.default)
    adj = []
    for parte in msg.walk():
        if parte.get_content_maintype() == 'multipart':
            continue
        nombre = parte.get_filename()
        disp = (parte.get('Content-Disposition') or '').lower()
        if not nombre:
            continue
        datos = parte.get_payload(decode=True) or b''
        if not datos or len(datos) > TAM_MAX:
            continue
        if 'inline' in disp and len(datos) < INLINE_MIN:
            continue
        adj.append((_nombre_seguro(nombre), datos))
    return msg, adj


def _nombre_seguro(n, maximo=120):
    n = re.sub(r'[\\/:*?"<>|\r\n\t]+', ' ', str(n)).strip().strip('.')
    return (re.sub(r'\s+', ' ', n) or 'adjunto')[:maximo]


def _fecha(msg):
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(msg.get('Date')).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def reflejar(con, nucleo, usuario_id, buzon, carpeta, uid, msg, adjuntos):
    sub = CARPETAS_CORREO.get(carpeta, carpeta)
    fecha = _fecha(msg)
    destino = f'{CARPETA}/{sub}/{fecha:%Y-%m}'
    if not DRY:
        nucleo.crear_carpeta(usuario_id, '/', CARPETA.strip('/')) if not _existe(nucleo, usuario_id, CARPETA) else None
        _asegurar(nucleo, usuario_id, CARPETA, sub)
        _asegurar(nucleo, usuario_id, f'{CARPETA}/{sub}', f'{fecha:%Y-%m}')
    n = 0
    for nombre, datos in adjuntos:
        ruta = f'{destino}/{nombre}'
        with con.cursor() as cur:
            cur.execute("SELECT 1 FROM correo_adjuntos WHERE usuario_id=%s AND buzon=%s AND carpeta_correo=%s AND uid=%s AND nombre=%s",
                        (usuario_id, buzon, carpeta, uid, nombre))
            if cur.fetchone():
                continue
            # nombre repetido de OTRO correo en la misma carpeta → sufijo con el UID
            cur.execute("SELECT 1 FROM correo_adjuntos WHERE usuario_id=%s AND ruta_drive=%s AND NOT (buzon=%s AND carpeta_correo=%s AND uid=%s)",
                        (usuario_id, ruta, buzon, carpeta, uid))
            if cur.fetchone():
                base, ext = os.path.splitext(nombre)
                nombre = f'{base} ({uid}){ext}'
                ruta = f'{destino}/{nombre}'
        if DRY:
            log(f'(dry-run) {buzon} {carpeta}#{uid} → {ruta} ({len(datos)} B)')
            n += 1
            continue
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(datos)
            tmp_path = tmp.name
        try:
            with open(tmp_path, 'rb') as flujo:
                nucleo.subir(usuario_id, destino, nombre, flujo)
            with con.cursor() as cur:
                cur.execute("""INSERT INTO correo_adjuntos (usuario_id, buzon, carpeta_correo, uid, message_id, asunto, remitente, fecha_correo, nombre, ruta_drive)
                               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                            (usuario_id, buzon, carpeta, uid, (msg.get('Message-ID') or '')[:500], (msg.get('Subject') or '')[:500],
                             (msg.get('From') or '')[:300], fecha, nombre, ruta))
            con.commit()
            n += 1
        except Exception as e:
            con.rollback()
            log(f'FALLO {buzon} {carpeta}#{uid} {nombre}: {e}')
        finally:
            os.unlink(tmp_path)
    return n


def _existe(nucleo, usuario_id, ruta):
    from seguridad_rutas import ruta_fisica
    return os.path.isdir(ruta_fisica(usuario_id, ruta))


def _asegurar(nucleo, usuario_id, padre, nombre):
    if not _existe(nucleo, usuario_id, f'{padre}/{nombre}'):
        try:
            nucleo.crear_carpeta(usuario_id, padre, nombre)
        except Exception as e:
            if 'existe' not in str(e).lower():
                raise


def limpiar_eliminados(con, nucleo, buzon, usuario_id):
    """Adjuntos cuyo correo ya no existe (eliminado definitivamente) → papelera del Drive."""
    with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
        cur.execute("SELECT DISTINCT carpeta_correo, uid FROM correo_adjuntos WHERE usuario_id=%s AND buzon=%s AND estado='activo'",
                    (usuario_id, buzon))
        pares = cur.fetchall()
    quitados = 0
    for p in pares:
        if uid_existe(buzon, p['carpeta_correo'], p['uid']):
            continue
        # ¿se movió a otra carpeta (p. ej. Papelera del correo)? buscar por Message-ID en todo el buzón
        with con.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT id, ruta_drive, message_id FROM correo_adjuntos WHERE usuario_id=%s AND buzon=%s AND carpeta_correo=%s AND uid=%s AND estado='activo'",
                        (usuario_id, buzon, p['carpeta_correo'], p['uid']))
            filas = cur.fetchall()
        mid = (filas[0]['message_id'] if filas else '') or ''
        if mid:
            rc, out, _ = doveadm('search', '-u', buzon, 'HEADER', 'Message-ID', mid)
            if rc == 0 and out.strip():
                continue   # sigue existiendo en otra carpeta (movido / en papelera del correo)
        for f in filas:
            if DRY:
                log(f'(dry-run) correo eliminado → papelera Drive: {f["ruta_drive"]}')
                continue
            try:
                nucleo.enviar_a_papelera(usuario_id, f['ruta_drive'])
            except Exception as e:
                log(f'papelera {f["ruta_drive"]}: {e}')
            with con.cursor() as cur:
                cur.execute("UPDATE correo_adjuntos SET estado='eliminado', actualizado_en=NOW() WHERE id=%s", (f['id'],))
            con.commit()
            quitados += 1
    return quitados


def main():
    import nucleo_archivos as nucleo
    import propietario_nfs
    propietario_nfs.instalar(nucleo)
    con = db_almacen()
    asegurar_tablas(con)
    total = quitados = 0
    for buzon, usuario_id in buzones_enlazados():
        for carpeta in CARPETAS_CORREO:
            with con.cursor() as cur:
                cur.execute("SELECT ultimo_uid FROM correo_sync_estado WHERE buzon=%s AND carpeta_correo=%s", (buzon, carpeta))
                r = cur.fetchone()
            ultimo = r[0] if r else 0
            uids = uids_desde(buzon, carpeta, ultimo)
            for uid in uids:
                crudo = mensaje_crudo(buzon, carpeta, uid)
                if not crudo:
                    continue
                try:
                    msg, adj = adjuntos_de(crudo)
                except Exception as e:
                    log(f'{buzon} {carpeta}#{uid}: no se pudo analizar ({e})')
                    continue
                if adj:
                    total += reflejar(con, nucleo, usuario_id, buzon, carpeta, uid, msg, adj)
            if uids and not DRY:
                with con.cursor() as cur:
                    cur.execute("""INSERT INTO correo_sync_estado (buzon, carpeta_correo, ultimo_uid, ultima_vez) VALUES (%s,%s,%s,NOW())
                                   ON CONFLICT (buzon, carpeta_correo) DO UPDATE SET ultimo_uid = EXCLUDED.ultimo_uid, ultima_vez = NOW()""",
                                (buzon, carpeta, max(uids)))
                con.commit()
        quitados += limpiar_eliminados(con, nucleo, buzon, usuario_id)
    log(f'Resumen: {total} adjuntos reflejados, {quitados} enviados a papelera por correo eliminado')
    con.close()


if __name__ == '__main__':
    main()
