// -----------------------------------------------------------------------------
// Drag & Drop para mover archivos
// -----------------------------------------------------------------------------

let elementoArrastrado = null;

function iniciarArrastre(event, elemento) {
    elementoArrastrado = {
        ruta: elemento.dataset.ruta,
        nombre: elemento.dataset.nombre,
        esCarpeta: elemento.dataset.carpeta === 'true'
    };

    // Efecto visual
    elemento.classList.add('dragging');

    // Datos para el drag
    event.dataTransfer.setData('text/plain', JSON.stringify(elementoArrastrado));
    event.dataTransfer.effectAllowed = 'move';

    // Imagen de arrastre personalizada
    const dragImage = document.createElement('div');
    dragImage.className = 'gd-drag-image';
    dragImage.innerHTML = `
        <span class="material-icons">${elementoArrastrado.esCarpeta ? 'folder' : 'insert_drive_file'}</span>
        <span>${elementoArrastrado.nombre}</span>
    `;
    dragImage.style.position = 'absolute';
    dragImage.style.top = '-1000px';
    document.body.appendChild(dragImage);
    event.dataTransfer.setDragImage(dragImage, 20, 20);

    setTimeout(() => {
        document.body.removeChild(dragImage);
    }, 0);
}

function finalizarArrastre(event) {
    document.querySelectorAll('.dragging').forEach(el => el.classList.remove('dragging'));
    document.querySelectorAll('.drop-target').forEach(el => el.classList.remove('drop-target'));
    elementoArrastrado = null;
}

function permitirSoltar(event, elemento) {
    // Solo permitir soltar en carpetas
    if (elemento.dataset.carpeta !== 'true') return;

    // No permitir soltar en sí mismo
    if (elementoArrastrado && elemento.dataset.ruta === elementoArrastrado.ruta) return;

    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
    elemento.classList.add('drop-target');
}

function salirSoltar(event, elemento) {
    elemento.classList.remove('drop-target');
}

async function soltarEnCarpeta(event, elementoDestino) {
    event.preventDefault();
    event.stopPropagation();

    elementoDestino.classList.remove('drop-target');

    if (!elementoArrastrado) return;

    const carpetaDestino = elementoDestino.dataset.ruta;

    // No mover a sí mismo o si el destino no es carpeta
    if (elementoDestino.dataset.carpeta !== 'true') return;
    if (carpetaDestino === elementoArrastrado.ruta) return;

    // Construir ruta destino
    let rutaDestino = carpetaDestino;
    if (!rutaDestino.endsWith('/')) rutaDestino += '/';
    rutaDestino += elementoArrastrado.nombre;

    try {
        const response = await fetch(`${API_BASE}/archivos/mover`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                origen: elementoArrastrado.ruta,
                destino: rutaDestino
            })
        });

        const data = await response.json();

        if (data.success) {
            mostrarNotificacion(`"${elementoArrastrado.nombre}" movido a "${elementoDestino.dataset.nombre}"`, 'success');
            cargarArchivos(rutaActual, true);
        } else {
            mostrarNotificacion(data.error || 'Error al mover el archivo', 'error');
        }
    } catch (error) {
        console.error('Error al mover:', error);
        mostrarNotificacion('Error al mover el archivo', 'error');
    }

    elementoArrastrado = null;
}

// Función para formatear fecha corta (para tarjetas)
function formatearFechaCorta(fechaISO) {
    if (!fechaISO) return '';
    try {
        const fecha = new Date(fechaISO);
        const hoy = new Date();
        const ayer = new Date(hoy);
        ayer.setDate(ayer.getDate() - 1);

        if (fecha.toDateString() === hoy.toDateString()) {
            return fecha.toLocaleTimeString('es-EC', { hour: '2-digit', minute: '2-digit' });
        } else if (fecha.toDateString() === ayer.toDateString()) {
            return 'Ayer';
        } else if (fecha.getFullYear() === hoy.getFullYear()) {
            return fecha.toLocaleDateString('es-EC', { day: 'numeric', month: 'short' });
        } else {
            return fecha.toLocaleDateString('es-EC', { day: 'numeric', month: 'short', year: '2-digit' });
        }
    } catch (e) {
        return '';
    }
}
// [movida a explorador-render.js]

// Función para formatear fechas de forma legible
function formatearFecha(fechaISO) {
    if (!fechaISO) return '-';

    try {
        const fecha = new Date(fechaISO);
        const ahora = new Date();
        const diferencia = ahora - fecha;

        // Menos de 1 minuto
        if (diferencia < 60000) return 'Hace un momento';

        // Menos de 1 hora
        if (diferencia < 3600000) {
            const minutos = Math.floor(diferencia / 60000);
            return `Hace ${minutos} min`;
        }

        // Menos de 24 horas
        if (diferencia < 86400000) {
            const horas = Math.floor(diferencia / 3600000);
            return `Hace ${horas} hora${horas > 1 ? 's' : ''}`;
        }

        // Menos de 7 días
        if (diferencia < 604800000) {
            const dias = Math.floor(diferencia / 86400000);
            return `Hace ${dias} día${dias > 1 ? 's' : ''}`;
        }

        // Más de 7 días - mostrar fecha completa
        const opciones = { day: 'numeric', month: 'short', year: 'numeric' };
        return fecha.toLocaleDateString('es-ES', opciones);
    } catch (e) {
        return '-';
    }
}

// -----------------------------------------------------------------------------
// Navegación
// -----------------------------------------------------------------------------
// [movida a explorador-navegacion.js]

// [Arbol del panel izquierdo movido a explorador-arbol.js - 2026-06-09]
// [movida a explorador-navegacion.js]

// Manejar botón atrás/adelante del navegador
window.addEventListener('popstate', function(event) {
    if (event.state && event.state.ruta !== undefined) {
        // Navegar a la ruta guardada en el historial sin agregar nueva entrada
        cargarArchivos(event.state.ruta);
    } else {
        // Si no hay estado, extraer ruta de la URL actual
        const path = window.location.pathname;
        if (path.startsWith(URL_BASE)) {
            const ruta = path.replace(URL_BASE, '') || '/';
            cargarArchivos(ruta);
        } else if (path.startsWith('/archivos')) {
            const ruta = path.replace('/archivos', '').replace('/mi-unidad', '') || '/';
            cargarArchivos(ruta);
        }
    }
});
// [movida a explorador-navegacion.js]

// -----------------------------------------------------------------------------
// Selección (con soporte para selección múltiple)
// -----------------------------------------------------------------------------

let elementosSeleccionados = [];

function seleccionarItem(event, elemento) {
    event.stopPropagation();

    const esMultiSeleccion = event.ctrlKey || event.metaKey;
    const esRangoSeleccion = event.shiftKey;

    if (!esMultiSeleccion && !esRangoSeleccion) {
        // Selección simple: limpiar selección anterior
        document.querySelectorAll('.gd-card.selected, .gd-folder-card.selected, .gd-list tr.selected')
            .forEach(el => el.classList.remove('selected'));
        elementosSeleccionados = [];
    }

    if (esMultiSeleccion && elemento.classList.contains('selected')) {
        // Ctrl+Click en elemento ya seleccionado: deseleccionar
        elemento.classList.remove('selected');
        elementosSeleccionados = elementosSeleccionados.filter(e => e.ruta !== elemento.dataset.ruta);
    } else {
        // Agregar a selección
        elemento.classList.add('selected');
        const item = {
            ruta: elemento.dataset.ruta,
            esCarpeta: elemento.dataset.carpeta === 'true',
            nombre: elemento.dataset.nombre,
            folder_id: elemento.dataset.folderId || null
        };

        if (!elementosSeleccionados.find(e => e.ruta === item.ruta)) {
            elementosSeleccionados.push(item);
        }
    }

    // Actualizar itemSeleccionado para compatibilidad
    if (elementosSeleccionados.length > 0) {
        itemSeleccionado = elementosSeleccionados[elementosSeleccionados.length - 1];

        // Obtener todos los datos del elemento para el panel de info
        const ds = elemento.dataset;
        itemSeleccionado.ruta_completa = ds.ruta || '';
        itemSeleccionado.tipo = ds.tipo || (itemSeleccionado.esCarpeta ? 'carpeta' : 'archivo');
        itemSeleccionado.extension = ds.extension || (itemSeleccionado.nombre ? itemSeleccionado.nombre.split('.').pop().toLowerCase() : '');
        itemSeleccionado.tamano_humano = ds.tamano || '';
        itemSeleccionado.modificado_at = ds.modificado || '';
        itemSeleccionado.es_favorito = ds.favorito === 'true';
        itemSeleccionado.es_favorita = ds.favorito === 'true';
        itemSeleccionado.es_compartido = ds.compartido === 'true';
        itemSeleccionado.es_compartida = ds.compartido === 'true';
        itemSeleccionado.es_editable = ds.editable === 'true';
        itemSeleccionado.preview_url = ds.previewUrl || '';
        itemSeleccionado.color_personalizado = ds.color || ds.colorPersonalizado || '';
        itemSeleccionado.color = ds.color || '';
        itemSeleccionado.mime_type = ds.mimeType || '';
        itemSeleccionado.file_id = ds.fileId || ds.folderId || '';
    } else {
        itemSeleccionado = null;
    }

    actualizarBarraSeleccion();

    // Si el panel de información está abierto, actualizarlo automáticamente
    if (panelActivo === 'info') {
        actualizarPanelInfo();
    }
}

// Función para actualizar el panel de información con el item seleccionado
function actualizarPanelInfo() {
    const content = document.getElementById('rightPanelContent');
    if (!content) return;

    if (itemSeleccionado) {
        content.innerHTML = generarContenidoDetalles(itemSeleccionado);
        cargarDimensionesImagen();
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
}

function actualizarBarraSeleccion() {
    const bar = document.getElementById('selectionBar');
    const countEl = document.getElementById('selectionCount');

    if (elementosSeleccionados.length > 0) {
        bar.classList.add('show');
        const texto = elementosSeleccionados.length === 1
            ? '1 seleccionado'
            : `${elementosSeleccionados.length} seleccionados`;
        countEl.textContent = texto;
    } else {
        bar.classList.remove('show');
    }
}

function limpiarSeleccion() {
    document.querySelectorAll('.gd-card.selected, .gd-folder-card.selected, .gd-list tr.selected')
        .forEach(el => el.classList.remove('selected'));
    elementosSeleccionados = [];
    itemSeleccionado = null;
    actualizarBarraSeleccion();
}

// Funciones de acciones múltiples
function compartirSeleccionados() {
    if (elementosSeleccionados.length === 1) {
        compartirSeleccionado();
    } else {
        mostrarNotificacion('Selecciona un solo elemento para compartir', 'warning');
    }
}

function descargarSeleccionados() {
    if (elementosSeleccionados.length === 1) {
        descargarSeleccionado();
    } else {
        // Para múltiples, descargar como ZIP
        mostrarNotificacion('Descargando archivos seleccionados...', 'info');
        elementosSeleccionados.forEach(item => {
            const url = `${API_BASE}/archivos/descargar?ruta=${encodeURIComponent(item.ruta)}`;
            const a = document.createElement('a');
            a.href = url;
            a.download = item.nombre;
            a.click();
        });
    }
}

function moverSeleccionados() {
    if (elementosSeleccionados.length === 1) {
        moverSeleccionado();
    } else {
        mostrarNotificacion('Selecciona un solo elemento para mover', 'warning');
    }
}

async function eliminarSeleccionados() {
    if (elementosSeleccionados.length === 0) return;

    const mensaje = elementosSeleccionados.length === 1
        ? `¿Eliminar "${elementosSeleccionados[0].nombre}"?`
        : `¿Eliminar ${elementosSeleccionados.length} elementos?`;

    if (confirm(mensaje)) {
        // FIX 2026-01-27: Usar Promise.all para esperar todas las eliminaciones
        const promesas = elementosSeleccionados.map(async (item) => {
            try {
                await fetch(`${API_BASE}/archivos/eliminar`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ ruta: item.ruta })
                });
            } catch (e) {
                console.error('Error eliminando:', item.nombre, e);
            }
        });

        // Esperar a que terminen todas las eliminaciones
        await Promise.all(promesas);

        mostrarNotificacion('Elementos movidos a la papelera', 'success');
        limpiarSeleccion();

        // Pequeño delay para que Nextcloud procese los cambios
        await new Promise(resolve => setTimeout(resolve, 300));

        // Refrescar lista forzando recarga
        await cargarArchivos(rutaActual, true);
    }
}

function copiarLinksSeleccionados() {
    const links = elementosSeleccionados.map(item =>
        `${window.location.origin}/archivos/compartir?ruta=${encodeURIComponent(item.ruta)}`
    ).join('\n');

    navigator.clipboard.writeText(links).then(() => {
        mostrarNotificacion('Enlaces copiados al portapapeles', 'success');
    });
}

function mostrarMasAcciones() {
    mostrarNotificacion('Más acciones disponibles en el menú contextual (clic derecho)', 'info');
}

function abrirItem(elemento) {
    // Acceso directo: abrir/navegar a su DESTINO, no al marcador.
    if (elemento.dataset.acceso === 'true' && elemento.dataset.destino) {
        const dest = elemento.dataset.destino;
        if (elemento.dataset.carpeta === 'true') navegarA(dest); else abrirArchivo(dest);
        return;
    }
    const ruta = elemento.dataset.ruta;
    const esCarpeta = elemento.dataset.carpeta === 'true';
    if (esCarpeta) {
        navegarA(ruta);
    } else {
        abrirArchivo(ruta);
    }
}

async function abrirArchivo(ruta) {
    const ext = ruta.split('.').pop().toLowerCase();

    // Documentos Office - abrir editor en nueva pestaña
    if (EXTENSIONES_OFFICE.includes(ext)) {
        _abrirEditorNube(ruta);
        return;
    }

    // Imágenes, PDFs, videos, Draw.io - abrir en lightbox (galería deslizable)
    if (EXTENSIONES_IMAGEN.includes(ext) ||
        EXTENSIONES_PDF.includes(ext) ||
        EXTENSIONES_VIDEO.includes(ext) ||
        EXTENSIONES_DRAWIO.includes(ext)) {
        abrirLightbox(ruta);
        return;
    }

    // Otros archivos - descargar
    window.location.href = `${API_BASE}/archivos/descargar?ruta=${encodeURIComponent(ruta)}`;
}

// -----------------------------------------------------------------------------
// Menú contextual
// -----------------------------------------------------------------------------

function mostrarContextMenu(event, elemento) {
    event.preventDefault();
    event.stopPropagation();

    // Cerrar cualquier submenú abierto
    cerrarSubmenus();

    seleccionarItem(event, elemento);

    const menu = document.getElementById('contextMenu');

    // Mostrar/ocultar opciones específicas de carpetas
    const esCarpeta = elemento?.dataset?.carpeta === 'true' || elemento?.tipo === 'carpeta';
    menu.querySelectorAll('.ctx-folder-only').forEach(item => {
        item.style.display = esCarpeta ? 'flex' : 'none';
    });

    // También ocultar en submenús
    document.querySelectorAll('.gd-context-submenu .ctx-folder-only').forEach(item => {
        item.style.display = esCarpeta ? 'flex' : 'none';
    });

    // Actualizar etiqueta de información
    const infoLabel = document.getElementById('ctxInfoLabel');
    if (infoLabel) {
        infoLabel.textContent = esCarpeta ? 'Información de la carpeta' : 'Información del archivo';
    }

    // Actualizar estado de favorito
    actualizarEstadoFavorito();

    // Primero mostrar para calcular dimensiones
    menu.style.visibility = 'hidden';
    menu.classList.add('show');

    const menuRect = menu.getBoundingClientRect();
    const menuHeight = menuRect.height;
    const menuWidth = menuRect.width;

    // Calcular posición considerando viewport
    const viewportHeight = window.innerHeight;
    const viewportWidth = window.innerWidth;

    let posX = event.clientX;
    let posY = event.clientY;

    // Si el menú se sale por abajo, posicionarlo arriba del click
    if (posY + menuHeight > viewportHeight - 20) {
        posY = Math.max(20, posY - menuHeight);
    }

    // Si el menú se sale por la derecha, ajustar
    if (posX + menuWidth > viewportWidth - 20) {
        posX = Math.max(20, viewportWidth - menuWidth - 20);
    }

    // Aplicar posición (fixed usa coordenadas del viewport)
    menu.style.left = posX + 'px';
    menu.style.top = posY + 'px';
    menu.style.visibility = 'visible';

    // Configurar event listeners para submenús
    configurarSubmenus(posX, menuWidth);
}

// Cerrar todos los submenús
function cerrarSubmenus() {
    document.querySelectorAll('.gd-context-submenu').forEach(sub => {
        sub.classList.remove('show');
    });
    document.querySelectorAll('.gd-context-item.has-submenu').forEach(item => {
        item.classList.remove('active');
    });
}

// Configurar eventos hover para submenús
function configurarSubmenus(menuX, menuWidth) {
    const menu = document.getElementById('contextMenu');
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    menu.querySelectorAll('.gd-context-item.has-submenu').forEach(item => {
        // Remover listeners previos
        item.onmouseenter = null;
        item.onmouseleave = null;

        item.onmouseenter = function() {
            // Cerrar otros submenús
            cerrarSubmenus();

            const submenuId = this.dataset.submenu;
            const submenu = document.getElementById(submenuId);
            if (!submenu) return;

            // Marcar item como activo
            this.classList.add('active');

            // Calcular posición del submenú
            const itemRect = this.getBoundingClientRect();
            let subX = itemRect.right;
            let subY = itemRect.top;

            // Verificar si cabe a la derecha, sino abrir a la izquierda
            submenu.style.visibility = 'hidden';
            submenu.classList.add('show');
            const subRect = submenu.getBoundingClientRect();

            if (subX + subRect.width > viewportWidth - 10) {
                subX = itemRect.left - subRect.width;
            }

            // Verificar si se sale por abajo
            if (subY + subRect.height > viewportHeight - 10) {
                subY = viewportHeight - subRect.height - 10;
            }

            submenu.style.position = 'fixed';
            submenu.style.left = subX + 'px';
            submenu.style.top = subY + 'px';
            submenu.style.visibility = 'visible';
        };
    });

    // Cerrar submenú cuando se sale del área
    menu.onmouseleave = function(e) {
        // Verificar si el mouse está sobre un submenú
        const submenus = document.querySelectorAll('.gd-context-submenu.show');
        let sobreSubmenu = false;
        submenus.forEach(sub => {
            const rect = sub.getBoundingClientRect();
            if (e.clientX >= rect.left && e.clientX <= rect.right &&
                e.clientY >= rect.top && e.clientY <= rect.bottom) {
                sobreSubmenu = true;
            }
        });
        if (!sobreSubmenu) {
            cerrarSubmenus();
        }
    };

    // Mantener submenú abierto mientras el mouse está sobre él
    document.querySelectorAll('.gd-context-submenu').forEach(submenu => {
        submenu.onmouseleave = function(e) {
            const menu = document.getElementById('contextMenu');
            const menuRect = menu.getBoundingClientRect();
            // Si el mouse vuelve al menú principal, no cerrar
            if (e.clientX >= menuRect.left && e.clientX <= menuRect.right &&
                e.clientY >= menuRect.top && e.clientY <= menuRect.bottom) {
                return;
            }
            cerrarSubmenus();
        };
    });
}

// Actualizar estado visual del favorito
function actualizarEstadoFavorito() {
    const iconoEl = document.getElementById('iconoDestacado');
    const labelEl = document.getElementById('labelDestacado');
    if (iconoEl && labelEl && itemSeleccionado) {
        const esFavorito = itemSeleccionado.es_favorita || itemSeleccionado.es_favorito;
        iconoEl.textContent = esFavorito ? 'star' : 'star_border';
        labelEl.textContent = esFavorito ? 'Quitar de Destacados' : 'Añadir a Destacados';
    }
}

// Aplicar color directamente desde el submenú de colores
async function aplicarColorDirecto(color) {
    cerrarSubmenus();
    document.getElementById('contextMenu').classList.remove('show');

    if (!itemSeleccionado) return;

    // Usar folder_id para que el color sea compartido entre usuarios
    const folderId = itemSeleccionado.folder_id;
    if (!folderId) {
        mostrarNotificacion('No se puede cambiar el color de esta carpeta', 'warning');
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/carpetas/estilo`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                folder_id: folderId,
                color: color || ''
            })
        });

        const data = await response.json();

        if (data.success) {
            mostrarNotificacion('Color actualizado para todos los usuarios', 'success');
            // Actualizar TODAS las apariciones (grid + lista) al instante
            const _col2 = color || '#5f6368';
            document.querySelectorAll(`[data-folder-id="${folderId}"]`).forEach(el => {
                const icon = el.querySelector('.folder-icon .material-icons, .file-icon .material-icons, .gd-list-name .material-icons, .gd-tree-folder');
                if (icon) icon.style.color = _col2;
                el.dataset.colorPersonalizado = color || '';
                el.dataset.color = _col2;
            });
        } else {
            mostrarNotificacion(data.error || 'Error al cambiar color', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        mostrarNotificacion('Error al cambiar color', 'error');
    }
}

// Crear acceso directo (symlink en Nextcloud)
async function crearAccesoDirecto() {
    cerrarSubmenus();
    document.getElementById('contextMenu').classList.remove('show');

    if (!itemSeleccionado) return;

    // Mostrar selector de carpeta destino
    const { value: carpetaDestino } = await Swal.fire({
        title: 'Añadir acceso directo',
        text: `Selecciona dónde crear el acceso directo a "${itemSeleccionado.nombre}"`,
        input: 'text',
        inputValue: '/',
        inputPlaceholder: 'Ruta de la carpeta destino (ej: /Accesos)',
        showCancelButton: true,
        confirmButtonText: 'Crear acceso directo',
        cancelButtonText: 'Cancelar'
    });

    if (carpetaDestino) {
        if (typeof MODO_ALMACEN !== 'undefined' && MODO_ALMACEN) {
            try {
                const r = await fetch(`${API_BASE}/archivos/acceso-directo`, {
                    method: 'POST', headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ destino: itemSeleccionado.ruta, carpeta: carpetaDestino })
                });
                const d = await r.json();
                if (d.success) {
                    mostrarNotificacion('Acceso directo creado', 'success');
                    if (typeof invalidarCache === 'function') invalidarCache(rutaActual);
                    cargarArchivos(rutaActual);
                } else {
                    mostrarNotificacion(d.error || 'No se pudo crear el acceso directo', 'error');
                }
            } catch (e) { mostrarNotificacion('Error de conexión', 'error'); }
        } else {
            mostrarNotificacion('Función de acceso directo en desarrollo', 'info');
        }
    }
}

function abrirSeleccionado() {
    if (!itemSeleccionado) return;
    if (itemSeleccionado.esCarpeta) {
        navegarA(itemSeleccionado.ruta);
    } else {
        abrirArchivo(itemSeleccionado.ruta);
    }
}

async function eliminarDefinitivoDePapelera() {
    if (!itemSeleccionado) return;
    const nombre = itemSeleccionado.nombre;

    const result = await Swal.fire({
        title: '¿Eliminar definitivamente?',
        html: `<b>${nombre}</b><br>Esta acción no se puede deshacer.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d93025',
        confirmButtonText: 'Eliminar definitivamente',
        cancelButtonText: 'Cancelar'
    });
    if (!result.isConfirmed) return;

    try {
        Swal.fire({
            title: 'Eliminando...',
            allowOutsideClick: false,
            didOpen: () => Swal.showLoading()
        });

        const response = await fetch(`${API_BASE}/papelera/eliminar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ruta: itemSeleccionado.ruta })
        });
        const data = await response.json();

        if (data.success) {
            itemSeleccionado = null;
            await new Promise(resolve => setTimeout(resolve, 300));
            Swal.fire({
                icon: 'success',
                title: 'Eliminado definitivamente',
                text: nombre,
                timer: 1500,
                showConfirmButton: false
            });
            await cargarArchivos(rutaActual, true);
        } else {
            Swal.fire('Error', data.error || 'No se pudo eliminar', 'error');
        }
    } catch (error) {
        Swal.fire('Error', 'No se pudo eliminar', 'error');
    }
}

function descargarSeleccionado() {
    if (!itemSeleccionado) return;
    window.location.href = `${API_BASE}/archivos/descargar?ruta=${encodeURIComponent(itemSeleccionado.ruta)}`;
}

async function eliminarSeleccionado() {
    if (!itemSeleccionado) return;

    // En la vista Papelera el borrado es DEFINITIVO (endpoint distinto):
    // el DELETE genérico de /archivos daba 404 porque el item ya no existe
    // en files/, vive en el trashbin (video reportado 2026-07-01).
    const enPapelera = (typeof vistaActual !== 'undefined' && vistaActual === 'papelera')
        || (typeof rutaActual !== 'undefined' && String(rutaActual).replace(/\/$/, '') === '/papelera');
    if (enPapelera) {
        await eliminarDefinitivoDePapelera();
        return;
    }

    const result = await Swal.fire({
        title: '¿Mover a la papelera?',
        text: itemSeleccionado.nombre,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d93025',
        confirmButtonText: 'Mover a la papelera',
        cancelButtonText: 'Cancelar'
    });

    if (result.isConfirmed) {
        const nombreEliminado = itemSeleccionado.nombre;

        try {
            // Mostrar indicador de carga
            Swal.fire({
                title: 'Eliminando...',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading()
            });

            const response = await fetch(
                `${API_BASE}/archivos?ruta=${encodeURIComponent(itemSeleccionado.ruta)}`,
                { method: 'DELETE' }
            );
            const data = await response.json();

            if (data.success) {
                // Limpiar selección
                itemSeleccionado = null;

                // Pequeño delay para que Nextcloud procese el cambio
                await new Promise(resolve => setTimeout(resolve, 300));

                // Mostrar éxito
                Swal.fire({
                    icon: 'success',
                    title: 'Movido a la papelera',
                    text: nombreEliminado,
                    timer: 1500,
                    showConfirmButton: false
                });

                // Refrescar lista - FIX 2026-01-27: Forzar recarga para invalidar caché
                await cargarArchivos(rutaActual, true);
            } else {
                Swal.fire('Error', data.error, 'error');
            }
        } catch (error) {
            Swal.fire('Error', 'No se pudo eliminar', 'error');
        }
    }
}

async function renombrarSeleccionado() {
    console.log('[Nube Maquita] Renombrar - itemSeleccionado:', itemSeleccionado);
    if (!itemSeleccionado) {
        console.log('[Nube Maquita] No hay item seleccionado');
        Swal.fire('Aviso', 'Selecciona un archivo o carpeta primero', 'info');
        return;
    }

    const { value: nuevoNombre } = await Swal.fire({
        title: 'Cambiar nombre',
        input: 'text',
        inputValue: itemSeleccionado.nombre,
        showCancelButton: true,
        confirmButtonText: 'Cambiar nombre',
        cancelButtonText: 'Cancelar'
    });

    if (nuevoNombre && nuevoNombre !== itemSeleccionado.nombre) {
        console.log('[Nube Maquita] Renombrando:', itemSeleccionado.ruta, '->', nuevoNombre);
        try {
            // Mostrar indicador de carga
            Swal.fire({
                title: 'Renombrando...',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading()
            });

            const response = await fetch(`${API_BASE}/archivos/renombrar`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ruta: itemSeleccionado.ruta,
                    nuevo_nombre: nuevoNombre
                })
            });
            const data = await response.json();
            console.log('[Nube Maquita] Respuesta renombrar:', data);

            if (data.success) {
                // Pequeño delay para que Nextcloud procese el cambio
                await new Promise(resolve => setTimeout(resolve, 300));

                Swal.fire({
                    icon: 'success',
                    title: 'Renombrado',
                    text: nuevoNombre,
                    timer: 1500,
                    showConfirmButton: false
                });
                invalidarCache(rutaActual);
                cargarArchivos(rutaActual);
            } else {
                Swal.fire('Error', data.error || 'No se pudo renombrar', 'error');
            }
        } catch (error) {
            console.error('[Nube Maquita] Error renombrando:', error);
            Swal.fire('Error', 'No se pudo renombrar: ' + error.message, 'error');
        }
    }
}

async function compartirSeleccionado() {
    // FIX 2026-07-03: cerrar el menu contextual antes de abrir el modal
    document.getElementById('contextMenu')?.classList.remove('show');
    cerrarSubmenus();
    // Usar el nuevo modal de compartir estilo Google Drive
    abrirModalCompartir(itemSeleccionado);
}

async function copiarLinkSeleccionado() {
    if (!itemSeleccionado) return;

    // En el motor propio ofrecemos expiración y clave (lo que Drive cobra en planes pagos).
    let extras = {};
    if (typeof MODO_ALMACEN !== 'undefined' && MODO_ALMACEN) {
        const cfg = await Swal.fire({
            title: 'Enlace público',
            html: `
                <div style="text-align:left">
                    <label>Expira en (días, 0 = nunca)</label>
                    <input id="lnkDias" type="number" min="0" value="0" class="swal2-input" style="margin:4px 0">
                    <label>Clave (opcional)</label>
                    <input id="lnkClave" type="text" class="swal2-input" style="margin:4px 0" placeholder="sin clave">
                    <label style="display:flex;gap:8px;align-items:center;margin-top:8px">
                        <input id="lnkDescarga" type="checkbox" checked> Permitir descargar/copiar
                    </label>
                </div>`,
            showCancelButton: true, confirmButtonText: 'Generar enlace', cancelButtonText: 'Cancelar',
            preConfirm: () => ({
                expira_dias: parseInt(document.getElementById('lnkDias').value) || 0,
                clave: document.getElementById('lnkClave').value || '',
                permite_descarga: document.getElementById('lnkDescarga').checked
            })
        });
        if (!cfg.isConfirmed) return;
        extras = cfg.value;
    }

    try {
        Swal.fire({
            title: 'Generando enlace...',
            allowOutsideClick: false,
            didOpen: () => { Swal.showLoading(); }
        });

        const response = await fetch(`${API_BASE}/compartir`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ruta: itemSeleccionado.ruta,
                tipo: 3,  // Enlace público
                permisos: 1,  // Solo lectura
                ...extras
            })
        });
        const data = await response.json();

        if (data.success && data.compartido) {
            // SIEMPRE construir URL del sistema central, NUNCA usar URL de Nextcloud
            // Usar las funciones helper definidas en el modal de compartir
            const token = data.compartido.token ||
                          (data.compartido.url_publica || data.compartido.url || '').match(/\/s\/([a-zA-Z0-9]+)/)?.[1];

            if (!token) {
                Swal.fire('Error', 'No se pudo obtener el token del enlace', 'error');
                return;
            }

            // Construir URL de compartido sobre el dominio actual
            const urlEnlace = `${window.location.origin}/archivos/s/${token}`;

            // Copiar al portapapeles
            await navigator.clipboard.writeText(urlEnlace);

            await Swal.fire({
                icon: 'success',
                title: 'Enlace copiado',
                html: `
                    <p>El enlace se copió al portapapeles:</p>
                    <div class="bg-light p-2 rounded" style="word-break: break-all; font-size: 12px;">
                        ${urlEnlace}
                    </div>
                `,
                confirmButtonText: 'Aceptar',
                confirmButtonColor: '#0061a1'
            });
        } else {
            console.error('Respuesta compartir:', data);
            Swal.fire('Error', data.error || 'No se pudo generar el enlace', 'error');
        }
    } catch (error) {
        console.error('Error generando enlace:', error);
        Swal.fire('Error', 'No se pudo generar el enlace: ' + error.message, 'error');
    }
}

async function moverSeleccionado() {
    cerrarSubmenus();
    document.getElementById('contextMenu').classList.remove('show');

    if (!itemSeleccionado) return;

    try {
        Swal.fire({ title: 'Cargando carpetas...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });

        const opcionesHtml = await _construirArbolCarpetas();

        const { value: destinoSeleccionado } = await Swal.fire({
            title: '<span class="material-icons" style="vertical-align:middle;margin-right:8px;">drive_file_move</span>Mover a',
            html: '<div class="text-start">'
                + '<p style="margin-bottom:12px;">Mover: <strong>' + itemSeleccionado.nombre + '</strong></p>'
                + '<p style="font-size:12px;color:#666;margin-bottom:8px;">Selecciona la carpeta destino:</p>'
                + opcionesHtml
                + '</div>',
            showCancelButton: true,
            confirmButtonText: 'Mover aqu\u00ed',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#0061a1',
            width: 450,
            preConfirm: () => {
                const sel = document.querySelector('#swal-tree .move-folder-item.selected');
                if (!sel) { Swal.showValidationMessage('Selecciona una carpeta'); return false; }
                return sel.dataset.ruta;
            }
        });

        if (destinoSeleccionado) {
            let rutaDestino = destinoSeleccionado;
            if (!rutaDestino.endsWith('/')) rutaDestino += '/';
            rutaDestino += itemSeleccionado.nombre;

            if (rutaDestino === itemSeleccionado.ruta) {
                Swal.fire('Aviso', 'El archivo ya est\u00e1 en esa ubicaci\u00f3n', 'warning');
                return;
            }

            Swal.fire({ title: 'Moviendo...', allowOutsideClick: false, didOpen: () => { Swal.showLoading(); } });

            const moveResponse = await fetch(`${API_BASE}/archivos/mover`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ origen: itemSeleccionado.ruta, destino: rutaDestino })
            });
            const moveData = await moveResponse.json();

            if (moveData.success) {
                Swal.fire('Movido', '"' + itemSeleccionado.nombre + '" se movi\u00f3 correctamente', 'success');
                cargarArchivos(rutaActual, true);
            } else {
                Swal.fire('Error', moveData.error || 'No se pudo mover', 'error');
            }
        }
    } catch (error) {
        console.error('Error moviendo:', error);
        Swal.fire('Error', 'No se pudo mover: ' + error.message, 'error');
    }
}

async function _cargarHijosCarpeta(ruta) {
    try {
        const resp = await fetch(`${API_BASE}/archivos?ruta=${encodeURIComponent(ruta)}`);
        const data = await resp.json();
        if (!data.success || !data.carpetas) return [];
        return data.carpetas.map(c => ({ ruta: c.ruta_completa || c.ruta, nombre: c.nombre, folder_id: c.folder_id || c.file_id || c.id || '', color: c.color || '' }));
    } catch { return []; }
}

function _renderNodoCarpeta(ruta, nombre, nivel) {
    const indent = 8 + nivel * 16;
    const iconColor = nivel === 0 ? '#0061a1' : '#f6a623';
    const r = String(ruta).replace(/"/g, '&quot;');
    return '<div class="tree-node" data-ruta="' + r + '" data-nivel="' + nivel + '">'
        + '<div class="move-folder-item" data-ruta="' + r + '" onclick="_seleccionarCarpetaMover(this)" '
        +   'style="padding:6px 10px;padding-left:' + indent + 'px;cursor:pointer;display:flex;align-items:center;gap:4px;border-radius:4px;" '
        +   'onmouseover="if(!this.classList.contains(\'selected\'))this.style.background=\'#f5f5f5\'" '
        +   'onmouseout="if(!this.classList.contains(\'selected\'))this.style.background=\'\'">'
        +   '<span class="tree-toggle material-icons" onclick="event.stopPropagation();_toggleCarpetaArbol(this)" '
        +     'style="font-size:18px;color:#888;cursor:pointer;width:18px;text-align:center;">chevron_right</span>'
        +   '<span class="material-icons" style="font-size:18px;color:' + iconColor + ';">folder</span>'
        +   '<span style="font-size:13px;">' + nombre + '</span>'
        + '</div>'
        + '<div class="tree-children" data-loaded="0" style="display:none;"></div>'
        + '</div>';
}

async function _toggleCarpetaArbol(toggleEl) {
    const node = toggleEl.closest('.tree-node');
    if (!node) return;
    const children = node.querySelector(':scope > .tree-children');
    const ruta = node.dataset.ruta;
    const nivel = parseInt(node.dataset.nivel || '0', 10);
    if (children.style.display === 'none') {
        if (children.dataset.loaded === '0') {
            toggleEl.textContent = 'hourglass_empty';
            const hijos = await _cargarHijosCarpeta(ruta);
            if (hijos.length === 0) {
                children.innerHTML = '<div style="padding:4px 10px;padding-left:' + (8 + (nivel + 1) * 16) + 'px;font-size:12px;color:#aaa;">(sin subcarpetas)</div>';
            } else {
                children.innerHTML = hijos.map(h => _renderNodoCarpeta(h.ruta, h.nombre, nivel + 1)).join('');
            }
            children.dataset.loaded = '1';
        }
        children.style.display = 'block';
        toggleEl.textContent = 'expand_more';
    } else {
        children.style.display = 'none';
        toggleEl.textContent = 'chevron_right';
    }
}

async function _construirArbolCarpetas() {
    const raiz = await _cargarHijosCarpeta('/');
    let html = '<div id="swal-tree" style="max-height:320px;overflow-y:auto;border:1px solid #dee2e6;border-radius:6px;padding:4px;text-align:left;">';
    html += '<div class="move-folder-item selected" data-ruta="/" onclick="_seleccionarCarpetaMover(this)" style="padding:6px 10px;cursor:pointer;display:flex;align-items:center;gap:6px;border-radius:4px;background:#e3f2fd;">'
        + '<span class="material-icons" style="font-size:18px;color:#0061a1;">home</span>'
        + '<span style="font-size:13px;">/ (Raíz)</span></div>';
    html += raiz.map(c => _renderNodoCarpeta(c.ruta, c.nombre, 0)).join('');
    html += '</div>';
    return html;
}

function _seleccionarCarpetaMover(el) {
    document.querySelectorAll('#swal-tree .move-folder-item').forEach(i => {
        i.classList.remove('selected');
        i.style.background = '';
    });
    el.classList.add('selected');
    el.style.background = '#e3f2fd';
}

// Copiar archivo/carpeta a otra ubicacion
async function copiarSeleccionado() {
    document.getElementById('contextMenu').classList.remove('show');

    if (!itemSeleccionado) return;

    try {
        // FIX 2026-06-09: cargar el ARBOL de carpetas (recursivo), igual que "Mover a".
        // Antes solo pedia la raiz y filtraba el campo equivocado (data.archivos) -> no mostraba carpetas.
        Swal.fire({ title: 'Cargando carpetas...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
        const opcionesHtml = await _construirArbolCarpetas();

        const result = await Swal.fire({
            title: '<span class="material-icons" style="vertical-align:middle;margin-right:8px;">content_copy</span>Copiar a',
            html: '<p style="margin-bottom:12px;">Selecciona la carpeta destino:</p>'
                + opcionesHtml,
            showCancelButton: true,
            confirmButtonText: 'Copiar aqui',
            cancelButtonText: 'Cancelar',
            preConfirm: () => {
                const sel = document.querySelector('#swal-tree .move-folder-item.selected');
                if (!sel) { Swal.showValidationMessage('Selecciona una carpeta'); return false; }
                return { destino: sel.dataset.ruta };
            }
        });

        if (result.isConfirmed) {
            const destino = result.value.destino === '/'
                ? '/' + itemSeleccionado.nombre
                : result.value.destino + '/' + itemSeleccionado.nombre;

            Swal.fire({ title: 'Copiando...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

            const copyResponse = await fetch(`${API_BASE}/archivos/copiar`, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ origen: itemSeleccionado.ruta, destino: destino })
            });
            const copyData = await copyResponse.json();

            if (copyData.success) {
                Swal.fire({ icon: 'success', title: 'Copiado', text: itemSeleccionado.nombre, timer: 1500, showConfirmButton: false });
                await cargarArchivos(rutaActual, true);
            } else {
                Swal.fire('Error', copyData.error || 'No se pudo copiar', 'error');
            }
        }
    } catch (error) {
        Swal.fire('Error', 'No se pudo copiar: ' + error.message, 'error');
    }
}

// Seleccionar todos los archivos visibles
function seleccionarTodosVisible() {
    seleccionarTodo();
    mostrarNotificacion(elementosSeleccionados.length + ' elementos seleccionados', 'info');
}


async function toggleFavorito() {
    // Cerrar menús
    cerrarSubmenus();
    document.getElementById('contextMenu').classList.remove('show');

    if (!itemSeleccionado) return;

    try {
        const response = await fetch(`${API_BASE}/archivos/favorito`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ruta: itemSeleccionado.ruta
            })
        });
        const data = await response.json();

        if (data.success) {
            const esFavorito = data.es_favorito;
            Swal.fire({
                icon: 'success',
                title: esFavorito ? 'Agregado a Destacados' : 'Removido de Destacados',
                text: `"${itemSeleccionado.nombre}" ${esFavorito ? 'ahora está en Destacados' : 'ya no está en Destacados'}`,
                timer: 2000,
                showConfirmButton: false
            });
            invalidarCache(rutaActual);
            cargarArchivos(rutaActual);
        } else {
            Swal.fire('Error', data.error || 'No se pudo actualizar Destacados', 'error');
        }
    } catch (error) {
        console.error('Error cambiando destacado:', error);
        Swal.fire('Error', 'No se pudo actualizar Destacados: ' + error.message, 'error');
    }
}

// -----------------------------------------------------------------------------
// Menú Nuevo
// -----------------------------------------------------------------------------

function toggleNewMenu() {
    document.getElementById('newMenu').classList.toggle('show');
}

async function crearCarpeta() {
    document.getElementById('newMenu').classList.remove('show');

    const { value: nombre } = await Swal.fire({
        title: 'Carpeta nueva',
        input: 'text',
        inputPlaceholder: 'Carpeta sin título',
        showCancelButton: true,
        confirmButtonText: 'Crear',
        cancelButtonText: 'Cancelar',
        inputValidator: (value) => {
            if (!value) return 'El nombre es requerido';
        }
    });

    if (nombre) {
        try {
            // Mostrar indicador de carga
            Swal.fire({
                title: 'Creando carpeta...',
                allowOutsideClick: false,
                didOpen: () => Swal.showLoading()
            });

            const response = await fetch(`${API_BASE}/carpetas`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ruta: rutaActual,
                    nombre: nombre
                })
            });
            const data = await response.json();

            if (data.success) {
                // Pequeño delay para que Nextcloud procese el cambio
                await new Promise(resolve => setTimeout(resolve, 300));

                // Mostrar éxito
                Swal.fire({
                    icon: 'success',
                    title: 'Carpeta creada',
                    text: nombre,
                    timer: 1500,
                    showConfirmButton: false
                });

                // Invalidar caché y refrescar lista
                invalidarCache(rutaActual);
                await cargarArchivos(rutaActual);
            } else {
                Swal.fire('Error', data.error, 'error');
            }
        } catch (error) {
            Swal.fire('Error', 'No se pudo crear la carpeta', 'error');
        }
    }
}

async function crearDocumento(tipo) {
    document.getElementById('newMenu').classList.remove('show');

    // Definir extensiones y nombres por tipo
    const tipos = {
        'documento': { extension: 'docx', nombre: 'Documento', icono: 'fa-file-word', color: '#2b579a' },
        'hoja': { extension: 'xlsx', nombre: 'Hoja de cálculo', icono: 'fa-file-excel', color: '#217346' },
        'presentacion': { extension: 'pptx', nombre: 'Presentación', icono: 'fa-file-powerpoint', color: '#b7472a' },
        'texto': { extension: 'txt', nombre: 'Archivo de texto', icono: 'fa-file-alt', color: '#6c757d' },
        'diagrama': { extension: 'drawio', nombre: 'Diagrama', icono: 'fa-project-diagram', color: '#f08705' }
    };

    const tipoInfo = tipos[tipo] || tipos['texto'];

    const { value: nombre } = await Swal.fire({
        title: `<i class="fas ${tipoInfo.icono} me-2" style="color: ${tipoInfo.color}"></i>Nuevo ${tipoInfo.nombre}`,
        input: 'text',
        inputPlaceholder: `${tipoInfo.nombre} sin título`,
        inputValue: `Nuevo ${tipoInfo.nombre}`,
        showCancelButton: true,
        confirmButtonText: '<i class="fas fa-plus me-2"></i>Crear',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#0061a1',
        inputValidator: (value) => {
            if (!value) return 'El nombre es requerido';
        }
    });

    if (nombre) {
        try {
            Swal.fire({
                title: 'Creando documento...',
                allowOutsideClick: false,
                didOpen: () => { Swal.showLoading(); }
            });

            // Crear archivo vacío con la extensión correcta
            const nombreArchivo = nombre.includes('.') ? nombre : `${nombre}.${tipoInfo.extension}`;
            const rutaCompleta = rutaActual === '/' ? `/${nombreArchivo}` : `${rutaActual}/${nombreArchivo}`;

            const response = await fetch(`${API_BASE}/archivos/crear`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ruta: rutaCompleta,
                    tipo: tipo
                })
            });
            const data = await response.json();

            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Documento creado',
                    text: `"${nombreArchivo}" se creó correctamente`,
                    showCancelButton: true,
                    confirmButtonText: '<i class="fas fa-edit me-2"></i>Abrir editor',
                    cancelButtonText: 'Cerrar',
                    confirmButtonColor: '#0061a1'
                }).then((result) => {
                    if (result.isConfirmed) {
                        // Abrir en el editor correspondiente
                        if (tipo === 'diagrama') {
                            _abrirEditorNube(rutaCompleta, 'diagrama');
                        } else if (['documento', 'hoja', 'presentacion'].includes(tipo)) {
                            _abrirEditorNube(rutaCompleta);
                        }
                    }
                });
                invalidarCache(rutaActual);
                cargarArchivos(rutaActual);
            } else {
                Swal.fire('Error', data.error || 'No se pudo crear el documento', 'error');
            }
        } catch (error) {
            console.error('Error creando documento:', error);
            Swal.fire('Error', 'No se pudo crear el documento: ' + error.message, 'error');
        }
    }
}

// -----------------------------------------------------------------------------
// Subir archivos
// -----------------------------------------------------------------------------

async function subirArchivos(files) {
    const panel = document.getElementById('uploadPanel');
    const items = document.getElementById('uploadItems');
    const title = document.getElementById('uploadTitle');
    const counter = document.getElementById('uploadCounter');
    const progressCircle = document.getElementById('uploadProgressCircle');
    const circleProgress = document.getElementById('uploadCircleProgress');
    const circleText = document.getElementById('uploadCircleText');

    // Determinar carpeta destino - en vistas especiales subir a la raíz
    const vistasEspeciales = ['recientes', 'favoritos', 'papelera', 'compartidos'];
    let carpetaDestino = rutaActual;

    if (vistasEspeciales.includes(vistaActual) || rutaActual.startsWith('/recientes') ||
        rutaActual.startsWith('/favoritos') || rutaActual.startsWith('/papelera') ||
        rutaActual.startsWith('/compartidos')) {
        carpetaDestino = '/';
        Swal.fire({
            icon: 'info',
            title: 'Subiendo a la raíz',
            text: 'Los archivos se subirán a tu carpeta principal',
            timer: 2000,
            showConfirmButton: false
        });
    }

    // Inicializar panel
    panel.classList.add('show');
    title.textContent = `Subiendo ${files.length} archivo${files.length > 1 ? 's' : ''}`;
    items.innerHTML = '';

    // Inicializar círculo de progreso
    progressCircle.className = 'gd-upload-progress-circle uploading';
    circleProgress.style.strokeDasharray = '0, 100';
    circleText.textContent = '0%';

    let archivosSubidos = 0;
    let archivosError = 0;
    const totalArchivos = files.length;

    // Actualizar contador
    counter.textContent = `0 de ${totalArchivos} archivos`;

    // Preparar todos los items del panel primero
    const fileItems = [];
    for (const file of files) {
        const itemId = 'upload_' + Date.now() + '_' + Math.floor(Math.random() * 100000);
        items.innerHTML += `
            <div class="gd-upload-item" id="${itemId}">
                <span class="material-icons">hourglass_empty</span>
                <span class="gd-upload-item-name">${file.name}</span>
                <div class="gd-upload-item-progress">
                    <div class="bar"><div class="fill" style="width: 0%"></div></div>
                </div>
            </div>
        `;
        fileItems.push({ file, itemId });
    }

    // Función para actualizar progreso
    function actualizarProgreso() {
        const procesados = archivosSubidos + archivosError;
        const porcentaje = Math.round((procesados / totalArchivos) * 100);
        circleProgress.style.strokeDasharray = `${porcentaje}, 100`;
        circleText.textContent = `${porcentaje}%`;
        counter.textContent = `${procesados} de ${totalArchivos} archivos`;
    }

    // Subir un archivo individual
    async function subirUnArchivo({ file, itemId }) {
        const formData = new FormData();
        formData.append('archivo', file);
        formData.append('carpeta', carpetaDestino);

        try {
            // FIX 2026-07-03: con reintentos ante errores transitorios
            const response = await fetchConReintento(`${API_BASE}/archivos`, {
                method: 'POST',
                body: formData
            }, 3);

            const itemElement = document.getElementById(itemId);
            const fill = itemElement ? itemElement.querySelector('.fill') : null;
            const icon = itemElement ? itemElement.querySelector('.material-icons') : null;

            if (response.status === 413) {
                archivosError++;
                if (fill) { fill.style.width = '100%'; fill.style.background = '#ea4335'; }
                if (icon) icon.textContent = 'error';
                if (itemElement) itemElement.classList.add('error');
            } else {
                let data;
                try {
                    data = await response.json();
                } catch (parseErr) {
                    throw new Error(`Error del servidor (HTTP ${response.status})`);
                }

                if (data.success) {
                    archivosSubidos++;
                    if (fill) { fill.style.width = '100%'; fill.style.background = '#34a853'; }
                    if (icon) icon.textContent = 'check_circle';
                    if (itemElement) itemElement.classList.add('complete');
                } else {
                    archivosError++;
                    if (fill) { fill.style.width = '100%'; fill.style.background = '#ea4335'; }
                    if (icon) icon.textContent = 'error';
                    if (itemElement) itemElement.classList.add('error');
                    const errMsg = data.error || 'Error desconocido';
                    if (errMsg.includes('permiso') || errMsg.includes('solo lectura') || response.status === 403) {
                        Swal.fire('Sin permisos', 'Esta carpeta fue compartida como solo lectura. Solicita al propietario que te otorgue permisos de edición.', 'warning');
                    }
                    console.error('[Nube Maquita] Error subiendo:', errMsg);
                }
            }
        } catch (error) {
            archivosError++;
            console.error('[Nube Maquita] Error en subida:', error);
            const itemElement = document.getElementById(itemId);
            const fill = itemElement ? itemElement.querySelector('.fill') : null;
            const icon = itemElement ? itemElement.querySelector('.material-icons') : null;
            if (fill) { fill.style.width = '100%'; fill.style.background = '#ea4335'; }
            if (icon) icon.textContent = 'error';
            if (itemElement) itemElement.classList.add('error');
        }
        actualizarProgreso();
    }

    // SUBIDA PARALELA: 3 archivos simultáneos para máxima velocidad
    const CONCURRENCIA = 3;
    for (let i = 0; i < fileItems.length; i += CONCURRENCIA) {
        const lote = fileItems.slice(i, i + CONCURRENCIA);
        await Promise.all(lote.map(item => subirUnArchivo(item)));
    }

    // Finalizar - mostrar estado final
    if (archivosError === 0) {
        progressCircle.className = 'gd-upload-progress-circle complete';
        title.textContent = `${archivosSubidos} archivo${archivosSubidos > 1 ? 's' : ''} subido${archivosSubidos > 1 ? 's' : ''}`;
    } else if (archivosSubidos === 0) {
        progressCircle.className = 'gd-upload-progress-circle error';
        title.textContent = 'Error al subir archivos';
    } else {
        progressCircle.className = 'gd-upload-progress-circle complete';
        title.textContent = `${archivosSubidos} subido${archivosSubidos > 1 ? 's' : ''}, ${archivosError} error${archivosError > 1 ? 'es' : ''}`;
    }

    counter.textContent = archivosError > 0 ? `${archivosError} con error` : 'Completado';

    setTimeout(() => {
        invalidarCache(rutaActual);
        cargarArchivos(rutaActual);
        // No cerrar automáticamente si hubo errores
        if (archivosError === 0) {
            panel.classList.remove('show');
        }
    }, 2000);
}

function cerrarUpload() {
    document.getElementById('uploadPanel').classList.remove('show');
}

// -----------------------------------------------------------------------------
// Cuota
// -----------------------------------------------------------------------------

async function cargarCuota() {
    try {
        const response = await fetch(`${API_BASE}/cuota`);
        const data = await response.json();

        if (data.success && data.cuota) {
            const porcentaje = data.cuota.porcentaje_usado || 0;
            const usado = data.cuota.usado_humano || '0 B';
            const total = data.cuota.total_humano || 'Sin límite';

            // Distribuir el porcentaje en segmentos (simulación)
            // En una implementación real, estos datos vendrían del backend
            const drivePercent = porcentaje * 0.7;  // 70% es Nube
            const emailPercent = porcentaje * 0.2;  // 20% es Email
            const otherPercent = porcentaje * 0.1;  // 10% es Otro

            // Actualizar barras segmentadas
            const driveBar = document.getElementById('storageBarDrive');
            const emailBar = document.getElementById('storageBarEmail');
            const otherBar = document.getElementById('storageBarOther');

            if (driveBar) driveBar.style.width = Math.max(drivePercent, 0.5) + '%';
            if (emailBar) emailBar.style.width = emailPercent + '%';
            if (otherBar) otherBar.style.width = otherPercent + '%';

            document.getElementById('storageText').textContent = `${usado} de ${total} usado`;
        } else {
            document.getElementById('storageText').textContent = 'No disponible';
            console.warn('Cuota no disponible:', data.error || 'Sin datos');
        }
    } catch (error) {
        document.getElementById('storageText').textContent = 'Error al cargar';
        console.error('Error cargando cuota:', error);
    }
}

function liberarEspacio() {
    Swal.fire({
        title: '<i class="fas fa-broom me-2"></i>Liberar espacio',
        html: `
            <div class="text-start">
                <p class="text-muted mb-3">Sugerencias para liberar espacio en tu ${window.DRIVE_NAME||'Nube Maquita'}:</p>
                <div class="list-group list-group-flush">
                    <a href="#" class="list-group-item list-group-item-action d-flex align-items-center" onclick="navegarA('/papelera')">
                        <span class="material-icons me-3 text-muted">delete</span>
                        <div>
                            <strong>Vaciar papelera</strong>
                            <small class="d-block text-muted">Los archivos en la papelera ocupan espacio</small>
                        </div>
                    </a>
                    <a href="#" class="list-group-item list-group-item-action d-flex align-items-center" onclick="buscarArchivosGrandes()">
                        <span class="material-icons me-3 text-muted">folder_special</span>
                        <div>
                            <strong>Archivos grandes</strong>
                            <small class="d-block text-muted">Revisar archivos que ocupan más espacio</small>
                        </div>
                    </a>
                    <a href="#" class="list-group-item list-group-item-action d-flex align-items-center" onclick="buscarDuplicados()">
                        <span class="material-icons me-3 text-muted">content_copy</span>
                        <div>
                            <strong>Archivos duplicados</strong>
                            <small class="d-block text-muted">Buscar y eliminar duplicados</small>
                        </div>
                    </a>
                </div>
            </div>
        `,
        showConfirmButton: false,
        showCloseButton: true,
        width: 450
    });
}

function buscarArchivosGrandes() {
    Swal.close();
    mostrarNotificacion('Buscando archivos grandes...', 'info');
    // Ordenar por tamaño descendente
    ordenarPor = 'tamano';
    ordenDir = 'desc';
    cargarArchivos(rutaActual);
}

function buscarDuplicados() {
    Swal.close();
    mostrarNotificacion('Función de búsqueda de duplicados próximamente disponible', 'info');
}

async function mostrarDetallesAlmacenamiento() {
    try {
        const response = await fetch(`${API_BASE}/cuota`);
        const data = await response.json();

        if (data.success && data.cuota) {
            const porcentaje = data.cuota.porcentaje_usado || 0;
            const usado = data.cuota.usado_humano || '0 B';
            const total = data.cuota.total_humano || 'Sin límite';
            const libre = data.cuota.libre_humano || total;

            Swal.fire({
                title: '<i class="fas fa-cloud me-2"></i>Almacenamiento',
                html: `
                    <div class="text-start">
                        <div class="mb-4">
                            <div class="progress" style="height: 8px; border-radius: 4px;">
                                <div class="progress-bar bg-primary" role="progressbar"
                                     style="width: ${porcentaje}%"></div>
                            </div>
                            <small class="text-muted mt-1 d-block">${porcentaje.toFixed(1)}% utilizado</small>
                        </div>
                        <div class="row text-center mb-3">
                            <div class="col-4">
                                <div class="fw-bold text-primary">${usado}</div>
                                <small class="text-muted">Usado</small>
                            </div>
                            <div class="col-4">
                                <div class="fw-bold text-success">${libre}</div>
                                <small class="text-muted">Disponible</small>
                            </div>
                            <div class="col-4">
                                <div class="fw-bold">${total}</div>
                                <small class="text-muted">Total</small>
                            </div>
                        </div>
                        <hr>
                        <p class="text-muted small mb-0">
                            <i class="fas fa-info-circle me-1"></i>
                            Tu almacenamiento en ${window.DRIVE_NAME||'Nube Maquita'} incluye todos tus archivos, carpetas y documentos compartidos.
                        </p>
                    </div>
                `,
                confirmButtonText: 'Entendido',
                confirmButtonColor: '#1a73e8',
                width: 400
            });
        } else {
            Swal.fire('Error', 'No se pudo obtener información de almacenamiento', 'error');
        }
    } catch (error) {
        console.error('Error:', error);
        Swal.fire('Error', 'Error al cargar información de almacenamiento', 'error');
    }
}

// -----------------------------------------------------------------------------
// Vista
// -----------------------------------------------------------------------------

function toggleVista() {
    vistaGrid = !vistaGrid;

    const mainGrid = document.getElementById('mainGrid');
    const list = document.getElementById('listView');
    const icon = document.getElementById('vistaIcon');

    if (vistaGrid) {
        if (mainGrid) mainGrid.style.display = 'flex';  // CORREGIDO: era 'grid', debe ser 'flex'
        list.classList.remove('active');
        icon.textContent = 'view_module';
    } else {
        if (mainGrid) mainGrid.style.display = 'none';
        list.classList.add('active');
        icon.textContent = 'view_list';
    }

    // Sincronizar botones de vista Google Drive
    actualizarBotonesVista();
}

// Función para cambiar vista estilo Google Drive
function cambiarVista(tipo) {
    const mainGrid = document.getElementById('mainGrid');
    const list = document.getElementById('listView');

    if (tipo === 'lista') {
        vistaGrid = false;
        if (mainGrid) mainGrid.style.display = 'none';
        list.classList.add('active');
    } else {
        vistaGrid = true;
        if (mainGrid) mainGrid.style.display = 'flex';  // CORREGIDO: era 'grid', debe ser 'flex'
        list.classList.remove('active');
    }

    actualizarBotonesVista();

    // Guardar preferencia de vista
    guardarPreferencias({ vista: vistaGrid ? 'cuadricula' : 'lista' });
}

// Actualizar estado visual de los botones de vista
function actualizarBotonesVista() {
    const btnList = document.getElementById('btnViewList');
    const btnGrid = document.getElementById('btnViewGrid');
    const icon = document.getElementById('vistaIcon');

    if (btnList && btnGrid) {
        if (vistaGrid) {
            btnList.classList.remove('active');
            btnGrid.classList.add('active');
        } else {
            btnList.classList.add('active');
            btnGrid.classList.remove('active');
        }
    }

    if (icon) {
        icon.textContent = vistaGrid ? 'view_module' : 'view_list';
    }
}

// -----------------------------------------------------------------------------
// Ordenamiento y Filtros
// -----------------------------------------------------------------------------

function cambiarOrdenamiento() {
    ordenarPor = document.getElementById('sortField').value;
    // Guardar preferencia
    guardarPreferencias({ orden_campo: ordenarPor });
    cargarArchivos(rutaActual);
}

function toggleOrden() {
    const btn = document.getElementById('sortDirection');
    ordenDir = ordenDir === 'desc' ? 'asc' : 'desc';

    if (ordenDir === 'desc') {
        btn.classList.add('desc');
        btn.title = 'Más reciente primero';
    } else {
        btn.classList.remove('desc');
        btn.title = 'Más antiguo primero';
    }

    // Guardar preferencia
    guardarPreferencias({ orden_dir: ordenDir });
    cargarArchivos(rutaActual);
}

// Ordenar lista por columna (estilo Google Drive)
let ordenColumna = 'nombre';
let ordenAscendente = true;

function ordenarLista(columna) {
    const headers = document.querySelectorAll('.gd-list th[data-sort]');

    // Si es la misma columna, invertir dirección
    if (ordenColumna === columna) {
        ordenAscendente = !ordenAscendente;
    } else {
        ordenColumna = columna;
        ordenAscendente = true;
    }

    // Actualizar estilos de encabezados
    headers.forEach(th => {
        th.classList.remove('sorted');
        const icon = th.querySelector('.sort-icon');
        if (icon) icon.textContent = 'arrow_upward';
    });

    const activeHeader = document.querySelector(`.gd-list th[data-sort="${columna}"]`);
    if (activeHeader) {
        activeHeader.classList.add('sorted');
        const icon = activeHeader.querySelector('.sort-icon');
        if (icon) icon.textContent = ordenAscendente ? 'arrow_upward' : 'arrow_downward';
    }

    // Mapear columna a campo del backend
    const mapeoColumnas = {
        'nombre': 'nombre',
        'propietario': 'nombre',
        'modificado': 'fecha',
        'tamano': 'tamano'
    };

    ordenarPor = mapeoColumnas[columna] || 'nombre';
    ordenDir = ordenAscendente ? 'asc' : 'desc';

    cargarArchivos(rutaActual);
}

// Acciones rápidas de fila
function compartirItem(tr) {
    const ruta = tr.dataset.ruta;
    const nombre = tr.dataset.nombre;
    itemSeleccionado = { ruta, ruta_completa: ruta, nombre, esCarpeta: tr.dataset.carpeta === 'true' };
    compartirSeleccionado();
}

function descargarItem(tr) {
    const ruta = tr.dataset.ruta;
    const nombre = tr.dataset.nombre;
    itemSeleccionado = { ruta, ruta_completa: ruta, nombre, esCarpeta: tr.dataset.carpeta === 'true' };
    descargarSeleccionado();
}

function filtrarPorTipo(tipo) {
    // Actualizar estado visual de los chips
    document.querySelectorAll('.gd-filter-chip').forEach(chip => {
        chip.classList.remove('active');
        if (chip.dataset.tipo === tipo) {
            chip.classList.add('active');
        }
    });

    filtroTipo = tipo === 'todos' ? null : tipo;
    cargarArchivos(rutaActual);
}

// Funciones de filtros dropdown estilo Google Drive
function mostrarFiltroTipo() {
    const opciones = [
        { valor: 'todos', label: 'Todos los tipos', icono: 'folder_open' },
        { valor: 'carpeta', label: 'Carpetas', icono: 'folder' },
        { valor: 'documento', label: 'Documentos', icono: 'description' },
        { valor: 'imagen', label: 'Imágenes', icono: 'image' },
        { valor: 'video', label: 'Videos', icono: 'videocam' },
        { valor: 'audio', label: 'Audio', icono: 'audiotrack' },
        { valor: 'pdf', label: 'PDF', icono: 'picture_as_pdf' },
        { valor: 'hoja', label: 'Hojas de cálculo', icono: 'grid_on' },
        { valor: 'presentacion', label: 'Presentaciones', icono: 'slideshow' },
        { valor: 'archivo', label: 'Archivos comprimidos', icono: 'archive' }
    ];
    mostrarDropdownFiltro('Tipo', opciones, filtroTipo || 'todos', (valor) => {
        filtroTipo = valor === 'todos' ? null : valor;
        cargarArchivos(rutaActual);
        actualizarBotonFiltro('Tipo', valor === 'todos' ? null : opciones.find(o => o.valor === valor)?.label);
    });
}

function mostrarFiltroPersonas() {
    const opciones = [
        { valor: 'todos', label: 'Cualquier persona', icono: 'people' },
        { valor: 'yo', label: 'De mi propiedad', icono: 'person' },
        { valor: 'compartido', label: 'Compartidos conmigo', icono: 'person_add' }
    ];
    mostrarDropdownFiltro('Personas', opciones, 'todos', (valor) => {
        // Por ahora solo filtramos visualmente, la lógica de backend se puede agregar después
        actualizarBotonFiltro('Personas', valor === 'todos' ? null : opciones.find(o => o.valor === valor)?.label);
    });
}

function mostrarFiltroModificado() {
    const opciones = [
        { valor: 'todos', label: 'En cualquier momento', icono: 'schedule' },
        { valor: 'hoy', label: 'Hoy', icono: 'today' },
        { valor: 'semana', label: 'Últimos 7 días', icono: 'date_range' },
        { valor: 'mes', label: 'Últimos 30 días', icono: 'calendar_month' },
        { valor: 'año', label: 'Este año', icono: 'event' }
    ];
    mostrarDropdownFiltro('Modificado', opciones, 'todos', (valor) => {
        // Por ahora solo filtramos visualmente
        actualizarBotonFiltro('Modificado', valor === 'todos' ? null : opciones.find(o => o.valor === valor)?.label);
    });
}

function mostrarFiltroFuente() {
    const opciones = [
        { valor: 'todos', label: 'Cualquier fuente', icono: 'source' },
        { valor: 'nube', label: (window.DRIVE_NAME||'Nube Maquita'), icono: 'cloud' },
        { valor: 'subido', label: 'Subido por mí', icono: 'upload' },
        { valor: 'compartido', label: 'Compartido conmigo', icono: 'share' },
        { valor: 'sincronizado', label: 'Sincronizado desde ordenador', icono: 'computer' }
    ];
    mostrarDropdownFiltro('Fuente', opciones, 'todos', (valor) => {
        // Por ahora solo filtramos visualmente
        actualizarBotonFiltro('Fuente', valor === 'todos' ? null : opciones.find(o => o.valor === valor)?.label);
    });
}

// Función genérica para mostrar dropdown de filtro
function mostrarDropdownFiltro(titulo, opciones, valorActual, onSelect) {
    // Cerrar cualquier dropdown existente
    cerrarDropdownFiltro();

    // Encontrar el botón que activó el dropdown
    const btn = event.target.closest('.gd-filter-btn');
    if (!btn) return;

    const rect = btn.getBoundingClientRect();

    // Crear el dropdown
    const dropdown = document.createElement('div');
    dropdown.className = 'gd-filter-dropdown';
    dropdown.style.position = 'fixed';
    dropdown.style.top = (rect.bottom + 4) + 'px';
    dropdown.style.left = rect.left + 'px';
    dropdown.style.zIndex = '10000';

    let html = `<div class="gd-dropdown-header">${titulo}</div>`;
    opciones.forEach(op => {
        const activo = op.valor === valorActual ? 'active' : '';
        html += `
            <div class="gd-dropdown-item ${activo}" data-valor="${op.valor}">
                <span class="material-icons">${op.icono}</span>
                <span>${op.label}</span>
                ${activo ? '<span class="material-icons check">check</span>' : ''}
            </div>
        `;
    });

    dropdown.innerHTML = html;
    document.body.appendChild(dropdown);

    // Agregar eventos a las opciones
    dropdown.querySelectorAll('.gd-dropdown-item').forEach(item => {
        item.addEventListener('click', () => {
            onSelect(item.dataset.valor);
            cerrarDropdownFiltro();
        });
    });

    // Cerrar al hacer clic fuera
    setTimeout(() => {
        document.addEventListener('click', cerrarDropdownFiltroHandler);
    }, 10);
}

function cerrarDropdownFiltroHandler(e) {
    if (!e.target.closest('.gd-filter-dropdown') && !e.target.closest('.gd-filter-btn')) {
        cerrarDropdownFiltro();
    }
}

function cerrarDropdownFiltro() {
    const dropdown = document.querySelector('.gd-filter-dropdown');
    if (dropdown) {
        dropdown.remove();
    }
    document.removeEventListener('click', cerrarDropdownFiltroHandler);
}

function actualizarBotonFiltro(filtro, valor) {
    const botones = document.querySelectorAll('.gd-filter-btn');
    botones.forEach(btn => {
        const texto = btn.textContent.trim().split('\n')[0].trim();
        if (texto.startsWith(filtro) || texto === filtro) {
            const span = btn.querySelector('span:not(.material-icons)') || btn.childNodes[0];
            if (valor) {
                btn.classList.add('active');
                if (span && span.nodeType === Node.TEXT_NODE) {
                    span.textContent = `${filtro}: ${valor}`;
                } else {
                    btn.firstChild.textContent = `${filtro}: ${valor}`;
                }
            } else {
                btn.classList.remove('active');
                if (span && span.nodeType === Node.TEXT_NODE) {
                    span.textContent = filtro;
                } else {
                    btn.firstChild.textContent = filtro;
                }
            }
        }
    });
}

// Inicializar controles de ordenamiento al cargar la página
function inicializarControlesOrden() {
    const sortField = document.getElementById('sortField');
    const sortBtn = document.getElementById('sortDirection');

    if (sortField) {
        sortField.value = ordenarPor;
    }

    if (sortBtn) {
        if (ordenDir === 'desc') {
            sortBtn.classList.add('desc');
        } else {
            sortBtn.classList.remove('desc');
        }
    }

    // Activar chip "Todos" por defecto
    const todosChip = document.querySelector('.gd-filter-chip[data-tipo="todos"]');
    if (todosChip) {
        todosChip.classList.add('active');
    }
}



// === PAPELERA: Restaurar archivos ===
async function restaurarSeleccionado() {
    document.getElementById("contextMenu").classList.remove("show");
    
    if (elementosSeleccionados.length === 0) {
        mostrarNotificacion("Selecciona un elemento para restaurar", "warning");
        return;
    }
    
    const nombre = elementosSeleccionados.length === 1 
        ? elementosSeleccionados[0].nombre 
        : elementosSeleccionados.length + " elementos";
    
    const result = await Swal.fire({
        title: "Restaurar",
        text: "¿Restaurar \"" + nombre + "\" a su ubicación original?",
        icon: "question",
        showCancelButton: true,
        confirmButtonText: "Restaurar",
        cancelButtonText: "Cancelar",
        confirmButtonColor: "#0061a1"
    });
    
    if (!result.isConfirmed) return;
    
    let exitos = 0;
    let errores = 0;
    
    for (const elem of elementosSeleccionados) {
        try {
            const ruta = elem.ruta_completa || elem.ruta;
            const resp = await fetch(API_BASE + "/papelera/restaurar", {
                method: "POST",
                headers: {"Content-Type": "application/json"},
                body: JSON.stringify({ruta: ruta})
            });
            if (resp.ok) {
                exitos++;
            } else {
                errores++;
                console.error("Error restaurando:", elem.nombre, await resp.text());
            }
        } catch (e) {
            errores++;
            console.error("Error restaurando:", elem.nombre, e);
        }
    }
    
    if (exitos > 0) {
        mostrarNotificacion(
            exitos === 1 ? "Archivo restaurado correctamente" : exitos + " archivos restaurados",
            "success"
        );
    }
    if (errores > 0) {
        mostrarNotificacion(errores + " archivo(s) no se pudieron restaurar", "error");
    }
    
    elementosSeleccionados = [];
    cargarArchivos(rutaActual);
}

// === PAPELERA: Vaciar papelera completa ===
async function vaciarPapelera() {
    const result = await Swal.fire({
        title: "¿Vaciar papelera?",
        text: "Se eliminarán permanentemente todos los archivos. Esta acción no se puede deshacer.",
        icon: "warning",
        showCancelButton: true,
        confirmButtonText: "Vaciar papelera",
        cancelButtonText: "Cancelar",
        confirmButtonColor: "#d33"
    });
    
    if (!result.isConfirmed) return;
    
    try {
        const resp = await fetch(API_BASE + "/papelera/vaciar", {
            method: "POST",
            headers: {"Content-Type": "application/json"}
        });
        if (resp.ok) {
            mostrarNotificacion("Papelera vaciada", "success");
            cargarArchivos(rutaActual);
        } else {
            mostrarNotificacion("Error al vaciar la papelera", "error");
        }
    } catch (e) {
        mostrarNotificacion("Error al vaciar la papelera", "error");
    }
}
