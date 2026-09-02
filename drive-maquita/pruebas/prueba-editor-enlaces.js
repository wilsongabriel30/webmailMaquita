/* Simulacro de la página del editor, sin navegador: comprueba que la tarjeta
   sale donde debe, con lo que debe, y que se va al hacer clic derecho. */

function nodo() {
    const n = {
        style: {}, className: '', textContent: '', title: '', innerHTML: '',
        offsetWidth: 300, offsetHeight: 230, parentNode: null, hijos: [],
        _porSelector: {}, onclick: null,
        setAttribute() { }, addEventListener() { },
        contains(otro) { return otro === n; },
        appendChild(h) { h.parentNode = n; n.hijos.push(h); },
        removeChild(h) { h.parentNode = null; },
        querySelector(sel) {
            if (!n._porSelector[sel]) n._porSelector[sel] = nodo();
            return n._porSelector[sel];
        },
        querySelectorAll() { return []; },
        getBoundingClientRect() { return { left: 0, top: 0 }; }
    };
    return n;
}

// ── El editor, dentro de un iframe a (100,60) ────────────────────────────
const contenedorHoja = { getBoundingClientRect() { return { left: 40, top: 120 }; } };
const celda = { asc_getX: () => 820, asc_getY: () => 150,
                asc_getWidth: () => 200, asc_getHeight: () => 26 };
const enlaceCelda = {
    asc_getText: () => 'C11.R2A4 Proceso Formativo <b>Masculinidades</b>',
    asc_getHyperlinkUrl: () => 'https://drive.google.com/drive/folders/1ISd5-I9D2Dbps20o22rPih2QGhhh9sgp?usp=drive_link'
};
let editado = 0, quitado = 0;
const creados = [];   // avisos flotantes que el editor pide crear
const escuchas = {};
const docEditor = {
    body: {}, getElementById: (id) => (id === 'editor_sdk' ? contenedorHoja : null),
    addEventListener(s, f) { (escuchas[s] = escuchas[s] || []).push(f); },
    querySelectorAll: () => []
};
const ventanaEditor = {
    document: docEditor,
    Asc: { editor: {
        wb: { getWorksheet: () => ({ getActiveCellCoord: () => celda }) },
        asc_getCellInfo: () => ({ asc_getHyperlink: () => enlaceCelda })
    } },
    SSE: { getController: () => ({
        permissions: { isEdit: true },
        onInsHyperlink() { editado++; },
        onDelHyperlink() { quitado++; }
    }) },
    Common: { UI: { Tooltip: function TooltipOriginal(opciones) {
        this.opciones = opciones; creados.push(opciones);
    } } },
    frameElement: { getBoundingClientRect() { return { left: 100, top: 60 }; } },
    open() { throw new Error('SE FUE AL ENLACE'); }
};
ventanaEditor.parent = global;

// ── La página ────────────────────────────────────────────────────────────
let puesta = null;
global.window = global;
global.innerWidth = 1365; global.innerHeight = 720;
global.document = {
    body: {
        appendChild(n) { n.parentNode = global.document.body; puesta = n; },
        removeChild() { puesta = null; }
    },
    head: { appendChild() { } },
    createElement: () => nodo(),
    querySelectorAll: (s) => (s === 'iframe' ? [{ contentWindow: ventanaEditor }] : []),
    addEventListener() { }
};
global.navigator = { clipboard: { writeText: () => Promise.resolve() } };
global.setInterval = (f) => { f(); return 1; };
const esperar = setTimeout;   // el de verdad: hay respuestas que llegan luego
global.addEventListener = () => { };
global.location = { href: 'https://datos.maquita.com.ec/archivos-almacen/editar' };
let preguntado = null;
global.fetch = (u) => {
    preguntado = u;
    return Promise.resolve({
        ok: true,
        json: () => Promise.resolve({
            success: true, acceso: true, es_maquita: true, tipo: 'carpeta',
            nombre: '1 Esmeraldas Procesos Formativos y Sociales',
            que: 'Carpeta del Drive Maquita',
            donde: 'Unidad compartida «Procesos Formativos»',
            propietario: 'KAREN ARMAS UQUILLAS',
            elementos: 4, elementos_hay_mas: false, existe: true,
            modificado: 1786635461
        })
    });
};

require('/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-enlaces.js');

const URL_PRUEBA = enlaceCelda.asc_getHyperlinkUrl();
const salida = ventanaEditor.open(URL_PRUEBA, '_blank');

const t = puesta;
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);

bien(salida === null, 'no se va al enlace');
bien(!!t, 'sale la tarjeta');
bien(t.style.left === '960px' && t.style.top === '360px',
     'colgada del borde de la celda (960px, 360px) — sale ' + t.style.left + ', ' + t.style.top);
bien(t.querySelector('.maq-te-titulo').textContent.indexOf('C11.R2A4') === 0,
     'lleva el nombre del enlace, no la direccion');
bien(t.innerHTML.indexOf('<b>Masculinidades</b>') === -1,
     'el texto de la celda NO se mete como HTML');
bien(t.querySelector('.maq-te-que').textContent === 'Carpeta de Google Drive',
     'dice que es una carpeta de Google Drive');
bien(t.querySelector('.maq-te-url').textContent.indexOf('drive.google.com') === 0,
     'muestra la direccion sin el https://');

t.querySelector('[data-accion="editar"]').onclick();
bien(editado === 1 && puesta === null, 'editar llama al editor y cierra la tarjeta');

ventanaEditor.open(URL_PRUEBA, '_blank');
puesta.querySelector('[data-accion="quitar"]').onclick();
bien(quitado === 1 && puesta === null, 'quitar llama al editor y cierra la tarjeta');

// ── Se va con el clic derecho dentro del editor ──────────────────────────
/* Reloj simulado: la tarjeta ignora lo que pase en sus primeros 400 ms
   —el clic que la abre sigue su curso y la cerraria al nacer—, asi que en
   cada prueba se adelanta el reloj despues de abrirla. */
let ahora = Date.now();
Date.now = () => ahora;

function abrirYEsperar() {
    ventanaEditor.open(URL_PRUEBA, '_blank');
    ahora += 5000;
}

ventanaEditor.open(URL_PRUEBA, '_blank');
const menu = escuchas['contextmenu'][0];
menu({ target: {} });
bien(puesta !== null, 'no se cierra sola al nacer (el clic que la abre sigue)');

ahora += 5000;
menu({ target: {} });
bien(puesta === null, 'el clic derecho la cierra');

abrirYEsperar();
escuchas['keydown'][0]({ target: {} });
bien(puesta === null, 'escribir la cierra');

abrirYEsperar();
escuchas['wheel'][0]({ target: {} });
bien(puesta === null, 'mover la rueda la cierra');

abrirYEsperar();
escuchas['mousedown'][0]({ target: {} });
bien(puesta === null, 'pulsar otra celda la cierra');

// Pulsar DENTRO de la tarjeta no la cierra: si no, no se podria usar.
abrirYEsperar();
const dentro = puesta;
escuchas['mousedown'][0]({ target: dentro });
bien(puesta === dentro, 'pulsar dentro de la tarjeta no la cierra');


// ── Los enlaces del propio Drive Maquita ─────────────────────────────────
const URL_MAQUITA = 'https://drive.maquita.com.ec/archivos-almacen/unidades/9/1%20Esmeraldas';

preguntado = null;
abrirYEsperar();              // URL_PRUEBA es de Google Drive, no nuestra
bien(preguntado === null, 'un enlace AJENO no se le pregunta al Drive');

preguntado = null;
ventanaEditor.open(URL_MAQUITA, '_blank');
ahora += 5000;
const tm = puesta;
bien(!!preguntado && preguntado.indexOf('/api/almacen/enlace-info?url=') === 0,
     'un enlace de MAQUITA se le pregunta al Drive');

// La respuesta llega despues: la tarjeta ya estaba en pantalla.
esperar(() => {
    bien(tm.querySelector('.maq-te-titulo').textContent.indexOf('1 Esmeraldas') === 0,
         'la tarjeta pasa a mostrar el nombre real');
    bien(tm.querySelector('.maq-te-que').textContent === 'Carpeta del Drive Maquita',
         'y que es una carpeta del Drive Maquita');
    const pie = tm.querySelector('.maq-te-detalles');
    const textos = pie.hijos.map(l => l.hijos[1].textContent);
    bien(textos.indexOf('Propiedad de KAREN ARMAS UQUILLAS') !== -1,
         'dice de quien es');
    bien(textos.indexOf('Unidad compartida «Procesos Formativos»') !== -1,
         'dice en que unidad vive');
    bien(textos.indexOf('4 elementos') !== -1, 'dice cuantas cosas tiene dentro');
    bien(textos.some(t => t.indexOf('Modificado el') === 0), 'dice cuando se toco');
}, 0);


// ── El aviso al pasar por encima de una celda con enlace ─────────────────
const UI = ventanaEditor.Common.UI;

// El del enlace: se le da uno mudo, que no ensena nada.
const avisoEnlace = new UI.Tooltip({ owner: { id: 'tip-container-hyperlinktip' },
                                     title: 'https://ejemplo/<br><b>Haga clic...</b>' });
bien(typeof avisoEnlace.getBSTip === 'function' && avisoEnlace.isVisible() === true,
     'el aviso del enlace se sustituye por uno mudo');
bien(avisoEnlace.getBSTip()['$tip'].height() === 0,
     'el mudo responde lo que el editor le pregunta, sin dibujar nada');

// Los demas avisos del editor NO se tocan.
const antes = creados.length;
const avisoFila = new UI.Tooltip({ owner: { id: 'tip-container-rowcolumntip' },
                                   title: 'Alto: 20 px' });
bien(creados.length === antes + 1 && avisoFila.opciones.title === 'Alto: 20 px',
     'los demas avisos del editor siguen funcionando');
