// -----------------------------------------------------------------------------
// Panel lateral derecho
// -----------------------------------------------------------------------------

let panelActivo = null;

function togglePanelInfo() {
    if (panelActivo === 'info') {
        cerrarPanelDerecho();
    } else {
        abrirPanelDetalles();
    }
}

function abrirPanelDetalles() {
    const panel = document.getElementById('rightPanelExpanded');
    const title = document.getElementById('rightPanelTitle');
    const content = document.getElementById('rightPanelContent');
    const main = document.querySelector('.gd-main');

    title.textContent = 'Detalles';
    panelActivo = 'info';

    // Activar botón correspondiente
    actualizarBotonesPanelDerecho();

    if (itemSeleccionado) {
        content.innerHTML = generarContenidoDetalles(itemSeleccionado);
        // Cargar dimensiones de imagen si aplica
        cargarDimensionesImagen();
        cargarPropietarioDetalle();
    } else {
        content.innerHTML = `
            <div class="gd-detail-preview">
                <span class="material-icons">info</span>
            </div>
            <p style="text-align: center; color: var(--gd-text-secondary);">
                Selecciona un archivo o carpeta para ver sus detalles
            </p>
        `;
    }

    panel.classList.add('show');
    main.classList.add('panel-open');
}

// Carga el propietario real (autor original) del archivo en el panel de detalles
function cargarPropietarioDetalle() {
    const el = document.getElementById('detallePropietario');
    if (!el) return;
    const ruta = el.dataset.ruta;
    if (!ruta) { el.textContent = '—'; return; }
    fetch(`${API_BASE}/archivo-autor?ruta=${encodeURIComponent(ruta)}`)
        .then(r => r.json())
        .then(d => {
            if (d && d.success) {
                el.textContent = d.propietario ? (d.es_propietario ? (d.propietario + ' (yo)') : d.propietario) : 'yo';
                const c = document.getElementById('detalleCompartido');
                if (c && !d.es_propietario && d.propietario) {
                    c.innerHTML = '<span style="color:#4285f4;">Sí &mdash; compartido por ' + d.propietario + '</span>';
                }
                const ed = document.getElementById('detalleEditable');
                if (ed && typeof d.puede_editar !== 'undefined') {
                    ed.innerHTML = d.puede_editar
                        ? '<span style="color:#0a8a0a;">Sí &mdash; ' + (d.permiso_txt || 'Editor') + '</span>'
                        : (d.permiso_txt || 'Lector');
                }
                const tm = document.getElementById('detalleTamano');
                if (tm && d.tamano_humano) { tm.textContent = d.tamano_humano; }
            } else {
                el.textContent = 'yo';
            }
        })
        .catch(() => { el.textContent = 'yo'; });
}

// Función para cargar dimensiones de imagen en el panel de detalles
function cargarDimensionesImagen() {
    const el = document.getElementById('imageDimensionsValue');
    if (!el) return;

    const ruta = el.dataset.ruta;
    if (!ruta) {
        el.textContent = 'No disponible';
        return;
    }

    const img = new Image();
    img.onload = function() {
        if (el) el.textContent = this.width + ' × ' + this.height + ' px';
    };
    img.onerror = function() {
        if (el) el.textContent = 'No disponible';
    };
    img.src = `${API_BASE}/archivos/descargar?ruta=${encodeURIComponent(ruta)}`;
}

function generarContenidoDetalles(item) {
    const tipo = item.esCarpeta ? 'carpeta' : (item.tipo || 'archivo');
    const icono = ICONOS[tipo] || 'insert_drive_file';
    const esImagen = EXTENSIONES_IMAGEN.includes((item.extension || '').toLowerCase());
    const esPdf = EXTENSIONES_PDF.includes((item.extension || '').toLowerCase());
    const esVideo = EXTENSIONES_VIDEO.includes((item.extension || '').toLowerCase());
    const esAudio = ['mp3', 'wav', 'ogg', 'flac', 'aac', 'm4a'].includes((item.extension || '').toLowerCase());

    // Generar preview para imágenes
    let previewHtml = '';
    if (esImagen && item.preview_url) {
        previewHtml = `
            <div class="gd-detail-preview" style="background-image: url('${item.preview_url}'); background-size: cover; background-position: center; border-radius: 8px; height: 150px;">
            </div>`;
    } else {
        previewHtml = `
            <div class="gd-detail-preview">
                <span class="material-icons" style="color: ${item.color_personalizado || item.color || '#5f6368'}; font-size: 80px;">${icono}</span>
            </div>`;
    }

    // Determinar tipo de archivo descriptivo
    let tipoDescriptivo = 'Archivo';
    if (item.esCarpeta) tipoDescriptivo = 'Carpeta';
    else if (esImagen) tipoDescriptivo = `Imagen ${(item.extension || '').toUpperCase()}`;
    else if (esPdf) tipoDescriptivo = 'Documento PDF';
    else if (esVideo) tipoDescriptivo = `Video ${(item.extension || '').toUpperCase()}`;
    else if (esAudio) tipoDescriptivo = `Audio ${(item.extension || '').toUpperCase()}`;
    else if (item.extension) tipoDescriptivo = `Archivo ${item.extension.toUpperCase()}`;

    // MIME type legible
    let mimeDescriptivo = item.mime_type || '';
    if (mimeDescriptivo) {
        mimeDescriptivo = mimeDescriptivo.replace('application/', '').replace('image/', '').replace('video/', '').replace('audio/', '');
    }

    return `
        ${previewHtml}
        <div class="gd-detail-filename" style="word-break: break-word;">${item.nombre}</div>

        <div class="gd-detail-section">
            <div class="gd-detail-section-title">
                <span class="material-icons" style="font-size: 18px; margin-right: 6px;">info</span>
                Información
            </div>

            <div class="gd-detail-item">
                <span class="gd-detail-label">Tipo</span>
                <span class="gd-detail-value">${tipoDescriptivo}</span>
            </div>

            ${item.mime_type ? `
            <div class="gd-detail-item">
                <span class="gd-detail-label">Formato</span>
                <span class="gd-detail-value" style="font-family: monospace; font-size: 12px;">${item.mime_type}</span>
            </div>
            ` : ''}

            ${!item.esCarpeta ? `
            <div class="gd-detail-item">
                <span class="gd-detail-label">Tamaño</span>
                <span class="gd-detail-value" id="detalleTamano">${item.tamano_humano || '<span style="color:#888">Cargando...</span>'}</span>
            </div>
            ` : ''}

            ${item.modificado_at ? `
            <div class="gd-detail-item">
                <span class="gd-detail-label">Modificado</span>
                <span class="gd-detail-value">${formatearFechaCompleta(item.modificado_at)}</span>
            </div>
            ` : ''}

            ${item.creado_at ? `
            <div class="gd-detail-item">
                <span class="gd-detail-label">Creado</span>
                <span class="gd-detail-value">${formatearFechaCompleta(item.creado_at)}</span>
            </div>
            ` : ''}
        </div>

        <div class="gd-detail-section">
            <div class="gd-detail-section-title">
                <span class="material-icons" style="font-size: 18px; margin-right: 6px;">folder</span>
                Ubicación
            </div>
            <div class="gd-detail-item">
                <span class="gd-detail-label">Ruta</span>
                <span class="gd-detail-value" style="word-break: break-all; font-family: monospace; font-size: 11px;">${item.ruta || '/'}</span>
            </div>
            <div class="gd-detail-item">
                <span class="gd-detail-label">Propietario</span>
                <span class="gd-detail-value" id="detallePropietario" data-ruta="${(item.ruta_completa || item.ruta || '').replace(/"/g, '&quot;')}">Cargando...</span>
            </div>
        </div>

        ${esImagen ? `
        <div class="gd-detail-section">
            <div class="gd-detail-section-title">
                <span class="material-icons" style="font-size: 18px; margin-right: 6px;">image</span>
                Imagen
            </div>
            <div class="gd-detail-item">
                <span class="gd-detail-label">Dimensiones</span>
                <span class="gd-detail-value" id="imageDimensionsValue" data-ruta="${(item.ruta || item.ruta_completa || '').replace(/"/g, '&quot;')}">Cargando...</span>
            </div>
        </div>
        ` : ''}

        <div class="gd-detail-section">
            <div class="gd-detail-section-title">
                <span class="material-icons" style="font-size: 18px; margin-right: 6px;">flag</span>
                Estado
            </div>
            <div class="gd-detail-item">
                <span class="gd-detail-label">Destacado</span>
                <span class="gd-detail-value">${item.es_favorito || item.es_favorita ? '<span style="color: #f4b400;">★ Sí</span>' : 'No'}</span>
            </div>
            <div class="gd-detail-item">
                <span class="gd-detail-label">Compartido</span>
                <span class="gd-detail-value" id="detalleCompartido">${item.es_compartido || item.es_compartida ? '<span style="color: #4285f4;">Sí</span>' : 'No'}</span>
            </div>
            ${!item.esCarpeta ? `
            <div class="gd-detail-item">
                <span class="gd-detail-label">Editable</span>
                <span class="gd-detail-value" id="detalleEditable">${item.es_editable ? 'Sí' : '<span style="color:#888">Cargando...</span>'}</span>
            </div>
            ` : ''}
        </div>

        <div class="gd-detail-section">
            <div class="gd-detail-section-title">
                <span class="material-icons" style="font-size: 18px; margin-right: 6px;">bolt</span>
                Acciones
            </div>
            <button class="btn btn-outline-primary btn-sm w-100 mb-2" onclick="compartirSeleccionado()">
                <span class="material-icons me-2" style="font-size: 18px;">person_add</span>
                Compartir
            </button>
            <button class="btn btn-outline-secondary btn-sm w-100 mb-2" onclick="descargarSeleccionado()">
                <span class="material-icons me-2" style="font-size: 18px;">download</span>
                Descargar
            </button>
            ${!item.esCarpeta ? `
            <button class="btn btn-outline-info btn-sm w-100" onclick="abrirArchivo('${(item.ruta || item.ruta_completa || '').replace(/'/g, "\\'")}')">
                <span class="material-icons me-2" style="font-size: 18px;">open_in_new</span>
                Abrir
            </button>
            ` : ''}
        </div>
    `;
}

// Función para formatear fecha completa con hora
function formatearFechaCompleta(fechaStr) {
    if (!fechaStr) return '';
    try {
        const fecha = new Date(fechaStr);
        const opciones = {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        };
        return fecha.toLocaleDateString('es-ES', opciones);
    } catch (e) {
        return fechaStr;
    }
}

function abrirCalendario() {
    panelActivo = 'calendar';
    actualizarBotonesPanelDerecho();
    const panel = document.getElementById('rightPanelExpanded');
    const title = document.getElementById('rightPanelTitle');
    const content = document.getElementById('rightPanelContent');
    const main = document.querySelector('.gd-main');

    title.textContent = 'Maquita Calendario';
    content.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <span class="material-icons" style="font-size: 64px; color: #4285f4;">calendar_today</span>
            <h4 style="margin-top: 16px;">Maquita Calendario</h4>
            <p style="color: var(--gd-text-secondary);">Próximamente: Integración con calendario</p>
        </div>
    `;

    panel.classList.add('show');
    main.classList.add('panel-open');
}

function abrirNotas() {
    panelActivo = 'notes';
    actualizarBotonesPanelDerecho();
    const panel = document.getElementById('rightPanelExpanded');
    const title = document.getElementById('rightPanelTitle');
    const content = document.getElementById('rightPanelContent');
    const main = document.querySelector('.gd-main');

    title.textContent = 'Maquita Notas';
    content.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <span class="material-icons" style="font-size: 64px; color: #fbbc04;">lightbulb</span>
            <h4 style="margin-top: 16px;">Maquita Notas</h4>
            <p style="color: var(--gd-text-secondary);">Próximamente: Notas rápidas</p>
        </div>
    `;

    panel.classList.add('show');
    main.classList.add('panel-open');
}

function abrirTareas() {
    panelActivo = 'tasks';
    actualizarBotonesPanelDerecho();
    const panel = document.getElementById('rightPanelExpanded');
    const title = document.getElementById('rightPanelTitle');
    const content = document.getElementById('rightPanelContent');
    const main = document.querySelector('.gd-main');

    title.textContent = 'Maquita Tareas';
    content.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <span class="material-icons" style="font-size: 64px; color: #4285f4;">check_circle</span>
            <h4 style="margin-top: 16px;">Maquita Tareas</h4>
            <p style="color: var(--gd-text-secondary);">Próximamente: Lista de tareas</p>
        </div>
    `;

    panel.classList.add('show');
    main.classList.add('panel-open');
}

function abrirContactos() {
    panelActivo = 'contacts';
    actualizarBotonesPanelDerecho();
    const panel = document.getElementById('rightPanelExpanded');
    const title = document.getElementById('rightPanelTitle');
    const content = document.getElementById('rightPanelContent');
    const main = document.querySelector('.gd-main');

    title.textContent = 'Contactos';
    content.innerHTML = `
        <div style="text-align: center; padding: 40px 20px;">
            <span class="material-icons" style="font-size: 64px; color: #4285f4;">contacts</span>
            <h4 style="margin-top: 16px;">Contactos</h4>
            <p style="color: var(--gd-text-secondary);">Próximamente: Gestión de contactos</p>
        </div>
    `;

    panel.classList.add('show');
    main.classList.add('panel-open');
}

function mostrarComplementos() {
    mostrarNotificacion('Complementos adicionales próximamente disponibles', 'info');
}

// IA Maquita - Asistente de Inteligencia Artificial (En desarrollo)
function abrirIAMaquita() {
    Swal.fire({
        title: '<span class="material-icons" style="color: #0061a1; vertical-align: middle;">auto_awesome</span> IA Maquita',
        html: `
            <div style="text-align: center; padding: 20px 0;">
                <div style="background: linear-gradient(135deg, #0061a1 0%, #004a7c 100%); width: 80px; height: 80px; border-radius: 50%; margin: 0 auto 20px; display: flex; align-items: center; justify-content: center;">
                    <span class="material-icons" style="color: #fff; font-size: 40px;">auto_awesome</span>
                </div>
                <h4 style="color: #0061a1; margin-bottom: 12px;">Función en Desarrollo</h4>
                <p style="color: var(--gd-text-secondary); margin-bottom: 20px;">
                    Estamos trabajando en la integración de inteligencia artificial para mejorar tus documentos.
                </p>
                <div style="background: #e3f2fd; border-radius: 8px; padding: 16px; text-align: left;">
                    <p style="font-size: 13px; color: #1565c0; margin-bottom: 8px;"><strong>Próximamente podrás:</strong></p>
                    <ul style="color: var(--gd-text-secondary); font-size: 13px; margin: 0; padding-left: 20px;">
                        <li>Resumir documentos automáticamente</li>
                        <li>Traducir contenido a otros idiomas</li>
                        <li>Corregir gramática y ortografía</li>
                        <li>Mejorar la redacción de textos</li>
                        <li>Extraer datos importantes</li>
                    </ul>
                </div>
            </div>
        `,
        confirmButtonText: 'Entendido',
        confirmButtonColor: '#0061a1',
        width: 420
    });
}

function iaAccion(accion) {
    // Función reservada para desarrollo futuro
    mostrarNotificacion('Función en desarrollo', 'info');
}

// IA Chat - Panel de asistencia en el panel derecho
function abrirIAChat() {
    panelActivo = 'ia-chat';
    actualizarBotonesPanelDerecho();
    const panel = document.getElementById('rightPanelExpanded');
    const title = document.getElementById('rightPanelTitle');
    const content = document.getElementById('rightPanelContent');
    const main = document.querySelector('.gd-main');

    title.textContent = 'Maquita IA';
    content.innerHTML = `
        <div class="gd-ia-chat-container">
            <div class="gd-ia-chat-messages" id="iaChatMessages">
                <div class="gd-ia-chat-welcome">
                    <div class="gd-ia-avatar">
                        <span class="material-icons">smart_toy</span>
                    </div>
                    <p>¡Hola! Soy el asistente de <strong>Maquita IA</strong>. ¿En qué puedo ayudarte hoy?</p>
                </div>
                <div class="gd-ia-chat-suggestions">
                    <button onclick="iaEnviarSugerencia('¿Cómo subo archivos?')">¿Cómo subo archivos?</button>
                    <button onclick="iaEnviarSugerencia('¿Cómo comparto una carpeta?')">¿Cómo comparto una carpeta?</button>
                    <button onclick="iaEnviarSugerencia('¿Cómo recupero un archivo eliminado?')">¿Cómo recupero archivos?</button>
                </div>
            </div>
            <div class="gd-ia-chat-input">
                <input type="text" id="iaChatInput" placeholder="Escribe tu pregunta..." onkeypress="if(event.key==='Enter')iaEnviarMensaje()">
                <button onclick="iaEnviarMensaje()">
                    <span class="material-icons">send</span>
                </button>
            </div>
        </div>
        <style>
            .gd-ia-chat-container {
                display: flex;
                flex-direction: column;
                height: calc(100vh - 180px);
            }
            .gd-ia-chat-messages {
                flex: 1;
                overflow-y: auto;
                padding: 16px;
            }
            .gd-ia-chat-welcome {
                text-align: center;
                padding: 20px;
            }
            .gd-ia-avatar {
                width: 60px;
                height: 60px;
                background: linear-gradient(135deg, #0061a1 0%, #004a7c 100%);
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0 auto 12px;
            }
            .gd-ia-avatar .material-icons {
                color: #fff;
                font-size: 32px;
            }
            .gd-ia-chat-welcome p {
                color: var(--gd-text-secondary);
                font-size: 14px;
            }
            .gd-ia-chat-suggestions {
                display: flex;
                flex-direction: column;
                gap: 8px;
                margin-top: 16px;
            }
            .gd-ia-chat-suggestions button {
                padding: 10px 16px;
                border: 1px solid #0061a1;
                border-radius: 20px;
                background: #fff;
                color: #0061a1;
                font-size: 13px;
                cursor: pointer;
                transition: all 0.2s;
            }
            .gd-ia-chat-suggestions button:hover {
                background: #e3f2fd;
            }
            .gd-ia-chat-input {
                display: flex;
                gap: 8px;
                padding: 12px;
                border-top: 1px solid var(--gd-border);
                background: #f8f9fa;
            }
            .gd-ia-chat-input input {
                flex: 1;
                padding: 10px 16px;
                border: 1px solid var(--gd-border);
                border-radius: 20px;
                font-size: 14px;
                outline: none;
            }
            .gd-ia-chat-input input:focus {
                border-color: #0061a1;
            }
            .gd-ia-chat-input button {
                width: 40px;
                height: 40px;
                border: none;
                border-radius: 50%;
                background: #0061a1;
                color: #fff;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .gd-ia-chat-input button:hover {
                background: #004a7c;
            }
            .gd-ia-message {
                margin: 12px 0;
                display: flex;
                gap: 8px;
            }
            .gd-ia-message.user {
                flex-direction: row-reverse;
            }
            .gd-ia-message-bubble {
                max-width: 80%;
                padding: 10px 14px;
                border-radius: 16px;
                font-size: 14px;
            }
            .gd-ia-message.user .gd-ia-message-bubble {
                background: #0061a1;
                color: #fff;
                border-bottom-right-radius: 4px;
            }
            .gd-ia-message.bot .gd-ia-message-bubble {
                background: #f1f3f4;
                color: var(--gd-text-primary);
                border-bottom-left-radius: 4px;
            }
        </style>
    `;

    panel.classList.add('show');
    main.classList.add('panel-open');
}

function iaEnviarMensaje() {
    const input = document.getElementById('iaChatInput');
    const mensaje = input.value.trim();
    if (!mensaje) return;

    agregarMensajeChat('user', mensaje);
    input.value = '';

    // Simular respuesta (en desarrollo)
    setTimeout(() => {
        agregarMensajeChat('bot', 'Esta función está en desarrollo. Pronto podré ayudarte con tus consultas sobre Nube Maquita.');
    }, 500);
}

function iaEnviarSugerencia(pregunta) {
    document.getElementById('iaChatInput').value = pregunta;
    iaEnviarMensaje();
}

function agregarMensajeChat(tipo, texto) {
    const container = document.getElementById('iaChatMessages');
    const suggestions = container.querySelector('.gd-ia-chat-suggestions');
    if (suggestions) suggestions.remove();

    const mensaje = document.createElement('div');
    mensaje.className = `gd-ia-message ${tipo}`;
    mensaje.innerHTML = `<div class="gd-ia-message-bubble">${texto}</div>`;
    container.appendChild(mensaje);
    container.scrollTop = container.scrollHeight;
}

function cerrarPanelDerecho() {
    const panel = document.getElementById('rightPanelExpanded');
    const main = document.querySelector('.gd-main');

    panel.classList.remove('show');
    main.classList.remove('panel-open');
    panelActivo = null;
    actualizarBotonesPanelDerecho();
}

// Toggle panel lateral (ocultar/mostrar)
function togglePanelLateral() {
    const rightPanel = document.getElementById('rightPanel');
    const main = document.querySelector('.gd-main');
    const toggleBtn = document.getElementById('panelToggle');

    const isHidden = rightPanel.classList.toggle('hidden');
    main.classList.toggle('panel-hidden', isHidden);
    toggleBtn.classList.toggle('panel-hidden', isHidden);

    // Actualizar tooltip
    toggleBtn.dataset.tooltip = isHidden ? 'Mostrar panel lateral' : 'Ocultar panel lateral';

    // Guardar preferencia
    localStorage.setItem('panelLateralOculto', isHidden);
}

// Restaurar estado del panel al cargar
function restaurarEstadoPanelLateral() {
    const isHidden = localStorage.getItem('panelLateralOculto') === 'true';
    if (isHidden) {
        const rightPanel = document.getElementById('rightPanel');
        const main = document.querySelector('.gd-main');
        const toggleBtn = document.getElementById('panelToggle');

        rightPanel.classList.add('hidden');
        main.classList.add('panel-hidden');
        toggleBtn.classList.add('panel-hidden');
        toggleBtn.dataset.tooltip = 'Mostrar panel lateral';
    }
}

function actualizarBotonesPanelDerecho() {
    const btns = document.querySelectorAll('.gd-right-panel-btn');
    btns.forEach(btn => btn.classList.remove('active'));

    // No activar ningún botón específico ya que los botones son para las apps
}

function verDetalles() {
    document.getElementById('contextMenu').classList.remove('show');
    abrirPanelDetalles();
}

function _fmtFechaAct(fecha) {
    if (!fecha) return 'Fecha desconocida';
    try {
        return new Date(fecha).toLocaleString('es-EC', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (e) { return fecha; }
}

function _eventoActHTML(icon, titulo, fecha, size, actual, fileId, versionId) {
    const f = _fmtFechaAct(fecha);
    let derecha = '';
    if (actual) {
        derecha = '<span style="font-size:11px;color:#1a73e8;font-weight:600;">Actual</span>';
    } else if (fileId && versionId) {
        derecha = `<button onclick="restaurarVersion('${fileId}','${versionId}','${f}')" class="btn btn-sm btn-outline-primary" style="font-size:11px;padding:2px 10px;border-radius:6px;"><span class="material-icons" style="font-size:13px;vertical-align:middle;">restore</span> Restaurar</button>`;
    }
    return `<div style="display:flex;align-items:center;gap:10px;padding:11px 16px;border-bottom:1px solid var(--gd-border,#f3f3f3);">
        <span class="material-icons" style="font-size:18px;color:${actual ? '#1a73e8' : 'var(--gd-text-secondary,#5f6368)'};">${icon}</span>
        <div style="flex:1;min-width:0;"><div style="font-size:13px;font-weight:500;">${titulo}</div>
        <div style="font-size:12px;color:var(--gd-text-secondary,#5f6368);">${f}${size ? ' &middot; ' + size : ''}</div></div>${derecha}</div>`;
}

function verActividad() {
    document.getElementById('contextMenu').classList.remove('show');
    panelActivo = 'activity';
    const panel = document.getElementById('rightPanelExpanded');
    const title = document.getElementById('rightPanelTitle');
    const content = document.getElementById('rightPanelContent');
    const main = document.querySelector('.gd-main');

    title.textContent = 'Actividad';
    panel.classList.add('show');
    main.classList.add('panel-open');

    if (!itemSeleccionado || itemSeleccionado.esCarpeta) {
        content.innerHTML = `<div style="text-align:center;padding:40px 20px;">
            <span class="material-icons" style="font-size:48px;color:var(--gd-text-secondary);opacity:.4;">history</span>
            <p style="color:var(--gd-text-secondary);margin-top:8px;">La actividad está disponible para archivos.</p></div>`;
        return;
    }

    const fileId = itemSeleccionado.file_id || itemSeleccionado.id || itemSeleccionado.folder_id;
    const nombre = itemSeleccionado.nombre || '';
    const modActual = itemSeleccionado.modificado_at || itemSeleccionado.modificado || itemSeleccionado.fecha_modificacion || '';
    const sizeActual = itemSeleccionado.tamano_humano || itemSeleccionado.tamano || '';

    content.innerHTML = `<div style="padding:40px;text-align:center;color:var(--gd-text-secondary);">
        <div class="spinner-border spinner-border-sm" role="status"></div><p style="margin-top:8px;">Cargando actividad...</p></div>`;

    if (!fileId) {
        content.innerHTML = '<div style="padding:20px;color:#c5221f;font-size:13px;">No se pudo obtener el archivo.</div>';
        return;
    }

    const rutaArch = itemSeleccionado.ruta_completa || itemSeleccionado.ruta || '';
    Promise.all([
        fetch(`${API_BASE}/versiones/${fileId}`).then(r => r.json()).catch(() => ({ success: false })),
        fetch(`${API_BASE}/archivo-autor?ruta=${encodeURIComponent(rutaArch)}`).then(r => r.json()).catch(() => ({ success: false }))
    ]).then(([data, autorData]) => {
        const versiones = (data && data.success && data.versiones) ? data.versiones : [];

        let autorHtml = '';
        if (autorData && autorData.success && autorData.propietario) {
            autorHtml = `<div style="padding:10px 16px;background:#f8f9fa;border-bottom:1px solid var(--gd-border,#eee);font-size:12px;">
                <div style="display:flex;align-items:center;gap:8px;">
                    <span class="material-icons" style="font-size:16px;color:#1a73e8;">person</span>
                    <span><strong>Autor / Propietario:</strong> ${autorData.propietario}</span></div>`;
            if (!autorData.es_propietario) {
                autorHtml += `<div style="display:flex;align-items:center;gap:8px;margin-top:5px;">
                    <span class="material-icons" style="font-size:16px;color:#34a853;">share</span>
                    <span><strong>Compartido por:</strong> ${autorData.propietario}</span></div>`;
            }
            autorHtml += '</div>';
        }

        let html = `<div style="padding:12px 16px;border-bottom:1px solid var(--gd-border,#eee);">
            <div style="font-weight:600;font-size:14px;display:flex;align-items:center;gap:8px;">
            <span class="material-icons" style="font-size:18px;color:var(--gd-text-secondary);">history</span>Historial del archivo</div>
            <div style="font-size:12px;color:var(--gd-text-secondary);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${nombre}</div></div>`;
        html += autorHtml;
        html += '<div>';
        html += _eventoActHTML('edit', 'Versión actual', modActual, sizeActual, true, null, null);
        versiones.forEach(v => {
            html += _eventoActHTML('history', 'Modificación anterior', v.fecha, v.tamano_humano, false, fileId, v.version_id);
        });
        if (versiones.length === 0) {
            html += `<div style="padding:16px;text-align:center;color:var(--gd-text-secondary);font-size:13px;">
                Sin versiones anteriores.<br><small>El historial se va creando cada vez que se modifica el archivo.</small></div>`;
        }
        html += '</div>';
        content.innerHTML = html;
    }).catch(() => {
        content.innerHTML = '<div style="padding:20px;color:#c5221f;font-size:13px;">Error cargando la actividad.</div>';
    });
}

function buscarEnCarpeta() {
    cerrarSubmenus();
    document.getElementById('contextMenu').classList.remove('show');

    if (!itemSeleccionado) {
        mostrarNotificacion('Selecciona una carpeta primero', 'warning');
        return;
    }

    if (!itemSeleccionado.esCarpeta) {
        mostrarNotificacion('Esta opción solo está disponible para carpetas', 'warning');
        return;
    }

    // Navegar a la carpeta y abrir búsqueda
    navegarA(itemSeleccionado.ruta);
    setTimeout(() => {
        document.getElementById('searchBox')?.focus();
    }, 300);
}

function cambiarColorCarpeta() {
    cerrarSubmenus();
    document.getElementById('contextMenu').classList.remove('show');

    if (!itemSeleccionado) {
        mostrarNotificacion('Selecciona una carpeta primero', 'warning');
        return;
    }

    if (!itemSeleccionado.esCarpeta) {
        mostrarNotificacion('Esta opción solo está disponible para carpetas', 'warning');
        return;
    }

    const carpeta = itemSeleccionado;

    const colores = [
        { nombre: 'Por defecto', color: '#5f6368' },
        { nombre: 'Rojo', color: '#ea4335' },
        { nombre: 'Naranja', color: '#fa7b17' },
        { nombre: 'Amarillo', color: '#f9ab00' },
        { nombre: 'Verde', color: '#34a853' },
        { nombre: 'Azul', color: '#4285f4' },
        { nombre: 'Púrpura', color: '#a142f4' },
        { nombre: 'Gris', color: '#9aa0a6' }
    ];

    let coloresHtml = colores.map(c => `
        <button class="gd-color-option" onclick="aplicarColorCarpeta('${carpeta.folder_id}', '${c.color}')" title="${c.nombre}" style="background: ${c.color};">
        </button>
    `).join('');

    Swal.fire({
        title: 'Cambiar color de carpeta',
        html: `
            <p style="color: var(--gd-text-secondary); margin-bottom: 16px;">Selecciona un color para "${carpeta.nombre}"</p>
            <div class="gd-color-picker">
                ${coloresHtml}
            </div>
            <style>
                .gd-color-picker {
                    display: flex;
                    gap: 8px;
                    justify-content: center;
                    flex-wrap: wrap;
                    padding: 10px;
                }
                .gd-color-option {
                    width: 36px;
                    height: 36px;
                    border-radius: 50%;
                    border: 2px solid transparent;
                    cursor: pointer;
                    transition: all 0.2s;
                }
                .gd-color-option:hover {
                    transform: scale(1.1);
                    border-color: var(--gd-text-primary);
                }
            </style>
        `,
        showConfirmButton: false,
        showCloseButton: true
    });
}

async function aplicarColorCarpeta(folderId, color) {
    Swal.close();

    try {
        const response = await fetch(`${API_BASE}/carpetas/estilo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder_id: folderId,
                color: color === '#5f6368' ? '' : color  // Enviar vacío para "Por defecto"
            })
        });

        const data = await response.json();

        if (data.success) {
            mostrarNotificacion('Color actualizado para todos los usuarios', 'success');

            // Actualizar TODAS las apariciones (grid + lista) al instante
            const _col = (!color || color === '#5f6368') ? '#5f6368' : color;
            document.querySelectorAll(`[data-folder-id="${folderId}"]`).forEach(el => {
                const icon = el.querySelector('.folder-icon .material-icons, .file-icon .material-icons, .gd-list-name .material-icons, .gd-tree-folder');
                if (icon) icon.style.color = _col;
                el.dataset.colorPersonalizado = (color === '#5f6368') ? '' : (color || '');
                el.dataset.color = _col;
            });
        } else {
            mostrarNotificacion(data.error || 'Error al cambiar color', 'error');
        }
    } catch (error) {
        console.error('Error aplicando color:', error);
        mostrarNotificacion('Error al cambiar color de carpeta', 'error');
    }
}

function cambiarIconoCarpeta() {
    cerrarSubmenus();
    document.getElementById('contextMenu').classList.remove('show');

    if (!itemSeleccionado) {
        mostrarNotificacion('Selecciona una carpeta primero', 'warning');
        return;
    }

    if (!itemSeleccionado.esCarpeta) {
        mostrarNotificacion('Esta opción solo está disponible para carpetas', 'warning');
        return;
    }

    const carpeta = itemSeleccionado;

    const iconos = [
        { nombre: 'Sin icono', icono: '', material: 'remove_circle_outline' },
        { nombre: 'Estrella', icono: 'star', material: 'star' },
        { nombre: 'Corazón', icono: 'favorite', material: 'favorite' },
        { nombre: 'Trabajo', icono: 'work', material: 'work' },
        { nombre: 'Casa', icono: 'home', material: 'home' },
        { nombre: 'Música', icono: 'music_note', material: 'music_note' },
        { nombre: 'Fotos', icono: 'photo_camera', material: 'photo_camera' },
        { nombre: 'Videos', icono: 'videocam', material: 'videocam' },
        { nombre: 'Documentos', icono: 'description', material: 'description' },
        { nombre: 'Descargas', icono: 'download', material: 'download' },
        { nombre: 'Importante', icono: 'priority_high', material: 'priority_high' },
        { nombre: 'Seguro', icono: 'lock', material: 'lock' },
        { nombre: 'Compartido', icono: 'people', material: 'people' },
        { nombre: 'Proyectos', icono: 'rocket_launch', material: 'rocket_launch' },
        { nombre: 'Código', icono: 'code', material: 'code' },
        { nombre: 'Finanzas', icono: 'payments', material: 'payments' }
    ];

    let iconosHtml = iconos.map(i => `
        <button class="gd-icon-option" onclick="aplicarIconoCarpeta('${carpeta.ruta_completa || carpeta.ruta}', '${i.icono}')" title="${i.nombre}">
            <span class="material-icons">${i.material}</span>
        </button>
    `).join('');

    Swal.fire({
        title: 'Cambiar icono de carpeta',
        html: `
            <p style="color: var(--gd-text-secondary); margin-bottom: 16px;">Selecciona un icono para "${carpeta.nombre}"</p>
            <div class="gd-icon-picker">
                ${iconosHtml}
            </div>
            <style>
                .gd-icon-picker {
                    display: grid;
                    grid-template-columns: repeat(4, 1fr);
                    gap: 8px;
                    padding: 10px;
                    max-width: 240px;
                    margin: 0 auto;
                }
                .gd-icon-option {
                    width: 48px;
                    height: 48px;
                    border-radius: 8px;
                    border: 1px solid #dadce0;
                    background: white;
                    cursor: pointer;
                    transition: all 0.2s;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .gd-icon-option:hover {
                    background: #e8f0fe;
                    border-color: #4285f4;
                }
                .gd-icon-option .material-icons {
                    color: #5f6368;
                    font-size: 24px;
                }
                .gd-icon-option:hover .material-icons {
                    color: #4285f4;
                }
            </style>
        `,
        showConfirmButton: false,
        showCloseButton: true
    });
}

async function aplicarIconoCarpeta(ruta, icono) {
    Swal.close();

    try {
        const response = await fetch(`${API_BASE}/carpetas/estilo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ruta: ruta,
                icono: icono
            })
        });

        const data = await response.json();

        if (data.success) {
            mostrarNotificacion('Icono de carpeta actualizado', 'success');

            // Actualizar visualmente la carpeta
            const carpetaElement = document.querySelector(`[data-ruta="${ruta}"]`);
            if (carpetaElement) {
                // Remover icono interno anterior si existe
                const oldInnerIcon = carpetaElement.querySelector('.folder-inner-icon');
                if (oldInnerIcon) {
                    oldInnerIcon.remove();
                }

                // Agregar nuevo icono interno si hay icono
                if (icono) {
                    const folderIcon = carpetaElement.querySelector('.folder-icon');
                    if (folderIcon) {
                        folderIcon.classList.add('has-inner-icon');
                        const innerIcon = document.createElement('span');
                        innerIcon.className = 'material-icons folder-inner-icon';
                        innerIcon.textContent = icono;
                        folderIcon.appendChild(innerIcon);
                    }
                } else {
                    const folderIcon = carpetaElement.querySelector('.folder-icon');
                    if (folderIcon) {
                        folderIcon.classList.remove('has-inner-icon');
                    }
                }
                // Guardar el icono en el dataset para persistencia
                carpetaElement.dataset.iconoPersonalizado = icono;
            }
        } else {
            mostrarNotificacion(data.error || 'Error al cambiar icono', 'error');
        }
    } catch (error) {
        console.error('Error aplicando icono:', error);
        mostrarNotificacion('Error al cambiar icono de carpeta', 'error');
    }
}

// -----------------------------------------------------------------------------
// Utilidades
// -----------------------------------------------------------------------------

function _mostrarEsqueleto() {
    const list = document.getElementById('listBody');
    const folders = document.getElementById('foldersBlock');
    const files = document.getElementById('filesBlock');
    let rows = '';
    for (let i = 0; i < 9; i++) {
        rows += '<tr class="gd-skeleton-row">'
              + '<td><div style="display:flex;align-items:center;gap:10px;"><div class="gd-skel gd-skel-ic"></div><div class="gd-skel gd-skel-name"></div></div></td>'
              + '<td><div class="gd-skel gd-skel-sm"></div></td>'
              + '<td><div class="gd-skel gd-skel-sm"></div></td>'
              + '<td><div class="gd-skel gd-skel-sm"></div></td>'
              + '<td></td></tr>';
    }
    if (list) list.innerHTML = rows;
    let cards = '';
    for (let i = 0; i < 8; i++) {
        cards += '<div class="gd-skeleton-card"><div class="gd-skel gd-skel-card"></div><div class="gd-skel gd-skel-name" style="margin-top:8px;"></div></div>';
    }
    if (folders) folders.innerHTML = cards;
    if (files) files.innerHTML = '';
}

function mostrarLoader(show) {
    // Loader amigable: en vez del spinner grande que tapa todo, mostramos
    // esqueletos (placeholders) en el area de archivos.
    const loader = document.getElementById('loader');
    if (loader) loader.style.display = 'none';
    const fc = document.getElementById('filesContainer');
    if (fc) fc.style.display = 'block';
    if (show) { try { _mostrarEsqueleto(); } catch (e) {} }
}

// -----------------------------------------------------------------------------
// Lightbox - Visor de Archivos
// -----------------------------------------------------------------------------

function abrirLightbox(ruta) {
    const archivo = lightboxArchivos.find(a => (a.ruta_completa || a.ruta) === ruta);
    if (!archivo) {
        // Si no se encuentra en la lista, crear objeto temporal
        const nombre = ruta.split('/').pop();
        const ext = nombre.split('.').pop().toLowerCase();
        lightboxArchivoActual = {
            nombre: nombre,
            ruta: ruta,
            ruta_completa: ruta,
            extension: ext,
            tipo: determinarTipo(ext)
        };
        lightboxIndice = -1;
    } else {
        lightboxArchivoActual = archivo;
        lightboxIndice = lightboxArchivos.indexOf(archivo);
    }

    const lightbox = document.getElementById('lightbox');
    const content = document.getElementById('lightboxContent');
    const title = document.getElementById('lightboxTitle');

    title.textContent = lightboxArchivoActual.nombre;
    content.innerHTML = generarContenidoLightbox(lightboxArchivoActual);

    lightbox.classList.add('show');
    actualizarNavegacionLightbox();
    document.body.style.overflow = 'hidden';
}

function determinarTipo(ext) {
    if (EXTENSIONES_IMAGEN.includes(ext)) return 'imagen';
    if (EXTENSIONES_PDF.includes(ext)) return 'pdf';
    if (EXTENSIONES_VIDEO.includes(ext)) return 'video';
    if (EXTENSIONES_OFFICE.includes(ext)) return 'documento';
    if (EXTENSIONES_DRAWIO.includes(ext)) return 'drawio';
    return 'otro';
}

function cerrarLightbox() {
    document.getElementById('lightbox').classList.remove('show');
    document.body.style.overflow = '';
    lightboxArchivoActual = null;
    // Limpiar contenido para detener videos/iframes
    document.getElementById('lightboxContent').innerHTML = '';
}

function generarContenidoLightbox(archivo) {
    const ext = (archivo.extension || archivo.nombre.split('.').pop()).toLowerCase();
    const ruta = archivo.ruta_completa || archivo.ruta;

    // Imágenes - mostrar directamente
    if (EXTENSIONES_IMAGEN.includes(ext)) {
        return `<img src="${API_BASE}/archivos/descargar?ruta=${encodeURIComponent(ruta)}" alt="${archivo.nombre}" onclick="event.stopPropagation();">`;
    }

    // PDF - usar visor nativo del navegador (PDF.js en Firefox/Chrome)
    if (EXTENSIONES_PDF.includes(ext)) {
        return `<iframe src="${API_BASE}/archivos/ver?ruta=${encodeURIComponent(ruta)}"
                        style="width: 100%; height: 100%; border: none; border-radius: 8px; background: white;"
                        onclick="event.stopPropagation();"></iframe>`;
    }

    // Videos
    if (EXTENSIONES_VIDEO.includes(ext)) {
        return `<video controls autoplay onclick="event.stopPropagation();">
            <source src="${API_BASE}/archivos/descargar?ruta=${encodeURIComponent(ruta)}">
            Tu navegador no soporta video HTML5.
        </video>`;
    }

    // Draw.io - mostrar vista previa del diagrama
    if (EXTENSIONES_DRAWIO.includes(ext)) {
        // Cargar preview del diagrama de forma asíncrona
        cargarPreviewDrawio(ruta, archivo.nombre);
        return `
            <div class="drawio-preview-container" onclick="event.stopPropagation();">
                <div class="drawio-loading" id="drawioLoading">
                    <div class="spinner-drawio"></div>
                    <p>Cargando diagrama...</p>
                </div>
                <iframe id="drawioPreviewFrame" style="display:none; width:100%; height:100%; border:none; background:white;"></iframe>
                <div class="drawio-preview-badge">
                    <span class="material-icons">visibility</span>
                    Vista previa
                </div>
            </div>
        `;
    }

    // BPMN - mostrar icono
    if (EXTENSIONES_BPMN.includes(ext)) {
        return `
            <div class="preview-fallback" onclick="event.stopPropagation();">
                <span class="material-icons" style="font-size: 120px; color: #5c6bc0;">account_tree</span>
                <p>${archivo.nombre}</p>
                <p style="color: #aaa; font-size: 14px;">Diagrama BPMN</p>
                <p style="color: #666; font-size: 12px; margin-top: 10px;">
                    Descarga y abre en un editor BPMN
                </p>
            </div>
        `;
    }

    // Office y otros - mostrar preview + mensaje
    const icono = ICONOS[archivo.tipo] || 'insert_drive_file';

    // Solo intentar cargar preview si el archivo tiene preview_url o es un tipo que soporta preview
    const tienePreview = archivo.preview_url || (
        EXTENSIONES_IMAGEN.includes(ext) ||
        EXTENSIONES_PDF.includes(ext) ||
        EXTENSIONES_OFFICE.includes(ext) ||
        EXTENSIONES_VIDEO.includes(ext)
    );

    if (tienePreview) {
        const previewUrl = archivo.preview_url || `${API_BASE}/preview?file=${encodeURIComponent(ruta)}&x=512&y=512`;
        return `
            <div class="preview-fallback" onclick="event.stopPropagation();">
                <img src="${previewUrl}" alt="${archivo.nombre}"
                     onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
                <div style="display:none;">
                    <span class="material-icons">${icono}</span>
                </div>
                <p>${archivo.nombre}</p>
                ${EXTENSIONES_OFFICE.includes(ext) ? '<p style="color: #aaa; font-size: 14px;">Haz clic en <span class="material-icons" style="font-size:16px;vertical-align:middle;">open_in_new</span> para editar en OnlyOffice</p>' : ''}
            </div>
        `;
    }

    // Archivos sin preview - mostrar solo icono
    return `
        <div class="preview-fallback" onclick="event.stopPropagation();">
            <span class="material-icons" style="font-size: 120px; color: #5f6368;">${icono}</span>
            <p>${archivo.nombre}</p>
        </div>
    `;
}

async function cargarPreviewDrawio(ruta, nombre) {
    try {
        // Obtener contenido XML del archivo (con cache-busting)
        const response = await fetch(`${API_BASE}/drawio/contenido?ruta=${encodeURIComponent(ruta)}&_t=${Date.now()}`);
        const data = await response.json();

        if (!data.success || !data.contenido) {
            mostrarErrorDrawioPreview('No se pudo cargar el diagrama');
            return;
        }

        const iframe = document.getElementById('drawioPreviewFrame');
        const loading = document.getElementById('drawioLoading');

        if (!iframe) return;

        // Guardar el contenido para enviarlo cuando el iframe esté listo
        window.drawioPreviewContent = data.contenido;

        // Escuchar mensajes del iframe
        window.drawioMessageHandler = (event) => {
            if (!event.origin.includes('diagrams.net')) return;

            try {
                const msg = JSON.parse(event.data);

                // Verificar que el iframe aún existe
                const currentIframe = document.getElementById('drawioPreviewFrame');
                if (!currentIframe) return;

                if (msg.event === 'init') {
                    // Editor listo, enviar el XML
                    currentIframe.contentWindow.postMessage(JSON.stringify({
                        action: 'load',
                        xml: window.drawioPreviewContent,
                        autosave: 0
                    }), '*');
                } else if (msg.event === 'load') {
                    // Diagrama cargado exitosamente
                    const loadingEl = document.getElementById('drawioLoading');
                    if (loadingEl) loadingEl.style.display = 'none';
                    currentIframe.style.display = 'block';
                }
            } catch (e) {
                // Ignorar errores de parsing silenciosamente
            }
        };

        window.removeEventListener('message', window.drawioMessageHandler);
        window.addEventListener('message', window.drawioMessageHandler);

        // Usar embed.diagrams.net en modo lectura
        // edit=0 para solo lectura, noSaveBtn=1 para ocultar guardar
        iframe.src = 'https://embed.diagrams.net/?embed=1&proto=json&spin=1&edit=0&noSaveBtn=1&noExitBtn=1';

        // Timeout de respaldo - mostrar aunque no reciba eventos
        setTimeout(() => {
            if (loading && loading.style.display !== 'none') {
                loading.style.display = 'none';
                iframe.style.display = 'block';
            }
        }, 8000);

    } catch (error) {
        console.error('[Draw.io Preview] Error:', error);
        mostrarErrorDrawioPreview(error.message);
    }
}

function mostrarErrorDrawioPreview(mensaje) {
    const container = document.querySelector('.drawio-preview-container');
    if (container) {
        container.innerHTML = `
            <div class="preview-fallback" style="text-align:center; color:#666;">
                <span class="material-icons" style="font-size: 120px; color: #F08705;">schema</span>
                <p style="color:white;">Error cargando preview</p>
                <p style="color:#aaa; font-size:14px;">${mensaje}</p>
                <p style="color:#888; font-size:13px; margin-top:20px;">
                    Haz clic en <span class="material-icons" style="font-size:16px;vertical-align:middle;">open_in_new</span> para abrir el editor
                </p>
            </div>
        `;
    }
}

function lightboxAnterior() {
    if (lightboxIndice > 0) {
        lightboxIndice--;
        const archivo = lightboxArchivos[lightboxIndice];
        lightboxArchivoActual = archivo;
        document.getElementById('lightboxTitle').textContent = archivo.nombre;
        document.getElementById('lightboxContent').innerHTML = generarContenidoLightbox(archivo);
        actualizarNavegacionLightbox();
    }
}

function lightboxSiguiente() {
    if (lightboxIndice < lightboxArchivos.length - 1) {
        lightboxIndice++;
        const archivo = lightboxArchivos[lightboxIndice];
        lightboxArchivoActual = archivo;
        document.getElementById('lightboxTitle').textContent = archivo.nombre;
        document.getElementById('lightboxContent').innerHTML = generarContenidoLightbox(archivo);
        actualizarNavegacionLightbox();
    }
}

function actualizarNavegacionLightbox() {
    const btnPrev = document.querySelector('.gd-lightbox-prev');
    const btnNext = document.querySelector('.gd-lightbox-next');

    if (lightboxArchivos.length <= 1 || lightboxIndice < 0) {
        btnPrev.classList.add('hidden');
        btnNext.classList.add('hidden');
    } else {
        btnPrev.classList.remove('hidden');
        btnNext.classList.remove('hidden');
        btnPrev.disabled = lightboxIndice <= 0;
        btnNext.disabled = lightboxIndice >= lightboxArchivos.length - 1;
    }
}

async function lightboxAbrir() {
    if (!lightboxArchivoActual) return;
    const ext = (lightboxArchivoActual.extension || lightboxArchivoActual.nombre.split('.').pop()).toLowerCase();
    const ruta = lightboxArchivoActual.ruta_completa || lightboxArchivoActual.ruta;

    if (EXTENSIONES_OFFICE.includes(ext)) {
        // Abrir editor en nueva pestaña
        _abrirEditorNube(ruta);
    } else if (EXTENSIONES_PDF.includes(ext)) {
        // Abrir PDF en visor nativo del navegador
        window.open(`${API_BASE}/archivos/ver?ruta=${encodeURIComponent(ruta)}`, '_blank');
    } else if (EXTENSIONES_DRAWIO.includes(ext)) {
        // Abrir editor Draw.io embebido en nueva pestaña
        _abrirEditorNube(ruta, 'diagrama');
    } else {
        window.open(`${API_BASE}/archivos/descargar?ruta=${encodeURIComponent(ruta)}`, '_blank');
    }
}

function lightboxDescargar() {
    if (!lightboxArchivoActual) return;
    const ruta = lightboxArchivoActual.ruta_completa || lightboxArchivoActual.ruta;
    window.location.href = `${API_BASE}/archivos/descargar?ruta=${encodeURIComponent(ruta)}`;
}

// Abrir archivo con OnlyOffice (PDFs y documentos Office)
function abrirConOnlyOffice(ruta) {
    _abrirEditorNube(ruta);
}

// Descargar archivo desde cualquier lugar
function descargarArchivo(ruta) {
    window.location.href = `${API_BASE}/archivos/descargar?ruta=${encodeURIComponent(ruta)}`;
}

function lightboxCompartir() {
    if (!lightboxArchivoActual) return;
    // Usar el mismo archivo del lightbox como item seleccionado
    itemSeleccionado = lightboxArchivoActual;
    compartirSeleccionado();
}

function lightboxImprimir() {
    const content = document.getElementById('lightboxContent');
    const img = content.querySelector('img:not(.preview-fallback img)');
    const iframe = content.querySelector('iframe');

    if (img && !content.querySelector('.preview-fallback')) {
        const win = window.open('', '_blank');
        win.document.write(`
            <html><head><title>Imprimir imagen</title></head>
            <body style="margin:0; display:flex; justify-content:center; align-items:center; min-height:100vh;">
                <img src="${img.src}" style="max-width:100%; max-height:100vh;" onload="window.print();">
            </body></html>
        `);
    } else if (iframe) {
        try {
            iframe.contentWindow.print();
        } catch (e) {
            Swal.fire('Imprimir', 'Usa Ctrl+P o el menú del visor de PDF', 'info');
        }
    } else {
        Swal.fire('Imprimir', 'Este tipo de archivo no se puede imprimir directamente. Descárgalo primero.', 'info');
    }
}

// Eventos del lightbox
document.addEventListener('keydown', (e) => {
    const lightbox = document.getElementById('lightbox');
    if (!lightbox || !lightbox.classList.contains('show')) return;

    if (e.key === 'Escape') cerrarLightbox();
    if (e.key === 'ArrowLeft') lightboxAnterior();
    if (e.key === 'ArrowRight') lightboxSiguiente();
});

// Cerrar al hacer clic en el fondo
document.addEventListener('DOMContentLoaded', () => {
    const lightbox = document.getElementById('lightbox');
    if (lightbox) {
        lightbox.addEventListener('click', (e) => {
            if (e.target.id === 'lightbox' || e.target.classList.contains('gd-lightbox-content')) {
                cerrarLightbox();
            }
        });
    }
});

