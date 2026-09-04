// chat-historial-llamadas.js — Historial de llamadas y grabaciones.
// Extraído de chat-page.js (líneas 424-546) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // HISTORIAL DE LLAMADAS (tabla chat_llamadas)
    // ============================================
    async function abrirHistorialLlamadas() {
        let ov = document.getElementById('histLlamadasOverlay');
        if (ov) ov.remove();
        ov = document.createElement('div');
        ov.id = 'histLlamadasOverlay';
        ov.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,.45);z-index:99990;display:flex;align-items:center;justify-content:center;';
        ov.addEventListener('click', (e) => { if (e.target === ov) ov.remove(); });
        ov.innerHTML = `
            <div style="background:var(--bg-color,#fff);color:var(--text-color,#222);width:min(560px,92vw);max-height:80vh;border-radius:14px;display:flex;flex-direction:column;box-shadow:0 12px 40px rgba(0,0,0,.35);overflow:hidden;">
                <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 18px;border-bottom:1px solid rgba(0,0,0,.08);">
                    <div class="btn-group btn-group-sm">
                        <button id="tabLlamadas" class="btn btn-primary" onclick="cambiarTabHistorial('llamadas')"><i class="fas fa-phone me-1"></i>Llamadas</button>
                        <button id="tabGrabaciones" class="btn btn-light" onclick="cambiarTabHistorial('grabaciones')"><i class="fas fa-video me-1"></i>Grabaciones</button>
                    </div>
                    <button class="btn btn-sm btn-light" onclick="document.getElementById('histLlamadasOverlay').remove()"><i class="fas fa-times"></i></button>
                </div>
                <div id="histLlamadasLista" style="overflow-y:auto;padding:6px 0;">
                    <div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm"></div> Cargando…</div>
                </div>
            </div>`;
        document.body.appendChild(ov);

        try {
            const resp = await fetch('/api/chat/llamadas/historial?limit=80', { credentials: 'same-origin' });
            const data = await resp.json();
            renderHistorialLlamadas(data.llamadas || []);
        } catch (e) {
            document.getElementById('histLlamadasLista').innerHTML =
                '<div class="text-center text-muted py-4">No se pudo cargar el historial</div>';
        }
    }

    function renderHistorialLlamadas(llamadas) {
        const cont = document.getElementById('histLlamadasLista');
        if (!cont) return;
        if (!llamadas.length) {
            cont.innerHTML = '<div class="text-center text-muted py-4">Aún no hay llamadas registradas</div>';
            return;
        }
        cont.innerHTML = llamadas.map(l => {
            const esConf = l.tipo === 'conferencia';
            const icono = esConf ? 'fa-users' : (l.tipo === 'video' ? 'fa-video' : 'fa-phone');
            const flecha = l.direccion === 'saliente'
                ? '<i class="fas fa-arrow-up" style="transform:rotate(45deg);color:#28a745;"></i>'
                : '<i class="fas fa-arrow-down" style="transform:rotate(45deg);color:' + (l.perdida ? '#ef4444' : '#0061a1') + ';"></i>';
            let estado = '';
            if (l.estado === 'completada') {
                const m = String(Math.floor(l.duracion_segundos / 60)).padStart(2, '0');
                const sg = String(l.duracion_segundos % 60).padStart(2, '0');
                estado = m + ':' + sg;
            } else if (l.perdida) {
                estado = '<span style="color:#ef4444;font-weight:600;">Perdida</span>';
            } else {
                estado = l.estado === 'rechazada' ? 'No disponible' : 'Sin respuesta';
            }
            const f = l.creado_en ? new Date(l.creado_en) : null;
            const fecha = f ? f.toLocaleDateString('es-EC', { day: '2-digit', month: 'short' }) + ' ' +
                f.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' }) : '';
            const nombre = esConf ? 'Conferencia grupal' : (l.otro && l.otro.nombre ? l.otro.nombre : 'Usuario');
            const puedeLlamar = !esConf && l.otro && l.otro.id;
            const botones = puedeLlamar ? `
                <button class="btn btn-sm btn-light" title="Llamar" onclick="llamarDesdeHistorial(${l.otro.id}, '${(nombre || '').replace(/'/g, "\\'")}', 'audio')"><i class="fas fa-phone" style="color:#28a745;"></i></button>
                <button class="btn btn-sm btn-light" title="Videollamada" onclick="llamarDesdeHistorial(${l.otro.id}, '${(nombre || '').replace(/'/g, "\\'")}', 'video')"><i class="fas fa-video" style="color:#0061a1;"></i></button>` : '';
            return `
                <div style="display:flex;align-items:center;gap:12px;padding:9px 18px;border-bottom:1px solid rgba(0,0,0,.05);">
                    <div style="width:22px;text-align:center;">${flecha}</div>
                    <div style="width:24px;text-align:center;"><i class="fas ${icono}" style="opacity:.6;"></i></div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;${l.perdida ? 'color:#ef4444;' : ''}">${nombre}</div>
                        <div class="small text-muted">${estado} · ${fecha}</div>
                    </div>
                    ${botones}
                </div>`;
        }).join('');
    }

    function cambiarTabHistorial(tab) {
        document.getElementById('tabLlamadas').className = tab === 'llamadas' ? 'btn btn-primary' : 'btn btn-light';
        document.getElementById('tabGrabaciones').className = tab === 'grabaciones' ? 'btn btn-primary' : 'btn btn-light';
        const lista = document.getElementById('histLlamadasLista');
        lista.innerHTML = '<div class="text-center text-muted py-4"><div class="spinner-border spinner-border-sm"></div> Cargando...</div>';
        if (tab === 'llamadas') {
            fetch('/api/chat/llamadas/historial?limit=80', { credentials: 'same-origin' })
                .then(r => r.json()).then(d => renderHistorialLlamadas(d.llamadas || []))
                .catch(() => lista.innerHTML = '<div class="text-center text-muted py-4">Error</div>');
        } else {
            fetch('/api/chat/grabacion/listar', { credentials: 'same-origin' })
                .then(r => r.json()).then(d => renderGrabaciones(d.grabaciones || []))
                .catch(() => lista.innerHTML = '<div class="text-center text-muted py-4">Error</div>');
        }
    }

    function renderGrabaciones(grabs) {
        const cont = document.getElementById('histLlamadasLista');
        if (!grabs.length) { cont.innerHTML = '<div class="text-center text-muted py-4">Aun no hay grabaciones</div>'; return; }
        cont.innerHTML = grabs.map(function(gr) {
            const icono = gr.es_conferencia ? 'fa-users' : 'fa-video';
            const f = gr.creado_en ? new Date(gr.creado_en) : null;
            const fecha = f ? f.toLocaleDateString('es-EC', {day:'2-digit',month:'short'}) + ' ' + f.toLocaleTimeString('es-EC', {hour:'2-digit',minute:'2-digit'}) : '';
            const nombre = gr.es_conferencia ? 'Conferencia' : 'Llamada';
            const listo = gr.estado === 'completada';
            const accion = listo
                ? '<a class="btn btn-sm btn-light" href="/api/chat/grabacion/descargar/' + gr.id + '" title="Descargar"><i class="fas fa-download" style="color:#0061a1;"></i></a>'
                : '<span class="badge bg-danger">grabando</span>';
            return '<div style="display:flex;align-items:center;gap:12px;padding:9px 18px;border-bottom:1px solid rgba(0,0,0,.05);">' +
                '<div style="width:24px;text-align:center;"><i class="fas ' + icono + '" style="opacity:.6;"></i></div>' +
                '<div style="flex:1;min-width:0;"><div style="font-weight:600;">' + nombre + '</div>' +
                '<div class="small text-muted">' + fecha + '</div></div>' + accion + '</div>';
        }).join('');
    }

    function llamarDesdeHistorial(userId, nombre, tipo) {
        const ov = document.getElementById('histLlamadasOverlay');
        if (ov) ov.remove();
        if (typeof iniciarLlamadaWebRTC === 'function') {
            iniciarLlamadaWebRTC(String(userId), String(userId), tipo, nombre, '');
        }
    }

    // Set global para rastrear mensajes ya mostrados (evita duplicados)
