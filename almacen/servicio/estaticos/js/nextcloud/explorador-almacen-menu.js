/**
 * explorador-almacen-menu.js  -  Módulo: panel «Configuración» del lateral, según el rol
 * Responsabilidad ÚNICA: decidir qué opciones ve cada persona y mostrar el espacio de su cuenta.
 *
 * Antes el panel era el mismo para todos: «Herramientas de administración (solo master)» con
 * la recuperación de archivos de otras personas, el destino del almacenamiento y las cuotas.
 * El servidor lo rechazaba bien (403), pero una cuenta normal no debe ver esos formularios.
 * Ahora ve solo lo suyo (actividad, unidades compartidas, su espacio).
 *
 * El rol lo conoce la página: la plantilla define window.ALMACEN_ES_ADMIN. Es solo
 * presentación; quien autoriza de verdad sigue siendo el servidor (/api/almacen/admin/*).
 *
 * Depende de: normalizarCuota (cuota.js), escHtml (escape.js), Swal y los paneles de
 *   explorador-almacen-admin.js (abrirActividad, abrirUnidades, abrirCuotas...).
 */

const OPCIONES_ALMACEN_PERSONALES = [
    ['schedule', 'Actividad reciente', 'abrirActividad'],
    ['groups', 'Unidades compartidas (equipos)', 'abrirUnidades'],
    ['pie_chart', 'Mi almacenamiento', 'abrirCuotaAlmacen']
];
const OPCIONES_ALMACEN_ADMIN = [
    ['restore', 'Recuperar archivos de un usuario', 'abrirRecuperacionAlmacen'],
    ['storage', 'Almacenamiento — dónde se guardan los archivos', 'abrirAlmacenamiento'],
    ['person', 'Espacio de usuarios (cuotas)', 'abrirCuotas']
];

function esAdminAlmacen() {
    return window.ALMACEN_ES_ADMIN === true;
}

/** Opciones del panel para el rol dado: [icono, rótulo, función]. */
function opcionesConfigAlmacen(esAdmin) {
    return esAdmin ? OPCIONES_ALMACEN_ADMIN.concat(OPCIONES_ALMACEN_PERSONALES) : OPCIONES_ALMACEN_PERSONALES.slice();
}

/** Las herramientas de administración lo llaman al empezar: una cuenta normal no las abre. */
function exigirAdminAlmacen() {
    if (esAdminAlmacen()) return true;
    Swal.fire({ icon: 'info', title: 'Solo para administradores',
                text: 'Esta herramienta es de administración. Si la necesita, solicítela al área de Tecnología.' });
    return false;
}

function abrirConfigAlmacen() {
    if (typeof MODO_ALMACEN === 'undefined' || !MODO_ALMACEN) return;
    const esAdmin = esAdminAlmacen();
    const botones = opcionesConfigAlmacen(esAdmin).map(o =>
        '<button class="alm-menu-btn" onclick="Swal.close(); ' + o[2] + '();">'
        + '<span class="material-icons">' + o[0] + '</span> ' + o[1] + '</button>').join('');
    Swal.fire({
        title: esAdmin ? 'Configuración del Almacén' : 'Configuración',
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
            ${esAdmin ? '<p style="color:#5f6368;font-size:.9rem;margin:0 0 10px">Incluye las herramientas de administración.</p>' : ''}
            <div id="menuConfigAlmacen" style="display:flex;flex-direction:column;gap:2px;text-align:left">${botones}</div>`,
        showConfirmButton: false,
        showCloseButton: true,
        width: 460,
    });
}

/** Rótulo de la cuota de la cuenta: dice si es propia o la predeterminada de la instalación. */
function rotuloCuotaCuenta(cuota, esPropia) {
    if (cuota.sin_limite) return 'Sin límite';
    return cuota.total_humano + (esPropia ? ' (asignada a su cuenta)' : ' (la predeterminada de la instalación)');
}

/** «Mi almacenamiento»: la misma fuente que el lateral (GET /cuota, leída con normalizarCuota). */
async function abrirCuotaAlmacen() {
    let datos, cuota;
    try {
        datos = await (await fetch('/api/almacen/cuota', { credentials: 'same-origin' })).json();
        cuota = normalizarCuota(datos);
    } catch (e) { cuota = null; }
    if (!cuota) {
        Swal.fire({ icon: 'error', title: 'No disponible', text: 'No se pudo leer el espacio de su cuenta.' });
        return;
    }
    Swal.fire({
        title: 'Mi almacenamiento',
        html: '<div id="miAlmacenamiento" style="text-align:left;line-height:1.9">'
            + 'Usado: <b>' + escHtml(cuota.usado_humano) + '</b><br>'
            + 'Cuota de su cuenta: <b>' + escHtml(rotuloCuotaCuenta(cuota, datos.cuota_propia === true)) + '</b><br>'
            + 'Libre: <b>' + escHtml(cuota.libre_humano) + '</b><br>'
            + 'Uso: <b>' + cuota.porcentaje_usado.toFixed(1) + ' %</b></div>',
        confirmButtonText: 'Cerrar',
        confirmButtonColor: '#3c4043'
    });
}

window.abrirConfigAlmacen = abrirConfigAlmacen;
