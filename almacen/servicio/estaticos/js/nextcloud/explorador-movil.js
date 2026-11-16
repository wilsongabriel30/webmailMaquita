// =============================================================================
// Nube en pantallas angostas (hasta 768 px): menú lateral deslizante y «Nuevo».
//
// Crea tres controles que solo se ven en pantallas angostas (los estilos están en
// explorador-movil.css): el botón que abre el menú lateral, el fondo que lo cierra
// al tocar fuera y un botón flotante «Nuevo». No cambia nada en escritorio.
// Debe cargarse después de los demás módulos del explorador.
// =============================================================================
(function () {
    'use strict';

    const ANGOSTA = window.matchMedia('(max-width: 768px)');
    const CLASE_ABIERTO = 'nube-menu-abierto';
    // Dentro del menú lateral, lo que al tocarse lleva a otra parte (y por eso lo cierra).
    const DESTINOS = 'a.gd-nav-item, .gd-tree-link, .gd-new-menu-item, .gd-storage-header, .gd-storage-link, .gd-storage-legend a';

    const cabecera = document.querySelector('.gd-header');
    const lateral = document.querySelector('.gd-sidebar');
    if (!cabecera || !lateral) return;

    function crearBoton(id, clase, icono, etiqueta) {
        const boton = document.createElement('button');
        boton.type = 'button';
        boton.id = id;
        boton.className = clase;
        boton.title = etiqueta;
        boton.setAttribute('aria-label', etiqueta);
        const simbolo = document.createElement('span');
        simbolo.className = 'material-icons';
        simbolo.setAttribute('aria-hidden', 'true');
        simbolo.textContent = icono;
        boton.appendChild(simbolo);
        return boton;
    }

    if (!lateral.id) lateral.id = 'menuLateralNube';

    const botonMenu = crearBoton('btnMenuMovil', 'gd-icon-btn gd-movil-menu-btn', 'menu', 'Abrir el menú');
    botonMenu.setAttribute('aria-controls', lateral.id);
    botonMenu.setAttribute('aria-expanded', 'false');
    cabecera.insertBefore(botonMenu, cabecera.firstChild);

    const fondo = document.createElement('div');
    fondo.className = 'gd-movil-fondo';
    document.body.appendChild(fondo);

    const botonNuevo = crearBoton('btnNuevoMovil', 'gd-movil-nuevo', 'add', 'Nuevo: crear o subir');
    document.body.appendChild(botonNuevo);

    function menuAbierto() {
        return document.body.classList.contains(CLASE_ABIERTO);
    }

    function cerrarMenu() {
        if (!menuAbierto()) return;
        document.body.classList.remove(CLASE_ABIERTO);
        botonMenu.setAttribute('aria-expanded', 'false');
        botonMenu.title = 'Abrir el menú';
        botonMenu.setAttribute('aria-label', 'Abrir el menú');
    }

    function abrirMenu() {
        document.body.classList.add(CLASE_ABIERTO);
        botonMenu.setAttribute('aria-expanded', 'true');
        botonMenu.title = 'Cerrar el menú';
        botonMenu.setAttribute('aria-label', 'Cerrar el menú');
    }

    botonMenu.addEventListener('click', function () {
        if (menuAbierto()) cerrarMenu(); else abrirMenu();
    });
    fondo.addEventListener('click', cerrarMenu);

    // Elegir una sección, una carpeta del árbol o una opción de «Nuevo» cierra el panel.
    // Las flechas que despliegan el árbol no cuentan: no llevan a ninguna parte.
    lateral.addEventListener('click', function (evento) {
        if (evento.target.closest('.gd-tree-toggle')) return;
        if (evento.target.closest(DESTINOS)) cerrarMenu();
    });

    document.addEventListener('keydown', function (evento) {
        if (evento.key === 'Escape') cerrarMenu();
    });

    // Al girar el teléfono o ensanchar la ventana, el panel no debe quedar «abierto» a escondidas.
    ANGOSTA.addEventListener('change', function (evento) {
        if (!evento.matches) cerrarMenu();
    });

    // Botón flotante «Nuevo»: mismo menú que el del panel lateral. Se abre en el siguiente
    // turno porque el explorador cierra ese menú con cualquier clic fuera de su botón original.
    botonNuevo.addEventListener('click', function () {
        const menu = document.getElementById('newMenu');
        if (!menu) return;
        const estabaAbierto = menu.classList.contains('show');
        setTimeout(function () { menu.classList.toggle('show', !estabaAbierto); }, 0);
    });

    // En pantalla angosta la franja de iconos de la derecha empieza plegada (ocupa 52 px de
    // 390), salvo que la persona ya haya elegido cómo la quiere; su botón sigue disponible.
    function plegarFranjaDerecha() {
        if (!ANGOSTA.matches) return;
        let preferencia = null;
        try { preferencia = localStorage.getItem('panelLateralOculto'); } catch (e) { /* sin almacenamiento local */ }
        if (preferencia !== null) return;
        const franja = document.getElementById('rightPanel');
        const principal = document.querySelector('.gd-main');
        const conmutador = document.getElementById('panelToggle');
        if (!franja || !principal) return;
        franja.classList.add('hidden');
        principal.classList.add('panel-hidden');
        if (conmutador) {
            conmutador.classList.add('panel-hidden');
            conmutador.dataset.tooltip = 'Mostrar panel lateral';
        }
    }
    plegarFranjaDerecha();
})();
