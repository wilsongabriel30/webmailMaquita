// -----------------------------------------------------------------------------
// Sistema de Preferencias Persistentes
// -----------------------------------------------------------------------------

let preferenciasUsuario = {
    vista: 'cuadricula',
    orden_campo: 'nombre',   // nombre por defecto (igual que Nextcloud)
    orden_dir: 'asc',        // ascendente (1-2-3, A-B-C)
    items_por_pagina: 20,
    ultima_ruta: '/',
    scroll_position: 0
};

// Cargar preferencias del servidor
async function cargarPreferencias() {
    try {
        const response = await fetch(`${API_BASE}/preferencias`);
        const data = await response.json();
        if (data.success && data.preferencias) {
            preferenciasUsuario = { ...preferenciasUsuario, ...data.preferencias };
            console.log('[Nube Maquita] Preferencias cargadas:', preferenciasUsuario);
        }
    } catch (error) {
        console.warn('[Nube Maquita] No se pudieron cargar preferencias:', error);
    }
}

// Guardar preferencias en el servidor (debounced)
let timeoutGuardarPrefs = null;
function guardarPreferencias(cambios = {}) {
    // Actualizar localmente
    preferenciasUsuario = { ...preferenciasUsuario, ...cambios };

    // Debounce para no hacer muchas llamadas
    clearTimeout(timeoutGuardarPrefs);
    timeoutGuardarPrefs = setTimeout(async () => {
        try {
            await fetch(`${API_BASE}/preferencias`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(cambios)
            });
            console.log('[Nube Maquita] Preferencias guardadas:', cambios);
        } catch (error) {
            console.warn('[Nube Maquita] Error guardando preferencias:', error);
        }
    }, 500);
}

// Aplicar preferencias a la UI
function aplicarPreferencias() {
    // Aplicar vista (lista/cuadrícula)
    vistaGrid = preferenciasUsuario.vista === 'cuadricula';
    actualizarVistaUI();

    // Aplicar orden (nombre ascendente por defecto, igual que Nextcloud)
    ordenarPor = preferenciasUsuario.orden_campo || 'nombre';
    ordenDir = preferenciasUsuario.orden_dir || 'asc';

    // Actualizar controles de orden en la UI
    const ordenSelect = document.getElementById('ordenarPor');
    if (ordenSelect) ordenSelect.value = ordenarPor;

    const dirSelect = document.getElementById('ordenDir');
    if (dirSelect) dirSelect.value = ordenDir;
}

// Actualizar visualización de la vista (sin recargar archivos)
function actualizarVistaUI() {
    const btnGrid = document.getElementById('btnViewGrid');
    const btnList = document.getElementById('btnViewList');
    const container = document.getElementById('filesContainer');

    if (vistaGrid) {
        btnGrid?.classList.add('active');
        btnList?.classList.remove('active');
        container?.classList.remove('list-view');
        document.getElementById('listView')?.classList.remove('active');
    } else {
        btnGrid?.classList.remove('active');
        btnList?.classList.add('active');
        container?.classList.add('list-view');
        document.getElementById('listView')?.classList.add('active');
    }
}

// -----------------------------------------------------------------------------
// Inicialización
// -----------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', async () => {
    // Primero cargar preferencias del usuario
    await cargarPreferencias();
    aplicarPreferencias();
    restaurarEstadoPanelLateral();

    inicializarControlesOrden();
    cargarArchivos(rutaActual);
    cargarCuota();
    inicializarArbolLateral();
    configurarEventos();
    actualizarNavActivo();

    // Configurar guardado de scroll position
    const mainContent = document.querySelector('.gd-main');
    if (mainContent) {
        mainContent.addEventListener('scroll', debounce(() => {
            if (vistaActual === 'archivos') {
                guardarPreferencias({ scroll_position: mainContent.scrollTop });
            }
        }, 1000));
    }

    // Establecer estado inicial del historial
    history.replaceState({ ruta: rutaActual }, '', window.location.pathname);

    // Restaurar scroll position después de cargar
    setTimeout(() => {
        if (preferenciasUsuario.scroll_position > 0 && vistaActual === 'archivos') {
            const mainContent = document.querySelector('.gd-main');
            if (mainContent) mainContent.scrollTop = preferenciasUsuario.scroll_position;
        }
    }, 500);
});

// Función debounce helper
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Función para actualizar el nav-item activo según la vista actual
function actualizarNavActivo() {
    // Quitar active de todos los nav-items
    document.querySelectorAll('.gd-nav-item').forEach(el => el.classList.remove('active'));

    // Mapeo de vistas a IDs de nav-items
    const vistaANav = {
        'principal': 'navPaginaPrincipal',
        'archivos': 'navMiUnidad',
        'compartidos': 'navCompartido',
        'recientes': 'navReciente',
        'favoritos': 'navDestacados',
        'spam': 'navSpam',
        'papelera': 'navPapelera'
    };

    // Determinar qué nav-item activar
    const navId = vistaANav[vistaActual] || 'navMiUnidad';
    const navElement = document.getElementById(navId);

    if (navElement) {
        navElement.classList.add('active');
    }
}

// Función para mostrar la página principal INTELIGENTE
// Muestra archivos sugeridos basados en actividad del usuario
async function mostrarPaginaPrincipal() {
    // Ocultar dashboard especial
    document.getElementById('paginaPrincipal').style.display = 'none';

    try {
        // Usar endpoint de sugeridos (basado en actividad del usuario)
        const response = await fetch(`${API_BASE}/sugeridos?limit=10&offset=0&_t=${Date.now()}`);
        const data = await response.json();

        if (data.success && data.sugeridos && data.sugeridos.length > 0) {
            // Actualizar breadcrumb para página principal
            actualizarBreadcrumb([{nombre: 'Página principal', ruta: '/'}]);

            // Separar en carpetas y archivos
            const carpetasRender = data.sugeridos.filter(i => i.es_carpeta);
            const archivosRender = data.sugeridos.filter(i => !i.es_carpeta);

            console.log('[Nube Maquita] Página Principal Inteligente:', data.sugeridos.length, 'sugeridos');

            // Usar renderizado especial con motivos
            renderizarSugeridos(data.sugeridos);

            // Guardar para carga progresiva
            window.sugeridosOffset = 10;
            window.hayMasSugeridos = data.hay_mas;
            window.cargandoMas = false;
        } else {
            mostrarEstadoVacio(
                'Bienvenido a Nube Maquita',
                'Comienza a trabajar con tus archivos y aquí aparecerán tus documentos más relevantes'
            );
        }

        mostrarLoader(false);

    } catch (error) {
        console.error('Error cargando página principal:', error);
        mostrarEstadoVacio('Error cargando archivos', 'No se pudieron cargar tus archivos sugeridos');
        mostrarLoader(false);
    }
}

// Renderizar archivos sugeridos con motivo visible
function renderizarSugeridos(sugeridos) {
    const container = document.getElementById('filesContainer');
    const foldersBlock = document.getElementById('foldersBlock');
    const filesBlock = document.getElementById('filesBlock');
    const listBody = document.getElementById('listBody');
    const emptyState = document.getElementById('emptyState');

    if (!foldersBlock || !filesBlock || !container) {
        console.warn('[Nube Maquita] Elementos del DOM no encontrados para renderizar sugeridos');
        return;
    }

    // Limpiar
    foldersBlock.innerHTML = '';
    filesBlock.innerHTML = '';
    if (listBody) listBody.innerHTML = '';

    // Separar carpetas y archivos
    const carpetas = sugeridos.filter(i => i.es_carpeta);
    const archivos = sugeridos.filter(i => !i.es_carpeta);

    // Renderizar con motivo
    carpetas.forEach(item => {
        foldersBlock.innerHTML += crearCardSugerido(item);
        if (listBody) listBody.innerHTML += crearFilaSugerido(item);
    });

    archivos.forEach(item => {
        filesBlock.innerHTML += crearCardSugerido(item);
        if (listBody) listBody.innerHTML += crearFilaSugerido(item);
    });

    container.style.display = 'block';
    if (emptyState) emptyState.style.display = 'none';

    // Aplicar vista
    aplicarVistaActual();
    inicializarLazyLoading();
}

// Card con motivo visible (por qué aparece)// [movida a explorador-render.js]

// Fila con motivo para vista lista// [movida a explorador-render.js]

// Registrar actividad del usuario con un archivo
async function registrarActividad(elemento, tipo = 'apertura') {
    try {
        const fileId = elemento.dataset.fileId || elemento.dataset.folderId;
        const ruta = elemento.dataset.ruta;
        const nombre = elemento.dataset.nombre;
        const esCarpeta = elemento.dataset.carpeta === 'true';

        if (!fileId) return; // No registrar si no hay file_id

        await fetch(`${API_BASE}/actividad/registrar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_id: fileId,
                ruta: ruta,
                nombre: nombre,
                es_carpeta: esCarpeta,
                tipo: tipo
            })
        });
    } catch (error) {
        console.warn('No se pudo registrar actividad:', error);
    }
}

// Mostrar estado vacío personalizado
function mostrarEstadoVacio(titulo, mensaje) {
    const emptyState = document.getElementById('emptyState');
    const filesContainer = document.getElementById('filesContainer');

    filesContainer.style.display = 'none';
    emptyState.style.display = 'block';

    const emptyTitle = emptyState.querySelector('h2');
    const emptyText = emptyState.querySelector('p');

    if (emptyTitle) emptyTitle.textContent = titulo;
    if (emptyText) emptyText.textContent = mensaje;
}

// -----------------------------------------------------------------------------
// Búsqueda de archivos
// -----------------------------------------------------------------------------

let archivosCache = []; // Cache de todos los archivos para búsqueda
let timeoutBusqueda = null;

// Sistema de caché para peticiones API (evita peticiones duplicadas)
const apiCache = new Map();
const API_CACHE_TTL = 30000; // 30 segundos de caché
let _nocacheBackend = false; // Flag para forzar bypass de caché del backend

async function fetchConCache(url, opciones = {}) {
    const ahora = Date.now();
    const cacheKey = url.replace(/[&?]_t=\d+/, ''); // Remover cache-buster para la key

    // Si hay datos en caché y no han expirado, usarlos
    if (apiCache.has(cacheKey)) {
        const cached = apiCache.get(cacheKey);
        if (ahora - cached.timestamp < API_CACHE_TTL) {
            console.log('[Cache] Usando caché para:', cacheKey);
            return cached.data;
        }
    }

    // Hacer la petición
    const response = await fetch(url, { cache: 'no-store', ...opciones });
    const data = await response.json();

    // Guardar en caché
    apiCache.set(cacheKey, { data, timestamp: ahora });

    // Limpiar caché antiguo (máximo 50 entradas)
    if (apiCache.size > 50) {
        const primeraKey = apiCache.keys().next().value;
        apiCache.delete(primeraKey);
    }

    return data;
}

// Invalidar caché de una ruta específica
function invalidarCache(ruta = null, incluirBackend = true) {
    if (ruta) {
        for (const key of apiCache.keys()) {
            if (key.includes(encodeURIComponent(ruta)) || key.includes(ruta)) {
                apiCache.delete(key);
            }
        }
    } else {
        apiCache.clear();
    }
    if (incluirBackend) {
        _nocacheBackend = true; // Forzar bypass de caché del backend en la próxima petición
    }
}

function buscarArchivos(termino) {
    const searchClear = document.getElementById('searchClear');

    // Mostrar/ocultar botón limpiar
    searchClear.style.display = termino.length > 0 ? 'block' : 'none';

    // Debounce de 300ms
    clearTimeout(timeoutBusqueda);
    timeoutBusqueda = setTimeout(async () => {
        if (termino.length === 0) {
            // Si no hay término, mostrar archivos normales
            const carpetas = archivosCache.filter(item => item.es_carpeta || item.tipo === 'carpeta');
            const archivos = archivosCache.filter(item => !item.es_carpeta && item.tipo !== 'carpeta');
            renderizarArchivos(carpetas, archivos);
            return;
        }

        if (termino.length < 2) return; // Mínimo 2 caracteres

        const terminoLower = termino.toLowerCase().trim();

        // Si empieza con punto, buscar por extensión en el servidor
        if (terminoLower.startsWith('.')) {
            await buscarGlobal(termino);
            return;
        }

        // Búsqueda global en el servidor (busca en todos los archivos)
        await buscarGlobal(termino);
    }, 300);
}

// Búsqueda global en el servidor
async function buscarGlobal(termino) {
    try {
        // Mostrar indicador de carga
        const foldersBlock = document.getElementById('foldersBlock');
        const filesBlock = document.getElementById('filesBlock');
        foldersBlock.innerHTML = '';
        filesBlock.innerHTML = '<div style="padding: 20px; color: var(--gd-text-secondary);">Buscando...</div>';

        const response = await fetch(`${API_BASE}/buscar?q=${encodeURIComponent(termino)}`);
        if (!response.ok) throw new Error('Error en búsqueda');

        const data = await response.json();
        const resultados = data.resultados || data.archivos || [];

        // Mostrar resultados
        renderizarResultadosBusqueda(resultados, termino);
    } catch (error) {
        console.error('Error en búsqueda global:', error);
        // Fallback a búsqueda local en cache
        buscarEnCacheLocal(termino);
    }
}

// Búsqueda local en cache (fallback)
function buscarEnCacheLocal(termino) {
    const terminoLower = termino.toLowerCase().trim();

    let resultados;
    if (terminoLower.startsWith('.')) {
        // Buscar por extensión
        const extension = terminoLower.substring(1); // quitar el punto
        resultados = archivosCache.filter(archivo =>
            archivo.extension && archivo.extension.toLowerCase() === extension
        );
    } else {
        // Buscar por nombre
        resultados = archivosCache.filter(archivo =>
            archivo.nombre.toLowerCase().includes(terminoLower)
        );
    }

    renderizarResultadosBusqueda(resultados, termino);
}

// Búsqueda avanzada
function mostrarFiltrosBusqueda() {
    document.getElementById('searchModal').classList.add('show');
}

function cerrarBusquedaAvanzada() {
    document.getElementById('searchModal').classList.remove('show');
}

function restablecerBusquedaAvanzada() {
    document.getElementById('searchType').value = '';
    document.getElementById('searchOwner').value = '';
    document.getElementById('searchWords').value = '';
    document.getElementById('searchName').value = '';
    document.getElementById('searchLocation').value = '';
    document.getElementById('searchDate').value = '';
    document.getElementById('searchSharedWith').value = '';
    document.getElementById('searchInTrash').checked = false;
    document.getElementById('searchStarred').checked = false;
}

function ejecutarBusquedaAvanzada() {
    const tipo = document.getElementById('searchType').value;
    const propietario = document.getElementById('searchOwner').value;
    const palabras = document.getElementById('searchWords').value.toLowerCase();
    const nombre = document.getElementById('searchName').value.toLowerCase();
    const ubicacion = document.getElementById('searchLocation').value;
    const fecha = document.getElementById('searchDate').value;
    const compartidoCon = document.getElementById('searchSharedWith').value.toLowerCase();
    const incluirPapelera = document.getElementById('searchInTrash').checked;
    const soloDestacados = document.getElementById('searchStarred').checked;

    // Filtrar archivos en cache según los criterios
    let resultados = [...archivosCache];

    // Filtrar por tipo
    if (tipo) {
        resultados = resultados.filter(item => {
            if (tipo === 'carpeta') return item.es_carpeta || item.tipo === 'carpeta';
            return item.tipo === tipo;
        });
    }

    // Filtrar por nombre
    if (nombre) {
        resultados = resultados.filter(item =>
            item.nombre.toLowerCase().includes(nombre)
        );
    }

    // Filtrar por palabras (también busca en nombre)
    if (palabras) {
        resultados = resultados.filter(item =>
            item.nombre.toLowerCase().includes(palabras)
        );
    }

    // Filtrar por fecha de modificación
    if (fecha) {
        const ahora = new Date();
        resultados = resultados.filter(item => {
            if (!item.modificado_at) return false;
            const fechaItem = new Date(item.modificado_at);
            const diferencia = ahora - fechaItem;

            switch(fecha) {
                case 'hoy':
                    return diferencia < 86400000; // 24 horas
                case 'semana':
                    return diferencia < 604800000; // 7 días
                case 'mes':
                    return diferencia < 2592000000; // 30 días
                case 'año':
                    return fechaItem.getFullYear() === ahora.getFullYear();
                default:
                    return true;
            }
        });
    }

    // Filtrar por destacados
    if (soloDestacados) {
        resultados = resultados.filter(item => item.favorito || item.es_favorito);
    }

    cerrarBusquedaAvanzada();

    // Construir descripción de búsqueda
    let descripcion = 'Búsqueda avanzada';
    if (nombre) descripcion += ` - nombre: "${nombre}"`;
    if (tipo) descripcion += ` - tipo: ${tipo}`;

    // Mostrar resultados
    if (resultados.length > 0) {
        renderizarResultadosBusqueda(resultados, descripcion);
        mostrarNotificacion(`Se encontraron ${resultados.length} resultados`, 'success');
    } else {
        renderizarResultadosBusqueda([], descripcion);
        mostrarNotificacion('No se encontraron resultados', 'info');
    }
}

// Cerrar modal al hacer clic fuera
document.addEventListener('click', (e) => {
    const modal = document.getElementById('searchModal');
    if (e.target === modal) {
        cerrarBusquedaAvanzada();
    }
});

function renderizarResultadosBusqueda(resultados, termino) {
    const foldersBlock = document.getElementById('foldersBlock');
    const filesBlock = document.getElementById('filesBlock');
    const emptyState = document.getElementById('emptyState');
    const filesContainer = document.getElementById('filesContainer');

    if (!foldersBlock || !filesBlock) {
        console.warn('[Nube Maquita] Elementos del DOM no encontrados para renderizar búsqueda');
        return;
    }

    // Separar carpetas y archivos
    const carpetas = resultados.filter(item => item.es_carpeta || item.tipo === 'carpeta');
    const archivos = resultados.filter(item => !item.es_carpeta && item.tipo !== 'carpeta');

    // Renderizar carpetas
    foldersBlock.innerHTML = '';
    carpetas.forEach(item => {
        foldersBlock.innerHTML += crearCard(item);
    });

    // Renderizar archivos
    filesBlock.innerHTML = '';
    archivos.forEach(item => {
        filesBlock.innerHTML += crearCard(item);
    });

    // Estado vacío si no hay resultados
    if (resultados.length === 0) {
        if (emptyState) {
            emptyState.style.display = 'block';
            emptyState.innerHTML = `
                <span class="material-icons" style="font-size: 64px; color: #dadce0;">search_off</span>
                <h2>No se encontraron resultados</h2>
                <p>No hay archivos que coincidan con "${termino}"</p>
            `;
        }
        if (filesContainer) filesContainer.style.display = 'none';
    } else {
        if (emptyState) emptyState.style.display = 'none';
        if (filesContainer) filesContainer.style.display = 'block';
    }
}

function limpiarBusqueda() {
    const searchInput = document.getElementById('searchInput');
    const searchClear = document.getElementById('searchClear');

    searchInput.value = '';
    searchClear.style.display = 'none';

    // Restaurar vista normal
    const carpetas = archivosCache.filter(item => item.es_carpeta || item.tipo === 'carpeta');
    const archivos = archivosCache.filter(item => !item.es_carpeta && item.tipo !== 'carpeta');
    renderizarArchivos(carpetas, archivos);

    // Restaurar títulos de sección
    const foldersSection = document.getElementById('foldersSection');
    const filesSection = document.getElementById('filesSection');
    const folderTitle = foldersSection ? foldersSection.querySelector('.gd-section-title') : null;
    const fileTitle = filesSection ? filesSection.querySelector('.gd-section-title') : null;
    if (folderTitle) folderTitle.textContent = 'Carpetas';
    if (fileTitle) fileTitle.textContent = 'Archivos';
}

// Toggle menú de apps
function toggleAppsMenu() {
    const menu = document.getElementById('appsMenu');
    menu.classList.toggle('show');
    // Cerrar otros menús
    document.getElementById('configMenu').classList.remove('show');
}

// Toggle menú de configuración
function toggleConfigMenu() {
    const menu = document.getElementById('configMenu');
    menu.classList.toggle('show');
    // Cerrar otros menús
    document.getElementById('appsMenu').classList.remove('show');
}

// Funciones del menú de configuración
function abrirConfiguracion() {
    document.getElementById('configMenu').classList.remove('show');
    Swal.fire({
        title: '<i class="fas fa-cog me-2"></i>Configuración',
        html: `
            <div class="text-start">
                <div class="mb-3">
                    <label class="form-check">
                        <input type="checkbox" class="form-check-input" id="configConvertir" checked>
                        <span class="form-check-label">Convertir archivos subidos a formato de Nube Maquita</span>
                    </label>
                </div>
                <div class="mb-3">
                    <label class="form-check">
                        <input type="checkbox" class="form-check-input" id="configOffline">
                        <span class="form-check-label">Disponible sin conexión</span>
                    </label>
                </div>
                <div class="mb-3">
                    <label class="form-label">Densidad de visualización</label>
                    <select class="form-select" id="configDensidad">
                        <option value="normal" selected>Normal</option>
                        <option value="compacta">Compacta</option>
                        <option value="comoda">Cómoda</option>
                    </select>
                </div>
                <div class="mb-3">
                    <label class="form-label">Idioma</label>
                    <select class="form-select" id="configIdioma">
                        <option value="es" selected>Español</option>
                        <option value="en">English</option>
                    </select>
                </div>
            </div>
        `,
        showCancelButton: true,
        confirmButtonText: 'Guardar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#1a73e8',
        width: 500
    }).then((result) => {
        if (result.isConfirmed) {
            mostrarNotificacion('Configuración guardada', 'success');
        }
    });
}

function restaurarVersiones() {
    document.getElementById('configMenu').classList.remove('show');
    Swal.fire({
        title: '<i class="fas fa-history me-2"></i>Restaurar versiones',
        html: `
            <div class="text-start">
                <p class="text-muted mb-3">
                    Puedes restaurar versiones anteriores de tus archivos desde la vista de detalles de cada archivo.
                </p>
                <ol class="text-muted small">
                    <li>Haz clic derecho en un archivo</li>
                    <li>Selecciona "Ver detalles"</li>
                    <li>Ve a la pestaña "Actividad"</li>
                    <li>Selecciona la versión que deseas restaurar</li>
                </ol>
                <hr>
                <p class="small text-muted mb-0">
                    <i class="fas fa-info-circle me-1"></i>
                    Las versiones se guardan automáticamente cada vez que editas un archivo.
                </p>
            </div>
        `,
        confirmButtonText: 'Entendido',
        confirmButtonColor: '#1a73e8',
        width: 450
    });
}

function instalarAppEscritorio() {
    document.getElementById('configMenu').classList.remove('show');
    // La app de escritorio del Drive esta EN PREPARACION. No se manda a un sitio externo:
    // es un producto ajeno y ademas el Almacen no habla WebDAV, seria un callejon sin salida.
    Swal.fire('Próximamente', 'La aplicación de escritorio del Drive está en preparación.', 'info');
}

function mostrarAtajosTeclado() {
    document.getElementById('configMenu').classList.remove('show');
    Swal.fire({
        title: '<i class="fas fa-keyboard me-2"></i>Combinaciones de teclas',
        html: `
            <div class="text-start" style="font-size: 13px;">
                <table class="table table-sm">
                    <tbody>
                        <tr><td><kbd>/</kbd></td><td>Buscar</td></tr>
                        <tr><td><kbd>N</kbd></td><td>Nueva carpeta</td></tr>
                        <tr><td><kbd>U</kbd></td><td>Subir archivo</td></tr>
                        <tr><td><kbd>Enter</kbd></td><td>Abrir archivo/carpeta</td></tr>
                        <tr><td><kbd>D</kbd></td><td>Descargar</td></tr>
                        <tr><td><kbd>I</kbd></td><td>Ver información</td></tr>
                        <tr><td><kbd>Delete</kbd></td><td>Mover a papelera</td></tr>
                        <tr><td><kbd>Ctrl+A</kbd></td><td>Seleccionar todo</td></tr>
                        <tr><td><kbd>Ctrl+Alt+E</kbd></td><td>Cambiar nombre</td></tr>
                        <tr><td><kbd>Ctrl+Alt+A</kbd></td><td>Compartir</td></tr>
                        <tr><td><kbd>Ctrl+Alt+M</kbd></td><td>Mover</td></tr>
                        <tr><td><kbd>Backspace</kbd></td><td>Volver atrás</td></tr>
                        <tr><td><kbd>Escape</kbd></td><td>Cerrar menús/limpiar selección</td></tr>
                    </tbody>
                </table>
            </div>
        `,
        confirmButtonText: 'Cerrar',
        confirmButtonColor: '#1a73e8',
        width: 400
    });
}

// -----------------------------------------------------------------------------
// Funciones de Drag & Drop para carpetas (en window para scope global garantizado)
// -----------------------------------------------------------------------------

// Procesar carpeta recursivamente para drag & drop
window.procesarCarpetaDrop = async function(entry, path) {
    const archivos = [];

    if (entry.isFile) {
        const file = await new Promise((resolve) => entry.file(resolve));
        archivos.push({ file, path: path });
    } else if (entry.isDirectory) {
        const reader = entry.createReader();
        const entries = await new Promise((resolve) => {
            const allEntries = [];
            const readEntries = () => {
                reader.readEntries((results) => {
                    if (results.length === 0) {
                        resolve(allEntries);
                    } else {
                        allEntries.push(...results);
                        readEntries();
                    }
                });
            };
            readEntries();
        });

        console.log('[Nube Maquita] Entries en', path, ':', entries.map(e => `${e.name} (${e.isDirectory ? 'dir' : 'file'})`));
        for (const childEntry of entries) {
            const childPath = path + '/' + childEntry.name;
            const childArchivos = await window.procesarCarpetaDrop(childEntry, childPath);
            archivos.push(...childArchivos);
        }
    }

    return archivos;
};

// Subir archivos con rutas (para carpetas)
// FIX 2026-07-03: fetch con reintentos (errores transitorios 5xx/red) y timeout.
// Un fallo puntual del proxy ya NO pierde archivos: se reintenta con backoff.
window.fetchConReintento = async function(url, opciones = {}, intentos = 3, timeoutMs = 20 * 60 * 1000) {
    let ultimoError = null;
    for (let i = 1; i <= intentos; i++) {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), timeoutMs);
        try {
            const resp = await fetch(url, { ...opciones, signal: ctrl.signal });
            clearTimeout(timer);
            if ([500, 502, 503, 504].includes(resp.status) && i < intentos) {
                await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i - 1)));
                continue;
            }
            return resp;
        } catch (e) {
            clearTimeout(timer);
            ultimoError = e;
            if (i < intentos) {
                await new Promise(r => setTimeout(r, 1000 * Math.pow(2, i - 1)));
            }
        }
    }
    throw ultimoError || new Error('Fallo de red tras reintentos');
};

window.subirArchivosConRuta = async function(archivosConRuta) {
    const panel = document.getElementById('uploadPanel');
    const items = document.getElementById('uploadItems');
    const title = document.getElementById('uploadTitle');
    const counter = document.getElementById('uploadCounter');
    const progressCircle = document.getElementById('uploadProgressCircle');
    const circleProgress = document.getElementById('uploadCircleProgress');
    const circleText = document.getElementById('uploadCircleText');

    // Determinar carpeta destino
    const vistasEspeciales = ['recientes', 'favoritos', 'papelera', 'compartidos'];
    let carpetaDestino = rutaActual;

    if (vistasEspeciales.includes(vistaActual) || rutaActual.startsWith('/recientes') ||
        rutaActual.startsWith('/favoritos') || rutaActual.startsWith('/papelera') ||
        rutaActual.startsWith('/compartidos')) {
        carpetaDestino = '/';
    }

    // Obtener nombre de la carpeta principal (si es una carpeta)
    const primerArchivo = archivosConRuta[0];
    const carpetaPrincipal = primerArchivo.path.split('/')[0];
    const esCarpeta = archivosConRuta.length > 1 || primerArchivo.path.includes('/');

    // Inicializar panel
    panel.classList.add('show');
    title.textContent = esCarpeta ? `Preparando carpeta "${carpetaPrincipal}"...` : `Subiendo ${archivosConRuta.length} archivo${archivosConRuta.length > 1 ? 's' : ''}`;
    items.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--gd-text-secondary);"><span class="material-icons" style="animation: spin 1s linear infinite;">sync</span> Creando estructura de carpetas...</div>';

    // Inicializar círculo de progreso
    progressCircle.className = 'gd-upload-progress-circle uploading';
    circleProgress.style.strokeDasharray = '0, 100';
    circleText.textContent = '0%';

    const totalArchivos = archivosConRuta.length;
    counter.textContent = `Preparando ${totalArchivos} archivos...`;

    // PASO 1: Recolectar TODAS las carpetas únicas que necesitan crearse
    const carpetasUnicas = new Set();
    for (const { path } of archivosConRuta) {
        const partes = path.split('/');
        partes.pop(); // Quitar nombre del archivo
        let rutaAcumulada = '';
        for (const parte of partes) {
            rutaAcumulada = rutaAcumulada ? rutaAcumulada + '/' + parte : parte;
            carpetasUnicas.add(rutaAcumulada);
        }
    }

    // PASO 2: Ordenar carpetas por profundidad (padres primero)
    const carpetasOrdenadas = Array.from(carpetasUnicas).sort((a, b) => {
        return a.split('/').length - b.split('/').length;
    });

    // PASO 3: Crear todas las carpetas ANTES de subir archivos
    // FIX 2026-01-27: Detectar si la carpeta principal ya existe en carpetaDestino para evitar duplicación
    const ultimaCarpetaDestino = carpetaDestino.split('/').filter(p => p).pop() || '';
    const primeraCarpetaPath = carpetaPrincipal; // Nombre de la carpeta que se está subiendo
    const carpetaYaExiste = ultimaCarpetaDestino === primeraCarpetaPath;

    console.log('[Nube Maquita] *** VERSION 2026-01-29 - FIX duplicación carpetas v2 ***');
    console.log('[Nube Maquita] carpetaDestino:', carpetaDestino, '| ultimaCarpetaDestino:', ultimaCarpetaDestino);
    console.log('[Nube Maquita] primeraCarpetaPath:', primeraCarpetaPath, '| carpetaYaExiste:', carpetaYaExiste);
    console.log('[Nube Maquita] Carpetas únicas:', Array.from(carpetasUnicas));
    console.log('[Nube Maquita] Paths de archivos:', archivosConRuta.map(a => a.path));
    console.log('[Nube Maquita] Creando', carpetasOrdenadas.length, 'carpetas en:', carpetaDestino);

    for (const carpetaRelativa of carpetasOrdenadas) {
        console.log('[Nube Maquita] Creando subcarpeta:', carpetaRelativa);
        let partes = carpetaRelativa.split('/');

        // FIX: Si la carpeta principal ya existe en el destino, omitirla
        if (carpetaYaExiste && partes.length > 0 && partes[0] === primeraCarpetaPath) {
            partes = partes.slice(1); // Quitar la primera carpeta que ya existe
            if (partes.length === 0) {
                console.log('[Nube Maquita] Carpeta ya existe, omitiendo:', carpetaRelativa);
                continue; // Esta carpeta ya existe, no crear
            }
        }

        const nombreCarpeta = partes.pop();
        const rutaPadre = partes.length > 0
            ? (carpetaDestino === '/' ? '/' + partes.join('/') : carpetaDestino + '/' + partes.join('/'))
            : carpetaDestino;

        try {
            // FIX 2026-07-03: con reintento (si aun asi falla, el backend recrea
            // la carpeta padre en el PUT del primer archivo — no se aborta)
            const resp = await fetchConReintento(`${API_BASE}/carpetas`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    nombre: nombreCarpeta,
                    ruta: rutaPadre
                })
            }, 2, 60 * 1000);
            const result = await resp.json();
            if (!resp.ok && !result.error?.includes('ya existe')) {
                console.warn('[Nube Maquita] Advertencia creando carpeta:', carpetaRelativa, result);
            }
        } catch (e) {
            console.warn('[Nube Maquita] Error creando carpeta:', carpetaRelativa, e);
        }
    }

    // PASO 4: Subir los archivos
    // FIX 2026-07-03: pool de 4 subidas simultaneas (antes serial = eterno),
    // reintentos con backoff (antes 1 fallo transitorio = archivo perdido),
    // DOM con createElement (antes innerHTML += era O(n^2) y congelaba el navegador)
    items.innerHTML = '';
    title.textContent = esCarpeta ? `Subiendo carpeta "${carpetaPrincipal}"` : `Subiendo ${totalArchivos} archivo${totalArchivos > 1 ? 's' : ''}`;
    counter.textContent = `0 de ${totalArchivos} archivos`;

    let archivosSubidos = 0;
    let archivosError = 0;
    const erroresDetalle = [];
    const MOSTRAR_ITEMS = totalArchivos <= 300; // miles de items en el panel congelan el navegador
    if (!MOSTRAR_ITEMS) {
        items.innerHTML = '<div style="padding: 16px; text-align: center; color: var(--gd-text-secondary);">Subiendo muchos archivos — mira el contador de arriba</div>';
    }

    const subirUno = async ({ file, path }) => {
        let itemElement = null, fill = null, icon = null;
        if (MOSTRAR_ITEMS) {
            const nombreMostrar = path.length > 40 ? '...' + path.slice(-37) : path;
            itemElement = document.createElement('div');
            itemElement.className = 'gd-upload-item';
            itemElement.innerHTML = `
                <span class="material-icons">hourglass_empty</span>
                <span class="gd-upload-item-name"></span>
                <div class="gd-upload-item-progress"><div class="bar"><div class="fill" style="width: 0%"></div></div></div>`;
            const nameSpan = itemElement.querySelector('.gd-upload-item-name');
            nameSpan.textContent = nombreMostrar;
            nameSpan.title = path;
            items.appendChild(itemElement);
            items.scrollTop = items.scrollHeight;
            fill = itemElement.querySelector('.fill');
            icon = itemElement.querySelector('.material-icons');
        }

        // Carpeta destino del archivo (FIX 2026-01-27: evitar duplicacion se mantiene)
        let partes = path.split('/');
        partes.pop();
        if (carpetaYaExiste && partes.length > 0 && partes[0] === primeraCarpetaPath) {
            partes = partes.slice(1);
        }
        const carpetaArchivo = partes.length > 0
            ? (carpetaDestino === '/' ? '/' + partes.join('/') : carpetaDestino + '/' + partes.join('/'))
            : carpetaDestino;

        const marcar = (ok, msj) => {
            if (ok) { archivosSubidos++; }
            else {
                archivosError++;
                erroresDetalle.push(`${path}: ${msj || 'error'}`);
            }
            if (itemElement) {
                if (fill) { fill.style.width = '100%'; fill.style.background = ok ? '#34a853' : '#ea4335'; }
                if (icon) icon.textContent = ok ? 'check_circle' : 'error';
                itemElement.classList.add(ok ? 'complete' : 'error');
                if (!ok && msj) itemElement.title = msj;
            }
        };

        try {
            const formData = new FormData();
            formData.append('archivo', file);
            formData.append('carpeta', carpetaArchivo);
            const response = await fetchConReintento(`${API_BASE}/archivos`, {
                method: 'POST',
                body: formData
            }, 3);

            if (response.status === 413) {
                marcar(false, 'Archivo demasiado grande para el servidor');
            } else if (response.status === 507) {
                marcar(false, 'Tu almacenamiento está lleno (cuota)');
            } else {
                let data;
                try {
                    data = await response.json();
                } catch (parseErr) {
                    throw new Error(`Error del servidor (HTTP ${response.status})`);
                }
                if (data.success) marcar(true);
                else marcar(false, data.error || 'error del servidor');
            }
        } catch (error) {
            marcar(false, String(error.message || error));
        }

        const procesados = archivosSubidos + archivosError;
        const porcentaje = Math.round((procesados / totalArchivos) * 100);
        circleProgress.style.strokeDasharray = `${porcentaje}, 100`;
        circleText.textContent = `${porcentaje}%`;
        counter.textContent = `${procesados} de ${totalArchivos} archivos`;
    };

    // Pool: 4 subidas simultaneas con cola continua (sin barrera por lotes)
    const cola = archivosConRuta.slice();
    const trabajadores = Array.from({ length: Math.min(4, cola.length) }, async () => {
        while (cola.length > 0) {
            const trabajo = cola.shift();
            if (trabajo) await subirUno(trabajo);
        }
    });
    await Promise.all(trabajadores);

    if (erroresDetalle.length > 0) {
        console.error('[Nube Maquita] Archivos con error (' + erroresDetalle.length + '):\n' + erroresDetalle.slice(0, 50).join('\n'));
    }

    // Finalizar
    if (archivosError === 0) {
        progressCircle.className = 'gd-upload-progress-circle complete';
        title.textContent = esCarpeta
            ? `Carpeta "${carpetaPrincipal}" subida`
            : `${archivosSubidos} archivo${archivosSubidos > 1 ? 's' : ''} subido${archivosSubidos > 1 ? 's' : ''}`;
    } else if (archivosSubidos === 0) {
        progressCircle.className = 'gd-upload-progress-circle error';
        title.textContent = 'Error al subir';
    } else {
        progressCircle.className = 'gd-upload-progress-circle complete';
        title.textContent = `${archivosSubidos} subidos, ${archivosError} errores`;
    }

    counter.textContent = archivosError > 0 ? `${archivosError} con error` : 'Completado';

    setTimeout(() => {
        invalidarCache(rutaActual);
        cargarArchivos(rutaActual);
        if (archivosError === 0) {
            panel.classList.remove('show');
        }
    }, 2000);
};

function configurarEventos() {
    // Cerrar menús al hacer clic fuera
    document.addEventListener('click', (e) => {
        if (!e.target.closest('#btnNew') && !e.target.closest('#newMenu')) {
            document.getElementById('newMenu').classList.remove('show');
        }
        // Cerrar menú de apps
        if (!e.target.closest('#btnApps') && !e.target.closest('#appsMenu')) {
            document.getElementById('appsMenu').classList.remove('show');
        }
        // Cerrar menú de configuración
        if (!e.target.closest('#btnConfig') && !e.target.closest('#configMenu')) {
            document.getElementById('configMenu').classList.remove('show');
        }
        // Cerrar menú contextual y submenús
        if (!e.target.closest('.gd-context-menu') && !e.target.closest('.gd-context-submenu')) {
            document.getElementById('contextMenu').classList.remove('show');
            cerrarSubmenus();
        }
        // Resetear padding extra que se agregó para mostrar el menú
        const mainContent = document.querySelector('.gd-main');
        if (mainContent) {
            mainContent.style.paddingBottom = '';
        }
    });

    // Drop zone
    const body = document.body;
    const dropZone = document.getElementById('dropZone');

    body.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('active');
    });

    body.addEventListener('dragleave', (e) => {
        if (e.relatedTarget === null) {
            dropZone.classList.remove('active');
        }
    });

    body.addEventListener('drop', async (e) => {
        e.preventDefault();
        dropZone.classList.remove('active');

        console.log('[Nube Maquita] ========== DROP DETECTADO ==========');

        // Verificar si hay items (para carpetas)
        const items = e.dataTransfer.items;
        const files = e.dataTransfer.files;

        console.log('[Nube Maquita] Items:', items?.length, 'Files:', files?.length);
        console.log('[Nube Maquita] webkitGetAsEntry disponible:', items?.[0]?.webkitGetAsEntry ? 'SÍ' : 'NO');

        if (items && items.length > 0) {
            const archivos = [];
            const promesas = [];
            let hayCarpetas = false;

            for (let i = 0; i < items.length; i++) {
                const item = items[i];
                console.log('[Nube Maquita] Item', i, '- kind:', item.kind, 'type:', item.type);

                if (item.kind === 'file') {
                    const entry = item.webkitGetAsEntry ? item.webkitGetAsEntry() : null;
                    console.log('[Nube Maquita] Entry:', entry, 'isDirectory:', entry?.isDirectory);

                    if (entry) {
                        if (entry.isDirectory) {
                            hayCarpetas = true;
                            console.log('[Nube Maquita] Procesando carpeta:', entry.name);
                            promesas.push(window.procesarCarpetaDrop(entry, entry.name));
                        } else {
                            const file = item.getAsFile();
                            if (file) {
                                console.log('[Nube Maquita] Archivo:', file.name);
                                archivos.push({ file, path: file.name });
                            }
                        }
                    } else {
                        // Fallback - verificar si es carpeta por el tipo vacío
                        const file = item.getAsFile();
                        if (file) {
                            // Las carpetas tienen size=0 y type vacío en algunos navegadores
                            if (file.size === 0 && file.type === '') {
                                console.log('[Nube Maquita] Posible carpeta detectada (fallback):', file.name);
                                Swal.fire({
                                    icon: 'warning',
                                    title: 'Carpeta detectada',
                                    html: `<p>Para subir la carpeta <strong>"${file.name}"</strong> con todo su contenido, usa el botón <strong>"+ Nuevo"</strong> → <strong>"Subir carpeta"</strong></p>`,
                                    confirmButtonText: 'Entendido',
                                    confirmButtonColor: '#0061a1'
                                });
                                return;
                            }
                            archivos.push({ file, path: file.name });
                        }
                    }
                }
            }

            // Esperar a que se procesen todas las carpetas
            if (promesas.length > 0) {
                console.log('[Nube Maquita] Procesando', promesas.length, 'carpetas...');
                const resultados = await Promise.all(promesas);
                resultados.forEach(arr => archivos.push(...arr));
                console.log('[Nube Maquita] Total archivos después de procesar carpetas:', archivos.length);
            }

            if (archivos.length > 0) {
                window.subirArchivosConRuta(archivos);
            } else if (hayCarpetas) {
                mostrarNotificacion('No se encontraron archivos en la carpeta', 'warning');
            }
        } else if (files && files.length > 0) {
            // Fallback para archivos simples
            console.log('[Nube Maquita] Usando fallback con files');

            // Verificar si alguno es carpeta (múltiples heurísticas)
            for (let i = 0; i < files.length; i++) {
                const file = files[i];
                const sinExtension = !file.name.includes('.') || file.name.startsWith('.');
                const tipoVacio = file.type === '';
                const tamanoSospechoso = file.size === 0 || file.size === 4096;

                console.log('[Nube Maquita] Fallback file:', file.name, 'size:', file.size, 'type:', file.type, 'sinExt:', sinExtension);

                // Si no tiene extensión y tipo vacío, probablemente es carpeta
                if (sinExtension && tipoVacio) {
                    console.log('[Nube Maquita] Detectada posible carpeta en fallback:', file.name);
                    Swal.fire({
                        icon: 'info',
                        title: 'Subir carpeta',
                        html: `<p>Para subir la carpeta <strong>"${file.name}"</strong> con todo su contenido, usa el botón <strong>"+ Nuevo"</strong> → <strong>"Subir carpeta"</strong></p>
                               <p style="margin-top:10px;font-size:13px;color:#5f6368;">El arrastre de carpetas solo funciona en navegadores compatibles (Chrome, Edge).</p>`,
                        confirmButtonText: 'Entendido',
                        confirmButtonColor: '#0061a1'
                    });
                    return;
                }
            }

            subirArchivos(files);
        }
    });

    // Input carpeta (boton Subir carpeta)
    document.getElementById("folderInput").addEventListener("change", (e) => {
        if (e.target.files.length > 0) {
            const archivos = [];
            for (const file of e.target.files) {
                const ruta = file.webkitRelativePath || file.name;
                archivos.push({ file: file, path: ruta });
            }
            if (archivos.length > 0) {
                window.subirArchivosConRuta(archivos);
            }
            e.target.value = "";
        }
    });

    // Input files
    document.getElementById('fileInput').addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            subirArchivos(e.target.files);
            e.target.value = '';
        }
    });

    // Atajos de teclado estilo Google Drive
    document.addEventListener('keydown', (e) => {
        // Ignorar si está en un input o textarea
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
            // Escape cierra modales desde inputs
            if (e.key === 'Escape') {
                cerrarBusquedaAvanzada();
                cerrarPanelDerecho();
                document.getElementById('contextMenu').classList.remove('show');
            }
            return;
        }

        // Delete - Eliminar seleccionado
        if (e.key === 'Delete' && itemSeleccionado) {
            e.preventDefault();
            eliminarSeleccionado();
        }

        // Ctrl+Alt+E - Renombrar
        if (e.ctrlKey && e.altKey && e.key === 'e' && itemSeleccionado) {
            e.preventDefault();
            renombrarSeleccionado();
        }

        // Ctrl+Alt+A - Compartir
        if (e.ctrlKey && e.altKey && e.key === 'a' && itemSeleccionado) {
            e.preventDefault();
            compartirSeleccionado();
        }

        // Ctrl+Alt+M - Mover
        if (e.ctrlKey && e.altKey && e.key === 'm' && itemSeleccionado) {
            e.preventDefault();
            moverSeleccionado();
        }

        // Ctrl+A - Seleccionar todo
        if (e.ctrlKey && e.key === 'a') {
            e.preventDefault();
            seleccionarTodo();
        }

        // Escape - Limpiar selección y cerrar paneles
        if (e.key === 'Escape') {
            limpiarSeleccion();
            cerrarBusquedaAvanzada();
            cerrarPanelDerecho();
            document.getElementById('contextMenu').classList.remove('show');
            document.getElementById('newMenu').classList.remove('show');
        }

        // / - Enfocar búsqueda
        if (e.key === '/' && !e.ctrlKey && !e.altKey) {
            e.preventDefault();
            document.getElementById('searchInput').focus();
        }

        // N - Nueva carpeta (cuando no hay input enfocado)
        if (e.key === 'n' && !e.ctrlKey && !e.altKey) {
            e.preventDefault();
            crearCarpeta();
        }

        // U - Subir archivo
        if (e.key === 'u' && !e.ctrlKey && !e.altKey) {
            e.preventDefault();
            document.getElementById('fileInput').click();
        }

        // Enter - Abrir seleccionado
        if (e.key === 'Enter' && itemSeleccionado) {
            e.preventDefault();
            const elemento = document.querySelector('.gd-card.selected, .gd-folder-card.selected, .gd-list tr.selected');
            if (elemento) {
                abrirItem(elemento);
            }
        }

        // Backspace - Volver atrás (navegación)
        if (e.key === 'Backspace' && !e.ctrlKey) {
            e.preventDefault();
            history.back();
        }

        // D - Descargar seleccionado
        if (e.key === 'd' && !e.ctrlKey && !e.altKey && itemSeleccionado) {
            e.preventDefault();
            descargarSeleccionado();
        }

        // I - Ver información/detalles
        if (e.key === 'i' && !e.ctrlKey && !e.altKey) {
            e.preventDefault();
            togglePanelInfo();
        }
    });
}

// Seleccionar todos los elementos
function seleccionarTodo() {
    const elementos = document.querySelectorAll('.gd-card, .gd-folder-card, .gd-list tbody tr');
    elementosSeleccionados = [];

    elementos.forEach(el => {
        el.classList.add('selected');
        const item = {
            ruta: el.dataset.ruta,
            esCarpeta: el.dataset.carpeta === 'true',
            nombre: el.dataset.nombre,
            folder_id: el.dataset.folderId || null
        };
        if (item.ruta) {
            elementosSeleccionados.push(item);
        }
    });

    if (elementosSeleccionados.length > 0) {
        itemSeleccionado = elementosSeleccionados[0];
    }
    actualizarBarraSeleccion();
}

// -----------------------------------------------------------------------------
// Cargar archivos
// -----------------------------------------------------------------------------
// [movida a explorador-navegacion.js]

function renderizarArchivos(carpetas, archivos) {
    const container = document.getElementById('filesContainer');
    const foldersBlock = document.getElementById('foldersBlock');
    const filesBlock = document.getElementById('filesBlock');
    const listBody = document.getElementById('listBody');
    const emptyState = document.getElementById('emptyState');

    // Guardar lista de archivos para navegación del lightbox
    lightboxArchivos = archivos;

    // Guardar en cache para búsqueda
    archivosCache = [
        ...carpetas.map(c => ({...c, tipo: 'carpeta', es_carpeta: true})),
        ...archivos
    ];

    // Determinar si hay filtro activo
    const hayFiltroActivo = filtroTipo && filtroTipo !== 'todos';

    // DOS BLOQUES SEPARADOS: carpetas primero, archivos después
    let foldersHtml = '';
    let filesHtml = '';
    let listHtml = '';

    // Bloque 1: Carpetas (si no hay filtro)
    if (!hayFiltroActivo) {
        for (let i = 0; i < carpetas.length; i++) {
            foldersHtml += crearCard(carpetas[i]);
            listHtml += crearFila(carpetas[i]);
        }
    }

    // Bloque 2: Archivos
    for (let i = 0; i < archivos.length; i++) {
        filesHtml += crearCard(archivos[i]);
        listHtml += crearFila(archivos[i]);
    }

    // Insertar en bloques separados (nunca se mezclan)
    foldersBlock.innerHTML = foldersHtml;
    filesBlock.innerHTML = filesHtml;
    listBody.innerHTML = listHtml;

    // Estado vacío
    const totalItems = (hayFiltroActivo ? 0 : carpetas.length) + archivos.length;
    if (totalItems === 0) {
        container.style.display = 'none';
        emptyState.style.display = 'block';
        // Personalizar mensaje de estado vacío según filtro
        const emptyTitle = emptyState.querySelector('h2');
        const emptyText = emptyState.querySelector('p');
        if (hayFiltroActivo && emptyTitle && emptyText) {
            emptyTitle.textContent = 'Sin resultados';
            emptyText.textContent = `No hay archivos de tipo "${filtroTipo}" en esta carpeta`;
        }
    } else {
        container.style.display = 'block';
        emptyState.style.display = 'none';
        // Restaurar mensaje por defecto
        const emptyTitle = emptyState.querySelector('h2');
        const emptyText = emptyState.querySelector('p');
        if (emptyTitle && emptyText) {
            emptyTitle.textContent = 'Bienvenido a Nube Maquita';
            emptyText.textContent = 'Arrastra archivos y carpetas aquí, o usa el botón "Nuevo"';
        }
    }

    // Aplicar la vista guardada (lista/cuadrícula) - GLOBAL para todas las secciones
    aplicarVistaActual();

    // Inicializar lazy loading para previews
    inicializarLazyLoading();
}

// Aplicar la vista actual (lista o cuadrícula) - se usa después de renderizar
function aplicarVistaActual() {
    const mainGrid = document.getElementById('mainGrid');
    const list = document.getElementById('listView');

    if (vistaGrid) {
        // Vista cuadrícula (flex vertical con grillas hijas)
        if (mainGrid) mainGrid.style.display = 'flex';
        list.classList.remove('active');
    } else {
        // Vista lista
        if (mainGrid) mainGrid.style.display = 'none';
        list.classList.add('active');
    }

    actualizarBotonesVista();
}

// -----------------------------------------------------------------------------
// Carga Progresiva / Infinite Scroll (REQ-09/10)
// -----------------------------------------------------------------------------

function renderizarSiguienteBloque(hayFiltroActivo = false) {
    if (cargandoMas) return;
    cargandoMas = true;

    const { carpetas, archivos } = archivosCompletos;
    const foldersBlock = document.getElementById('foldersBlock');
    const filesBlock = document.getElementById('filesBlock');
    const listBody = document.getElementById('listBody');

    if (!foldersBlock || !filesBlock) {
        cargandoMas = false;
        return;
    }

    // Calcular qué items renderizar en este bloque
    const totalCarpetas = hayFiltroActivo ? 0 : carpetas.length;
    const totalItems = totalCarpetas + archivos.length;
    const inicio = itemsMostrados;
    const fin = Math.min(inicio + ITEMS_POR_BLOQUE, totalItems);

    let foldersHtml = '';
    let filesHtml = '';
    let listHtml = '';

    for (let i = inicio; i < fin; i++) {
        if (i < totalCarpetas) {
            // Es una carpeta
            const carpeta = carpetas[i];
            foldersHtml += crearCard(carpeta);
            listHtml += crearFila(carpeta);
        } else {
            // Es un archivo
            const archivo = archivos[i - totalCarpetas];
            filesHtml += crearCard(archivo);
            listHtml += crearFila(archivo);
        }
    }

    // Agregar al DOM (no reemplazar)
    foldersBlock.innerHTML += foldersHtml;
    filesBlock.innerHTML += filesHtml;
    if (listBody) listBody.innerHTML += listHtml;

    itemsMostrados = fin;
    cargandoMas = false;

    // Ocultar loader si ya cargamos todo
    const loader = document.getElementById('infiniteScrollLoader');
    if (loader) {
        loader.style.display = itemsMostrados >= totalItems ? 'none' : 'flex';
    }

    // Reinicializar lazy loading para nuevos elementos
    inicializarLazyLoading();
}

function inicializarInfiniteScroll() {
    // Desconectar observer anterior
    if (observerInfiniteScroll) {
        observerInfiniteScroll.disconnect();
    }

    const loader = document.getElementById('infiniteScrollLoader');
    if (!loader) return;

    observerInfiniteScroll = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting && !cargandoMas) {
                const hayFiltroActivo = filtroTipo && filtroTipo !== 'todos';
                const totalCarpetas = hayFiltroActivo ? 0 : archivosCompletos.carpetas.length;
                const totalItems = totalCarpetas + archivosCompletos.archivos.length;

                if (itemsMostrados < totalItems) {
                    renderizarSiguienteBloque(hayFiltroActivo);
                }
            }
        });
    }, {
        root: document.querySelector('.gd-main'),
        rootMargin: '200px',
        threshold: 0.1
    });

    observerInfiniteScroll.observe(loader);
}

function crearLoaderInfiniteScroll() {
    let loader = document.getElementById('infiniteScrollLoader');
    if (!loader) {
        loader = document.createElement('div');
        loader.id = 'infiniteScrollLoader';
        loader.className = 'infinite-scroll-loader';
        loader.innerHTML = `
            <div class="loader-spinner"></div>
            <span>Cargando más archivos...</span>
        `;
        const filesSection = document.getElementById('filesSection');
        if (filesSection) {
            filesSection.appendChild(loader);
        }
    }

    // Mostrar/ocultar según si hay más items
    const hayFiltroActivo = filtroTipo && filtroTipo !== 'todos';
    const totalCarpetas = hayFiltroActivo ? 0 : archivosCompletos.carpetas.length;
    const totalItems = totalCarpetas + archivosCompletos.archivos.length;
    loader.style.display = itemsMostrados >= totalItems ? 'none' : 'flex';
}

// -----------------------------------------------------------------------------
// Lazy Loading de Previews (evita sobrecarga del servidor)
// -----------------------------------------------------------------------------

let previewObserver = null;
let previewQueue = [];
let previewsLoading = 0;
const MAX_CONCURRENT_PREVIEWS = 8; // Máximo de previews cargando simultáneamente

function inicializarLazyLoading() {
    // Desconectar observer anterior si existe
    if (previewObserver) {
        previewObserver.disconnect();
    }

    // Crear nuevo observer
    previewObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const element = entry.target;
                agregarAColaPreview(element);
                previewObserver.unobserve(element);
            }
        });
    }, {
        root: null,
        rootMargin: '400px', // Cargar con anticipación antes de que sea visible
        threshold: 0.1
    });

    // Observar todos los elementos con lazy-preview
    document.querySelectorAll('.lazy-preview').forEach(el => {
        previewObserver.observe(el);
    });
}

function agregarAColaPreview(element) {
    previewQueue.push(element);
    procesarColaPreview();
}

function procesarColaPreview() {
    while (previewQueue.length > 0 && previewsLoading < MAX_CONCURRENT_PREVIEWS) {
        const element = previewQueue.shift();
        cargarPreview(element);
    }
}

function cargarPreview(element) {
    const previewUrl = element.dataset.previewUrl;
    const iconoFallback = element.dataset.icon || 'insert_drive_file';

    if (!previewUrl) return;

    previewsLoading++;

    const img = new Image();
    img.onload = function() {
        // Preview cargado exitosamente
        element.style.backgroundImage = `url('${previewUrl}')`;
        element.style.backgroundSize = 'cover';
        element.style.backgroundPosition = 'center';
        element.innerHTML = ''; // Quitar placeholder
        element.classList.remove('lazy-preview');

        previewsLoading--;
        procesarColaPreview();
    };

    img.onerror = function() {
        // Error cargando preview - mantener icono
        element.classList.remove('lazy-preview');
        previewsLoading--;
        procesarColaPreview();
    };

    // Timeout de 5 segundos para evitar que una imagen lenta bloquee todo
    setTimeout(() => {
        if (previewsLoading > 0 && element.classList.contains('lazy-preview')) {
            element.classList.remove('lazy-preview');
            previewsLoading--;
            procesarColaPreview();
        }
    }, 5000);

    img.src = previewUrl;
}
// [movida a explorador-render.js]

// =============================================================================
// Versiones de Archivos
// =============================================================================

function verVersiones() {
    document.getElementById('contextMenu').classList.remove('show');

    if (!itemSeleccionado) {
        Swal.fire('Info', 'Selecciona un archivo primero', 'info');
        return;
    }

    if (itemSeleccionado.esCarpeta) {
        Swal.fire('Info', 'Las versiones solo están disponibles para archivos', 'info');
        return;
    }

    // Obtener file_id del elemento DOM
    const selectedEl = document.querySelector('.gd-card.selected, .gd-folder-card.selected, .gd-list-item.selected');
    let fileId = selectedEl ? (selectedEl.dataset.fileId || selectedEl.dataset.folderId) : null;
    // Robustez ante cache: tomar el ID tambien del item seleccionado
    if (!fileId && itemSeleccionado) {
        fileId = itemSeleccionado.file_id || itemSeleccionado.id || itemSeleccionado.folder_id;
    }

    if (!fileId) {
        Swal.fire('Error', 'No se pudo obtener el ID del archivo', 'error');
        return;
    }

    const item = itemSeleccionado;

    // Mostrar modal
    const modal = new bootstrap.Modal(document.getElementById('versionesModal'));
    document.getElementById('versionesFileName').textContent = item.nombre;
    document.getElementById('versionesContenido').innerHTML = `
        <div style="padding: 40px; text-align: center; color: var(--gd-text-secondary, #5f6368);">
            <div class="spinner-border spinner-border-sm" role="status"></div>
            <p style="margin-top: 8px;">Cargando versiones...</p>
        </div>`;
    modal.show();

    // Cargar versiones
    fetch(`${API_BASE}/versiones/${fileId}`)
        .then(r => r.json())
        .then(data => {
            if (!data.success) {
                document.getElementById('versionesContenido').innerHTML = `
                    <div style="padding: 30px; text-align: center; color: var(--gd-text-secondary);">
                        <span class="material-icons" style="font-size: 48px; opacity: 0.3;">error_outline</span>
                        <p>Error al obtener versiones</p>
                    </div>`;
                return;
            }

            const versiones = data.versiones || [];
            if (versiones.length === 0) {
                document.getElementById('versionesContenido').innerHTML = `
                    <div style="padding: 30px; text-align: center; color: var(--gd-text-secondary);">
                        <span class="material-icons" style="font-size: 48px; opacity: 0.3;">history</span>
                        <p style="margin-top: 8px;">No hay versiones anteriores</p>
                        <small>Las versiones se crean automáticamente al editar el archivo</small>
                    </div>`;
                return;
            }

            let html = `<div style="padding: 8px 20px 4px; font-size: 12px; color: var(--gd-text-secondary);">${versiones.length} versión(es) anterior(es)</div>`;

            versiones.forEach((v, i) => {
                const fecha = v.fecha ? new Date(v.fecha).toLocaleString('es-EC', {
                    day: '2-digit', month: 'short', year: 'numeric',
                    hour: '2-digit', minute: '2-digit'
                }) : 'Fecha desconocida';

                html += `
                <div class="version-item" style="display: flex; align-items: center; justify-content: space-between; padding: 12px 20px; border-bottom: 1px solid var(--gd-border, #f0f0f0); transition: background 0.15s;"
                     onmouseenter="this.style.background='var(--gd-bg-hover, #f5f5f5)'"
                     onmouseleave="this.style.background='transparent'">
                    <div style="display: flex; align-items: center; gap: 12px; flex: 1;">
                        <span class="material-icons" style="color: var(--gd-text-secondary, #5f6368); font-size: 20px;">schedule</span>
                        <div>
                            <div style="font-size: 13px; font-weight: 500;">${fecha}</div>
                            <div style="font-size: 12px; color: var(--gd-text-secondary, #5f6368);">${v.tamano_humano}</div>
                        </div>
                    </div>
                    <button onclick="restaurarVersion('${fileId}', '${v.version_id}', '${fecha}')"
                            class="btn btn-sm btn-outline-primary"
                            style="border-radius: 8px; font-size: 12px; padding: 4px 12px;">
                        <span class="material-icons" style="font-size: 16px; vertical-align: middle;">restore</span>
                        Restaurar
                    </button>
                </div>`;
            });

            document.getElementById('versionesContenido').innerHTML = html;
        })
        .catch(err => {
            console.error('Error cargando versiones:', err);
            document.getElementById('versionesContenido').innerHTML = `
                <div style="padding: 30px; text-align: center; color: var(--gd-text-secondary);">
                    <span class="material-icons" style="font-size: 48px; opacity: 0.3;">cloud_off</span>
                    <p>Error de conexión</p>
                </div>`;
        });
}

function restaurarVersion(fileId, versionId, fechaVersion) {
    Swal.fire({
        title: '¿Restaurar esta versión?',
        html: `Se restaurará la versión del <b>${fechaVersion}</b>.<br>La versión actual se guardará como versión anterior.`,
        icon: 'question',
        showCancelButton: true,
        confirmButtonText: 'Restaurar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#1a73e8'
    }).then(result => {
        if (!result.isConfirmed) return;

        Swal.fire({ title: 'Restaurando...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });

        fetch(`${API_BASE}/versiones/${fileId}/restaurar`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ version_id: versionId })
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Versión restaurada',
                    text: 'El archivo ha sido restaurado a la versión anterior',
                    timer: 2000,
                    showConfirmButton: false
                });
                // Cerrar modal y refrescar
                bootstrap.Modal.getInstance(document.getElementById('versionesModal'))?.hide();
                cargarArchivos(rutaActual);
            } else {
                Swal.fire('Error', data.error || 'No se pudo restaurar la versión', 'error');
            }
        })
        .catch(err => {
            console.error('Error restaurando versión:', err);
            Swal.fire('Error', 'Error de conexión al restaurar', 'error');
        });
    });
}

