/**
 * explorador-navegacion.js  -  Modulo: Navegacion del explorador
 * Responsabilidad UNICA: cargar/listar archivos de una ruta, navegar (SPA) y breadcrumb.
 * Depende de globales: renderizarArchivos (render.js), mostrarLoader (panels.js),
 *   mostrarPaginaPrincipal/invalidarCache (core.js), rutaActual, vistaActual, URL_BASE, API_BASE,
 *   seccionDeCarga/tituloDeSeccion/actualizarTituloSeccion (secciones.js),
 *   ajustarVistaPapelera (papelera.js).
 * Cargar DESPUES de config, core, interactions, render, secciones y papelera.
 */

/** Tras pintar una lista: el encabezado dice la sección y la Papelera muestra (u oculta) lo suyo. */
function _anunciarSeccion(seccion, total) {
    if (typeof actualizarTituloSeccion === 'function') actualizarTituloSeccion(seccion);
    if (typeof ajustarVistaPapelera === 'function') ajustarVistaPapelera(seccion === 'papelera', total);
}


async function cargarArchivos(ruta, forzarRecarga = false, silencioso = false) {
    // Mapear rutas amigables a rutas reales de Nextcloud
    if (ruta === '/mi-unidad' || ruta === '/mi-unidad/') {
        ruta = '/';
    } else if (ruta.startsWith('/mi-unidad/')) {
        ruta = ruta.replace('/mi-unidad', '');
    }

    // En refresco silencioso (actualización en vivo por notify_push) NO mostramos
    // el loader ni popups de error: la lista solo se actualiza cuando llegan datos,
    // evitando el parpadeo de "desaparecen/reaparecen".
    if (!silencioso) mostrarLoader(true);
    console.log('[Nube Maquita] Cargando archivos de:', ruta, 'Vista:', vistaActual);
    if (typeof ocultarAvisoCompartidosConmigo === 'function') ocultarAvisoCompartidosConmigo();

    // Si se fuerza recarga, invalidar caché de esta ruta
    if (forzarRecarga) {
        invalidarCache(ruta);
    }

    // Si es la página principal, mostrar el dashboard
    if (vistaActual === 'principal') {
        mostrarPaginaPrincipal();
        return;
    }

    // «Compartido conmigo» en el Almacén del webmail: el servidor abre la sección con
    // vista = 'compartidos' y ruta '/', y la lista sale de GET /compartidos-conmigo
    // (explorador-compartidos-conmigo.js). Sin esto se pedía la lista propia (/archivos?ruta=/).
    if (MODO_ALMACEN && typeof esVistaCompartidosConmigo === 'function' && esVistaCompartidosConmigo(ruta)) {
        await cargarCompartidosConmigo(ruta, silencioso);
        _anunciarSeccion('compartidos', 0);
        if (!silencioso) mostrarLoader(false);
        return;
    }

    try {
        let url;
        let esVistaEspecial = false;

        // Cache-buster para forzar datos frescos
        const cacheBuster = `_t=${Date.now()}`;

        // Determinar qué API llamar según la vista
        // Solo usar API de compartidos para la raíz de compartidos, no para subcarpetas
        if (ruta === '/compartidos' || ruta === '/compartidos/') {
            url = `${API_BASE}/compartidos?tipo=conmigo&${cacheBuster}`;
            esVistaEspecial = true;
        } else if (ruta === '/compartidos_por_mi' || ruta === '/compartidos_por_mi/') {
            url = `${API_BASE}/compartidos?tipo=por_mi&${cacheBuster}`;
            esVistaEspecial = true;
        } else if (ruta === '/papelera' || ruta === '/papelera/' || vistaActual === 'papelera') {
            url = `${API_BASE}/papelera?${cacheBuster}`;
            esVistaEspecial = true;
        } else if (ruta === '/favoritos' || ruta === '/favoritos/' || vistaActual === 'favoritos') {
            url = `${API_BASE}/favoritos?${cacheBuster}`;
            esVistaEspecial = true;
        } else if (ruta === '/recientes' || ruta === '/recientes/' || vistaActual === 'recientes') {
            url = `${API_BASE}/recientes?${cacheBuster}`;
            esVistaEspecial = true;
        } else {
            // Para cualquier otra ruta (incluyendo carpetas dentro de compartidos), usar API de archivos
            url = `${API_BASE}/archivos?ruta=${encodeURIComponent(ruta)}&orden=${ordenarPor}&dir=${ordenDir}&${cacheBuster}`;
            if (filtroTipo && filtroTipo !== 'todos') {
                url += `&filtro=${filtroTipo}`;
            }
            if (_nocacheBackend) {
                url += '&nocache=1';
                _nocacheBackend = false;
            }
        }

        console.log('[Nube Maquita] Llamando API:', url);

        // Usar sistema de caché para evitar peticiones duplicadas
        const data = await fetchConCache(url);
        console.log('[Nube Maquita] Data recibida:', data);

        if (data.success) {
            if (esVistaEspecial) {
                // Para vistas especiales, el formato de respuesta es diferente
                rutaActual = ruta;

                // Título según la sección (ruta pedida o vista con que se abrió la página)
                const seccion = seccionDeCarga(ruta);
                const tituloVista = tituloDeSeccion(seccion);
                actualizarBreadcrumb([{nombre: tituloVista, ruta: ruta}]);

                // Procesar respuesta según el tipo
                let items = [];
                let _esCompartidosVista = false;
                if (data.compartidos) {
                    _esCompartidosVista = true;
                    // Compartidos - incluir folder_id y color para estilos compartidos
                    items = data.compartidos.map(c => ({
                        id: c.id,
                        folder_id: c.folder_id,
                        nombre: c.nombre_archivo || c.ruta.split('/').pop(),
                        ruta: c.ruta,
                        ruta_completa: c.ruta,
                        es_carpeta: c.es_carpeta,
                        tipo: c.es_carpeta ? 'carpeta' : 'documento',
                        tamano_humano: c.tamano_humano || '-',
                        modificado_at: c.modificado_at || c.creado_at,
                        compartido_at: c.creado_at,
                        compartido_con: c.compartido_con_nombre || c.compartido_con,
                        propietario_nc: c.propietario_nc || '',
                        propietario_nombre: c.propietario_nombre || '',
                        propietario_email: c.propietario_email || '',
                        color: c.color || '',
                        icono_interno: c.icono || ''
                    }));
                } else if (data.archivos || data.carpetas) {
                    // Papelera, Favoritos, Recientes
                    const carpetasData = (data.carpetas || []).map(c => ({...c, es_carpeta: true, tipo: 'carpeta'}));
                    const archivosData = (data.archivos || []).map(a => ({...a, es_carpeta: false}));
                    items = [...carpetasData, ...archivosData];
                } else if (data.items) {
                    items = data.items;
                }

                const carpetas = items.filter(i => i.es_carpeta);
                const archivos = items.filter(i => !i.es_carpeta);
                console.log('[Nube Maquita] Renderizando vista especial:', carpetas.length, 'carpetas,', archivos.length, 'archivos');
                
                if (_esCompartidosVista && typeof renderizarCompartidosAgrupados === 'function') {
                    renderizarCompartidosAgrupados([...carpetas, ...archivos]);
                } else {
                    if (typeof _ocultarFiltrosComp === 'function') _ocultarFiltrosComp();
                    renderizarArchivos(carpetas, archivos);
                }
                _anunciarSeccion(seccion, carpetas.length + archivos.length);
            } else {
                rutaActual = data.ruta_actual;
                actualizarBreadcrumb(data.breadcrumb);
                console.log('[Nube Maquita] Renderizando:', data.carpetas.length, 'carpetas,', data.archivos.length, 'archivos');
                if (typeof _ocultarFiltrosComp === 'function') _ocultarFiltrosComp();
                renderizarArchivos(data.carpetas, data.archivos);
                _anunciarSeccion(seccionDeCarga(rutaActual), data.carpetas.length + data.archivos.length);
            }
        } else {
            console.error('[Nube Maquita] Error en respuesta:', data.error);
            if (!silencioso) Swal.fire('Error', data.error || 'Error desconocido', 'error');
        }
    } catch (error) {
        console.error('[Nube Maquita] Error fetch:', error);
        // En refresco silencioso no molestamos al usuario: se mantiene la lista actual.
        if (!silencioso) Swal.fire('Error', 'No se pudieron cargar los archivos: ' + error.message, 'error');
    }

    if (!silencioso) mostrarLoader(false);
}


function navegarA(ruta) {
    cargarArchivos(ruta);
    history.pushState({ ruta: ruta }, '', `${URL_BASE}${ruta === '/' ? '' : ruta}`);
}


function navegarASpam() {
    // Mostrar mensaje informativo sobre la sección de no deseados
    Swal.fire({
        icon: 'info',
        title: 'Correo no deseado',
        html: `
            <div style="text-align: left;">
                <p>Esta sección contiene archivos sospechosos que han sido marcados automática o manualmente.</p>
                <p style="margin-top: 12px; color: var(--gd-text-secondary);">
                    <span class="material-icons" style="vertical-align: middle; font-size: 18px;">info</span>
                    Los archivos de esta sección se eliminan automáticamente después de 30 días.
                </p>
            </div>
        `,
        confirmButtonText: 'Entendido',
        confirmButtonColor: '#1a73e8'
    });

    // Marcar el ítem activo en el sidebar
    document.querySelectorAll('.gd-nav-item').forEach(el => el.classList.remove('active'));
    document.getElementById('navSpam')?.classList.add('active');
}


function actualizarBreadcrumb(breadcrumb) {
    const container = document.getElementById('breadcrumb');
    let html = '';

    breadcrumb.forEach((item, index) => {
        if (index > 0) {
            html += '<span class="separator"><span class="material-icons">chevron_right</span></span>';
        }

        // [A-13] el nombre se escapa y la ruta va en un atributo, no dentro del código del onclick
        if (index === breadcrumb.length - 1) {
            html += `<span>${escHtml(item.nombre)}</span>`;
        } else {
            html += `<a href="#" data-ruta="${escHtml(item.ruta)}" onclick="navegarA(this.dataset.ruta);return false;">${escHtml(item.nombre)}</a>`;
        }
    });

    container.innerHTML = html;
}
