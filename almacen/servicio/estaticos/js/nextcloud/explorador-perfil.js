/**
 * explorador-perfil.js  -  Modulo: "Mi perfil en la Nube"
 * Responsabilidad UNICA: ver/editar como te ven los demas (nombre visible).
 * Default = nombre de Nomina; si el usuario lo cambia, aplica. Foto y correo de Nomina.
 * Depende de globales: API_BASE, Swal.
 */
async function abrirPanelPerfil() {
    try {
        const resp = await fetch(`${API_BASE}/mi-perfil`);
        const d = await resp.json();
        if (!d || !d.success) { Swal.fire('Error', 'No se pudo cargar tu perfil', 'error'); return; }
        const ini = ((d.nombre_nomina || '?').trim().charAt(0) || '?').toUpperCase();
        const fotoHtml = d.foto_url
            ? `<img src="${d.foto_url}" style="width:96px;height:96px;border-radius:50%;object-fit:cover;box-shadow:0 2px 10px rgba(0,0,0,.18);">`
            : `<div style="width:96px;height:96px;border-radius:50%;background:#0061a1;color:#fff;font-size:38px;display:flex;align-items:center;justify-content:center;margin:auto;">${ini}</div>`;
        const valorActual = (d.nombre_visible || d.nombre_nomina || '').replace(/"/g, '&quot;');
        const result = await Swal.fire({
            title: 'Mi perfil en la Nube',
            html: `
                <div style="text-align:center;margin-bottom:16px;">${fotoHtml}</div>
                <div style="text-align:left;font-size:13px;max-width:340px;margin:auto;">
                    <label style="font-weight:600;color:#5f6368;display:block;margin-bottom:4px;">Nombre visible</label>
                    <input id="perfilNombre" class="swal2-input" style="margin:0;width:100%;box-sizing:border-box;" value="${valorActual}" placeholder="${(d.nombre_nomina || '').replace(/"/g, '&quot;')}">
                    <p style="color:#9aa0a6;font-size:12px;margin:6px 0 14px;">Asi te veran los demas cuando compartas archivos. Si lo dejas vacio, se usa tu nombre de Nomina (<strong>${d.nombre_nomina || '-'}</strong>).</p>
                    <label style="font-weight:600;color:#5f6368;display:block;margin-bottom:2px;">Correo</label>
                    <div style="padding:4px 0;color:#202124;">${d.email || '-'}</div>
                </div>`,
            showCancelButton: true,
            confirmButtonText: 'Guardar',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#0061a1',
            focusConfirm: false,
            preConfirm: () => ({ nombre: (document.getElementById('perfilNombre').value || '').trim() })
        });
        if (result.isConfirmed) {
            const r = await fetch(`${API_BASE}/mi-perfil`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nombre_visible: result.value.nombre })
            });
            const rd = await r.json();
            if (rd && rd.success) {
                Swal.fire({ icon: 'success', title: 'Guardado', text: 'Tu nombre visible se actualizo.', timer: 1600, showConfirmButton: false });
            } else {
                Swal.fire('Error', 'No se pudo guardar', 'error');
            }
        }
    } catch (e) {
        Swal.fire('Error', 'No se pudo abrir tu perfil: ' + e.message, 'error');
    }
}
