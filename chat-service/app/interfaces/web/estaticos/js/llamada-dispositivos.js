// Elegir micrófono, altavoz y cámara desde la propia llamada, y probar el micro antes de hablar.
//
// Hasta ahora la llamada usaba lo que el navegador tuviera por omisión: quien tiene dos cámaras
// (la del portátil y una externa), unos cascos y los altavoces del equipo, no podía cambiar sin
// salirse a la configuración de Windows. Y no había manera de saber si el micrófono se oye
// ANTES de que alguien esté al otro lado esperando.
//
// Vive aparte de `llamada.html` a propósito: la plantilla ya ronda las 600 líneas y esto lo usan
// también la conferencia grupal y cualquier pantalla futura con llamada.
(function (global) {
  'use strict';

  const TIPOS = {
    audioinput:  { icono: 'fa-microphone',    titulo: 'Micrófono' },
    audiooutput: { icono: 'fa-volume-up',     titulo: 'Altavoz' },
    videoinput:  { icono: 'fa-video',         titulo: 'Cámara' },
  };

  /** Lo elegido se recuerda para la próxima llamada: nadie quiere elegir sus cascos cada vez. */
  const RECUERDO = 'maquita.llamada.dispositivos';

  function recordado() {
    try { return JSON.parse(localStorage.getItem(RECUERDO) || '{}'); } catch { return {}; }
  }
  function recordar(tipo, id) {
    try {
      const r = recordado(); r[tipo] = id;
      localStorage.setItem(RECUERDO, JSON.stringify(r));
    } catch { /* ventana privada: se usa solo durante esta llamada */ }
  }

  /** Los dispositivos que hay, ya con nombre legible.
   *  Ojo: el navegador solo da los nombres DESPUÉS de conceder permisos; antes devuelve
   *  etiquetas vacías. Por eso esto se llama cuando la vista previa ya pidió la cámara. */
  async function listar(tipo) {
    let todos = [];
    try {
      todos = await navigator.mediaDevices.enumerateDevices();
    } catch { return []; }
    return todos
      .filter((d) => d.kind === tipo)
      .map((d, i) => ({
        id: d.deviceId,
        nombre: d.label || `${TIPOS[tipo].titulo} ${i + 1}`,
      }));
  }

  /** ¿Puede este navegador cambiar de altavoz? Firefox y iOS aún no. */
  function permiteElegirAltavoz() {
    return typeof HTMLMediaElement !== 'undefined' &&
           'setSinkId' in HTMLMediaElement.prototype;
  }

  // ─────────────────────────────────────────────── medidor para probar el micrófono
  let medidor = null;

  /** Enciende una barra que se mueve con la voz: sirve para saber si el micro elegido capta.
   *  Se apaga sola al cerrar el menú; si no, dejaría el micrófono abierto sin que se note. */
  async function medirMicrofono(deviceId, alMedir) {
    pararMedidor();
    try {
      const flujo = await navigator.mediaDevices.getUserMedia({
        audio: deviceId ? { deviceId: { exact: deviceId } } : true,
      });
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const fuente = ctx.createMediaStreamSource(flujo);
      const analizador = ctx.createAnalyser();
      analizador.fftSize = 512;
      fuente.connect(analizador);
      const datos = new Uint8Array(analizador.frequencyBinCount);
      let vivo = true;

      (function tick() {
        if (!vivo) return;
        analizador.getByteTimeDomainData(datos);
        // Cuánto se aparta la onda del silencio: 0 = nada, 1 = a tope.
        let pico = 0;
        for (const v of datos) pico = Math.max(pico, Math.abs(v - 128) / 128);
        alMedir(Math.min(1, pico * 2));
        requestAnimationFrame(tick);
      })();

      medidor = {
        parar() {
          vivo = false;
          try { flujo.getTracks().forEach((t) => t.stop()); } catch { /* ya parado */ }
          try { ctx.close(); } catch { /* ya cerrado */ }
        },
      };
    } catch {
      alMedir(-1); // -1 = no se pudo abrir ese micrófono
    }
  }

  function pararMedidor() {
    if (medidor) { medidor.parar(); medidor = null; }
  }

  // ─────────────────────────────────────────────── el menú
  /** Dibuja el menú de un tipo de dispositivo junto a su botón.
   *  `alElegir(id)` recibe el dispositivo elegido; quien llama decide qué hacer con él. */
  async function abrirMenu(tipo, boton, alElegir) {
    cerrarMenus();
    const lista = await listar(tipo);
    const menu = document.createElement('div');
    menu.className = 'menu-dispositivos';
    menu.dataset.tipo = tipo;

    if (!lista.length) {
      menu.innerHTML = '<div class="md-vacio">No se encontró ningún ' +
        TIPOS[tipo].titulo.toLowerCase() + '</div>';
    } else {
      const elegido = recordado()[tipo];
      for (const d of lista) {
        const fila = document.createElement('button');
        fila.className = 'md-opcion' + (d.id === elegido ? ' md-elegida' : '');
        fila.textContent = d.nombre;
        fila.onclick = async (e) => {
          e.stopPropagation();
          recordar(tipo, d.id);
          cerrarMenus();
          try { await alElegir(d.id); } catch { /* quien llama ya avisa si falla */ }
        };
        menu.appendChild(fila);
      }
      // Con el micrófono, además, se puede probar sin llamar a nadie.
      if (tipo === 'audioinput') {
        const prueba = document.createElement('div');
        prueba.className = 'md-prueba';
        prueba.innerHTML = '<div class="md-prueba-texto">Habla para probar</div>' +
                           '<div class="md-barra"><div class="md-barra-nivel"></div></div>';
        menu.appendChild(prueba);
        const nivel = prueba.querySelector('.md-barra-nivel');
        medirMicrofono(recordado()[tipo], (v) => {
          if (!nivel.isConnected) { pararMedidor(); return; }
          nivel.style.width = v < 0 ? '0%' : Math.round(v * 100) + '%';
          nivel.style.background = v < 0 ? '#a4262c' : '#107c10';
          if (v < 0) prueba.querySelector('.md-prueba-texto').textContent =
            'No se pudo abrir ese micrófono';
        });
      }
    }

    document.body.appendChild(menu);
    const caja = boton.getBoundingClientRect();
    menu.style.left = Math.max(8, Math.min(caja.left, window.innerWidth - menu.offsetWidth - 8)) + 'px';
    menu.style.top = (caja.top - menu.offsetHeight - 10) + 'px';
    setTimeout(() => document.addEventListener('click', cerrarMenus, { once: true }), 0);
  }

  function cerrarMenus() {
    pararMedidor();
    document.querySelectorAll('.menu-dispositivos').forEach((m) => m.remove());
  }

  /** Añade la flechita junto a un botón de la barra para desplegar sus dispositivos. */
  function ponerFlecha(botonId, tipo, alElegir) {
    const boton = document.getElementById(botonId);
    if (!boton || boton.dataset.conFlecha) return;
    if (tipo === 'audiooutput' && !permiteElegirAltavoz()) return; // el navegador no puede

    boton.dataset.conFlecha = '1';
    const flecha = document.createElement('button');
    flecha.className = 'flecha-dispositivos';
    flecha.title = 'Elegir ' + TIPOS[tipo].titulo.toLowerCase();
    flecha.innerHTML = '<i class="fas fa-chevron-up"></i>';
    flecha.onclick = (e) => { e.stopPropagation(); abrirMenu(tipo, boton, alElegir); };
    boton.insertAdjacentElement('afterend', flecha);
  }

  global.LlamadaDispositivos = { ponerFlecha, listar, cerrarMenus, permiteElegirAltavoz };
})(window);
