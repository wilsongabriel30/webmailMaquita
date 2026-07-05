/**
 * explorador-compartidos.js  -  Modulo: vista "Compartido conmigo" (estilo Google Drive)
 * Responsabilidad UNICA: filtrar (Tipo/Personas), agrupar por fecha y renderizar los compartidos.
 * Depende de: crearFila, crearCard (render.js), aplicarVistaActual, inicializarLazyLoading (core.js),
 *   contenedores #listBody/#foldersBlock/#filesBlock/#filesContainer/#emptyState.
 */
let _compItems = [];
let _compFiltroTipo = '';
let _compFiltroPersona = '';

function _bucketFechaCompartido(fechaStr) {
    if (!fechaStr) return 'Anteriores';
    const f = new Date(fechaStr);
    if (isNaN(f.getTime())) return 'Anteriores';
    const hoy = new Date(); hoy.setHours(0, 0, 0, 0);
    const dia = new Date(f); dia.setHours(0, 0, 0, 0);
    const diff = Math.round((hoy.getTime() - dia.getTime()) / 86400000);
    if (diff <= 0) return 'Hoy';
    if (diff === 1) return 'Ayer';
    if (diff <= 7) return 'Semana pasada';
    if (diff <= 31) return 'Mes pasado';
    return 'Anteriores';
}

function _tipoLabelComp(it) {
    if (it.es_carpeta) return 'Carpetas';
    const ext = (it.nombre || '').split('.').pop().toLowerCase();
    if (['xlsx', 'xls', 'csv', 'ods', 'xlsm'].includes(ext)) return 'Hojas de calculo';
    if (['docx', 'doc', 'odt', 'txt', 'rtf'].includes(ext)) return 'Documentos';
    if (['pptx', 'ppt', 'odp'].includes(ext)) return 'Presentaciones';
    if (ext === 'pdf') return 'PDF';
    if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(ext)) return 'Imagenes';
    if (['mp4', 'mov', 'avi', 'webm', 'mkv'].includes(ext)) return 'Videos';
    return 'Otros';
}

function _ocultarFiltrosComp() {
    const bar = document.getElementById('compFiltros');
    if (bar) bar.style.display = 'none';
}

function _renderFiltrosComp() {
    let bar = document.getElementById('compFiltros');
    if (!bar) {
        bar = document.createElement('div');
        bar.id = 'compFiltros';
        bar.className = 'gd-comp-filtros';
        const cont = document.getElementById('filesContainer');
        if (cont && cont.parentElement) cont.parentElement.insertBefore(bar, cont);
    }
    const tipos = [...new Set(_compItems.map(_tipoLabelComp))].sort();
    const personas = [...new Set(_compItems.map(i => i.propietario_nombre).filter(Boolean))].sort();
    const opt = (v, sel) => '<option value="' + String(v).replace(/"/g, '&quot;') + '"' + (sel === v ? ' selected' : '') + '>' + v + '</option>';
    bar.innerHTML =
        '<select class="gd-comp-select" onchange="_compFiltroTipo=this.value;_pintarComp()"><option value="">Tipo</option>'
        + tipos.map(t => opt(t, _compFiltroTipo)).join('') + '</select>'
        + '<select class="gd-comp-select" onchange="_compFiltroPersona=this.value;_pintarComp()"><option value="">Personas</option>'
        + personas.map(p => opt(p, _compFiltroPersona)).join('') + '</select>'
        + ((_compFiltroTipo || _compFiltroPersona) ? '<button class="gd-comp-clear" onclick="_compFiltroTipo=\'\';_compFiltroPersona=\'\';_renderFiltrosComp();_pintarComp()">Limpiar filtros</button>' : '');
    bar.style.display = 'flex';
}

function _pintarComp() {
    let arr = _compItems.slice();
    if (_compFiltroTipo) arr = arr.filter(i => _tipoLabelComp(i) === _compFiltroTipo);
    if (_compFiltroPersona) arr = arr.filter(i => i.propietario_nombre === _compFiltroPersona);
    arr.sort((a, b) => new Date(b.compartido_at || b.modificado_at || 0).getTime() - new Date(a.compartido_at || a.modificado_at || 0).getTime());

    const ORDEN = ['Hoy', 'Ayer', 'Semana pasada', 'Mes pasado', 'Anteriores'];
    const grupos = {};
    arr.forEach(it => { const b = _bucketFechaCompartido(it.compartido_at || it.modificado_at); (grupos[b] = grupos[b] || []).push(it); });

    let listHtml = '', gridHtml = '';
    ORDEN.forEach(g => {
        if (!grupos[g]) return;
        listHtml += '<tr class="gd-group-header"><td colspan="5">' + g + '</td></tr>';
        gridHtml += '<div class="gd-group-header-grid">' + g + '</div>';
        grupos[g].forEach(it => { try { listHtml += crearFila(it); } catch (e) {} try { gridHtml += crearCard(it); } catch (e) {} });
    });
    const listBody = document.getElementById('listBody');
    const foldersBlock = document.getElementById('foldersBlock');
    const filesBlock = document.getElementById('filesBlock');
    if (listBody) listBody.innerHTML = listHtml;
    if (foldersBlock) foldersBlock.innerHTML = gridHtml;
    if (filesBlock) filesBlock.innerHTML = '';
    const container = document.getElementById('filesContainer');
    const emptyState = document.getElementById('emptyState');
    if (container) container.style.display = arr.length ? 'block' : 'none';
    if (emptyState) emptyState.style.display = arr.length ? 'none' : 'block';
    if (typeof aplicarVistaActual === 'function') aplicarVistaActual();
    if (typeof inicializarLazyLoading === 'function') inicializarLazyLoading();
}

function renderizarCompartidosAgrupados(items) {
    _compItems = items || [];
    // Llenar archivosCache para que la busqueda y otras features funcionen en esta vista
    try { archivosCache = _compItems.slice(); } catch (e) {}
    _renderFiltrosComp();
    _pintarComp();
}
