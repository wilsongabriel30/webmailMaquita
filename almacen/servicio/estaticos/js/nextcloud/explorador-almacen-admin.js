// ============================================================================
// el sistema central — Almacén Maquita: PANEL DE CONFIGURACIÓN / ADMINISTRACIÓN (solo master)
// Se carga SOLO en modo Almacén. Da al master la recuperación global:
// ver la papelera y la retención (papelera vaciada, 90 días) de CUALQUIER
// persona y restaurar en minutos. Usa los endpoints /api/almacen/admin/*.
// ============================================================================

function _soloAlmacen() { return typeof MODO_ALMACEN !== 'undefined' && MODO_ALMACEN; }

// Abre el panel principal de configuración/administración
async function abrirConfigAlmacen() {
    if (!_soloAlmacen()) return;
    Swal.fire({
        title: '⚙️ Configuración del Almacén',
        html: `
            <style>
              .alm-menu-btn{display:flex;align-items:center;gap:12px;width:100%;padding:12px 14px;
                border:none;border-bottom:1px solid #ececec;background:#fff;color:#3c4043;
                font-size:.95rem;font-family:Roboto,Arial,sans-serif;cursor:pointer;text-align:left;
                border-radius:0;transition:background .12s}
              .alm-menu-btn:hover{background:#f5f6f7}
              .alm-menu-btn:last-child{border-bottom:none}
              .alm-menu-btn .material-icons{font-size:20px;color:#5f6368}
            </style>
            <p style="color:#5f6368;font-size:.9rem;margin:0 0 10px">
                Herramientas de administración (solo master).
            </p>
            <div style="display:flex;flex-direction:column;gap:2px;text-align:left">
                <button class="alm-menu-btn" onclick="Swal.close(); abrirRecuperacionAlmacen();"><span class="material-icons">restore</span> Recuperar archivos de un usuario</button>
                <button class="alm-menu-btn" onclick="Swal.close(); abrirAlmacenamiento();"><span class="material-icons">storage</span> Almacenamiento — dónde se guardan los archivos</button>
                <button class="alm-menu-btn" onclick="Swal.close(); abrirActividad();"><span class="material-icons">schedule</span> Actividad reciente</button>
                <button class="alm-menu-btn" onclick="Swal.close(); abrirCuotas();"><span class="material-icons">person</span> Espacio de usuarios (cuotas)</button>
                <button class="alm-menu-btn" onclick="Swal.close(); abrirUnidades();"><span class="material-icons">groups</span> Unidades compartidas (equipos)</button>
                <button class="alm-menu-btn" onclick="Swal.close(); abrirCuotaAlmacen();"><span class="material-icons">pie_chart</span> Ver almacenamiento (mi cuenta)</button>
            </div>`,
        showConfirmButton: false,
        showCloseButton: true,
        width: 460,
    });
}

// --- Recuperación de archivos de cualquier usuario (papelera + retención) ---
async function abrirRecuperacionAlmacen() {
    const { value: consulta } = await Swal.fire({
        title: '♻️ Recuperar archivos',
        input: 'text',
        inputLabel: '¿De qué persona? (nombre o usuario)',
        inputPlaceholder: 'Ej: maria, jose...',
        showCancelButton: true,
        confirmButtonText: 'Buscar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#3c4043',
    });
    if (!consulta || consulta.trim().length < 2) return;

    let usuarios = [];
    try {
        const r = await fetch(`/api/almacen/admin/usuarios?q=${encodeURIComponent(consulta.trim())}`);
        usuarios = (await r.json()).usuarios || [];
    } catch (e) { /* cae abajo */ }
    if (!usuarios.length) {
        Swal.fire({ icon: 'info', title: 'Sin resultados', text: 'No se encontró a esa persona.' });
        return;
    }

    const opciones = {};
    usuarios.forEach(u => { opciones[u.id] = `${u.nombre} (${u.username})`; });
    const { value: uid } = await Swal.fire({
        title: 'Elige la persona',
        input: 'select', inputOptions: opciones,
        inputPlaceholder: 'Selecciona...',
        showCancelButton: true, confirmButtonText: 'Ver archivos borrados',
        confirmButtonColor: '#3c4043',
    });
    if (!uid) return;
    verBorradosUsuario(parseInt(uid), opciones[uid]);
}

// Lista lo recuperable de un usuario: papelera (aún recuperable por él) + retención (vació la papelera)
async function verBorradosUsuario(uid, etiqueta) {
    Swal.fire({ title: 'Cargando...', didOpen: () => Swal.showLoading(), allowOutsideClick: false });
    let papelera = [], retencion = [];
    try {
        const [rp, rr] = await Promise.all([
            fetch(`/api/almacen/admin/papelera?usuario_id=${uid}`).then(r => r.json()),
            fetch(`/api/almacen/admin/retencion?usuario_id=${uid}`).then(r => r.json()),
        ]);
        papelera = rp.archivos || [];
        retencion = rr.elementos || [];
    } catch (e) {
        Swal.fire({ icon: 'error', title: 'Error', text: 'No se pudieron cargar los archivos borrados.' });
        return;
    }

    const esc = t => String(t == null ? '' : t).replace(/</g, '&lt;');
    const filaPap = it => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;border-bottom:1px solid #eee">
            <span>🗑️ ${esc(it.nombre)}</span>
            <button class="swal2-styled" style="margin:0;padding:4px 10px;font-size:.8rem;background:#3c4043"
                onclick="restaurarItemAlmacen('papelera', ${uid}, '${esc(it.ruta)}')">Restaurar</button>
        </div>`;
    const filaRet = it => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;border-bottom:1px solid #eee">
            <span>♻️ ${esc(it.nombre)} <small style="color:#999">(${it.dias_restantes}d)</small></span>
            <button class="swal2-styled" style="margin:0;padding:4px 10px;font-size:.8rem;background:#3c4043"
                onclick="restaurarItemAlmacen('retencion', ${uid}, '${esc(it.ruta)}')">Recuperar</button>
        </div>`;

    let html = `<div style="text-align:left;max-height:360px;overflow:auto">`;
    html += `<div style="font-weight:600;margin:4px 0">En su papelera (${papelera.length})</div>`;
    html += papelera.length ? papelera.map(filaPap).join('') : '<div style="color:#999;padding:6px">Vacía</div>';
    html += `<div style="font-weight:600;margin:12px 0 4px">Retención — vació su papelera (${retencion.length}, hasta 90 días)</div>`;
    html += retencion.length ? retencion.map(filaRet).join('') : '<div style="color:#999;padding:6px">Nada retenido</div>';
    html += `</div>`;

    Swal.fire({ title: `Archivos borrados de ${esc(etiqueta)}`, html, width: 560,
                showConfirmButton: false, showCloseButton: true });
}

// Restaura un item (de papelera o retención) a la unidad del dueño
async function restaurarItemAlmacen(origen, uid, ruta) {
    const url = origen === 'retencion'
        ? '/api/almacen/admin/retencion/restaurar'
        : '/api/almacen/admin/restaurar';
    try {
        const r = await fetch(url, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usuario_id: uid, ruta })
        });
        const d = await r.json();
        if (d.success) {
            Swal.fire({ icon: 'success', title: 'Recuperado', text: d.message || 'Devuelto a su unidad.',
                        confirmButtonColor: '#3c4043' });
        } else {
            Swal.fire({ icon: 'error', title: 'No se pudo', text: d.error || 'Error' });
        }
    } catch (e) {
        Swal.fire({ icon: 'error', title: 'Error de conexión' });
    }
}

// Utilidad simple: cuota propia
async function abrirCuotaAlmacen() {
    try {
        const d = await (await fetch('/api/almacen/cuota')).json();
        Swal.fire({ title: '📊 Mi almacenamiento',
            html: `<div style="text-align:left">Usado: <b>${d.usado_humano}</b><br>Total: <b>${d.total_humano}</b><br>Libre: <b>${(d.libre/1073741824).toFixed(2)} GB</b><br>Uso: <b>${d.porcentaje}%</b></div>`,
            confirmButtonColor: '#3c4043' });
    } catch (e) { Swal.fire({ icon: 'error', title: 'Error' }); }
}

// ============================================================================
// ALMACENAMIENTO — elegir/conectar dónde se guardan los archivos (solo master)
// ============================================================================
async function abrirAlmacenamiento() {
    Swal.fire({ title: 'Cargando...', didOpen: () => Swal.showLoading(), allowOutsideClick: false });
    let info;
    try {
        info = await (await fetch('/api/almacen/admin/almacenamiento')).json();
    } catch (e) {
        Swal.fire({ icon: 'error', title: 'Error', text: 'No se pudo leer el almacenamiento.' });
        return;
    }
    const esc = t => String(t == null ? '' : t).replace(/</g, '&lt;');
    const a = info.actual || {};
    const uh = a.uso_humano || {};

    // Discos ya conectados donde se puede cambiar
    const cand = (info.candidatos || []).filter(c => c.escribible);
    const opciones = cand.map(c =>
        `<option value="${esc(c.ruta)}">${esc(c.ruta)} — libre ${esc(c.libre_humano)} de ${esc(c.total_humano)} (${esc(c.tipo)})</option>`
    ).join('');

    const html = `
        <div style="text-align:left">
            <div style="background:#e8f0fe;border-radius:8px;padding:10px;margin-bottom:12px">
                <b>Guardando ahora en:</b><br>
                <code style="font-size:.85rem">${esc(a.ruta_actual || '')}</code><br>
                ${uh.total ? `<small>Libre ${esc(uh.libre)} de ${esc(uh.total)}</small>` : ''}
            </div>

            <b>1) Cambiar a un disco YA conectado</b>
            <div style="display:flex;gap:8px;margin:6px 0 14px">
                <select id="almDestino" class="swal2-select" style="margin:0;flex:1">
                    <option value="">— elige un destino —</option>${opciones}
                </select>
                <button class="swal2-styled" style="margin:0;background:#3c4043"
                        onclick="usarDestinoAlmacen()">Usar</button>
            </div>

            <b>2) Conectar un almacenamiento nuevo</b>
            <select id="almTipo" class="swal2-select" style="margin:6px 0" onchange="camposConexionAlm()">
                <option value="">— tipo —</option>
                <option value="usb">💽 Disco USB</option>
                <option value="local">🗂️ Carpeta local / disco de la VM</option>
                <option value="nfs">🌐 Red NFS (Linux/NAS)</option>
                <option value="smb">🪟 Red SMB / Windows / NAS</option>
                <option value="nas">📦 NAS (guía)</option>
                <option value="nube">☁️ Nube (Google Drive / OneDrive, vía rclone)</option>
            </select>
            <div id="almCampos"></div>
            <button class="swal2-styled" style="margin:8px 0 0;background:#1a73e8"
                    onclick="generarComandoAlm()">Generar instrucción</button>
            <pre id="almComando" style="display:none;white-space:pre-wrap;background:#202124;color:#e8eaed;
                 padding:10px;border-radius:8px;font-size:.78rem;margin-top:10px"></pre>
        </div>`;
    Swal.fire({ title: '💾 Almacenamiento', html, width: 620,
                showConfirmButton: false, showCloseButton: true });
}

function camposConexionAlm() {
    const tipo = document.getElementById('almTipo').value;
    const box = document.getElementById('almCampos');
    const inp = (id, ph) => `<input id="${id}" class="swal2-input" style="margin:4px 0" placeholder="${ph}">`;
    if (tipo === 'nfs') box.innerHTML = inp('almServidor', 'IP del servidor/NAS') + inp('almExport', 'Carpeta exportada (/export/almacen)');
    else if (tipo === 'smb') box.innerHTML = inp('almServidor', 'IP del servidor/NAS') + inp('almCarpeta', 'Carpeta compartida') + inp('almUsuario', 'Usuario');
    else if (tipo === 'nube') box.innerHTML = inp('almRemoto', 'Nombre del remoto rclone (ej: drive)');
    else if (tipo === 'local') box.innerHTML = inp('almRuta', 'Ruta del disco (/mnt/midisco)');
    else box.innerHTML = '';
}

async function generarComandoAlm() {
    const tipo = document.getElementById('almTipo').value;
    if (!tipo) { Swal.showValidationMessage && Swal.showValidationMessage('Elige un tipo'); return; }
    const val = id => (document.getElementById(id) || {}).value || '';
    const body = { tipo, servidor: val('almServidor'), export: val('almExport'),
                   carpeta: val('almCarpeta'), usuario: val('almUsuario'),
                   remoto: val('almRemoto'), ruta: val('almRuta') };
    try {
        const d = await (await fetch('/api/almacen/admin/almacenamiento/comando', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)
        })).json();
        const pre = document.getElementById('almComando');
        pre.textContent = (d.comando || 'Sin comando') +
            '\n\n➡️ Ejecuta esto UNA vez (con un administrador). Luego el destino aparecerá en la lista de arriba para elegirlo.';
        pre.style.display = 'block';
    } catch (e) { /* noop */ }
}

async function usarDestinoAlmacen() {
    const ruta = document.getElementById('almDestino').value;
    if (!ruta) return;
    try {
        const d = await (await fetch('/api/almacen/admin/almacenamiento/usar', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ruta })
        })).json();
        if (d.success) {
            Swal.fire({ icon: 'success', title: 'Destino cambiado', text: d.message, confirmButtonColor: '#3c4043' });
        } else {
            Swal.fire({ icon: 'error', title: 'No se pudo', text: d.error || 'Error' });
        }
    } catch (e) { Swal.fire({ icon: 'error', title: 'Error de conexión' }); }
}

// ============================================================================
// ACTIVIDAD RECIENTE + COMENTARIOS (colaboración estilo Drive) — 2026-07-03
// ============================================================================
function _escAlm(t) { return String(t == null ? '' : t).replace(/</g, '&lt;'); }
function _hace(iso) {
    const seg = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (seg < 60) return 'hace un momento';
    if (seg < 3600) return 'hace ' + Math.floor(seg / 60) + ' min';
    if (seg < 86400) return 'hace ' + Math.floor(seg / 3600) + ' h';
    return 'hace ' + Math.floor(seg / 86400) + ' días';
}

// Mi actividad reciente (desde Configuración)
async function abrirActividad() {
    Swal.fire({ title: 'Cargando...', didOpen: () => Swal.showLoading(), allowOutsideClick: false });
    let items = [];
    try { items = (await (await fetch('/api/almacen/actividad')).json()).actividad || []; }
    catch (e) { Swal.fire({ icon: 'error', title: 'Error' }); return; }
    const html = items.length
        ? '<div style="text-align:left;max-height:420px;overflow:auto">' + items.map(a =>
            `<div style="display:flex;justify-content:space-between;align-items:center;padding:8px 4px;border-bottom:1px solid #eee;font-size:.87rem">
                <div>
                    <b>${_escAlm(a.usuario)}</b> ${_escAlm(a.accion_texto)}
                    <span style="color:#5f6368">${_escAlm((a.ruta || '').split('/').pop())}</span><br>
                    <small style="color:#9aa0a6">${_hace(a.creado_en)}</small>
                </div>
                ${['elimino','movio','renombro'].includes(a.accion)
                    ? `<button onclick="deshacerActividad(${a.id})" style="padding:4px 10px;border:1px solid #dadce0;background:#fff;border-radius:6px;cursor:pointer;font-size:.8rem;white-space:nowrap">↺ Deshacer</button>`
                    : ''}
            </div>`).join('') + '</div>'
        : '<div style="color:#999;padding:20px">Sin actividad todavía</div>';
    Swal.fire({ title: '🕒 Actividad reciente', html, width: 560,
                showConfirmButton: false, showCloseButton: true });
}

// Comentarios de un archivo/carpeta (desde el menú contextual)
async function comentariosItem() {
    document.getElementById('contextMenu')?.classList.remove('show');
    if (typeof cerrarSubmenus === 'function') cerrarSubmenus();
    if (typeof itemSeleccionado === 'undefined' || !itemSeleccionado) return;
    const ruta = itemSeleccionado.ruta;
    await pintarComentarios(ruta, itemSeleccionado.nombre);
}

async function pintarComentarios(ruta, nombre) {
    let lista = [];
    try { lista = (await (await fetch('/api/almacen/archivos/comentarios?ruta=' + encodeURIComponent(ruta))).json()).comentarios || []; }
    catch (e) { /* noop */ }
    const filas = lista.length
        ? lista.map(c => `
            <div style="padding:7px 4px;border-bottom:1px solid #eee;font-size:.87rem">
                <b>${_escAlm(c.usuario)}</b> <small style="color:#9aa0a6">${_hace(c.creado_en)}</small><br>
                ${_escAlm(c.texto)}
            </div>`).join('')
        : '<div style="color:#999;padding:10px">Aún no hay comentarios</div>';
    const { value: texto } = await Swal.fire({
        title: '💬 Comentarios — ' + _escAlm(nombre),
        html: `<div style="text-align:left;max-height:300px;overflow:auto;margin-bottom:10px">${filas}</div>
               <textarea id="nuevoComentario" class="swal2-textarea" placeholder="Escribe un comentario..."></textarea>`,
        width: 560, showCancelButton: true, confirmButtonText: 'Comentar', cancelButtonText: 'Cerrar',
        confirmButtonColor: '#3c4043',
        preConfirm: () => document.getElementById('nuevoComentario').value.trim()
    });
    if (texto) {
        try {
            const r = await fetch('/api/almacen/archivos/comentarios', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ruta, texto })
            });
            if ((await r.json()).success) { pintarComentarios(ruta, nombre); }  // recargar
        } catch (e) { /* noop */ }
    }
}

// ============================================================================
// CUOTAS POR USUARIO — panel minimalista estilo Google (sin colores) — 2026-07-03
// ============================================================================
async function abrirCuotas() {
    let def = 20;
    try { def = (await (await fetch('/api/almacen/admin/cuota-defecto')).json()).gb || 20; } catch (e) {}
    const html = `
        <div style="text-align:left;font-family:Roboto,Arial,sans-serif;color:#202124">
            <div style="font-size:.85rem;color:#5f6368;margin-bottom:14px">
                Asigna el espacio en la nube de cada persona. Por defecto ${def} GB.
            </div>
            <div style="border:1px solid #dadce0;border-radius:8px;padding:12px;margin-bottom:14px">
                <div style="font-weight:500;margin-bottom:6px">Cuota por defecto</div>
                <div style="display:flex;gap:8px;align-items:center">
                    <input id="qDef" type="number" min="1" value="${def}"
                        style="width:90px;padding:6px 8px;border:1px solid #dadce0;border-radius:6px">
                    <span style="color:#5f6368">GB</span>
                    <button onclick="guardarCuotaDefecto()"
                        style="margin-left:auto;padding:6px 14px;border:none;background:#3c4043;color:#fff;border-radius:6px;cursor:pointer">Guardar</button>
                </div>
            </div>
            <div style="font-weight:500;margin-bottom:6px">Espacio de una persona</div>
            <input id="qBuscar" placeholder="Buscar por nombre o usuario..." autocomplete="off"
                style="width:100%;padding:8px;border:1px solid #dadce0;border-radius:6px;margin-bottom:6px">
            <div id="qResultados"></div>
            <div id="qDetalle" style="margin-top:10px"></div>
        </div>`;
    Swal.fire({ title: 'Espacio de usuarios', html, width: 560, background: '#fff',
                showConfirmButton: false, showCloseButton: true,
                didOpen: () => {
                    const inp = document.getElementById('qBuscar'); let t = null;
                    inp.addEventListener('input', () => { clearTimeout(t); t = setTimeout(() => buscarUsuarioCuota(inp.value), 250); });
                } });
}

async function buscarUsuarioCuota(q) {
    const box = document.getElementById('qResultados');
    if (!q || q.trim().length < 2) { box.innerHTML = ''; return; }
    try {
        const d = await (await fetch('/api/almacen/admin/usuarios?q=' + encodeURIComponent(q.trim()))).json();
        const esc = t => String(t || '').replace(/</g, '&lt;');
        box.innerHTML = (d.usuarios || []).map(u =>
            `<div onclick="verCuotaUsuario(${u.id}, '${esc(u.nombre)}')"
                style="padding:8px 10px;border-radius:6px;cursor:pointer"
                onmouseover="this.style.background='#f1f3f4'" onmouseout="this.style.background=''">
                ${esc(u.nombre)} <span style="color:#80868b;font-size:.85rem">${esc(u.username)}</span>
            </div>`).join('') || '<div style="color:#80868b;padding:6px">Sin resultados</div>';
    } catch (e) {}
}

async function verCuotaUsuario(uid, nombre) {
    document.getElementById('qResultados').innerHTML = '';
    document.getElementById('qBuscar').value = nombre;
    const det = document.getElementById('qDetalle');
    det.innerHTML = 'Cargando...';
    try {
        const d = await (await fetch('/api/almacen/admin/cuota/' + uid)).json();
        det.innerHTML = `
            <div style="border:1px solid #dadce0;border-radius:8px;padding:12px">
                <div style="font-weight:500">${String(nombre).replace(/</g,'&lt;')}</div>
                <div style="font-size:.85rem;color:#5f6368;margin:4px 0 10px">
                    Usa <b>${d.usado_gb} GB</b> de ${d.limite_gb} GB (${d.porcentaje}%)
                    ${d.tiene_cuota_propia ? '· cuota propia' : '· por defecto'}
                </div>
                <div style="display:flex;gap:8px;align-items:center">
                    <input id="qGb" type="number" min="0" value="${d.limite_gb}"
                        style="width:90px;padding:6px 8px;border:1px solid #dadce0;border-radius:6px">
                    <span style="color:#5f6368">GB</span>
                    <button onclick="guardarCuotaUsuario(${uid})"
                        style="padding:6px 14px;border:none;background:#3c4043;color:#fff;border-radius:6px;cursor:pointer">Asignar</button>
                    <button onclick="document.getElementById('qGb').value=0; guardarCuotaUsuario(${uid})"
                        style="padding:6px 10px;border:1px solid #dadce0;background:#fff;border-radius:6px;cursor:pointer">Usar defecto</button>
                </div>
            </div>`;
    } catch (e) { det.innerHTML = '<span style="color:#d33">Error</span>'; }
}

async function guardarCuotaUsuario(uid) {
    const gb = parseFloat(document.getElementById('qGb').value) || 0;
    try {
        const d = await (await fetch('/api/almacen/admin/cuota', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usuario_id: uid, gb })
        })).json();
        if (d.success) Swal.fire({ icon: 'success', title: 'Guardado', text: d.message || (gb + ' GB asignados'), confirmButtonColor: '#3c4043' });
    } catch (e) {}
}

async function guardarCuotaDefecto() {
    const gb = parseFloat(document.getElementById('qDef').value) || 0;
    if (gb <= 0) return;
    try {
        const d = await (await fetch('/api/almacen/admin/cuota-defecto', {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ gb })
        })).json();
        if (d.success) Swal.fire({ icon: 'success', title: 'Cuota por defecto: ' + gb + ' GB', confirmButtonColor: '#3c4043' });
    } catch (e) {}
}

// ============================================================================
// UNIDADES COMPARTIDAS — crear y gestionar equipos/miembros — 2026-07-03
// ============================================================================
async function abrirUnidades() {
    let unidades = [];
    try { unidades = (await (await fetch('/api/almacen/unidades')).json()).unidades || []; } catch (e) {}
    const esc = t => String(t || '').replace(/</g, '&lt;');
    const filas = unidades.length ? unidades.map(u => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:8px 10px;border-bottom:1px solid #eee">
            <span onclick="window.location.href='/archivos-almacen/unidades/${u.id}'" style="cursor:pointer">
                👥 ${esc(u.nombre)} <small style="color:#80868b">(${u.miembros} miembros · ${esc(u.mi_rol)})</small>
            </span>
            <button onclick="gestionarMiembros(${u.id}, '${esc(u.nombre)}')"
                style="padding:4px 10px;border:1px solid #dadce0;background:#fff;border-radius:6px;cursor:pointer">Miembros</button>
        </div>`).join('') : '<div style="color:#80868b;padding:8px">Aún no hay unidades compartidas</div>';
    Swal.fire({
        title: 'Unidades compartidas', width: 560, background: '#fff',
        html: `<div style="text-align:left">
                 <div style="font-size:.85rem;color:#5f6368;margin-bottom:10px">Drives de equipo (propiedad de la organización).</div>
                 <div style="max-height:280px;overflow:auto">${filas}</div>
                 <button onclick="crearUnidad()" style="margin-top:12px;padding:8px 14px;border:none;background:#3c4043;color:#fff;border-radius:6px;cursor:pointer">➕ Nueva unidad</button>
               </div>`,
        showConfirmButton: false, showCloseButton: true,
    });
}

async function crearUnidad() {
    const { value: nombre } = await Swal.fire({
        title: 'Nueva unidad compartida', input: 'text', inputPlaceholder: 'Ej: Contabilidad',
        showCancelButton: true, confirmButtonText: 'Crear', confirmButtonColor: '#3c4043'
    });
    if (!nombre) return;
    try {
        const d = await (await fetch('/api/almacen/unidades', {
            method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nombre })
        })).json();
        if (d.success) { Swal.fire({ icon: 'success', title: 'Unidad creada', confirmButtonColor: '#3c4043' }).then(abrirUnidades); }
        else Swal.fire({ icon: 'error', title: 'No se pudo', text: d.error || '' });
    } catch (e) {}
}

async function gestionarMiembros(unidadId, nombre) {
    let miembros = [];
    try { miembros = (await (await fetch(`/api/almacen/unidades/${unidadId}/miembros`)).json()).miembros || []; } catch (e) {}
    const esc = t => String(t || '').replace(/</g, '&lt;');
    const lista = miembros.map(m => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:6px 8px;border-bottom:1px solid #eee">
            <span>${esc(m.nombre)} <small style="color:#80868b">${esc(m.rol)}</small></span>
            <button onclick="quitarMiembro(${unidadId}, ${m.usuario_id}, '${esc(nombre)}')"
                style="border:none;background:none;color:#d33;cursor:pointer">Quitar</button>
        </div>`).join('') || '<div style="color:#80868b;padding:6px">Sin miembros</div>';
    Swal.fire({
        title: 'Miembros — ' + esc(nombre), width: 560, background: '#fff',
        html: `<div style="text-align:left">
                 <div style="max-height:220px;overflow:auto">${lista}</div>
                 <hr style="margin:10px 0">
                 <div style="font-weight:500;margin-bottom:6px">Agregar persona</div>
                 <input id="mBuscar" placeholder="Buscar..." autocomplete="off" style="width:100%;padding:8px;border:1px solid #dadce0;border-radius:6px">
                 <div id="mRes"></div>
                 <select id="mRol" style="margin-top:8px;padding:6px;border:1px solid #dadce0;border-radius:6px">
                    <option value="viewer">Solo ver</option>
                    <option value="editor" selected>Editor (subir/editar/borrar)</option>
                    <option value="manager">Manager (gestiona miembros)</option>
                 </select>
                 <input type="hidden" id="mElegido">
               </div>`,
        showConfirmButton: false, showCloseButton: true,
        didOpen: () => {
            const inp = document.getElementById('mBuscar'); let t = null;
            inp.addEventListener('input', () => { clearTimeout(t); t = setTimeout(async () => {
                const q = inp.value.trim(); const box = document.getElementById('mRes');
                if (q.length < 2) { box.innerHTML = ''; return; }
                try {
                    const d = await (await fetch('/api/almacen/admin/usuarios?q=' + encodeURIComponent(q))).json();
                    box.innerHTML = (d.usuarios || []).map(u =>
                        `<div onclick="document.getElementById('mElegido').value=${u.id};agregarMiembro(${unidadId},'${esc(nombre)}')"
                            style="padding:6px 8px;border-radius:6px;cursor:pointer" onmouseover="this.style.background='#f1f3f4'" onmouseout="this.style.background=''">
                            ${esc(u.nombre)} <small style="color:#80868b">${esc(u.username)}</small></div>`).join('');
                } catch (e) {}
            }, 250); });
        }
    });
}

async function agregarMiembro(unidadId, nombre) {
    const uid = document.getElementById('mElegido').value;
    const rol = document.getElementById('mRol').value;
    if (!uid) return;
    try {
        await fetch(`/api/almacen/unidades/${unidadId}/miembros`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ usuario_id: parseInt(uid), rol })
        });
        gestionarMiembros(unidadId, nombre);  // recargar
    } catch (e) {}
}

async function quitarMiembro(unidadId, miembroId, nombre) {
    try {
        await fetch(`/api/almacen/unidades/${unidadId}/miembros/${miembroId}`, { method: 'DELETE' });
        gestionarMiembros(unidadId, nombre);
    } catch (e) {}
}

// ============================================================================
// HISTORIAL DE VERSIONES — ver, restaurar y fijar versiones de un archivo
// ============================================================================
async function versionesItem() {
    document.getElementById('contextMenu')?.classList.remove('show');
    if (typeof cerrarSubmenus === 'function') cerrarSubmenus();
    if (typeof itemSeleccionado === 'undefined' || !itemSeleccionado) return;
    if (itemSeleccionado.es_carpeta) { mostrarNotificacion('Las versiones aplican a archivos, no a carpetas', 'info'); return; }
    await pintarVersiones(itemSeleccionado.id, itemSeleccionado.nombre);
}
async function pintarVersiones(fileId, nombre) {
    let lista = [];
    try { lista = (await (await fetch('/api/almacen/versiones/' + encodeURIComponent(fileId))).json()).versiones || []; } catch (e) {}
    const esc = t => String(t == null ? '' : t).replace(/</g, '&lt;');
    const filas = lista.length ? lista.map((v, i) => `
        <div style="display:flex;justify-content:space-between;align-items:center;padding:9px 6px;border-bottom:1px solid #ececec">
            <div style="font-size:.88rem">Versión ${lista.length - i}${v.guardar_siempre ? ' <span style=\'color:#5f6368;font-size:.78rem\'>· fijada</span>' : ''}<br><small style="color:#80868b">${_hace(v.creado_en)} · ${esc(v.tamano_humano)}</small></div>
            <div style="display:flex;gap:6px">
                <button onclick="fijarVersion('${esc(fileId)}', ${v.version_id}, ${!v.guardar_siempre}, '${esc(nombre)}')" style="padding:4px 8px;border:1px solid #dadce0;background:#fff;border-radius:6px;cursor:pointer;font-size:.8rem">${v.guardar_siempre ? 'No fijar' : 'Mantener'}</button>
                <button onclick="restaurarVersion('${esc(fileId)}', ${v.version_id}, '${esc(nombre)}')" style="padding:4px 10px;border:none;background:#3c4043;color:#fff;border-radius:6px;cursor:pointer;font-size:.8rem">Restaurar</button>
            </div>
        </div>`).join('') : '<div style="color:#80868b;padding:14px;text-align:center">Sin versiones anteriores.<br><small>Se crea una versión cada vez que subes un archivo con el mismo nombre.</small></div>';
    Swal.fire({ title: 'Historial — ' + esc(nombre), width: 560, background: '#fff', html: `<div style="text-align:left;max-height:400px;overflow:auto">${filas}</div>`, showConfirmButton: false, showCloseButton: true });
}
async function restaurarVersion(fileId, versionId, nombre) {
    try {
        const d = await (await fetch('/api/almacen/versiones/' + encodeURIComponent(fileId) + '/restaurar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId }) })).json();
        if (d.success) { Swal.fire({ icon: 'success', title: 'Versión restaurada', text: 'Se guardó también la versión actual, por si acaso.', confirmButtonColor: '#3c4043' }).then(() => { if (typeof cargarArchivos === 'function') cargarArchivos(rutaActual); }); }
        else Swal.fire({ icon: 'error', title: 'No se pudo', text: d.error || '' });
    } catch (e) { Swal.fire({ icon: 'error', title: 'Error de conexión' }); }
}
async function fijarVersion(fileId, versionId, fijar, nombre) {
    try { await fetch('/api/almacen/versiones/' + encodeURIComponent(fileId) + '/fijar', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version_id: versionId, fijar }) }); pintarVersiones(fileId, nombre); } catch (e) {}
}


// ============================================================================
// COMPARTIR CON UNA PERSONA POR CORREO (interno o EXTERNO) — solo lectura v1
// Genera un enlace con clave y expiración opcionales, listo para enviar.
// ============================================================================
async function compartirCorreoItem() {
    document.getElementById('contextMenu')?.classList.remove('show');
    if (typeof cerrarSubmenus === 'function') cerrarSubmenus();
    if (typeof itemSeleccionado === 'undefined' || !itemSeleccionado) return;
    const nombre = itemSeleccionado.nombre;
    const cfg = await Swal.fire({
        title: 'Compartir con una persona',
        width: 460, background: '#fff',
        html: `
            <div style="text-align:left;font-family:Roboto,Arial,sans-serif;color:#3c4043">
                <div style="font-size:.85rem;color:#5f6368;margin-bottom:10px">Comparte <b>${String(nombre).replace(/</g,'&lt;')}</b> con cualquier correo (interno o externo). Recibe un enlace de solo lectura.</div>
                <input id="shEmail" type="email" placeholder="correo@ejemplo.com"
                    style="width:100%;padding:8px;border:1px solid #dadce0;border-radius:6px;margin-bottom:8px;box-sizing:border-box">
                <div style="display:flex;gap:8px;margin-bottom:8px">
                    <input id="shDias" type="number" min="0" value="0" placeholder="Días"
                        style="width:90px;padding:8px;border:1px solid #dadce0;border-radius:6px">
                    <span style="align-self:center;color:#5f6368;font-size:.85rem">días para expirar (0 = nunca)</span>
                </div>
                <input id="shClave" type="text" placeholder="Clave de acceso (opcional)"
                    style="width:100%;padding:8px;border:1px solid #dadce0;border-radius:6px;box-sizing:border-box">
                <div style="font-size:.78rem;color:#9aa0a6;margin-top:8px">La edición online (Word/Excel) llegará con OnlyOffice; por ahora el enlace es de lectura/descarga.</div>
            </div>`,
        showCancelButton: true, confirmButtonText: 'Generar enlace', cancelButtonText: 'Cancelar',
        confirmButtonColor: '#3c4043',
        preConfirm: () => ({
            email: (document.getElementById('shEmail').value || '').trim(),
            expira_dias: parseInt(document.getElementById('shDias').value) || 0,
            clave: document.getElementById('shClave').value || ''
        })
    });
    if (!cfg.isConfirmed) return;
    const v = cfg.value;
    if (!v.email) { Swal.fire({ icon: 'warning', title: 'Falta el correo' }); return; }
    try {
        const d = await (await fetch(`${API_BASE}/compartir`, {
            method: 'POST', headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ruta: itemSeleccionado.ruta, tipo: 3, permisos: 1,
                                   email: v.email, rol: 'lector', expira_dias: v.expira_dias, clave: v.clave })
        })).json();
        if (!d.success || !d.compartido) { Swal.fire({ icon: 'error', title: 'No se pudo', text: d.error || '' }); return; }
        const url = d.compartido.url;
        await Swal.fire({
            title: 'Enlace listo', width: 520, background: '#fff', icon: 'success', iconColor: '#3c4043',
            html: `<div style="text-align:left;font-size:.9rem">
                     Envía este enlace a <b>${v.email.replace(/</g,'&lt;')}</b>:
                     <div style="display:flex;gap:6px;margin-top:8px">
                       <input id="shUrl" value="${url}" readonly style="flex:1;padding:8px;border:1px solid #dadce0;border-radius:6px">
                       <button onclick="navigator.clipboard.writeText(document.getElementById('shUrl').value); this.textContent='Copiado'" style="padding:8px 12px;border:1px solid #dadce0;background:#fff;border-radius:6px;cursor:pointer">Copiar</button>
                     </div>
                     ${v.clave ? '<div style="color:#5f6368;margin-top:8px">Clave: <b>'+v.clave.replace(/</g,'&lt;')+'</b> (compártela aparte)</div>' : ''}
                   </div>`,
            showConfirmButton: true, confirmButtonText: 'Listo', confirmButtonColor: '#3c4043'
        });
    } catch (e) { Swal.fire({ icon: 'error', title: 'Error de conexión' }); }
}
window.compartirCorreoItem = compartirCorreoItem;

window.abrirConfigAlmacen = abrirConfigAlmacen;
window.abrirAlmacenamiento = abrirAlmacenamiento;
async function deshacerActividad(id) {
    try {
        const d = await (await fetch('/api/almacen/actividad/' + id + '/deshacer', { method: 'POST', headers: { 'Content-Type': 'application/json' } })).json();
        if (d.success) {
            Swal.fire({ icon: 'success', title: 'Borrado deshecho', text: d.message || '', confirmButtonColor: '#3c4043' })
                .then(() => { if (typeof cargarArchivos === 'function') cargarArchivos(rutaActual); abrirActividad(); });
        } else Swal.fire({ icon: 'error', title: 'No se pudo deshacer', text: d.error || '' });
    } catch (e) { Swal.fire({ icon: 'error', title: 'Error de conexión' }); }
}
window.abrirActividad = abrirActividad;
window.deshacerActividad = deshacerActividad;
window.comentariosItem = comentariosItem;
window.abrirCuotas = abrirCuotas;
window.abrirUnidades = abrirUnidades;
window.versionesItem = versionesItem;
