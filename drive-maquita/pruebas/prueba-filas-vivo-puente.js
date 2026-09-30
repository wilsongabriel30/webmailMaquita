/* Prueba del puente «respuestas del formulario en vivo»: qué le pide al
   servidor y al complemento, en qué orden, y —lo importante— que NO dé por
   escritas las respuestas si el complemento no pudo escribirlas. */

const fs = require('fs');
const vm = require('vm');

const RUTA_PUENTE = '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/editor-respuestas-filas-vivo.js';
const fallos = [];

function comprobar(ok, texto) {
    console.log((ok ? '  BIEN  ' : '  MAL   ') + texto);
    if (!ok) { fallos.push(texto); }
}

function montar(opciones) {
    const llamadas = [];
    const oyentes = [];
    const contexto = {
        console: { log: () => {} },
        URLSearchParams: URLSearchParams,
        location: { search: '?ruta=' + encodeURIComponent('/unidades/12/IBI 2025/hoja.xlsx') },
        setTimeout: (fn, ms) => (ms >= 5000 ? { tope: true } : setTimeout(fn, 0)),
        clearTimeout: () => {},
        Promise: Promise,
        fetch: (url, cfg) => {
            const cuerpo = cfg && cfg.body ? JSON.parse(cfg.body) : null;
            llamadas.push({ url: url.split('?')[0], cuerpo: cuerpo });
            return Promise.resolve({ json: () => Promise.resolve(opciones.servidor(url, cuerpo)) });
        },
    };
    contexto.window = contexto;
    contexto.window.location = contexto.location;
    contexto.window.addEventListener = (tipo, fn) => { if (tipo === 'message') { oyentes.push(fn); } };
    vm.createContext(contexto);
    vm.runInContext(fs.readFileSync(RUTA_PUENTE, 'utf8'), contexto);

    // El complemento: responde a lo que le mande el puente.
    const complemento = {
        postMessage: (mensaje) => {
            llamadas.push({ complemento: mensaje.tipo, hoja: mensaje.hoja, filas: mensaje.filas });
            const respuesta = opciones.complemento(mensaje);
            if (respuesta) { setTimeout(() => avisar(respuesta), 0); }
        },
    };
    const avisar = (datos) => oyentes.forEach((fn) => fn({ origin: 'https://intranet.example.org', source: complemento, data: datos }));
    contexto.window.location.origin = 'https://intranet.example.org';

    // El complemento se presenta.
    oyentes.forEach((fn) => fn({ origin: 'https://intranet.example.org', source: complemento,
                                 data: { tipo: 'maquita:filas:hola' } }));
    return { llamadas: llamadas };
}

const HOJAS = { success: true, hojas: [{ encuesta_id: 'f-1', hoja: 'Prueba IFO', pendientes: 1 }] };
const FILAS = { success: true, filas: [['21/09/2026', 'Ana', null]], columnas: [], renombres: [],
                hasta: '2026-09-21T12:00:00-05:00' };

function servidorNormal(url) {
    if (url.indexOf('/hojas') >= 0) { return HOJAS; }
    if (url.indexOf('/filas') >= 0) { return FILAS; }
    return { success: true };
}

async function principal() {
    // 1. Camino bueno: lee la hoja, pide filas, escribe y confirma.
    let escenario = montar({
        servidor: servidorNormal,
        complemento: (m) => {
            if (m.tipo === 'maquita:filas:leer') {
                return { tipo: 'maquita:filas:cabeceras', hoja: m.hoja,
                         estado: { encabezados: ['Fecha', 'Quién', 'TOTAL'], cabeceras: 4, ultima: 17 } };
            }
            if (m.tipo === 'maquita:filas:escribir') {
                return { tipo: 'maquita:filas:escrito', hoja: m.hoja, ok: true, escritas: 1 };
            }
            return null;
        },
    });
    await new Promise((r) => setTimeout(r, 60));
    let urls = escenario.llamadas.filter((l) => l.url).map((l) => l.url);
    let mensajes = escenario.llamadas.filter((l) => l.complemento).map((l) => l.complemento);
    comprobar(urls[0].endsWith('/encuestas/vivo/hojas'), 'primero pregunta si hay pendientes');
    comprobar(mensajes[0] === 'maquita:filas:leer', 'luego pide los encabezados al editor');
    comprobar(urls[1] && urls[1].endsWith('/encuestas/vivo/filas'), 'pide al servidor las filas ya colocadas');
    const pedido = escenario.llamadas.find((l) => l.url && l.url.endsWith('/filas')).cuerpo;
    comprobar(pedido.encabezados.join('|') === 'Fecha|Quién|TOTAL',
              'manda al servidor los encabezados que ve el editor');
    comprobar(mensajes[1] === 'maquita:filas:escribir', 'manda las filas al complemento');
    comprobar(urls[2] && urls[2].endsWith('/encuestas/vivo/aplicado'), 'solo al final confirma');
    const confirmado = escenario.llamadas.find((l) => l.url && l.url.endsWith('/aplicado')).cuerpo;
    comprobar(confirmado.hasta === FILAS.hasta, 'confirma justo hasta la respuesta escrita');

    // 2. El complemento no puede escribir: NO se confirma nada.
    escenario = montar({
        servidor: servidorNormal,
        complemento: (m) => {
            if (m.tipo === 'maquita:filas:leer') {
                return { tipo: 'maquita:filas:cabeceras', hoja: m.hoja,
                         estado: { encabezados: ['Fecha', 'Quién', 'TOTAL'], cabeceras: 4, ultima: 17 } };
            }
            if (m.tipo === 'maquita:filas:escribir') {
                return { tipo: 'maquita:filas:escrito', hoja: m.hoja, ok: false };
            }
            return null;
        },
    });
    await new Promise((r) => setTimeout(r, 60));
    comprobar(!escenario.llamadas.some((l) => l.url && l.url.endsWith('/aplicado')),
              'si el editor no escribe, la respuesta NO se da por escrita');

    // 3. La hoja no se puede leer: ni se piden filas ni se confirma.
    escenario = montar({
        servidor: servidorNormal,
        complemento: (m) => (m.tipo === 'maquita:filas:leer'
            ? { tipo: 'maquita:filas:cabeceras', hoja: m.hoja, estado: null } : null),
    });
    await new Promise((r) => setTimeout(r, 60));
    comprobar(!escenario.llamadas.some((l) => l.url && (l.url.endsWith('/filas') || l.url.endsWith('/aplicado'))),
              'sin poder leer la tabla no se escribe ni se confirma');

    // 4. Sin pendientes: no molesta al editor.
    escenario = montar({
        servidor: (url) => (url.indexOf('/hojas') >= 0 ? { success: true, hojas: [] } : { success: true }),
        complemento: () => null,
    });
    await new Promise((r) => setTimeout(r, 60));
    comprobar(!escenario.llamadas.some((l) => l.complemento),
              'sin respuestas pendientes no se toca el editor');

    console.log(fallos.length ? 'RESULTADO: FALLOS -> ' + fallos.join(' · ') : 'RESULTADO: TODO BIEN');
    process.exit(fallos.length ? 1 : 0);
}

principal();
