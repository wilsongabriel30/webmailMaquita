# -*- coding: utf-8 -*-
"""
Firmar el PDF con un certificado digital (archivo .p12).
========================================================

Estaba dentro de `pdf_editor_api.py`, que además de esto lleva toda la API
del editor. Son dos asuntos que no se parecen en nada, y juntos hacían un
archivo de 1.600 líneas. Las rutas no cambian: se cuelgan del mismo
blueprint, que se importa de allí.

Autoría: Equipo de Tecnología Maquita — 29-jul-2026
"""

import os
import logging
from flask import Blueprint, request, jsonify, send_file, g, current_app
from functools import wraps

logger = logging.getLogger(__name__)

bp_pdf_api = Blueprint('pdf_api', __name__)

from .pdf_editor_api import (bp_pdf_api, obtener_servicio_pdf,
                             obtener_usuario_id,
                             requiere_autenticacion,
                             _DIR_CERTS_FIRMA)

logger = logging.getLogger(__name__)


def dir_certificados_usuario(uid):
    """Carpeta privada de certificados del usuario (se crea si no existe)."""
    d = os.path.join(_DIR_CERTS_FIRMA, str(uid))
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d



def ruta_p12_guardado(uid, cid):
    """Ruta del .p12 guardado del usuario, o None si no existe."""
    cid = os.path.basename(str(cid))   # evita path traversal
    p = os.path.join(dir_certificados_usuario(uid), cid + '.p12')
    return p if os.path.exists(p) else None



# --- Cifrado de contraseñas guardadas (opcional, elección del usuario) ---
# La contraseña se guarda CIFRADA en reposo con Fernet (AES-128-CBC + HMAC),
# usando una clave maestra que vive SOLO en el servidor (fuera de rutas web,
# permisos 600). Solo se descifra en el servidor al momento de firmar y para el
# propio certificado del usuario (aislado por su sesión). Nunca viaja al cliente.
def _ruta_clave_maestra():
    return os.path.join(os.path.dirname(_DIR_CERTS_FIRMA), '.firma_master.key')



def _fernet_firma():
    from cryptography.fernet import Fernet
    kp = _ruta_clave_maestra()
    if not os.path.exists(kp):
        clave = Fernet.generate_key()
        umask_ant = os.umask(0o077)
        try:
            with open(kp, 'wb') as f:
                f.write(clave)
            os.chmod(kp, 0o600)
        finally:
            os.umask(umask_ant)
    with open(kp, 'rb') as f:
        return Fernet(f.read())



def cifrar_password_firma(password):
    """Devuelve el token cifrado (str) de la contraseña."""
    return _fernet_firma().encrypt((password or '').encode('utf-8')).decode('ascii')



def descifrar_password_firma(token):
    """Descifra el token; devuelve None si falla."""
    try:
        return _fernet_firma().decrypt(token.encode('ascii')).decode('utf-8')
    except Exception:
        return None



def password_guardado(uid, cid):
    """Contraseña guardada (descifrada) del certificado del usuario, o None."""
    import json
    cid = os.path.basename(str(cid))
    meta = os.path.join(dir_certificados_usuario(uid), cid + '.json')
    if not os.path.exists(meta):
        return None
    try:
        with open(meta, encoding='utf-8') as f:
            datos = json.load(f)
    except Exception:
        return None
    tok = datos.get('pw_enc')
    return descifrar_password_firma(tok) if tok else None



def _cargar_p12_robusto(p12_data, password):
    """Carga un certificado .p12/.pfx tolerando los casos reales del campo:
    contraseñas con tildes/ñ (utf-8 y latin-1) y certificados con cifrado
    legacy (RC2/3DES viejo) que las librerías modernas rechazan — esos se
    convierten al vuelo con `openssl -legacy` y se reintenta.

    Devuelve (clave, certificado, cadena, p12_convertido_o_None).
    Lanza ValueError con un mensaje claro para el usuario.
    """
    from cryptography.hazmat.primitives.serialization import pkcs12

    contrasenas = [None] if not password else []
    if password:
        contrasenas.append(password.encode('utf-8'))
        try:
            latin = password.encode('latin-1')
            if latin != password.encode('utf-8'):
                contrasenas.append(latin)
        except UnicodeEncodeError:
            pass

    ultimo_error = None
    for pw in contrasenas:
        try:
            clave, cert, cadena = pkcs12.load_key_and_certificates(p12_data, pw)
            return clave, cert, cadena, None
        except Exception as e:
            ultimo_error = e

    # Cifrado legacy no soportado: convertir con openssl y reintentar
    import subprocess
    import tempfile as _tmp
    import os as _os
    try:
        with _tmp.TemporaryDirectory() as td:
            origen = _os.path.join(td, 'origen.p12')
            with open(origen, 'wb') as f:
                f.write(p12_data)
            entorno = dict(_os.environ, P12PW=password or '')
            pem = subprocess.run(
                ['openssl', 'pkcs12', '-in', origen, '-legacy', '-nodes',
                 '-passin', 'env:P12PW'],
                capture_output=True, timeout=30, env=entorno)
            if pem.returncode == 0 and pem.stdout:
                conv = subprocess.run(
                    ['openssl', 'pkcs12', '-export', '-passout', 'env:P12PW'],
                    input=pem.stdout, capture_output=True, timeout=30, env=entorno)
                if conv.returncode == 0 and conv.stdout:
                    clave, cert, cadena = pkcs12.load_key_and_certificates(
                        conv.stdout, password.encode('utf-8') if password else None)
                    return clave, cert, cadena, conv.stdout
    except Exception:
        logger.exception('Conversión legacy del .p12 falló')

    msg = str(ultimo_error or '').lower()
    if 'invalid password' in msg or 'mac verify' in msg or 'incorrect password' in msg:
        raise ValueError('La contraseña del certificado es incorrecta.')
    raise ValueError('No se pudo leer el certificado. Verifica que sea un archivo '
                     '.p12/.pfx válido y que la contraseña sea la correcta.')



def _generar_apariencia_firmaec(nombre, razon, ubicacion, fecha_iso,
                                box_w_pt, box_h_pt, escala=6):
    """
    Genera la imagen de apariencia de la firma visible al estilo FirmaEC:
    un QR (a la izquierda) con los datos del firmante y, a la derecha, el texto
    'Validar únicamente en FirmaEC.' / 'Firmado electrónicamente por:' / NOMBRE.
    El contenido del QR replica el formato oficial de FirmaEC.
    """
    import qrcode
    from PIL import Image, ImageDraw, ImageFont

    FUENTE_MONO = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    FUENTE_MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

    def _wrap(draw, texto, font, max_w):
        palabras, lineas, actual = texto.split(), [], ""
        for p in palabras:
            prueba = (actual + " " + p).strip()
            if draw.textlength(prueba, font=font) <= max_w:
                actual = prueba
            else:
                if actual:
                    lineas.append(actual)
                actual = p
        if actual:
            lineas.append(actual)
        return lineas

    def _fit_font(draw, texto, ruta, max_w, s_ini, s_min=6):
        s = s_ini
        while s > s_min:
            f = ImageFont.truetype(ruta, s)
            if draw.textlength(texto, font=f) <= max_w:
                return f
            s -= 1
        return ImageFont.truetype(ruta, s_min)

    W = max(1, int(box_w_pt * escala))
    H = max(1, int(box_h_pt * escala))
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    contenido = (
        "FIRMADO POR: %s\nRAZON: %s\nLOCALIZACION: %s\nFECHA: %s\n"
        "VALIDAR CON: https://www.firmadigital.gob.ec\n"
        "Firmado digitalmente con FirmaEC 5.1.0"
    ) % (nombre, razon or "", ubicacion or "", fecha_iso)
    # Se genera el QR con un tamaño de módulo ENTERO (sin reescalado posterior):
    # así los módulos quedan nítidos y de negro puro (sin el "gris/plomo" que
    # produce el suavizado al redimensionar a un tamaño no múltiplo).
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L,
                       box_size=10, border=0)
    qr.add_data(contenido)
    qr.make(fit=True)
    modulos = qr.modules_count
    box_size = max(1, H // modulos)          # px por módulo (entero)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L,
                       box_size=box_size, border=0)
    qr.add_data(contenido)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    lado = qr_img.size[0]
    if lado > H:                              # caja muy pequeña: encajar sin pasarse
        qr_img = qr_img.resize((H, H), Image.NEAREST)
        lado = H
    img.paste(qr_img, (0, 0))

    gap = int(H * 0.08)
    tx = lado + gap
    tw = max(10, W - tx)
    linea1 = "Validar únicamente en FirmaEC."
    linea2 = "Firmado electrónicamente por:"
    _f20 = ImageFont.truetype(FUENTE_MONO, 20)
    ref = linea1 if d.textlength(linea1, font=_f20) >= d.textlength(linea2, font=_f20) else linea2
    f_peq = _fit_font(d, ref, FUENTE_MONO, tw, int(H * 0.16))
    f_nom = ImageFont.truetype(FUENTE_MONO_BOLD, int(f_peq.size * 1.28))
    nom_lineas = _wrap(d, (nombre or "").upper(), f_nom, tw)
    bloques = [(linea1, f_peq), (linea2, f_peq)] + [(nl, f_nom) for nl in nom_lineas]
    interlin = int(H * 0.045)
    alturas = [f.getbbox("Ág")[3] - f.getbbox("Ág")[1] for _, f in bloques]
    alto_total = sum(alturas) + interlin * max(0, (len(bloques) - 1))
    y = max(0, (H - alto_total) // 2)
    for (txt, fnt), h in zip(bloques, alturas):
        asc = fnt.getbbox("Ág")[1]
        d.text((tx, y - asc), txt, font=fnt, fill="black")
        y += h + interlin
    return img



def firmar_pdf_una(pdf_bytes, ruta_p12, password, razon, ubicacion,
                   pagina, pos_x, pos_y, pos_ancho, pos_alto):
    """
    Aplica UNA firma FirmaEC sobre pdf_bytes y devuelve los bytes firmados.
    Reutilizable para firmar en lote (varias firmas en un mismo documento).
    Lanza ValueError si la contraseña/certificado es inválido.
    """
    import io as _io
    import time as _time
    import datetime as _dt
    from pyhanko.sign import signers, fields as sig_fields, PdfSigner
    from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
    from cryptography.x509.oid import NameOID

    with open(ruta_p12, 'rb') as f:
        p12_data = f.read()
    _clave, certificate, _cadena, conv = _cargar_p12_robusto(p12_data, password)
    if conv:
        with open(ruta_p12, 'wb') as f:
            f.write(conv)
    signer = signers.SimpleSigner.load_pkcs12(
        pfx_file=ruta_p12,
        passphrase=password.encode('utf-8') if password else None)
    try:
        cn = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
    except Exception:
        cn = 'Desconocido'

    field_name = 'Firma_%d' % int(_time.time() * 1000000)
    _tz = _dt.timezone(_dt.timedelta(hours=-5))
    fecha_iso = _dt.datetime.now(_tz).isoformat()

    w = IncrementalPdfFileWriter(_io.BytesIO(pdf_bytes), strict=False)
    estilo_sello = None
    if pagina > 0:
        spec = sig_fields.SigFieldSpec(
            sig_field_name=field_name, on_page=pagina - 1,
            box=(pos_x, pos_y, pos_x + pos_ancho, pos_y + pos_alto))
        sig_fields.append_signature_field(w, spec)
        try:
            from pyhanko.pdf_utils.images import PdfImage
            from pyhanko.stamp import TextStampStyle
            from pyhanko.pdf_utils.layout import (
                SimpleBoxLayoutRule, AxisAlignment, Margins)
            ap_img = _generar_apariencia_firmaec(
                cn, razon, ubicacion, fecha_iso, pos_ancho, pos_alto)
            estilo_sello = TextStampStyle(
                stamp_text='', background=PdfImage(ap_img), border_width=0,
                background_layout=SimpleBoxLayoutRule(
                    x_align=AxisAlignment.ALIGN_MIN,
                    y_align=AxisAlignment.ALIGN_MIN,
                    margins=Margins(0, 0, 0, 0)))
        except Exception:
            logger.exception('Apariencia FirmaEC falló en firma en lote')
            estilo_sello = None

    meta = signers.PdfSignatureMetadata(
        field_name=field_name, reason=razon, location=ubicacion)
    if estilo_sello is not None:
        pdf_signer = PdfSigner(meta, signer=signer, stamp_style=estilo_sello)
    else:
        pdf_signer = PdfSigner(meta, signer=signer)
    salida = _io.BytesIO()
    pdf_signer.sign_pdf(w, output=salida)
    return salida.getvalue()



@bp_pdf_api.route('/firma-digital/firmar', methods=['POST'])
@requiere_autenticacion
def firmar_pdf_con_p12():
    """
    Firma digitalmente un PDF usando un certificado .p12.

    POST /api/pdf/firma-digital/firmar
    Body: multipart/form-data
      - archivo: PDF a firmar
      - certificado: archivo .p12
      - password: contraseña del .p12
      - razon: razón de la firma (opcional)
      - ubicacion: ubicación (opcional)
      - pagina: número de página para firma visible (opcional, 0=invisible)
      - x, y, ancho, alto: posición de firma visible (opcional)
    """
    archivo_pdf = request.files.get('archivo')
    archivo_p12 = request.files.get('certificado')
    # Alternativa: certificado ya guardado del usuario (firmar desde cualquier equipo)
    certificado_id = request.form.get('certificado_id')
    password = request.form.get('password', '')
    razon = request.form.get('razon', 'Documento firmado digitalmente')
    ubicacion = request.form.get('ubicacion', 'Ecuador')
    pagina = int(request.form.get('pagina', '0'))
    pos_x = float(request.form.get('x', '50'))
    pos_y = float(request.form.get('y', '50'))
    pos_ancho = float(request.form.get('ancho', '200'))
    pos_alto = float(request.form.get('alto', '70'))

    if not archivo_pdf:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo PDF'}), 400

    # Resolver el .p12: archivo subido o certificado guardado del usuario
    ruta_p12_origen = None
    if not archivo_p12:
        if certificado_id:
            _uid = obtener_usuario_id()
            ruta_p12_origen = ruta_p12_guardado(_uid, certificado_id)
            if not ruta_p12_origen:
                return jsonify({'exito': False, 'mensaje': 'El certificado guardado no existe'}), 404
            # Si no se envió contraseña, usar la guardada (cifrada) si existe
            if not password:
                password = password_guardado(_uid, certificado_id) or ''
        else:
            return jsonify({'exito': False, 'mensaje': 'Se requiere un certificado .p12'}), 400

    import tempfile
    rutas_temp = []

    try:
        # Guardar archivos temporales
        fd_pdf, ruta_pdf = tempfile.mkstemp(suffix='.pdf')
        os.close(fd_pdf)
        archivo_pdf.save(ruta_pdf)
        rutas_temp.append(ruta_pdf)

        fd_p12, ruta_p12 = tempfile.mkstemp(suffix='.p12')
        os.close(fd_p12)
        if archivo_p12:
            archivo_p12.save(ruta_p12)
        else:
            # Copiar el .p12 guardado del usuario al temporal
            with open(ruta_p12_origen, 'rb') as _src, open(ruta_p12, 'wb') as _dst:
                _dst.write(_src.read())
        rutas_temp.append(ruta_p12)

        fd_out, ruta_salida = tempfile.mkstemp(suffix='_firmado.pdf')
        os.close(fd_out)
        rutas_temp.append(ruta_salida)

        # Firmar con pyHanko
        from pyhanko.sign import signers, fields as sig_fields
        # NOTA: load_cert_builder no existe en pyhanko>=0.35 y no se usaba; se firma con SimpleSigner.load_pkcs12
        from pyhanko import stamp
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.hazmat.backends import default_backend

        # Cargar el certificado .p12
        with open(ruta_p12, 'rb') as f:
            p12_data = f.read()

        try:
            private_key, certificate, chain, p12_convertido = _cargar_p12_robusto(p12_data, password)
        except ValueError as e_p12:
            return jsonify({'exito': False, 'mensaje': str(e_p12)}), 400
        if p12_convertido:
            # el certificado venía con cifrado legacy: SimpleSigner debe leer la
            # versión convertida (el archivo original le fallaría igual)
            with open(ruta_p12, 'wb') as f:
                f.write(p12_convertido)

        if not private_key or not certificate:
            return jsonify({
                'exito': False,
                'mensaje': 'El archivo .p12 no contiene una clave privada o certificado válido'
            }), 400

        # Extraer info del certificado para la respuesta
        from cryptography.x509.oid import NameOID
        cn = ''
        org = ''
        try:
            cn = certificate.subject.get_attributes_for_oid(NameOID.COMMON_NAME)[0].value
        except (IndexError, Exception):
            cn = 'Desconocido'
        try:
            org = certificate.subject.get_attributes_for_oid(NameOID.ORGANIZATION_NAME)[0].value
        except (IndexError, Exception):
            org = ''

        # Configurar el signer
        signer = signers.SimpleSigner.load_pkcs12(
            pfx_file=ruta_p12,
            passphrase=password.encode('utf-8') if password else None
        )

        with open(ruta_pdf, 'rb') as inf:
            # strict=False permite firmar PDFs con secciones de referencia
            # cruzada hibridas (hybrid xrefs), comunes en PDFs generados por
            # Office/impresoras antiguas. Sin esto pyHanko rechaza el documento.
            w = IncrementalPdfFileWriter(inf, strict=False)

            # Nombre de campo único: permite estampar VARIAS firmas en el mismo
            # documento (cada firma es un campo distinto y una actualización
            # incremental independiente).
            import time as _time
            field_name = 'Firma_%d' % int(_time.time() * 1000)

            # Fecha en formato FirmaEC (Ecuador, UTC-5)
            import datetime as _dt
            _tz = _dt.timezone(_dt.timedelta(hours=-5))
            fecha_iso = _dt.datetime.now(_tz).isoformat()

            estilo_sello = None
            if pagina > 0:
                # Firma visible en la página indicada
                sig_field_spec = sig_fields.SigFieldSpec(
                    sig_field_name=field_name,
                    on_page=pagina - 1,
                    box=(pos_x, pos_y, pos_x + pos_ancho, pos_y + pos_alto)
                )
                sig_fields.append_signature_field(w, sig_field_spec)

                # Apariencia visible estilo FirmaEC (QR + datos del firmante)
                try:
                    from pyhanko.pdf_utils.images import PdfImage
                    from pyhanko.stamp import TextStampStyle
                    from pyhanko.pdf_utils.layout import (
                        SimpleBoxLayoutRule, AxisAlignment, Margins)
                    ap_img = _generar_apariencia_firmaec(
                        cn, razon, ubicacion, fecha_iso, pos_ancho, pos_alto)
                    estilo_sello = TextStampStyle(
                        stamp_text='', background=PdfImage(ap_img), border_width=0,
                        background_layout=SimpleBoxLayoutRule(
                            x_align=AxisAlignment.ALIGN_MIN,
                            y_align=AxisAlignment.ALIGN_MIN,
                            margins=Margins(0, 0, 0, 0)))
                except Exception:
                    logger.exception('No se pudo generar apariencia FirmaEC; '
                                     'se firma sin sello visible')
                    estilo_sello = None

            # Crear metadata de firma
            meta = signers.PdfSignatureMetadata(
                # pyhanko>=0.35 exige field_name siempre; si no hay firma visible
                # crea un campo invisible con ese nombre
                field_name=field_name,
                reason=razon,
                location=ubicacion,
            )

            from pyhanko.sign import PdfSigner

            if estilo_sello is not None:
                pdf_signer = PdfSigner(meta, signer=signer, stamp_style=estilo_sello)
            else:
                pdf_signer = PdfSigner(meta, signer=signer)

            with open(ruta_salida, 'wb') as outf:
                pdf_signer.sign_pdf(w, output=outf)

        # Enviar resultado
        from io import BytesIO
        with open(ruta_salida, 'rb') as f:
            resultado = f.read()

        nombre_salida = archivo_pdf.filename.rsplit('.', 1)[0] + '_firmado.pdf' if archivo_pdf.filename else 'firmado.pdf'

        return send_file(
            BytesIO(resultado),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=nombre_salida
        )

    except Exception as e:
        logger.error(f"Error firmando PDF: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'exito': False, 'mensaje': f'Error al firmar: {str(e)}'}), 400

    finally:
        for ruta in rutas_temp:
            if os.path.exists(ruta):
                try:
                    os.remove(ruta)
                except Exception:
                    pass



@bp_pdf_api.route('/firma-digital/verificar-p12', methods=['POST'])
@requiere_autenticacion
def verificar_certificado_p12():
    """
    Verifica un certificado .p12 y retorna su información.

    POST /api/pdf/firma-digital/verificar-p12
    Body: multipart/form-data
      - certificado: archivo .p12
      - password: contraseña
    """
    archivo_p12 = request.files.get('certificado')
    password = request.form.get('password', '')

    if not archivo_p12:
        return jsonify({'exito': False, 'mensaje': 'Se requiere un archivo .p12'}), 400

    try:
        p12_data = archivo_p12.read()
        from cryptography.hazmat.primitives.serialization import pkcs12
        from cryptography.hazmat.backends import default_backend
        from cryptography.x509.oid import NameOID

        try:
            private_key, certificate, chain, _conv = _cargar_p12_robusto(p12_data, password)
        except ValueError as e_p12:
            return jsonify({'exito': False, 'mensaje': str(e_p12)}), 400

        if not certificate:
            return jsonify({'exito': False, 'mensaje': 'Certificado no válido'}), 400

        def get_attr(oid):
            try:
                return certificate.subject.get_attributes_for_oid(oid)[0].value
            except (IndexError, Exception):
                return ''

        info = {
            'nombre_comun': get_attr(NameOID.COMMON_NAME),
            'organizacion': get_attr(NameOID.ORGANIZATION_NAME),
            'email': get_attr(NameOID.EMAIL_ADDRESS),
            'pais': get_attr(NameOID.COUNTRY_NAME),
            'serial': str(certificate.serial_number),
            'valido_desde': certificate.not_valid_before_utc.isoformat(),
            'valido_hasta': certificate.not_valid_after_utc.isoformat(),
            'emisor': str(certificate.issuer),
            'cadena_certs': len(chain) if chain else 0
        }

        # Verificar si esta vigente
        from datetime import datetime, timezone
        ahora = datetime.now(timezone.utc)
        info['vigente'] = certificate.not_valid_before_utc <= ahora <= certificate.not_valid_after_utc

        return jsonify({'exito': True, 'datos': info})

    except Exception as e:
        return jsonify({
            'exito': False,
            'mensaje': f'Error al leer certificado: {str(e)}. Verifica la contraseña.'
        }), 400
