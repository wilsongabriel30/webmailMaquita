/* ============================================================
   Raíces Maquita — Editor PDF · firma p12
   Esta es UNA PARTE del editor. Antes todo esto vivía dentro de editor_nucleo.js,
   que había crecido hasta más de 6.000 líneas: imposible de revisar y de trabajar
   entre varias personas a la vez. Cada parte se registra aquí abajo y el núcleo la
   arranca al final, pasándole `E`: el objeto con lo ÚNICO que se comparte entre
   partes (el estado del documento, las ayudas comunes y las funciones de otras).
   ============================================================ */
window.PDFEditorPartes = window.PDFEditorPartes || {};
window.PDFEditorPartes.firma_p12 = function (E) {
    'use strict';

    // Lo que esta parte toma del núcleo (cuando arranca ya está todo listo):
    const { $, _abrirModal, _cerrarModal, _currentPageWrapper, _descargarBlob, _getPageFromEvent, _getPdfBlob, _necesitaPDF, loadPDF, mostrarToast, state } = E;
    // ==================== FIRMA DIGITAL CON CERTIFICADO .P12 ====================
    (function() {
        // ===== Firma electrónica: DIBUJAR primero, elegir certificado después =====
        // Los certificados .p12 quedan GUARDADOS entre sesiones (IndexedDB, ver
        // firma_certificados.js): se suben una vez y luego solo se elige el
        // certificado y se escribe la contraseña. La contraseña NO se guarda; se
        // conserva en memoria (_pwCache) solo durante la sesión actual.
        // certsGuardados: [{id, name, nombre, org, blob}]
        let certsGuardados = [];
        const _pwCache = {};       // id -> contraseña (solo en memoria de la sesión)
        let _pendingBox = null;    // recuadro dibujado esperando elegir certificado

        const dropP12 = $('dropZonaP12');
        const inputP12 = $('inputP12');
        let _archivoCargando = null;   // .p12 en el diálogo de carga (aún sin verificar)

        function _certId(file) { return file.name + '|' + file.size; }

        async function _cargarCertsGuardados() {
            try { certsGuardados = await window.FaroFirmaCerts.listar(); }
            catch (e) { certsGuardados = []; }
        }
        // Precargar la lista al iniciar
        _cargarCertsGuardados();

        // -------- Aviso de privacidad / términos y condiciones --------
        let _consentimientoOK = false;

        // Garantiza que el usuario haya leído y aceptado el aviso antes de guardar
        // su certificado/contraseña en el servidor. Devuelve true si aceptó.
        async function _asegurarConsentimiento() {
            if (_consentimientoOK) return true;
            let est = {};
            try { est = await window.FaroFirmaCerts.estadoConsentimiento(); } catch (e) { est = {}; }
            if (est && est.aceptado) { _consentimientoOK = true; return true; }
            const version = (est && est.version_actual) || '';
            return await _mostrarAvisoPrivacidad(version);
        }

        function _mostrarAvisoPrivacidad(version) {
            return new Promise(resolve => {
                const ov = document.createElement('div');
                ov.id = 'avisoPrivacidadFirma';
                ov.style.cssText = 'position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,.5);display:flex;align-items:center;justify-content:center;padding:16px;';
                ov.innerHTML =
                    '<div style="background:#fff;max-width:560px;width:100%;max-height:85vh;overflow:auto;border-radius:12px;box-shadow:0 8px 30px rgba(0,0,0,.3);">' +
                    '<div style="padding:16px 20px;border-bottom:1px solid #eee;font-weight:700;font-size:16px;color:#0b57c9;"><i class="bi bi-shield-lock"></i> Aviso de privacidad y términos de uso — Firma electrónica</div>' +
                    '<div style="padding:16px 20px;font-size:13px;color:#333;line-height:1.5;">' +
                    '<p>Para poder firmar desde cualquier dispositivo sin volver a subir tu certificado, Raíces puede <b>almacenar en el servidor</b> tu archivo de firma (<b>.p12/.pfx</b>) y, <b>solo si tú lo eliges</b>, su contraseña.</p>' +
                    '<ul style="margin:8px 0 8px 18px;padding:0;">' +
                    '<li>Tu certificado y contraseña se guardan <b>cifrados</b> y son <b>de uso exclusivo tuyo</b>: están aislados por tu cuenta y <b>ningún otro usuario</b> puede verlos ni usar tu firma.</li>' +
                    '<li>La contraseña (si decides guardarla) <b>nunca se muestra</b> ni sale del servidor; solo se usa para aplicar <b>tus</b> firmas.</li>' +
                    '<li>Eres responsable del uso de tu firma electrónica y de los documentos que firmes con ella.</li>' +
                    '<li>Puedes <b>eliminar</b> tu certificado o <b>quitar</b> la contraseña guardada en cualquier momento.</li>' +
                    '<li>Guardar la contraseña es <b>opcional</b>: si no lo activas, se te pedirá cada vez que firmes.</li>' +
                    '</ul>' +
                    '<label style="display:flex;align-items:center;gap:8px;margin-top:12px;font-weight:600;"><input type="checkbox" id="chkAceptaPriv"> He leído y acepto el aviso de privacidad y los términos de uso.</label>' +
                    '</div>' +
                    '<div style="padding:14px 20px;border-top:1px solid #eee;display:flex;gap:8px;justify-content:flex-end;">' +
                    '<button id="btnRechazaPriv" class="btn-modal secondary">Cancelar</button>' +
                    '<button id="btnAceptaPriv" class="btn-modal primary" disabled><i class="bi bi-check2"></i> Aceptar y continuar</button>' +
                    '</div></div>';
                document.body.appendChild(ov);
                const chk = ov.querySelector('#chkAceptaPriv');
                const btnOk = ov.querySelector('#btnAceptaPriv');
                chk.addEventListener('change', () => { btnOk.disabled = !chk.checked; });
                const cerrar = (val) => { ov.remove(); resolve(val); };
                ov.querySelector('#btnRechazaPriv').addEventListener('click', () => cerrar(false));
                btnOk.addEventListener('click', async () => {
                    btnOk.disabled = true; btnOk.innerHTML = '<i class="bi bi-hourglass-split"></i> Guardando...';
                    const res = await window.FaroFirmaCerts.aceptarConsentimiento(version);
                    if (res && res.exito) { _consentimientoOK = true; cerrar(true); }
                    else { btnOk.disabled = false; btnOk.innerHTML = 'Aceptar y continuar'; mostrarToast('No se pudo registrar la aceptación', 'error'); }
                });
            });
        }

        // -------- Entrada principal: el botón inicia el modo "dibujar recuadro" --------
        $('toolFirmaDigitalP12')?.addEventListener('click', () => {
            if (_necesitaPDF()) return;
            _iniciarDibujoFirma();
        });

        // -------- Diálogo para CARGAR un certificado (modal) --------
        $('btnCerrarFirmaDigital')?.addEventListener('click', () => _cerrarDialogoCargarCert());
        $('btnCancelarFirmaDigital')?.addEventListener('click', () => _cerrarDialogoCargarCert());

        if (dropP12) {
            dropP12.addEventListener('click', () => inputP12.click());
            dropP12.addEventListener('dragover', e => { e.preventDefault(); dropP12.style.borderColor = '#28a745'; dropP12.style.background = '#f0fdf4'; });
            dropP12.addEventListener('dragleave', () => { dropP12.style.borderColor = ''; dropP12.style.background = ''; });
            dropP12.addEventListener('drop', e => {
                e.preventDefault();
                dropP12.style.borderColor = ''; dropP12.style.background = '';
                if (e.dataTransfer.files.length > 0) cargarP12(e.dataTransfer.files[0]);
            });
        }
        inputP12?.addEventListener('change', e => {
            if (e.target.files.length > 0) cargarP12(e.target.files[0]);
        });

        function cargarP12(file) {
            const ext = file.name.toLowerCase();
            if (!ext.endsWith('.p12') && !ext.endsWith('.pfx')) {
                mostrarErrorFirma('Solo se aceptan archivos .p12 o .pfx');
                return;
            }
            _archivoCargando = file;
            $('p12NombreArchivo').textContent = file.name;
            $('p12InfoCert').textContent = (file.size / 1024).toFixed(1) + ' KB';
            $('infoP12Cargado').style.display = 'block';
            $('dropZonaP12').style.display = 'none';
            $('btnVerificarP12').disabled = false;
            $('errorFirmaDigital').style.display = 'none';
        }

        $('btnQuitarP12')?.addEventListener('click', () => {
            _archivoCargando = null;
            $('infoP12Cargado').style.display = 'none';
            $('dropZonaP12').style.display = 'block';
            $('btnVerificarP12').disabled = true;
        });

        // Abre el diálogo modal para agregar un certificado nuevo a la sesión
        function _abrirDialogoCargarCert() {
            _archivoCargando = null;
            $('inputP12').value = '';
            $('inputPasswordP12').value = '';
            $('infoP12Cargado').style.display = 'none';
            $('dropZonaP12').style.display = 'block';
            $('pasoInfoCert').style.display = 'none';
            $('pasoCargarP12').style.display = 'block';
            $('btnVerificarP12').disabled = true;
            $('btnEjecutarFirmaDigital').style.display = 'none';
            $('errorFirmaDigital').style.display = 'none';
            $('exitoFirmaDigital').style.display = 'none';
            // Control "Recordar contraseña" (OPCIONAL, decisión del usuario;
            // apagado por defecto). Si lo activa, no se le pide al firmar.
            if (!$('chkRecordarPwCarga')) {
                const cont = document.createElement('div');
                cont.style.cssText = 'margin:6px 0 12px;';
                cont.innerHTML =
                    '<label style="display:flex;align-items:center;gap:8px;font-size:13px;color:#333;font-weight:600;cursor:pointer;">' +
                    '<input type="checkbox" id="chkRecordarPwCarga"> <i class="bi bi-unlock" style="color:#16a34a;"></i> Recordar contraseña (no volver a pedirla)</label>' +
                    '<div style="font-size:11px;color:#888;margin-top:3px;">Opcional. Se guarda cifrada en el servidor. Si no lo activas, se te pedirá cada vez que firmes (el certificado igual queda guardado).</div>';
                const pw = $('inputPasswordP12');
                pw.parentNode.insertBefore(cont, pw.nextSibling);
            }
            cargarFirmasGuardadas();
            _abrirModal('modalFirmaDigital');
        }

        function _cerrarDialogoCargarCert() {
            _cerrarModal('modalFirmaDigital');
            // Si había un recuadro pendiente, volver a mostrar el selector sobre él
            if (_pendingBox) _reabrirPicker();
        }

        // -------- Verificar y AGREGAR certificado a la sesión --------
        $('btnVerificarP12')?.addEventListener('click', async () => {
            if (!_archivoCargando) return;
            const password = $('inputPasswordP12').value;
            const btn = $('btnVerificarP12');
            btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Verificando...';
            btn.disabled = true;
            $('errorFirmaDigital').style.display = 'none';
            try {
                // Aviso de privacidad / términos: obligatorio antes de guardar
                const acepta = await _asegurarConsentimiento();
                if (!acepta) {
                    mostrarErrorFirma('Debes aceptar el aviso de privacidad para guardar el certificado.');
                    return;
                }
                // Guarda el certificado EN EL SERVIDOR (verifica contraseña y lo
                // deja disponible desde cualquier dispositivo). "recordar" es la
                // decisión del usuario (apagado por defecto).
                const recordar = $('chkRecordarPwCarga') ? $('chkRecordarPwCarga').checked : false;
                const res = await window.FaroFirmaCerts.guardar(_archivoCargando, password, recordar);
                if (!res || !res.exito) throw new Error((res && res.mensaje) || 'No se pudo guardar el certificado');
                const meta = res.datos;
                _pwCache[meta.id] = password;
                await _cargarCertsGuardados();
                mostrarToast('Certificado guardado: ' + (meta.nombre || _archivoCargando.name), 'ok');
                _cerrarModal('modalFirmaDigital');
                if (_modoMultiple) {
                    // Se agregó un certificado desde el modo múltiple: volver a él
                    _mostrarPanelMultiple();
                    _firmaDibujo.activo = true;
                    document.body.style.cursor = 'crosshair';
                    _bannerDibujo(true);
                    _panelSeleccionarCert();
                } else if (_pendingBox) {
                    _reabrirPicker();
                } else {
                    mostrarToast('Ahora dibuja el recuadro donde va la firma', 'info');
                    _iniciarDibujoFirma();
                }
            } catch(e) {
                mostrarErrorFirma(e.message);
            } finally {
                btn.innerHTML = '<i class="bi bi-shield-check"></i> Guardar certificado';
                btn.disabled = !_archivoCargando;
            }
        });

        // -------- Firma: estampa la firma FirmaEC en `pos` con el certificado dado --------
        async function firmarDocumento(pos, cert, descargar) {
            if (!cert || !state.pdfBytes) return false;
            try {
                const formData = new FormData();
                formData.append('archivo', _getPdfBlob(), 'documento.pdf');
                if (cert.file) {
                    formData.append('certificado', cert.file, cert.name || 'certificado.p12');
                } else {
                    formData.append('certificado_id', cert.id);
                }
                formData.append('password', cert.password);
                formData.append('razon', 'Documento firmado digitalmente');
                formData.append('ubicacion', 'Ecuador');
                if (pos) {
                    formData.append('pagina', pos.pagina);
                    formData.append('x', pos.x);
                    formData.append('y', pos.y);
                    formData.append('ancho', pos.ancho);
                    formData.append('alto', pos.alto);
                } else {
                    formData.append('pagina', '0');
                }
                const resp = await fetch('/api/pdf/firma-digital/firmar', {
                    method: 'POST', body: formData, credentials: 'same-origin'
                });
                if (!resp.ok) {
                    const datos = await resp.json().catch(() => ({}));
                    throw new Error(datos.mensaje || 'Error del servidor (' + resp.status + ')');
                }
                const blob = await resp.blob();
                const buf = await blob.arrayBuffer();
                await loadPDF(buf.slice(0));   // recarga el PDF firmado (firma visible)
                state.hayCambios = true;
                _mostrarBotonDescargarFirmado();
                if (descargar) _descargarBlob(new Blob([buf], { type: 'application/pdf' }), _nombreFirmado());
                mostrarToast('Firma estampada correctamente', 'ok');
                return true;
            } catch(e) {
                mostrarToast('Error al firmar: ' + e.message, 'error');
                return false;
            }
        }

        function mostrarErrorFirma(msg) {
            $('errorFirmaDigital').textContent = msg;
            $('errorFirmaDigital').style.display = 'block';
        }

        // Nombre de la descarga: nombre ORIGINAL del documento + "_firmado" (en español)
        function _nombreFirmado() {
            let base = (state.nombreOriginal || 'documento').replace(/\.pdf$/i, '');
            if (!/_firmado$/i.test(base)) base += '_firmado';
            return base + '.pdf';
        }

        // Botón flotante para descargar el documento firmado (aparece tras firmar)
        function _mostrarBotonDescargarFirmado() {
            if ($('btnDescargarFirmado')) return;
            const b = document.createElement('button');
            b.id = 'btnDescargarFirmado';
            b.style.cssText = 'position:fixed;bottom:20px;right:20px;z-index:9998;background:#28a745;color:#fff;border:none;border-radius:24px;padding:10px 18px;font-size:14px;cursor:pointer;box-shadow:0 3px 12px rgba(0,0,0,.3);display:flex;align-items:center;gap:8px;';
            b.innerHTML = '<i class="bi bi-download"></i> Descargar documento firmado';
            b.addEventListener('click', () => _descargarBlob(_getPdfBlob(), _nombreFirmado()));
            document.body.appendChild(b);
        }

        // ============ DIBUJO DEL RECUADRO DE LA FIRMA ============
        const _firmaDibujo = { activo:false, dibujando:false, pagina:null, x0:0, y0:0, previa:null, wrapper:null, ultimo:null };

        function _iniciarDibujoFirma() {
            if (!state.pdfDoc) { mostrarToast('Primero abre un PDF', 'error'); return; }
            _quitarPreviaFirma();
            _pendingBox = null;
            _firmaDibujo.activo = true;
            document.body.style.cursor = 'crosshair';
            _bannerDibujo(true);
        }

        function _bannerDibujo(mostrar) {
            let b = $('bannerDibujoFirma');
            if (!b && mostrar) {
                b = document.createElement('div');
                b.id = 'bannerDibujoFirma';
                b.style.cssText = 'position:fixed;top:12px;left:50%;transform:translateX(-50%);z-index:9999;background:#1473e6;color:#fff;padding:8px 16px;border-radius:22px;font-size:13px;box-shadow:0 2px 8px rgba(0,0,0,.3);display:flex;gap:10px;align-items:center;';
                b.innerHTML = '<span><i class="bi bi-vector-pen"></i> Dibuja un recuadro donde quieres la firma</span>' +
                    '<button id="btnModoMultiple" style="background:#0b57c9;border:none;color:#fff;border-radius:10px;padding:2px 10px;cursor:pointer;"><i class="bi bi-layers"></i> Firma múltiple</button>' +
                    '<button id="btnCancelarDibujoFirma" style="background:rgba(255,255,255,.25);border:none;color:#fff;border-radius:10px;padding:2px 10px;cursor:pointer;">Cancelar</button>';
                document.body.appendChild(b);
                $('btnCancelarDibujoFirma').addEventListener('click', _cancelarDibujoFirma);
                $('btnModoMultiple').addEventListener('click', _entrarModoMultiple);
            }
            if (b) b.style.display = mostrar ? 'flex' : 'none';
        }

        function _cancelarDibujoFirma() {
            _firmaDibujo.activo = false;
            _firmaDibujo.dibujando = false;
            _pendingBox = null;
            document.body.style.cursor = '';
            _bannerDibujo(false);
            _quitarPreviaFirma();
        }

        function _quitarPreviaFirma() {
            document.getElementById('firmaPreviaBox')?.remove();
            document.getElementById('firmaPickerBox')?.remove();
        }

        $('viewerScroll')?.addEventListener('mousedown', e => {
            if (!_firmaDibujo.activo) return;
            e.preventDefault();
            _getPageFromEvent(e);
            const wrapper = _currentPageWrapper();
            if (!wrapper) return;
            _quitarPreviaFirma();
            const rect = wrapper.getBoundingClientRect();
            _firmaDibujo.pagina = state.currentPage;
            _firmaDibujo.wrapper = wrapper;
            _firmaDibujo.x0 = (e.clientX - rect.left) / state.zoom;
            _firmaDibujo.y0 = (e.clientY - rect.top) / state.zoom;
            const box = document.createElement('div');
            box.id = 'firmaPreviaBox';
            box.style.cssText = 'position:absolute;border:2px dashed #1473e6;background:rgba(20,115,230,.12);z-index:50;pointer-events:none;';
            wrapper.appendChild(box);
            _firmaDibujo.previa = box;
            _firmaDibujo.dibujando = true;
        });

        $('viewerScroll')?.addEventListener('mousemove', e => {
            if (!_firmaDibujo.activo || !_firmaDibujo.dibujando || !_firmaDibujo.previa) return;
            const rect = _firmaDibujo.wrapper.getBoundingClientRect();
            const x1 = (e.clientX - rect.left) / state.zoom;
            const y1 = (e.clientY - rect.top) / state.zoom;
            const x = Math.min(_firmaDibujo.x0, x1), y = Math.min(_firmaDibujo.y0, y1);
            const w = Math.abs(x1 - _firmaDibujo.x0), h = Math.abs(y1 - _firmaDibujo.y0);
            const b = _firmaDibujo.previa;
            b.style.left = (x*state.zoom)+'px'; b.style.top = (y*state.zoom)+'px';
            b.style.width = (w*state.zoom)+'px'; b.style.height = (h*state.zoom)+'px';
            _firmaDibujo.ultimo = { x, y, w, h };
        });

        document.addEventListener('mouseup', () => {
            if (!_firmaDibujo.activo || !_firmaDibujo.dibujando) return;
            _firmaDibujo.dibujando = false;
            document.body.style.cursor = '';
            _bannerDibujo(false);
            const u = _firmaDibujo.ultimo;
            _firmaDibujo.ultimo = null;
            if (!u || u.w < 20 || u.h < 12) {
                _cancelarDibujoFirma();
                mostrarToast('El recuadro es muy pequeño. Intenta de nuevo.', 'error');
                return;
            }
            // Calcular posición en puntos PDF (origen inferior-izquierdo)
            const pageH = _firmaDibujo.wrapper.offsetHeight / state.zoom;
            const pos = {
                pagina: _firmaDibujo.pagina,
                x: Math.round(u.x),
                y: Math.round(pageH - (u.y + u.h)),
                ancho: Math.round(u.w),
                alto: Math.round(u.h)
            };
            if (_modoMultiple) {
                // Modo múltiple: se acumula la colocación y se sigue dibujando
                _agregarColocacion(_firmaDibujo.wrapper, u, pos);
                _firmaDibujo.previa = null;   // el recuadro pasa a ser marcador fijo
                return;
            }
            _firmaDibujo.activo = false;
            _pendingBox = { wrapper: _firmaDibujo.wrapper, u: u, pos: pos };
            _mostrarPicker();
        });

        // -------- Selector de certificado sobre el recuadro dibujado --------
        function _reabrirPicker() {
            // El recuadro azul de vista previa sigue en el wrapper; volver a mostrar el selector
            _mostrarPicker();
        }

        async function _mostrarPicker() {
            document.getElementById('firmaPickerBox')?.remove();
            if (!_pendingBox) return;
            await _cargarCertsGuardados();   // refrescar lista del servidor
            const { wrapper, u } = _pendingBox;
            const box = document.createElement('div');
            box.id = 'firmaPickerBox';
            const left = (u.x + u.w) * state.zoom + 8;
            const top = u.y * state.zoom;
            box.style.cssText = 'position:absolute;z-index:60;left:'+left+'px;top:'+top+'px;min-width:230px;max-width:300px;background:#fff;border:1px solid #ccc;border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,.22);padding:10px;font-size:13px;';
            let html = '<div style="font-weight:600;margin-bottom:8px;color:#166534;"><i class="bi bi-shield-lock" style="color:#28a745;"></i> Aplicar firma aquí</div>';
            if (certsGuardados.length === 0) {
                html += '<div style="color:#888;font-size:12px;margin-bottom:8px;">Aún no tienes certificados guardados.</div>';
            } else {
                html += '<div style="font-size:11px;color:#888;margin-bottom:4px;">Elige tu certificado:</div>';
                certsGuardados.forEach((c, i) => {
                    html += '<div class="firma-cert-row" style="display:flex;align-items:center;gap:4px;margin-bottom:5px;">'+
                            '<button class="firma-cert-item" data-idx="'+i+'" style="flex:1;text-align:left;border:1px solid #e2e8f0;background:#f8fafc;border-radius:6px;padding:7px 9px;cursor:pointer;">'+
                            '<div style="font-weight:600;color:#1473e6;"><i class="bi bi-patch-check-fill" style="color:#28a745;"></i> '+_esc(c.nombre)+'</div>'+
                            (c.org ? '<div style="font-size:11px;color:#666;">'+_esc(c.org)+'</div>' : '')+
                            (c.tiene_password ? '<div style="font-size:10px;color:#16a34a;"><i class="bi bi-unlock"></i> Sin pedir contraseña</div>' : '')+
                            '</button>'+
                            (c.tiene_password ? '<button class="firma-cert-forget" data-idx="'+i+'" title="Pedir la contraseña siempre (olvidar la guardada)" style="border:none;background:none;color:#d97706;cursor:pointer;font-size:14px;padding:4px;"><i class="bi bi-lock"></i></button>' : '')+
                            '<button class="firma-cert-del" data-idx="'+i+'" title="Quitar este certificado" style="border:none;background:none;color:#dc2626;cursor:pointer;font-size:14px;padding:4px;"><i class="bi bi-trash"></i></button>'+
                            '</div>';
                });
            }
            html += '<div id="firmaPwZona"></div>';
            html += '<button id="btnCargarCertPicker" style="width:100%;border:1px dashed #94a3b8;background:#fff;border-radius:6px;padding:7px;margin-top:2px;cursor:pointer;color:#334155;"><i class="bi bi-plus-lg"></i> Agregar certificado .p12</button>';
            html += '<button id="btnCancelarPicker" style="width:100%;border:none;background:none;color:#dc2626;padding:6px;margin-top:4px;cursor:pointer;font-size:12px;">Cancelar</button>';
            box.innerHTML = html;
            wrapper.appendChild(box);

            box.querySelectorAll('.firma-cert-item').forEach(btn => {
                btn.addEventListener('click', () => _elegirCert(certsGuardados[parseInt(btn.dataset.idx)], box));
            });
            box.querySelectorAll('.firma-cert-forget').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const c = certsGuardados[parseInt(btn.dataset.idx)];
                    await window.FaroFirmaCerts.olvidarPassword(c.id);
                    delete _pwCache[c.id];
                    mostrarToast('Ahora se pedirá la contraseña de ' + (c.nombre || c.name), 'ok');
                    _mostrarPicker();
                });
            });
            box.querySelectorAll('.firma-cert-del').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    e.stopPropagation();
                    const c = certsGuardados[parseInt(btn.dataset.idx)];
                    if (!confirm('¿Quitar el certificado "' + (c.nombre || c.name) + '"?')) return;
                    await window.FaroFirmaCerts.eliminar(c.id);
                    delete _pwCache[c.id];
                    _mostrarPicker();
                });
            });
            $('btnCargarCertPicker').addEventListener('click', () => {
                document.getElementById('firmaPickerBox')?.remove();
                _abrirDialogoCargarCert();
            });
            $('btnCancelarPicker').addEventListener('click', _cancelarDibujoFirma);
        }

        // Elegir un certificado: si ya tenemos la contraseña en memoria firma
        // directo; si no, pide solo la contraseña.
        function _elegirCert(certMeta, box) {
            const pwGuardada = _pwCache[certMeta.id];
            if (pwGuardada) {
                _aplicarFirmaCon(certMeta, pwGuardada, box);
                return;
            }
            if (certMeta.tiene_password) {
                // Contraseña guardada en el servidor: no se pide, firma directo
                _aplicarFirmaCon(certMeta, '', box);
                return;
            }
            const zona = box.querySelector('#firmaPwZona');
            zona.innerHTML =
                '<div style="margin:6px 0;padding:8px;background:#f0f7ff;border:1px solid #cfe0ff;border-radius:6px;">'+
                '<div style="font-size:11px;color:#555;margin-bottom:4px;"><i class="bi bi-key"></i> Contraseña de <b>'+_esc(certMeta.nombre)+'</b></div>'+
                '<input type="password" id="inputPwFirma" placeholder="Contraseña del certificado" style="width:100%;box-sizing:border-box;padding:6px;border:1px solid #bbb;border-radius:5px;font-size:13px;">'+
                '<label style="display:flex;align-items:center;gap:5px;font-size:11px;color:#555;margin-top:6px;cursor:pointer;"><input type="checkbox" id="chkRecordarPw"> <i class="bi bi-unlock" style="color:#16a34a;"></i> Recordar contraseña (no volver a pedirla)</label>'+
                '<button id="btnAplicarFirmaPw" class="btn-modal primary" style="width:100%;margin-top:6px;"><i class="bi bi-shield-lock"></i> Firmar</button>'+
                '</div>';
            const inp = zona.querySelector('#inputPwFirma');
            inp.focus();
            const aplicar = async () => {
                const pw = inp.value;
                if (!pw) { inp.focus(); return; }
                const recordar = zona.querySelector('#chkRecordarPw').checked;
                if (recordar) {
                    // Persistir la contraseña (cifrada) requiere aceptar el aviso
                    if (await _asegurarConsentimiento()) {
                        const r = await window.FaroFirmaCerts.recordarPassword(certMeta.id, pw);
                        if (r && r.exito) { certMeta.tiene_password = true; mostrarToast('Contraseña recordada para ' + certMeta.nombre, 'ok'); }
                    }
                }
                _aplicarFirmaCon(certMeta, pw, box);
            };
            zona.querySelector('#btnAplicarFirmaPw').addEventListener('click', aplicar);
            inp.addEventListener('keydown', e => { if (e.key === 'Enter') aplicar(); });
        }

        async function _aplicarFirmaCon(certMeta, password, box) {
            box.querySelectorAll('button, input').forEach(b => b.disabled = true);
            const btnAplicar = box.querySelector('#btnAplicarFirmaPw');
            if (btnAplicar) btnAplicar.innerHTML = '<i class="bi bi-hourglass-split"></i> Firmando...';
            const pos = _pendingBox.pos;
            const ok = await firmarDocumento(pos, { id: certMeta.id, name: certMeta.name, password: password }, false);
            if (ok) {
                _pendingBox = null;
                _quitarPreviaFirma();
                mostrarToast('Firma agregada. Dibuja otro recuadro para firmar de nuevo o descarga el documento.', 'ok');
            } else {
                // contraseña incorrecta u otro error: reactivar y olvidar la contraseña
                delete _pwCache[certMeta.id];
                box.querySelectorAll('button, input').forEach(b => b.disabled = false);
                if (btnAplicar) btnAplicar.innerHTML = '<i class="bi bi-shield-lock"></i> Firmar';
            }
        }

        // ============ MODO FIRMA MÚLTIPLE ============
        // Coloca varias firmas (muchas hojas o varias veces) eligiendo entre tus
        // firmas guardadas, y aplica TODO al final en una sola descarga.
        let _modoMultiple = false;
        let _certActual = null;      // firma actualmente seleccionada para colocar
        let _colocaciones = [];      // [{pos, cert, el}]

        function _entrarModoMultiple() {
            if (!state.pdfDoc) { mostrarToast('Primero abre un PDF', 'error'); return; }
            _modoMultiple = true;
            _quitarPreviaFirma();
            _firmaDibujo.activo = true;
            document.body.style.cursor = 'crosshair';
            const b = $('bannerDibujoFirma');
            if (b) b.querySelector('span').innerHTML = '<i class="bi bi-layers"></i> Firma múltiple: dibuja recuadros en las hojas que necesites';
            const bm = $('btnModoMultiple'); if (bm) bm.style.display = 'none';
            _mostrarPanelMultiple();
            if (!_certActual) _panelSeleccionarCert();
        }

        function _salirModoMultiple() {
            _modoMultiple = false;
            _firmaDibujo.activo = false;
            document.body.style.cursor = '';
            _bannerDibujo(false);
            document.getElementById('panelFirmaMultiple')?.remove();
            document.querySelectorAll('.firmaColocacionMarker').forEach(el => el.remove());
            _colocaciones = [];
            _certActual = null;
        }

        function _mostrarPanelMultiple() {
            let p = document.getElementById('panelFirmaMultiple');
            if (!p) {
                p = document.createElement('div');
                p.id = 'panelFirmaMultiple';
                p.style.cssText = 'position:fixed;top:60px;right:16px;z-index:9999;width:255px;background:#fff;border:1px solid #cbd5e1;border-radius:10px;box-shadow:0 4px 16px rgba(0,0,0,.2);padding:12px;font-size:13px;';
                document.body.appendChild(p);
            }
            _actualizarPanelMultiple();
        }

        function _actualizarPanelMultiple() {
            const p = document.getElementById('panelFirmaMultiple');
            if (!p) return;
            const nombre = _certActual ? _esc(_certActual.nombre) : '<span style="color:#dc2626;">Sin elegir</span>';
            const n = _colocaciones.length;
            p.innerHTML =
                '<div style="font-weight:700;color:#0b57c9;margin-bottom:8px;"><i class="bi bi-layers"></i> Firma múltiple</div>' +
                '<div style="font-size:11px;color:#888;">Firma actual:</div>' +
                '<div style="display:flex;align-items:center;gap:6px;margin-bottom:8px;"><i class="bi bi-patch-check-fill" style="color:#28a745;"></i><b>'+nombre+'</b></div>' +
                '<button id="btnCambiarFirmaMult" style="width:100%;border:1px solid #cbd5e1;background:#f8fafc;border-radius:6px;padding:6px;margin-bottom:8px;cursor:pointer;"><i class="bi bi-arrow-repeat"></i> Elegir / cambiar firma</button>' +
                '<div style="background:#f1f5f9;border-radius:6px;padding:6px 8px;margin-bottom:8px;">Firmas colocadas: <b>'+n+'</b></div>' +
                '<button id="btnAplicarMult" class="btn-modal primary" style="width:100%;margin-bottom:6px;" '+(n?'':'disabled')+'><i class="bi bi-check2-circle"></i> Aplicar y descargar ('+n+')</button>' +
                '<button id="btnSalirMult" style="width:100%;border:none;background:none;color:#dc2626;padding:4px;cursor:pointer;font-size:12px;">Terminar sin aplicar</button>' +
                '<div id="panelMultCertZona"></div>';
            $('btnCambiarFirmaMult').addEventListener('click', _panelSeleccionarCert);
            $('btnSalirMult').addEventListener('click', () => { if (!n || confirm('¿Terminar sin aplicar las firmas colocadas?')) _salirModoMultiple(); });
            const bAp = $('btnAplicarMult');
            if (bAp && n) bAp.addEventListener('click', _aplicarMultiple);
        }

        async function _panelSeleccionarCert() {
            await _cargarCertsGuardados();
            const zona = document.getElementById('panelMultCertZona');
            if (!zona) return;
            if (!certsGuardados.length) {
                zona.innerHTML = '<div style="margin-top:8px;font-size:12px;color:#888;">No tienes certificados guardados.</div>' +
                    '<button id="btnAddCertMult" style="width:100%;border:1px dashed #94a3b8;background:#fff;border-radius:6px;padding:6px;margin-top:4px;cursor:pointer;"><i class="bi bi-plus-lg"></i> Agregar certificado</button>';
                $('btnAddCertMult').addEventListener('click', () => { _pendingBox = null; _abrirDialogoCargarCert(); });
                return;
            }
            let html = '<div style="margin-top:8px;font-size:11px;color:#888;">Elige la firma:</div>';
            certsGuardados.forEach((c, i) => {
                html += '<button class="mult-cert-item" data-idx="'+i+'" style="display:block;width:100%;text-align:left;border:1px solid #e2e8f0;background:#f8fafc;border-radius:6px;padding:6px 8px;margin-top:4px;cursor:pointer;"><b style="color:#1473e6;">'+_esc(c.nombre)+'</b>'+(c.org?'<div style="font-size:11px;color:#666;">'+_esc(c.org)+'</div>':'')+'</button>';
            });
            html += '<button id="btnAddCertMult2" style="width:100%;border:1px dashed #94a3b8;background:#fff;border-radius:6px;padding:6px;margin-top:6px;cursor:pointer;"><i class="bi bi-plus-lg"></i> Agregar otro</button>';
            zona.innerHTML = html;
            zona.querySelectorAll('.mult-cert-item').forEach(btn => {
                btn.addEventListener('click', () => _fijarCertActual(certsGuardados[parseInt(btn.dataset.idx)], zona));
            });
            $('btnAddCertMult2').addEventListener('click', () => { _pendingBox = null; _abrirDialogoCargarCert(); });
        }

        function _fijarCertActual(cert, zona) {
            if (_pwCache[cert.id] || cert.tiene_password) {
                // Ya tenemos la contraseña (memoria) o está guardada en el servidor
                _certActual = cert; zona.innerHTML = ''; _actualizarPanelMultiple();
                mostrarToast('Firma actual: ' + cert.nombre, 'ok'); return;
            }
            zona.innerHTML = '<div style="margin-top:8px;padding:8px;background:#f0f7ff;border:1px solid #cfe0ff;border-radius:6px;">' +
                '<div style="font-size:11px;color:#555;margin-bottom:4px;"><i class="bi bi-key"></i> Contraseña de <b>'+_esc(cert.nombre)+'</b></div>' +
                '<input type="password" id="pwMultInput" placeholder="Contraseña" style="width:100%;box-sizing:border-box;padding:6px;border:1px solid #bbb;border-radius:5px;">' +
                '<label style="display:flex;align-items:center;gap:5px;font-size:11px;color:#555;margin-top:6px;cursor:pointer;"><input type="checkbox" id="chkRecordarPwMult"> <i class="bi bi-unlock" style="color:#16a34a;"></i> Recordar contraseña</label>' +
                '<button id="pwMultOk" class="btn-modal primary" style="width:100%;margin-top:6px;">Usar esta firma</button></div>';
            const inp = zona.querySelector('#pwMultInput'); inp.focus();
            const ok = async () => {
                if (!inp.value) { inp.focus(); return; }
                _pwCache[cert.id] = inp.value;   // se usa para las firmas de este lote
                if (zona.querySelector('#chkRecordarPwMult').checked) {
                    if (await _asegurarConsentimiento()) {
                        const r = await window.FaroFirmaCerts.recordarPassword(cert.id, inp.value);
                        if (r && r.exito) cert.tiene_password = true;
                    }
                }
                _certActual = cert; zona.innerHTML = ''; _actualizarPanelMultiple();
                mostrarToast('Firma actual: ' + cert.nombre, 'ok');
            };
            zona.querySelector('#pwMultOk').addEventListener('click', ok);
            inp.addEventListener('keydown', e => { if (e.key === 'Enter') ok(); });
        }

        function _agregarColocacion(wrapper, u, pos) {
            if (!_certActual) {
                document.getElementById('firmaPreviaBox')?.remove();
                mostrarToast('Primero elige la firma a colocar (panel derecho)', 'warn');
                _panelSeleccionarCert();
                return;
            }
            const marker = document.getElementById('firmaPreviaBox');
            const idx = _colocaciones.length + 1;
            if (marker) {
                marker.id = 'firmaColoc_' + Date.now() + '_' + idx;
                marker.className = 'firmaColocacionMarker';
                marker.style.border = '2px solid #16a34a';
                marker.style.background = 'rgba(22,163,74,.14)';
                marker.style.pointerEvents = 'none';
                const lbl = document.createElement('div');
                lbl.style.cssText = 'position:absolute;top:-15px;left:0;background:#16a34a;color:#fff;font-size:10px;padding:1px 5px;border-radius:6px;white-space:nowrap;';
                lbl.textContent = idx + '. ' + (_certActual.nombre || 'Firma');
                marker.appendChild(lbl);
            }
            _colocaciones.push({ pos: pos, cert: _certActual, el: marker });
            _actualizarPanelMultiple();
        }

        async function _aplicarMultiple() {
            if (!_colocaciones.length) return;
            const btn = $('btnAplicarMult');
            if (btn) { btn.disabled = true; btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Aplicando...'; }
            const firmas = _colocaciones.map(c => ({ certificado_id: c.cert.id, pagina: c.pos.pagina, x: c.pos.x, y: c.pos.y, ancho: c.pos.ancho, alto: c.pos.alto }));
            const passwords = {}; _colocaciones.forEach(c => { passwords[c.cert.id] = _pwCache[c.cert.id] || ''; });
            try {
                const fd = new FormData();
                fd.append('archivo', _getPdfBlob(), 'documento.pdf');
                fd.append('firmas', JSON.stringify(firmas));
                fd.append('passwords', JSON.stringify(passwords));
                const resp = await fetch('/api/pdf/firma-digital/firmar-multiple', { method: 'POST', body: fd, credentials: 'same-origin' });
                if (!resp.ok) { const d = await resp.json().catch(() => ({})); throw new Error(d.mensaje || ('Error ' + resp.status)); }
                const buf = await (await resp.blob()).arrayBuffer();
                const nombre = _nombreFirmado();
                await loadPDF(buf.slice(0));
                state.hayCambios = true;
                _descargarBlob(new Blob([buf], { type: 'application/pdf' }), nombre);
                _mostrarBotonDescargarFirmado();
                const total = firmas.length;
                _salirModoMultiple();
                mostrarToast('Se aplicaron ' + total + ' firmas y se descargó el documento', 'ok');
            } catch(e) {
                mostrarToast('Error al aplicar firmas: ' + e.message, 'error');
                if (btn) { btn.disabled = false; btn.innerHTML = '<i class="bi bi-check2-circle"></i> Aplicar y descargar (' + _colocaciones.length + ')'; }
            }
        }

        function _esc(s) {
            return String(s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
        }

        // ---- Certificados usados en sesiones anteriores (solo nombres, localStorage) ----
        function guardarFirmaEnLocal(nombre, cn, org) {
            try {
                let firmas = JSON.parse(localStorage.getItem('faro_firmas_p12') || '[]');
                if (firmas.some(f => f.nombre === nombre)) return;
                firmas.push({ nombre, cn, org, fecha: new Date().toISOString() });
                if (firmas.length > 5) firmas = firmas.slice(-5);
                localStorage.setItem('faro_firmas_p12', JSON.stringify(firmas));
            } catch(e) { /* localStorage no disponible */ }
        }

        function cargarFirmasGuardadas() {
            try {
                const firmas = JSON.parse(localStorage.getItem('faro_firmas_p12') || '[]');
                let container = $('listaFirmasGuardadas');
                if (!container) {
                    container = document.createElement('div');
                    container.id = 'listaFirmasGuardadas';
                    container.style.cssText = 'margin-top:12px;';
                    $('pasoCargarP12').appendChild(container);
                }
                if (firmas.length === 0) { container.style.display = 'none'; return; }
                container.style.display = 'block';
                container.innerHTML = '<div style="font-size:11px;font-weight:600;color:#888;margin-bottom:6px;"><i class="bi bi-clock-history"></i> Certificados usados anteriormente:</div>' +
                    firmas.map(f =>
                        '<div style="font-size:12px;padding:6px 8px;background:#f8f9fa;border-radius:4px;margin-bottom:4px;display:flex;align-items:center;gap:6px;">' +
                        '<i class="bi bi-shield-check" style="color:#28a745;"></i> ' +
                        '<span>' + _esc(f.cn || f.nombre) + (f.org ? ' - ' + _esc(f.org) : '') + '</span>' +
                        '</div>'
                    ).join('');
            } catch(e) { /* ignore */ }
        }
    })();

    // ==================== AGREGAR INICIALES ====================

};
