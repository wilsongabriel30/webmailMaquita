"""Barreras de la subida de personas externas (15/10/2026).

Quien sube desde fuera no tiene cuenta: si le roban el correo, el ladrón
también recibe el código. Por eso, además del código, cada archivo pasa por:
  1. Plazo: solo se sube entre `subida_desde` y `subida_hasta` (obligatorio).
  2. Tipo: ejecutables, scripts y Office con macros no entran (por extensión y
     por contenido, incluido lo que viaje dentro de un .zip). Las macros se
     pueden permitir por invitación (opción avanzada `permite_macros`); los
     programas y scripts, nunca.
  3. Tope: como mucho TOPE_INVITACION en total por invitación.
  4. Antivirus: ClamAV (clamd) revisa el archivo ANTES de que entre al Drive.
     Si el antivirus no responde, NO se guarda (falla cerrado).
"""
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

log = logging.getLogger(__name__)

ECUADOR = timezone(timedelta(hours=-5))
TOPE_INVITACION = 20 * 1024 ** 3          # 20 GB por invitación
DIR_TEMPORAL = '/var/tmp/subida-externa'
EXT_BLOQUEADAS = {
    # ejecutables e instaladores
    'exe', 'msi', 'msp', 'com', 'scr', 'pif', 'cpl', 'dll', 'sys', 'drv', 'ocx', 'apk', 'app', 'deb', 'rpm',
    # scripts y accesos directos
    'bat', 'cmd', 'ps1', 'psm1', 'psd1', 'vbs', 'vbe', 'js', 'jse', 'wsf', 'wsh', 'hta', 'sh', 'bash',
    'jar', 'py', 'pl', 'rb', 'php', 'lnk', 'url', 'reg', 'inf', 'scf', 'iso', 'img', 'vhd', 'vhdx',
    # Office con macros
    'docm', 'dotm', 'xlsm', 'xltm', 'xlam', 'xlsb', 'pptm', 'potm', 'ppam', 'ppsm', 'sldm',
}


def _fecha(momento):
    return momento.astimezone(ECUADOR).strftime('%d/%m/%Y %H:%M')


def plazo_abierto(fila):
    """(True, '') si hoy se puede subir; (False, motivo) si no."""
    ahora = datetime.now(timezone.utc)
    desde, hasta = fila.get('subida_desde'), fila.get('subida_hasta')
    if not hasta:
        return False, 'Esta invitación no tiene plazo para subir archivos.'
    if desde and ahora < desde:
        return False, 'Podrás subir archivos a partir del %s.' % _fecha(desde)
    if ahora >= hasta:
        return False, 'El plazo para subir archivos terminó el %s.' % _fecha(hasta)
    return True, ''


EXT_CON_MACROS = {'docm', 'dotm', 'xlsm', 'xltm', 'xlam', 'xlsb', 'pptm', 'potm', 'ppam', 'ppsm', 'sldm'}
AVISO_MACROS = ('El archivo «%s» contiene macros. Por seguridad está restringida la subida de documentos '
                'con macros. Guárdalo sin macros (.xlsx, .docx, .pptx) y vuelve a subirlo.')
AVISO_PROGRAMA = ('El archivo «%s» es un programa, un script o un acceso directo. Por seguridad está '
                  'restringida la subida de este tipo de archivos.')


def _ext(nombre):
    return nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ''


def tipo_prohibido(nombre, con_macros=False):
    """Aviso si la extensión no se admite; None si se admite.
    `con_macros`: la invitación tiene la opción avanzada «Permitir documentos
    con macros» (solo levanta ESA barrera; los programas siguen fuera)."""
    ext = _ext(nombre)
    if ext in EXT_CON_MACROS:
        return None if con_macros else AVISO_MACROS % nombre
    if ext in EXT_BLOQUEADAS:
        return AVISO_PROGRAMA % nombre
    return None


def tiene_macros(ruta, nombre):
    import macros
    return macros.extension_de(nombre) in macros.EXTENSIONES_OFIMATICA and macros.tiene_macros(ruta, nombre)


def contenido_prohibido(ruta, nombre, con_macros=False):
    """Mira DENTRO del archivo ya recibido (la extensión se puede cambiar):
      - documento de Office: ¿trae macros? (macros.py, el detector del Drive;
        ante la duda dice que sí) — salvo que la invitación las permita;
      - .zip: ¿lleva dentro programas (o documentos con macros, si no se permiten)?
    Devuelve el aviso o None."""
    import zipfile
    if not con_macros and tiene_macros(ruta, nombre):
        return AVISO_MACROS % nombre
    if _ext(nombre) == 'zip':
        try:
            with zipfile.ZipFile(ruta) as comprimido:
                for interno in comprimido.namelist():
                    if tipo_prohibido(interno.rsplit('/', 1)[-1], con_macros):
                        return ('El comprimido «%s» lleva dentro «%s», que no se admite (programa, script o '
                                'documento con macros). Quítalo del .zip y vuelve a subirlo.' % (nombre, interno))
        except zipfile.BadZipFile:
            return 'El comprimido «%s» está dañado y no se puede revisar.' % nombre
    return None


def cabe(fila, tamano):
    return (int(fila.get('subida_bytes') or 0) + int(tamano or 0)) <= TOPE_INVITACION


def a_temporal(flujo, limite):
    """Copia el archivo a disco local. Devuelve (ruta, tamaño) o lanza ValueError si pasa el límite."""
    os.makedirs(DIR_TEMPORAL, mode=0o700, exist_ok=True)
    descriptor, ruta = tempfile.mkstemp(dir=DIR_TEMPORAL)
    tamano = 0
    try:
        with os.fdopen(descriptor, 'wb') as destino:
            while True:
                trozo = flujo.read(1024 * 1024)
                if not trozo:
                    break
                tamano += len(trozo)
                if tamano > limite:
                    raise ValueError('El archivo supera el límite de 2 GB.')
                destino.write(trozo)
    except Exception:
        borrar(ruta)
        raise
    return ruta, tamano


def revisar_virus(ruta):
    """(True, '') si está limpio; (False, firma) si tiene virus.
    Lanza RuntimeError si el antivirus no pudo revisarlo."""
    try:
        r = subprocess.run(['clamdscan', '--fdpass', '--no-summary', '--stdout', ruta],
                           capture_output=True, text=True, timeout=600)
    except Exception as excepcion:
        raise RuntimeError('antivirus no disponible: %s' % excepcion)
    if r.returncode == 0:
        return True, ''
    if r.returncode == 1:
        firma = (r.stdout.strip().split(': ', 1)[-1]).replace(' FOUND', '')
        return False, firma[:120]
    raise RuntimeError('antivirus con error: %s' % (r.stdout + r.stderr).strip()[:200])


def borrar(ruta):
    try:
        if ruta and os.path.exists(ruta):
            os.remove(ruta)
    except OSError:
        pass
