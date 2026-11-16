/**
 * explorador-perfil.js  -  Módulo: «Mi perfil»
 * Responsabilidad ÚNICA: ver y, si el directorio lo permite, editar el nombre con el que
 * los demás ven a la persona (GET/POST /mi-perfil; `editable` lo decide el servidor).
 * Depende de globales: API_BASE (config.js), escHtml (escape.js), Swal.
 */
async function abrirPanelPerfil() {
    try {
        const resp = await fetch(`${API_BASE}/mi-perfil`);
        const d = await resp.json().catch(() => null);
        if (!resp.ok || !d || !d.success) {
            Swal.fire('Error', (d && d.error) || 'No se pudo cargar su perfil', 'error');
            return;
        }
        const predeterminado = d.nombre_nomina || '';
        const editable = d.editable !== false;
        const ini = (predeterminado.trim().charAt(0) || '?').toUpperCase();
        const fotoHtml = d.foto_url
            ? `<img src="${escHtml(d.foto_url)}" alt="" style="width:96px;height:96px;border-radius:50%;object-fit:cover;box-shadow:0 2px 10px rgba(0,0,0,.18);">`
            : `<div style="width:96px;height:96px;border-radius:50%;background:#0061a1;color:#fff;font-size:38px;display:flex;align-items:center;justify-content:center;margin:auto;">${escHtml(ini)}</div>`;
        const ayuda = editable
            ? `Así le verán los demás cuando comparta archivos. Si lo deja vacío, se usa su nombre predeterminado (<strong>${escHtml(predeterminado || '-')}</strong>).`
            : 'Así le ven los demás cuando comparte archivos. Su nombre lo administra el directorio de la institución.';
        const result = await Swal.fire({
            title: 'Mi perfil',
            html: `
                <div style="text-align:center;margin-bottom:16px;">${fotoHtml}</div>
                <div style="text-align:left;font-size:13px;max-width:340px;margin:auto;">
                    <label for="perfilNombre" style="font-weight:600;color:#5f6368;display:block;margin-bottom:4px;">Nombre visible</label>
                    <input id="perfilNombre" class="swal2-input" maxlength="80" style="margin:0;width:100%;box-sizing:border-box;" value="${escHtml(d.nombre_visible || predeterminado)}" placeholder="${escHtml(predeterminado)}"${editable ? '' : ' disabled'}>
                    <p style="color:#9aa0a6;font-size:12px;margin:6px 0 14px;">${ayuda}</p>
                    <label style="font-weight:600;color:#5f6368;display:block;margin-bottom:2px;">Correo electrónico</label>
                    <div style="padding:4px 0;color:#202124;">${escHtml(d.email || '-')}</div>
                </div>`,
            showCancelButton: editable,
            confirmButtonText: editable ? 'Guardar' : 'Cerrar',
            cancelButtonText: 'Cancelar',
            confirmButtonColor: '#0061a1',
            focusConfirm: false,
            preConfirm: () => ({ nombre: (document.getElementById('perfilNombre').value || '').trim() })
        });
        if (editable && result.isConfirmed) {
            const r = await fetch(`${API_BASE}/mi-perfil`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ nombre_visible: result.value.nombre })
            });
            const rd = await r.json().catch(() => null);
            if (r.ok && rd && rd.success) {
                Swal.fire({ icon: 'success', title: 'Guardado', text: 'Su nombre visible se actualizó.', timer: 1600, showConfirmButton: false });
            } else {
                Swal.fire('Error', (rd && rd.error) || 'No se pudo guardar', 'error');
            }
        }
    } catch (e) {
        Swal.fire('Error', 'No se pudo abrir su perfil: ' + e.message, 'error');
    }
}
