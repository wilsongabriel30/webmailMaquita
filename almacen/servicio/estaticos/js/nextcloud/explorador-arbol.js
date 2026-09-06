/**
 * explorador-arbol.js  -  Modulo: Arbol de carpetas del panel izquierdo (Mi unidad)
 * Responsabilidad UNICA: render, navegacion (SPA) y memoria (localStorage) del arbol lateral.
 * Depende de globales de otros modulos:
 *   _cargarHijosCarpeta(ruta)   -> explorador-interactions.js
 *   navegarA(ruta), rutaActual, vistaActual
 * IMPORTANTE: cargar DESPUES de explorador-interactions.js.
 */

// ===== Arbol de carpetas del panel izquierdo (Drive-like: SPA + memoria localStorage) =====
const _TREE_KEY = 'nube_arbol_abiertas';
function _ramasAbiertas() { try { return new Set(JSON.parse(localStorage.getItem(_TREE_KEY) || '[]')); } catch(e){ return new Set(); } }
function _guardarRama(ruta, abierta) {
    try { const st = _ramasAbiertas(); if (abierta) st.add(ruta); else st.delete(ruta); localStorage.setItem(_TREE_KEY, JSON.stringify([...st])); } catch(e){}
}
// Usa URL_BASE (en modo Almacén = /archivos-almacen; en producción = /archivos/mi-unidad)
function _sidebarHref(ruta) { return URL_BASE + encodeURI(ruta); }
function _nodoPorRuta(ruta) {
    const nodos = document.querySelectorAll('#sidebarTree .gd-tree-node');
    for (const n of nodos) { if (n.dataset.ruta === ruta) return n; }
    return null;
}
function _renderNodoSidebar(h, nivel) {
    const ruta = h.ruta, nombre = h.nombre;
    const indent = 6 + nivel * 14;
    const r = escHtml(ruta);   // [A-13]
    const fid = escHtml(h.folder_id || '');
    const col = (h.color && h.color !== '#5f6368') ? h.color : '';
    const colStyle = col ? (' style="color:' + col + ';"') : '';
    return '<div class="gd-tree-node" data-ruta="' + r + '" data-nivel="' + nivel + '" data-folder-id="' + fid + '">'
        + '<div class="gd-tree-row" style="padding-left:' + indent + 'px;">'
        +   '<span class="gd-tree-toggle material-icons" onclick="event.preventDefault();event.stopPropagation();_toggleArbolLateral(this)">chevron_right</span>'
        +   '<a class="gd-tree-link" href="' + _sidebarHref(ruta) + '" onclick="return _irACarpetaArbol(event, this)">'
        +     '<span class="gd-tree-folder material-icons"' + colStyle + '>folder</span>'
        +     '<span class="gd-tree-name">' + escHtml(nombre) + '</span>'
        +   '</a>'
        + '</div>'
        + '<div class="gd-tree-children" data-loaded="0" style="display:none;"></div>'
        + '</div>';
}
async function _toggleArbolLateral(toggleEl) {
    const node = toggleEl.closest('.gd-tree-node');
    if (!node) return;
    const children = node.querySelector(':scope > .gd-tree-children');
    const ruta = node.dataset.ruta;
    const nivel = parseInt(node.dataset.nivel || '0', 10);
    if (children.style.display === 'none') {
        if (children.dataset.loaded === '0') {
            toggleEl.textContent = 'hourglass_empty';
            const hijos = await _cargarHijosCarpeta(ruta);
            children.innerHTML = hijos.map(h => _renderNodoSidebar(h, nivel + 1)).join('');
            children.dataset.loaded = '1';
            if (!hijos.length) { toggleEl.style.visibility = 'hidden'; return; }
        }
        children.style.display = 'block';
        toggleEl.textContent = 'expand_more';
        _guardarRama(ruta, true);
    } else {
        children.style.display = 'none';
        toggleEl.textContent = 'chevron_right';
        _guardarRama(ruta, false);
    }
}
function _toggleSidebarRoot(el) {
    const tree = document.getElementById('sidebarTree');
    if (!tree) return;
    const oculto = (tree.style.display === 'none' || !tree.style.display);
    tree.style.display = oculto ? 'block' : 'none';
    if (el) el.textContent = oculto ? 'expand_more' : 'chevron_right';
}
function _irACarpetaArbol(ev, linkEl) {
    if (ev.ctrlKey || ev.metaKey || ev.shiftKey || ev.button === 1) return true;
    ev.preventDefault();
    const node = linkEl.closest('.gd-tree-node');
    if (!node) return false;
    const ruta = node.dataset.ruta;
    try { vistaActual = 'archivos'; } catch(e){}
    const pp = document.getElementById('paginaPrincipal'); if (pp) pp.style.display = 'none';
    document.querySelectorAll('#sidebarTree .gd-tree-link.activo').forEach(l => l.classList.remove('activo'));
    linkEl.classList.add('activo');
    navegarA(ruta);
    return false;
}
async function _restaurarRamasAbiertas() {
    const abiertas = [..._ramasAbiertas()].sort((a, b) => a.split('/').length - b.split('/').length);
    for (const ruta of abiertas) {
        const nodo = _nodoPorRuta(ruta);
        if (!nodo) continue;
        const children = nodo.querySelector(':scope > .gd-tree-children');
        const toggle = nodo.querySelector(':scope > .gd-tree-row > .gd-tree-toggle');
        if (children && children.style.display === 'none' && toggle) { await _toggleArbolLateral(toggle); }
    }
}
async function _expandirHastaRutaActual() {
    let ruta = (typeof rutaActual !== 'undefined' && rutaActual) ? rutaActual : '/';
    if (!ruta || ruta === '/') return;
    const partes = ruta.split('/').filter(Boolean);
    let acum = '';
    for (let i = 0; i < partes.length; i++) {
        acum += '/' + partes[i];
        const nodo = _nodoPorRuta(acum);
        if (!nodo) break;
        if (i < partes.length - 1) {
            const toggle = nodo.querySelector(':scope > .gd-tree-row > .gd-tree-toggle');
            const children = nodo.querySelector(':scope > .gd-tree-children');
            if (children && children.style.display === 'none' && toggle) { await _toggleArbolLateral(toggle); }
        } else {
            const link = nodo.querySelector(':scope > .gd-tree-row > .gd-tree-link');
            if (link) { link.classList.add('activo'); try { link.scrollIntoView({block:'nearest'}); } catch(e){} }
        }
    }
}
async function inicializarArbolLateral() {
    const cont = document.getElementById('sidebarTree');
    if (!cont) return;
    try {
        const hijos = await _cargarHijosCarpeta('/');
        cont.innerHTML = hijos.length ? hijos.map(h => _renderNodoSidebar(h, 0)).join('') : '';
        cont.style.display = 'block';
        await _restaurarRamasAbiertas();
        await _expandirHastaRutaActual();
    } catch (e) { cont.innerHTML = ''; }
}
