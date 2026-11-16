/**
 * explorador-compartidos-conmigo-menu.js  -  Módulo: menú de un elemento de «Compartido conmigo»
 * Responsabilidad ÚNICA: el menú (clic derecho o botón «Más acciones») con «Abrir» y «Descargar».
 *
 * Los elementos de «Compartido conmigo» no son archivos propios: el menú general del explorador
 * (renombrar, mover, papelera…) no les corresponde, y sin menú no había forma visible de descargar
 * (informe de Andes, 15/11/2026).
 *
 * Depende de: abrirCompartidoConmigo y descargarCompartidoConmigo (explorador-compartidos-conmigo.js).
 */

let _elementoMenuCompartidoConmigo = null;

function _menuCompartidoConmigo() {
    let menu = document.getElementById('menuCompartidoConmigo');
    if (menu) return menu;
    menu = document.createElement('div');
    menu.id = 'menuCompartidoConmigo';
    menu.className = 'gd-context-menu';
    menu.innerHTML =
        '<div class="gd-context-item" data-accion="abrir"><span class="material-icons">open_in_new</span><span>Abrir</span></div>'
        + '<div class="gd-context-item" data-accion="descargar"><span class="material-icons">download</span><span>Descargar</span></div>';
    menu.addEventListener('click', function (e) {
        const opcion = e.target.closest('[data-accion]');
        const el = _elementoMenuCompartidoConmigo;
        cerrarMenuCompartidoConmigo();
        if (!opcion || !el) return;
        if (opcion.dataset.accion === 'abrir') abrirCompartidoConmigo(el);
        else descargarCompartidoConmigo(el);
    });
    document.body.appendChild(menu);
    return menu;
}

function cerrarMenuCompartidoConmigo() {
    const menu = document.getElementById('menuCompartidoConmigo');
    if (menu) menu.classList.remove('show');
    _elementoMenuCompartidoConmigo = null;
}

function abrirMenuCompartidoConmigo(evento, el) {
    if (!el) return;
    evento.preventDefault();
    evento.stopPropagation();
    const general = document.getElementById('contextMenu');
    if (general) general.classList.remove('show');
    const menu = _menuCompartidoConmigo();
    _elementoMenuCompartidoConmigo = el;
    const descargar = menu.querySelector('[data-accion="descargar"]');
    descargar.style.display = el.dataset.descarga === 'true' ? '' : 'none';
    menu.classList.add('show');
    // dentro de la pantalla, también en celular
    const ancho = menu.offsetWidth || 200, alto = menu.offsetHeight || 90;
    menu.style.left = Math.max(8, Math.min(evento.clientX, window.innerWidth - ancho - 8)) + 'px';
    menu.style.top = Math.max(8, Math.min(evento.clientY, window.innerHeight - alto - 8)) + 'px';
}

// En fase de captura: se adelanta al menú general del explorador, que no aplica a estos elementos.
document.addEventListener('contextmenu', function (e) {
    const el = e.target.closest && e.target.closest('.gd-comp-conmigo');
    if (el) abrirMenuCompartidoConmigo(e, el);
}, true);
document.addEventListener('click', function (e) {
    if (!e.target.closest || !e.target.closest('#menuCompartidoConmigo')) cerrarMenuCompartidoConmigo();
});
document.addEventListener('keydown', function (e) { if (e.key === 'Escape') cerrarMenuCompartidoConmigo(); });
