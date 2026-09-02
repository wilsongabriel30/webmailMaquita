"""Conectar dispositivos al Drive como disco — Almacén Maquita.

Da a cada persona lo que necesita para montar su unidad en el ordenador o el
móvil, sin pasar por Tecnología y sin usar su contraseña de FARO.

  POST   /dav/dispositivos            crea una llave para un equipo
  GET    /dav/dispositivos            lista los equipos conectados
  POST   /dav/dispositivos/<id>/revocar   corta el acceso de uno

LA LLAVE SE MUESTRA UNA SOLA VEZ
    En la base se guarda unicamente el hash. Si alguien la pierde, no se
    recupera: se revoca y se crea otra. Es lo mismo que hacen Google, GitHub o
    cualquier sistema serio de contrasenas de aplicacion, y por el mismo
    motivo: una llave que el servidor puede leer es una llave que se puede
    filtrar desde el servidor.

POR QUE UNA LLAVE POR EQUIPO Y NO LA CONTRASENA DE FARO
    Porque un equipo se pierde, se presta o se deja en una oficina. Con una
    llave por equipo se corta ESE acceso desde el panel, en un clic, sin
    cambiarle la contrasena a nadie ni tocar los demas dispositivos.

Servidor WebDAV: /home/sistemas/almacen-dav/servidor_dav.py
Doc: 00-CLAUDE-CONTEXTO/PLAN-CLIENTE-DISCO-Y-MOVIL.md
"""

import hashlib
import logging
import secrets

from flask import Blueprint, jsonify, request, Response

from almacen_bd import consultar, ejecutar
from api_archivos import error, usuario_actual

log = logging.getLogger('almacen.dav')

bp_dav = Blueprint('almacen_dav', __name__)

# Tope de equipos por persona. No es una limitacion técnica: es que una lista
# de treinta llaves ya nadie la revisa, y las llaves que nadie revisa son las
# que se quedan activas en equipos que ya no se usan.
MAXIMO_DISPOSITIVOS = 10


def _hash(token):
    """Mismo cálculo que hace el servidor WebDAV al validar."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


@bp_dav.route('/dav/dispositivos', methods=['GET'])
def listar_dispositivos():
    """Equipos con acceso. NUNCA devuelve la llave, que no se guarda."""
    usuario = usuario_actual()
    filas = consultar("""
        SELECT id, nombre, solo_lectura, creado, ultimo_uso, ultima_ip
          FROM dav_tokens
         WHERE usuario_id = %s AND revocado IS NULL
         ORDER BY COALESCE(ultimo_uso, creado) DESC
    """, (usuario,))
    return jsonify({
        'success': True,
        'dispositivos': [{
            'id': f['id'],
            'nombre': f['nombre'],
            'solo_lectura': f['solo_lectura'],
            'creado': f['creado'].isoformat() if f['creado'] else None,
            'ultimo_uso': f['ultimo_uso'].isoformat() if f['ultimo_uso'] else None,
            'ultima_ip': f['ultima_ip'],
            # Si nunca se uso, seguramente la configuracion quedo a medias.
            'usado': bool(f['ultimo_uso']),
        } for f in filas],
        'maximo': MAXIMO_DISPOSITIVOS,
    })


@bp_dav.route('/dav/dispositivos', methods=['POST'])
def crear_dispositivo():
    """Crea una llave. La devuelve EN CLARO una sola vez."""
    usuario = usuario_actual()
    datos = request.get_json() or {}
    nombre = (datos.get('nombre') or '').strip()[:60]
    if not nombre:
        return error('Ponle un nombre al equipo para reconocerlo después '
                     '(por ejemplo: «Portátil de contabilidad»)', 400)

    cuantos = consultar(
        "SELECT COUNT(*) AS n FROM dav_tokens "
        " WHERE usuario_id = %s AND revocado IS NULL", (usuario,))[0]['n']
    if cuantos >= MAXIMO_DISPOSITIVOS:
        return error('Ya tienes %s equipos conectados, que es el máximo. '
                     'Revoca alguno que ya no uses antes de añadir otro.'
                     % MAXIMO_DISPOSITIVOS, 409)

    # 32 bytes al azar. Se muestra una vez y se guarda solo su hash.
    token = secrets.token_urlsafe(32)
    ejecutar("""
        INSERT INTO dav_tokens (usuario_id, nombre, token_hash, solo_lectura)
        VALUES (%s, %s, %s, TRUE)
    """, (usuario, nombre, _hash(token)))

    log.info('Nuevo dispositivo DAV "%s" para usuario %s', nombre, usuario)
    return jsonify({
        'success': True,
        'usuario': str(usuario),
        'token': token,          # la unica vez que sale del servidor
        'solo_lectura': True,
        'aviso': 'Guarda esta clave ahora: no se puede volver a mostrar.',
    }), 201


@bp_dav.route('/dav/dispositivos/revocar-todos', methods=['POST'])
def revocar_todos_dispositivos():
    """Corta el acceso de TODOS los equipos del usuario de una vez. Para cuando
    se pierde o roban un equipo y no se sabe cual es: revocas todo y vuelves a
    conectar los que sigas usando."""
    usuario = usuario_actual()
    cuantos = consultar("SELECT COUNT(*) AS n FROM dav_tokens "
                        "WHERE usuario_id = %s AND revocado IS NULL",
                        (usuario,))[0]['n']
    ejecutar("UPDATE dav_tokens SET revocado = now() "
             "WHERE usuario_id = %s AND revocado IS NULL", (usuario,))
    log.warning('TODOS los dispositivos revocados por usuario %s (%d)', usuario, cuantos)
    return jsonify({'success': True, 'revocados': cuantos,
                    'mensaje': ('Se cortó el acceso de %d equipo%s. Vuelve a '
                                'conectar los que sigas usando.'
                                % (cuantos, '' if cuantos == 1 else 's'))})


@bp_dav.route('/dav/dispositivos/<int:dispositivo_id>/revocar', methods=['POST'])
def revocar_dispositivo(dispositivo_id):
    """Corta el acceso de un equipo. Inmediato: la siguiente petición falla."""
    usuario = usuario_actual()
    # El filtro por usuario_id no es adorno: impide revocar el equipo de otro
    # cambiando el número en la dirección.
    # `ejecutar` devuelve la PRIMERA FILA cuando hay RETURNING, no una lista.
    fila = ejecutar("""
        UPDATE dav_tokens SET revocado = now()
         WHERE id = %s AND usuario_id = %s AND revocado IS NULL
        RETURNING nombre
    """, (dispositivo_id, usuario))
    if not fila:
        return error('Ese equipo no existe o ya estaba revocado', 404)

    log.info('Dispositivo DAV %s revocado por usuario %s', dispositivo_id, usuario)
    return jsonify({'success': True,
                    'mensaje': 'Se cortó el acceso de "%s"' % fila['nombre']})


# ── Instalador de un clic para Windows ──────────────────────────────────────
# El usuario NO tiene que hacer pasos: baja este archivo, lo ejecuta, y la
# unidad queda montada sola, con el logo de Maquita. El token va DENTRO del
# archivo (por eso no pide credenciales). Cada descarga crea una llave nueva;
# el usuario puede revocar las que no use desde «Ordenadores».
_PLANTILLA_BAT = r"""@echo off
chcp 65001 >nul
title Conectar Drive Maquita
rem ===== Autoelevacion (necesita permisos para el servicio WebDAV) =====
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -Command "Start-Process -FilePath '%~f0' -Verb RunAs" >nul 2>&1
    exit /b
)
echo.
echo   Conectando tu Drive Maquita, espera un momento...
echo.
rem ===== Servicio WebDAV de Windows =====
sc config WebClient start= auto >nul 2>&1
net start WebClient >nul 2>&1
rem ===== Permitir archivos grandes por WebDAV (4 GB) =====
reg add "HKLM\SYSTEM\CurrentControlSet\Services\WebClient\Parameters" /v FileSizeLimitInBytes /t REG_DWORD /d 4294967295 /f >nul 2>&1
net stop WebClient >nul 2>&1
net start WebClient >nul 2>&1
rem ===== Montar la unidad __LETRA__: =====
net use __LETRA__: /delete /y >nul 2>&1
net use __LETRA__: "\\drive.maquita.com.ec@SSL\dav" /user:__USUARIO__ __TOKEN__ /persistent:yes
if %errorlevel% neq 0 (
    echo   No se pudo conectar. Revisa tu internet y vuelve a ejecutar.
    echo   Si sigue, avisa a Tecnologia.
    pause
    exit /b
)
rem ===== Logo de Maquita y nombre de la unidad =====
if not exist "%LOCALAPPDATA%\MaquitaDrive" mkdir "%LOCALAPPDATA%\MaquitaDrive"
powershell -Command "try{Invoke-WebRequest -UseBasicParsing -Uri 'https://drive.maquita.com.ec/static/maquita-drive.ico' -OutFile \"$env:LOCALAPPDATA\MaquitaDrive\maquita.ico\"}catch{}" >nul 2>&1
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\DriveIcons\__LETRA__\DefaultIcon" /ve /t REG_SZ /d "%LOCALAPPDATA%\MaquitaDrive\maquita.ico" /f >nul 2>&1
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\DriveIcons\__LETRA__\DefaultLabel" /ve /t REG_SZ /d "Drive Maquita" /f >nul 2>&1
rem ===== Refrescar y abrir =====
start "" __LETRA__:\
echo.
echo   Listo. Tu Drive Maquita esta en la unidad __LETRA__:
echo   Ya puedes cerrar esta ventana.
echo.
timeout /t 6 >nul
"""


def _uso_personal_bytes(usuario_id):
    """Bytes que ocupa el espacio PERSONAL del usuario, para la app de Windows.

    P-17 (05/08/2026): la app necesita saber cuánto pesa el Drive ANTES de la
    primera descarga, para avisar si no cabe en el disco. Lo hacía con
    `rclone size` (PROPFIND recursivo) y en espacios grandes no terminaba: con
    56.752 archivos se abandonó a los 270 segundos. El servidor lo sabe al
    instante porque lo tiene indexado.

    Se cuenta SOLO lo que la app va a descargar:
      - sin «Unidades compartidas» (viven fuera del espacio del usuario y en la
        app se trabajan en vivo, no se bajan);
      - sin la PAPELERA (ocupa cuota pero no se sincroniza), a diferencia de
        `nucleo.cuota()`, que sí la suma porque allí interesa el cobro de cuota.

    Devuelve None si no se puede calcular: la app tiene su plan B y es mejor
    callar que dar una cifra equivocada.
    """
    try:
        from almacen_bd import consultar
        filas = consultar(
            'SELECT COALESCE(SUM(tamano), 0) AS s FROM indice_nombres '
            ' WHERE usuario_id = %s AND NOT es_carpeta', (usuario_id,))
        total = int(filas[0]['s']) if filas else 0
        return total if total > 0 else None
    except Exception as excepcion:
        log.warning('No se pudo calcular uso_bytes de %s: %s', usuario_id, excepcion)
        return None


def _perfil_del_usuario(usuario_id):
    """Perfil de la persona para que la app muestre unas opciones u otras (P-07).

    Devuelve el `rol` real de FARO y un `perfil` ya resumido, que es lo que la
    app necesita para decidir qué enseñar:

      administrador → master / master_admin: administra el Drive entero.
      avanzado      → administra alguna «unidad compartida»: sabe de permisos.
      basico        → el resto.

    Nota: en FARO hoy solo existen los roles user, trabajador, master y
    master_admin; «avanzado» no es un rol, se deduce de administrar unidades.
    Si algún día se crean más roles, el mapeo se ajusta AQUÍ, no en el cliente.
    """
    from almacen_bd import consultar, rol_usuario

    try:
        rol = rol_usuario(usuario_id)
    except Exception:
        rol = 'user'

    # OJO: el rol de quien administra una unidad se llama 'manager' (los otros
    # son 'editor' y 'viewer'). 'editor' no cuenta: edita archivos, pero no
    # gestiona miembros ni permisos, que es lo que distingue a un avanzado.
    unidades_admin = 0
    try:
        unidades_admin = consultar(
            "SELECT COUNT(*) AS n FROM unidad_miembros "
            " WHERE usuario_id = %s AND rol = 'manager'", (usuario_id,))[0]['n']
    except Exception:
        unidades_admin = 0

    if rol in ('master', 'master_admin'):
        perfil = 'administrador'
    elif unidades_admin:
        perfil = 'avanzado'
    else:
        perfil = 'basico'

    return {
        'perfil': perfil,
        'rol': rol,
        'es_master': rol in ('master', 'master_admin'),
        'unidades_que_administra': unidades_admin,
    }


@bp_dav.route('/dav/instalador-windows', methods=['GET'])
def instalador_windows():
    """Genera y descarga un .bat personalizado que conecta el Drive solo."""
    usuario = usuario_actual()

    # P-10 (04/08/2026): el MISMO equipo no debe consumir cupo cada vez que se
    # reinstala o reconecta. La app manda el nombre del equipo en ?equipo=NOMBRE
    # (o cabecera X-Equipo). Si ya hay un token activo con ese nombre para este
    # usuario, se REVOCA (se reemplaza) antes de emitir el nuevo, en vez de
    # sumar otro y topar el limite de 10.
    equipo = (request.args.get('equipo')
              or request.headers.get('X-Equipo') or '').strip()[:60]
    if equipo:
        # P-23 (27/08/2026): solo se reemplaza un token del MISMO equipo si esta
        # INACTIVO (no usado en la ultima hora). Antes se revocaba SIEMPRE, y como
        # la app volvia a pedir el instalador con el equipo ya conectado, se
        # revocaba el token que estaba usando en ese momento -> 401 "sin
        # explicacion" y bucle de re-login. Un reinstalar/reconectar real (token
        # viejo, sin uso reciente) sigue reemplazandose y no consume cupo extra.
        reemplazados = consultar(
            "SELECT COUNT(*) AS n FROM dav_tokens "
            " WHERE usuario_id = %s AND nombre = %s AND revocado IS NULL "
            "   AND COALESCE(ultimo_uso, creado) < now() - interval '1 hour'",
            (usuario, equipo))[0]['n']
        if reemplazados:
            ejecutar("UPDATE dav_tokens SET revocado = now() "
                     " WHERE usuario_id = %s AND nombre = %s AND revocado IS NULL "
                     "   AND COALESCE(ultimo_uso, creado) < now() - interval '1 hour'",
                     (usuario, equipo))
            log.info('Instalador: reemplazando %d token(s) INACTIVO(s) del equipo "%s" de %s',
                     reemplazados, equipo, usuario)

    cuantos = consultar(
        "SELECT COUNT(*) AS n FROM dav_tokens "
        " WHERE usuario_id = %s AND revocado IS NULL", (usuario,))[0]['n']
    if cuantos >= MAXIMO_DISPOSITIVOS:
        return error('Ya tienes %s equipos conectados, que es el máximo. '
                     'Revoca alguno desde «Ordenadores» antes de conectar otro.'
                     % MAXIMO_DISPOSITIVOS, 409)

    # Letra de unidad opcional (?letra=M). Por defecto M:. Solo A-Z.
    letra = (request.args.get('letra') or 'M').strip().upper()[:1]
    if not letra.isalpha():
        letra = 'M'

    # Token de LECTURA-ESCRITURA: es el equipo propio de la persona, trabaja
    # normal. (Un equipo ajeno se conecta de solo lectura desde el otro botón.)
    # El nombre del token es el del equipo, para poder reemplazarlo despues.
    token = secrets.token_urlsafe(32)
    nombre = equipo or 'Mi equipo (instalador Windows)'
    ejecutar("""
        INSERT INTO dav_tokens (usuario_id, nombre, token_hash, solo_lectura)
        VALUES (%s, %s, %s, FALSE)
    """, (usuario, nombre, _hash(token)))
    log.info('Instalador Windows generado para usuario %s', usuario)

    # La app nativa de Windows pide ?formato=json y recibe el token para
    # montar ella misma; el navegador (sin ese parametro) baja el .bat.
    if (request.args.get('formato') or '').lower() == 'json':
        respuesta = {
            'success': True,
            'usuario': str(usuario),
            'token': token,
            'solo_lectura': False,
            'letra': letra,
            'dav_url': 'https://drive.maquita.com.ec/dav',
            'unc': r'\\drive.maquita.com.ec@SSL\dav',
            'icono': 'https://drive.maquita.com.ec/static/maquita-drive.ico',
        }
        respuesta.update(_perfil_del_usuario(usuario))   # P-07
        # P-17: peso del Drive personal, para que la app sepa si cabe en el
        # disco sin tener que recorrer el árbol entero por WebDAV.
        uso = _uso_personal_bytes(usuario)
        if uso is not None:
            respuesta['uso_bytes'] = uso
        # P-21: también el tope asignado, para que la app pueda pintar el
        # «X de Y» sin una segunda llamada nada más instalarse.
        try:
            import nucleo_archivos as _nucleo
            respuesta['cuota_bytes'] = int(_nucleo.cuota(usuario)['total'])
        except Exception:
            pass
        return jsonify(respuesta), 201

    bat = (_PLANTILLA_BAT
           .replace('__LETRA__', letra)
           .replace('__USUARIO__', str(usuario))
           .replace('__TOKEN__', token))
    # Windows lee mejor los .bat en UTF-8 con BOM.
    datos = b'\xef\xbb\xbf' + bat.encode('utf-8')
    return Response(
        datos, mimetype='application/octet-stream',
        headers={'Content-Disposition':
                 'attachment; filename="Conectar-Drive-Maquita.bat"',
                 'Cache-Control': 'no-store'})
