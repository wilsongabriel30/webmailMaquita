/**
 * El documento vive en el servidor mientras se edita.
 * =================================================================
 * Hasta ahora, cada clic mandaba el PDF entero y recibía el PDF entero: en una
 * proforma de 130 páginas, 3 MB de subida y 3 MB de bajada por cada celda que se
 * guarda. Con mil personas trabajando a la vez ese es el techo, y ya no es de
 * procesador sino de red.
 *
 * Ahora el documento se deja una vez en el servidor y cada cambio manda solo su
 * identificador. Como el servidor guarda **añadiendo al final**, lo que devuelve
 * es únicamente ese añadido: aquí se pega a la copia que ya tenemos y listo.
 * Medido: de 6.300 kB por clic a 150.
 *
 * Si algo se tuerce —la sesión caducó, el documento cambió por otro camino, dos
 * pestañas a la vez— el servidor lo dice (409) y aquí se vuelve a subir el
 * documento y se repite la operación. El usuario no se entera de nada.
 *
 * Autoría: Equipo de Tecnología Maquita — 2026-07-29
 */
(function () {
    'use strict';

    let identificador = null;
    let abriendo = null;          // la subida en curso, para no hacer dos

    /**
     * La huella del documento: 64 letras que lo identifican sin mandarlo.
     *
     * Cuesta unas centésimas de segundo y puede ahorrar una subida entera.
     * Si el navegador no sabe calcularla (no debería pasar: hace falta https,
     * y esto va por https) se devuelve null y se sube como siempre.
     */
    async function huellaDe(bytes) {
        try {
            if (!window.crypto || !crypto.subtle) return null;
            const resumen = await crypto.subtle.digest('SHA-256', bytes);
            return Array.from(new Uint8Array(resumen))
                .map(b => b.toString(16).padStart(2, '0')).join('');
        } catch (e) {
            return null;
        }
    }

    /** ¿El servidor ya tiene este mismo documento? Devuelve su id, o null. */
    async function yaEstaba(huella, cuanto) {
        if (!huella) return null;
        try {
            const cuerpo = new FormData();
            cuerpo.append('huella', huella);
            cuerpo.append('tamano', cuanto);
            const resp = await fetch('/api/pdf/sesion/huella', {
                method: 'POST', body: cuerpo, credentials: 'same-origin'
            });
            const json = await resp.json();
            return (json && json.exito) ? (json.doc || null) : null;
        } catch (e) {
            return null;
        }
    }

    /**
     * Deja el documento en el servidor. Devuelve su identificador, o null.
     *
     * Antes de subir nada se pregunta si ya está: al recargar la página, al
     * abrirlo en otra pestaña o al volver al documento de ayer, el archivo
     * sigue ahí y la subida —que en una proforma de 20 MB es lo más lento de
     * todo el editor— se ahorra entera.
     *
     * Y cuando hay que subirlo, se manda tal cual, sin envoltorio de
     * formulario: el servidor lo escribe según llega en vez de dejarlo de paso
     * en un archivo temporal en disco.
     */
    async function abrir(bytes) {
        if (!bytes || !bytes.length) return null;
        if (abriendo) return abriendo;
        abriendo = (async () => {
            try {
                const huella = await huellaDe(bytes);
                const conocido = await yaEstaba(huella, bytes.length);
                if (conocido) {
                    identificador = conocido;
                    return identificador;
                }
                const resp = await fetch('/api/pdf/sesion', {
                    method: 'POST',
                    body: bytes,
                    headers: {
                        'Content-Type': 'application/pdf',
                        'X-Pdf-Huella': huella || ''
                    },
                    credentials: 'same-origin'
                });
                const json = await resp.json();
                identificador = (json && json.exito) ? json.doc : null;
            } catch (e) {
                // Sin sesión se sigue trabajando como siempre: mandando el PDF
                // entero. Más lento, pero nunca deja al usuario sin editor.
                identificador = null;
            } finally {
                abriendo = null;
            }
            return identificador;
        })();
        return abriendo;
    }

    function id() { return identificador; }

    /**
     * El identificador, esperando a la subida si está a medias.
     *
     * Es la diferencia entre subir el documento una vez o cuatro: mientras la
     * subida inicial iba por la mitad, cada consulta y cada cambio adjuntaba
     * el PDF ENTERO otra vez —porque todavía no había identificador— y todas
     * esas copias competían por la misma línea, haciendo aún más lenta la
     * subida que estaban esperando. (Auditoría del 18-ago-2026.)
     */
    async function listo() {
        if (identificador) return identificador;
        if (abriendo) {
            try { return await abriendo; } catch (e) { return null; }
        }
        return null;
    }

    /** El documento del servidor ya no vale: se olvida (y se vuelve a subir). */
    function olvidar() { identificador = null; }

    /** Borra el documento del servidor. Al cerrar el editor. */
    function cerrar() {
        if (!identificador) return;
        const doc = identificador;
        identificador = null;
        try {
            // `keepalive` para que salga aunque la pestaña se esté cerrando.
            fetch('/api/pdf/sesion/' + encodeURIComponent(doc),
                  {method: 'DELETE', credentials: 'same-origin', keepalive: true});
        } catch (e) { /* si no sale, el servidor lo barre solo */ }
    }

    /**
     * Envía una operación y devuelve el PDF resultante ya montado.
     *
     * `campos` son los datos propios de la operación. `bytesActuales` es nuestra
     * copia del documento, que hace falta para pegarle el trozo que llegue y
     * para poder rehacer la sesión si se perdió.
     *
     * Devuelve `{bytes, aviso}`.
     */
    async function enviar(url, campos, bytesActuales, sinReintento) {
        const cuerpo = new FormData();
        Object.keys(campos).forEach(k => cuerpo.append(k, campos[k]));

        const doc = await listo();
        if (doc) {
            cuerpo.append('doc', doc);
            // Cuánto mide NUESTRA copia: si el servidor tiene otra cosa, lo dice
            // en vez de mezclarlas.
            cuerpo.append('base', bytesActuales.length);
        } else {
            cuerpo.append('archivo',
                          new Blob([bytesActuales], {type: 'application/pdf'}),
                          'documento.pdf');
        }

        const resp = await fetch(url, {
            method: 'POST', body: cuerpo, credentials: 'same-origin'
        });

        if (resp.status === 409 && !sinReintento) {
            // La sesión se perdió. Se sube otra vez lo que tenemos y se repite.
            olvidar();
            await abrir(bytesActuales);
            return enviar(url, campos, bytesActuales, true);
        }
        if (resp.status === 503 && !sinReintento) {
            // El servidor está lleno: espera lo que él diga y reintenta una vez.
            const espera = parseInt(resp.headers.get('Retry-After') || '5', 10);
            await new Promise(r => setTimeout(r, Math.min(espera, 10) * 1000));
            return enviar(url, campos, bytesActuales, true);
        }
        if (!resp.ok) {
            let mensaje = 'El servidor respondió ' + resp.status;
            try { mensaje = (await resp.json()).mensaje || mensaje; } catch (e) { /* no era JSON */ }
            throw new Error(mensaje);
        }

        const aviso = resp.headers.get('X-Aviso-Tabla');
        const desde = parseInt(resp.headers.get('X-Pdf-Desde') || '0', 10);
        const llegado = new Uint8Array(await resp.arrayBuffer());

        if (desde > 0 && desde <= bytesActuales.length) {
            // Solo llegó lo añadido: se pega al final de lo que ya teníamos.
            const montado = new Uint8Array(desde + llegado.length);
            montado.set(bytesActuales.subarray(0, desde), 0);
            montado.set(llegado, desde);
            return {bytes: montado, aviso: aviso};
        }
        return {bytes: llegado, aviso: aviso};
    }

    /**
     * Una consulta que no cambia el documento (reconocer tablas, leer un párrafo).
     *
     * Va aparte de  porque devuelve JSON y no un PDF, pero necesita lo
     * mismo: si la sesión se perdió, volver a subir el documento y repetir. Sin
     * esto, el reconocimiento de tablas se quedaba atascado con un aviso de error
     * hasta que el usuario recargaba la página. (Auditoría del 29-jul-2026.)
     */
    async function consultar(url, campos, bytesActuales, sinReintento) {
        const resp = await fetch(url, {
            method: 'POST', body: await datosDeConsulta(campos, bytesActuales),
            credentials: 'same-origin'
        });
        if (resp.status === 409 && !sinReintento) {
            olvidar();
            await abrir(bytesActuales);
            return consultar(url, campos, bytesActuales, true);
        }
        return resp;
    }

    /** Los datos de una consulta que no cambia el documento (detectar, párrafo).
     *
     * Espera a la subida si está en curso, por lo mismo que `enviar`: mandar
     * el documento entero mientras se está subiendo es pagarlo dos veces.
     */
    async function datosDeConsulta(campos, bytesActuales) {
        const cuerpo = new FormData();
        Object.keys(campos).forEach(k => cuerpo.append(k, campos[k]));
        const doc = await listo();
        if (doc) {
            cuerpo.append('doc', doc);
            cuerpo.append('base', bytesActuales.length);
        } else {
            cuerpo.append('archivo',
                          new Blob([bytesActuales], {type: 'application/pdf'}),
                          'documento.pdf');
        }
        return cuerpo;
    }

    window.PDFSesion = {
        abrir: abrir,
        id: id,
        listo: listo,
        olvidar: olvidar,
        cerrar: cerrar,
        enviar: enviar,
        consultar: consultar,
        datosDeConsulta: datosDeConsulta
    };

    window.addEventListener('pagehide', cerrar);
})();
