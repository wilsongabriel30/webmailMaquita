/**
 * explorador-compartidos-conmigo.js  -  Módulo: vista «Compartido conmigo» del Almacén del webmail
 * Responsabilidad ÚNICA: pedir GET /compartidos-conmigo (lo que otras personas compartieron
 * con el correo de quien tiene la sesión) y pintarlo en lista y en cuadrícula.
 *
 * Cada elemento se abre con SU ENLACE (token), no con una ruta de la unidad propia: por eso
 * estas filas no usan crearFila/crearCard (abrirían la ruta en la unidad de quien mira).
 *
 * Depende de: API_BASE (config.js), escHtml (escape.js), formatearFecha/formatearFechaCorta
 *   (interactions.js), actualizarBreadcrumb (navegacion.js), aplicarVistaActual (core.js),
 *   contenedores #listBody/#foldersBlock/#filesBlock/#filesContainer/#emptyState.
 * Cargar ANTES de explorador-navegacion.js (que consulta esVistaCompartidosConmigo).
 */

/** ¿La carga pedida corresponde a «Compartido conmigo»? El servidor abre esa sección con
 *  vista = 'compartidos' y ruta inicial '/', así que no basta con mirar la ruta. */
function esVistaCompartidosConmigo(ruta) {
    if (ruta === '/compartidos' || ruta === '/compartidos/') return true;
    return typeof vistaActual !== 'undefined' && vistaActual === 'compartidos' && (ruta === '/' || ruta === '');
}

function _iconoCompartidoConmigo(extension) {
    const ext = (extension || '').toLowerCase();
    if (['doc', 'docx', 'odt', 'rtf'].includes(ext)) return ['description', 'word'];
    if (['xls', 'xlsx', 'ods', 'csv'].includes(ext)) return ['grid_on', 'excel'];
    if (['ppt', 'pptx', 'odp'].includes(ext)) return ['slideshow', 'powerpoint'];
    if (ext === 'pdf') return ['picture_as_pdf', 'pdf'];
    if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(ext)) return ['image', 'image'];
    if (['mp4', 'avi', 'mkv', 'mov', 'webm'].includes(ext)) return ['videocam', 'video'];
    if (['mp3', 'wav', 'ogg', 'flac', 'm4a'].includes(ext)) return ['audiotrack', 'audio'];
    if (['zip', 'rar', '7z', 'tar', 'gz'].includes(ext)) return ['folder_zip', 'archive'];
    return ['insert_drive_file', 'default'];
}

function _tamanoCompartidoConmigo(bytes) {
    let n = Number(bytes);
    if (!isFinite(n) || n < 0) return '-';
    const unidades = ['B', 'KB', 'MB', 'GB', 'TB'];
    let i = 0;
    while (n >= 1024 && i < unidades.length - 1) { n /= 1024; i++; }
    return (i === 0 ? String(Math.round(n)) : n.toFixed(1)) + ' ' + unidades[i];
}

/** Dirección que abre el elemento: el editor en línea si es un documento sin clave; en los
 *  demás casos, la página del enlace (pide la clave si la tiene y ofrece la descarga). */
function _urlCompartidoConmigo(token, enLinea, conClave) {
    const base = '/almacen-s/' + encodeURIComponent(token);
    return (enLinea && !conClave) ? base + '/editar' : base;
}

function abrirCompartidoConmigo(el) {
    const d = el.dataset;
    if (!d.token) return;
    window.open(_urlCompartidoConmigo(d.token, d.enLinea === 'true', d.conClave === 'true'), 'oo-' + d.token);
}

function descargarCompartidoConmigo(el) {
    if (el.dataset.token) window.open('/almacen-s/' + encodeURIComponent(el.dataset.token), '_blank');
}

function _datosCompartidoConmigo(c) {
    return 'data-token="' + escHtml(c.token || '') + '" data-en-linea="' + (c.abre_en_linea ? 'true' : 'false')
        + '" data-con-clave="' + (c.requiere_clave ? 'true' : 'false') + '" data-nombre="' + escHtml(c.nombre) + '"';
}

function _filaCompartidoConmigo(c) {
    const icono = _iconoCompartidoConmigo(c.extension)[0];
    const de = c.de || '';
    const inicial = (de.trim().charAt(0) || '?').toUpperCase();
    const verbo = c.puede_editar ? 'Editar en línea' : 'Ver en línea';
    const marcas = (c.requiere_clave ? ' <span class="material-icons" style="font-size:16px;color:#5f6368;vertical-align:middle;" title="El enlace tiene clave">lock</span>' : '')
        + (c.puede_editar ? ' <span style="font-size:11px;font-weight:600;color:#188038;margin-left:6px;" title="Usted puede editarlo">Editor</span>' : '');
    const botones = (c.abre_en_linea
            ? '<button class="gd-icon-btn" onclick="event.stopPropagation(); abrirCompartidoConmigo(this.closest(\'tr\'))" title="' + verbo + '"><span class="material-icons">' + (c.puede_editar ? 'edit' : 'visibility') + '</span></button>'
            : '')
        + (c.permite_descarga
            ? '<button class="gd-icon-btn" onclick="event.stopPropagation(); descargarCompartidoConmigo(this.closest(\'tr\'))" title="Descargar"><span class="material-icons">download</span></button>'
            : '');
    return '<tr class="gd-comp-conmigo" ' + _datosCompartidoConmigo(c) + ' ondblclick="abrirCompartidoConmigo(this)">'
        + '<td><div class="gd-list-name"><div class="file-icon"><span class="material-icons" style="color:#5f6368">' + icono + '</span></div>'
        + '<span class="file-name">' + escHtml(c.nombre) + '</span>' + marcas + '</div></td>'
        + '<td><div class="gd-list-owner" title="' + escHtml(de) + '"><div class="owner-avatar">' + escHtml(inicial) + '</div><span>' + escHtml(de) + '</span></div></td>'
        + '<td>' + escHtml(formatearFecha(c.creado_en)) + '</td>'
        + '<td>' + _tamanoCompartidoConmigo(c.tamano_bytes) + '</td>'
        + '<td class="gd-list-actions"><div class="gd-list-actions-btns">' + botones + '</div></td>'
        + '</tr>';
}

function _tarjetaCompartidoConmigo(c) {
    const par = _iconoCompartidoConmigo(c.extension);
    const pie = 'Compartido por ' + (c.de || '') + (c.creado_en ? ' · ' + formatearFechaCorta(c.creado_en) : '');
    return '<div class="gd-card gd-comp-conmigo" ' + _datosCompartidoConmigo(c) + ' ondblclick="abrirCompartidoConmigo(this)" title="Doble clic para abrir">'
        + '<div class="gd-card-header"><div class="type-icon ' + par[1] + '"><span class="material-icons">' + par[0] + '</span></div>'
        + '<span class="file-name" title="' + escHtml(c.nombre) + '">' + escHtml(c.nombre) + '</span></div>'
        + '<div class="gd-card-preview"><span class="material-icons">' + par[0] + '</span></div>'
        + '<div class="gd-card-footer"><div class="gd-card-meta">' + escHtml(pie) + '</div></div>'
        + '</div>';
}

/** Aviso propio de la sección vacía (el estado vacío general invita a subir archivos). */
function _avisoVacioCompartidosConmigo(mostrar) {
    let aviso = document.getElementById('compConmigoVacio');
    if (!aviso && mostrar) {
        aviso = document.createElement('div');
        aviso.id = 'compConmigoVacio';
        aviso.className = 'gd-empty';
        aviso.innerHTML = '<span class="material-icons" style="font-size:64px;color:#dadce0;">people</span>'
            + '<h2>Nadie le ha compartido archivos todavía</h2>'
            + '<p>Cuando otra persona comparta un archivo con su correo, aparecerá aquí.</p>';
        const vacio = document.getElementById('emptyState');
        if (vacio && vacio.parentElement) vacio.parentElement.insertBefore(aviso, vacio);
    }
    if (aviso) aviso.style.display = mostrar ? 'block' : 'none';
}

/** Lo llama cargarArchivos al empezar cualquier carga: el aviso solo vale en esta sección. */
function ocultarAvisoCompartidosConmigo() {
    _avisoVacioCompartidosConmigo(false);
}

function _pintarCompartidosConmigo(compartidos) {
    const listBody = document.getElementById('listBody');
    const foldersBlock = document.getElementById('foldersBlock');
    const filesBlock = document.getElementById('filesBlock');
    if (listBody) listBody.innerHTML = compartidos.map(_filaCompartidoConmigo).join('');
    if (foldersBlock) foldersBlock.innerHTML = '';
    if (filesBlock) filesBlock.innerHTML = compartidos.map(_tarjetaCompartidoConmigo).join('');
    const contenedor = document.getElementById('filesContainer');
    const vacio = document.getElementById('emptyState');
    if (contenedor) contenedor.style.display = compartidos.length ? 'block' : 'none';
    if (vacio) vacio.style.display = 'none';
    _avisoVacioCompartidosConmigo(compartidos.length === 0);
    // La búsqueda rápida trabaja sobre la unidad propia: aquí no hay nada suyo que filtrar.
    try { archivosCache = []; } catch (e) {}
    if (typeof _ocultarFiltrosComp === 'function') _ocultarFiltrosComp();
    if (typeof aplicarVistaActual === 'function') aplicarVistaActual();
}

/** Carga y pinta la sección. Devuelve true si se pudo; en modo silencioso no avisa de fallos. */
async function cargarCompartidosConmigo(ruta, silencioso) {
    try {
        const resp = await fetch(API_BASE + '/compartidos-conmigo?_t=' + Date.now(), { credentials: 'same-origin' });
        const data = await resp.json();
        if (!resp.ok || !data || !data.success) throw new Error((data && data.error) || ('HTTP ' + resp.status));
        rutaActual = ruta;
        actualizarBreadcrumb([{ nombre: 'Compartido conmigo', ruta: ruta }]);
        _pintarCompartidosConmigo(data.compartidos || []);
        return true;
    } catch (e) {
        console.error('[Nube Maquita] No se pudo cargar «Compartido conmigo»:', e);
        if (!silencioso) Swal.fire('Error', 'No se pudo cargar lo que le han compartido: ' + e.message, 'error');
        return false;
    }
}
