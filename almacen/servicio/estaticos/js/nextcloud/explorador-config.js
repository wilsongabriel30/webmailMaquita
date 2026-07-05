// =============================================================================
// NUBE MAQUITA - JavaScript
// =============================================================================

// API_BASE/URL_BASE por defecto apuntan a la Nube en producción (Nextcloud).
// Si la página define window.ALMACEN_OVERRIDE (modo pruebas del motor propio,
// solo master), el MISMO explorador se conecta al Almacén Maquita sin chocar
// con producción. Ver /archivos-almacen. (2026-07-03)
const API_BASE = (window.ALMACEN_OVERRIDE && window.ALMACEN_OVERRIDE.api) || '/api/nextcloud';
const URL_BASE = (window.ALMACEN_OVERRIDE && window.ALMACEN_OVERRIDE.url) || '/archivos/mi-unidad';
// True cuando el explorador está conectado al motor propio (Almacén), no a Nextcloud.
const MODO_ALMACEN = !!(window.ALMACEN_OVERRIDE);

// Abre el editor online (OnlyOffice). En modo Almacén usa el editor del motor
// propio (/archivos-almacen/editar → servidor OnlyOffice dedicado); diagramas
// aún no. tipo: 'diagrama' para Draw.io, cualquier otro = documento.
function _abrirEditorNube(ruta, tipo) {
    if (MODO_ALMACEN) {
        if (tipo === 'diagrama') {
            mostrarNotificacion('El editor de diagramas aún no está disponible en el motor propio', 'info');
            return;
        }
        window.open(`/archivos-almacen/editar?ruta=${encodeURIComponent(ruta)}`, '_blank');
        return;
    }
    const destino = (tipo === 'diagrama') ? '/archivos/editar-diagrama' : '/archivos/editar';
    window.open(`${destino}?ruta=${encodeURIComponent(ruta)}`, '_blank');
}
let itemSeleccionado = null;
let vistaGrid = true;

// Variables de ordenamiento y filtro
let ordenarPor = 'nombre';   // nombre, fecha, tamano, tipo (nombre = igual que Nextcloud)
let ordenDir = 'asc';        // asc, desc (asc = A-Z, 1-2-3)
let filtroTipo = null;       // null = todos, documento, imagen, video, etc.

// Variables para carga progresiva (REQ-09/10)
const ITEMS_POR_BLOQUE = 50;
let archivosCompletos = { carpetas: [], archivos: [] };
let itemsMostrados = 0;
let cargandoMas = false;
let observerInfiniteScroll = null;

// Función de notificaciones (toast)
function mostrarNotificacion(mensaje, tipo = 'info') {
    const iconos = {
        success: 'check_circle',
        error: 'error',
        warning: 'warning',
        info: 'info'
    };
    const colores = {
        success: '#34a853',
        error: '#ea4335',
        warning: '#f9ab00',
        info: '#4285f4'
    };

    Swal.fire({
        toast: true,
        position: 'bottom-end',
        icon: tipo,
        title: mensaje,
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true
    });
}

// Mapeo de tipos a iconos Material
const ICONOS = {
    carpeta: 'folder',
    documento: 'description',
    hoja_calculo: 'table_chart',
    presentacion: 'slideshow',
    pdf: 'picture_as_pdf',
    imagen: 'image',
    video: 'videocam',
    audio: 'audiotrack',
    comprimido: 'folder_zip',
    drawio: 'schema',
    otro: 'insert_drive_file'
};

const CLASES_TIPO = {
    carpeta: 'folder',
    documento: 'document',
    hoja_calculo: 'spreadsheet',
    presentacion: 'presentation',
    pdf: 'pdf',
    imagen: 'image',
    video: 'video',
    audio: 'audio',
    comprimido: 'archive',
    drawio: 'drawio',
    otro: 'default'
};

// Estado del lightbox
let lightboxArchivos = [];
let lightboxIndice = 0;
let lightboxArchivoActual = null;

// Extensiones por tipo
const EXTENSIONES_IMAGEN = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp', 'ico', 'tiff', 'tif'];
const EXTENSIONES_PDF = ['pdf'];
const EXTENSIONES_OFFICE = ['doc', 'docx', 'xls', 'xlsx', 'xlsm', 'ppt', 'pptx', 'odt', 'ods', 'odp'];
const EXTENSIONES_VIDEO = ['mp4', 'webm', 'mov', 'avi', 'mkv'];
const EXTENSIONES_DRAWIO = ['drawio', 'dwb'];
const EXTENSIONES_BPMN = ['bpmn'];
const EXTENSIONES_SIN_PREVIEW = ['bpmn', 'xml', 'json', 'yml', 'yaml', 'ini', 'conf', 'sh', 'bat', 'ps1'];

