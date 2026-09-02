/*
 * Cliente de certificados de firma (.p12) por usuario.
 *
 * Los certificados se guardan EN EL SERVIDOR asociados al usuario, así están
 * disponibles desde cualquier dispositivo (PC, celular): se suben una vez y luego
 * solo se elige el certificado y se escribe la contraseña al firmar.
 *
 * La contraseña NO se guarda: se pide al usar el certificado y se conserva solo
 * en memoria durante la sesión.
 *
 * API global: window.FaroFirmaCerts = { guardar, listar, eliminar }
 *   guardar(file, password) -> {exito, datos:{id,name,nombre,org}} | {exito:false,mensaje}
 *   listar()               -> [{id, name, nombre, org}]
 *   eliminar(id)           -> {exito}
 */
(function () {
    'use strict';
    const BASE = '/api/pdf/firma-digital/certificados';

    async function guardar(file, password, recordarPassword) {
        const fd = new FormData();
        fd.append('certificado', file, file.name || 'certificado.p12');
        fd.append('password', password || '');
        // Si el usuario lo eligió, la contraseña se guarda CIFRADA en el servidor
        fd.append('guardar_password', recordarPassword ? 'true' : 'false');
        const r = await fetch(BASE, { method: 'POST', body: fd, credentials: 'same-origin' });
        try { return await r.json(); }
        catch (e) { return { exito: false, mensaje: 'Error del servidor (' + r.status + ')' }; }
    }

    async function listar() {
        try {
            const r = await fetch(BASE, { method: 'GET', credentials: 'same-origin' });
            const d = await r.json();
            return (d && d.exito && Array.isArray(d.datos)) ? d.datos : [];
        } catch (e) {
            return [];
        }
    }

    async function eliminar(id) {
        try {
            const r = await fetch(BASE + '/' + encodeURIComponent(id), {
                method: 'DELETE', credentials: 'same-origin'
            });
            return await r.json();
        } catch (e) {
            return { exito: false };
        }
    }

    async function recordarPassword(id, password) {
        const fd = new FormData();
        fd.append('password', password || '');
        try {
            const r = await fetch(BASE + '/' + encodeURIComponent(id) + '/password', {
                method: 'POST', body: fd, credentials: 'same-origin'
            });
            return await r.json();
        } catch (e) { return { exito: false }; }
    }

    async function olvidarPassword(id) {
        try {
            const r = await fetch(BASE + '/' + encodeURIComponent(id) + '/password', {
                method: 'DELETE', credentials: 'same-origin'
            });
            return await r.json();
        } catch (e) { return { exito: false }; }
    }

    // --- Aviso de privacidad / términos ---
    async function estadoConsentimiento() {
        try {
            const r = await fetch('/api/pdf/firma-digital/consentimiento', { credentials: 'same-origin' });
            return await r.json();
        } catch (e) { return { exito: false, aceptado: false }; }
    }

    async function aceptarConsentimiento(version) {
        const fd = new FormData();
        fd.append('version', version || '');
        try {
            const r = await fetch('/api/pdf/firma-digital/consentimiento', {
                method: 'POST', body: fd, credentials: 'same-origin'
            });
            return await r.json();
        } catch (e) { return { exito: false }; }
    }

    window.FaroFirmaCerts = {
        guardar, listar, eliminar,
        recordarPassword, olvidarPassword,
        estadoConsentimiento, aceptarConsentimiento,
    };
})();
