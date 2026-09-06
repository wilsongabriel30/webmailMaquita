/**
 * explorador-render.js  -  Modulo: Render de items (tarjetas y filas)
 * Responsabilidad UNICA: construir el HTML de cada archivo/carpeta (item -> HTML).
 * Funciones puras. Depende de globales:
 *   ICONOS, CLASES_TIPO (explorador-config.js), formatearFecha (explorador-interactions.js)
 * Cargar DESPUES de config, core e interactions.
 */

/**
 * [A-13] Escape para atributos y texto. Los nombres de archivo y carpeta los pone
 * el usuario y aqui se interpolaban crudos: un archivo llamado
 *   x" onmouseover=alert(1) y="
 * rompia el atributo y ejecutaba codigo en el dominio del correo, para cualquiera
 * que abriera esa carpeta (tambien en una unidad compartida).
 */
// escHtml vive en explorador-escape.js (se carga antes) [A-13]

function _avatarOnError(img, inicial) {
    try {
        const div = document.createElement('div');
        div.className = 'owner-avatar';
        div.textContent = inicial || '?';
        if (img && img.parentElement) img.parentElement.replaceChild(div, img);
    } catch (e) {}
}


function crearCard(item) {
    const tipo = item.es_carpeta ? 'carpeta' : item.tipo;
    const icono = ICONOS[tipo] || 'insert_drive_file';
    const clase = CLASES_TIPO[tipo] || 'default';
    const esCarpeta = item.es_carpeta === true || item.es_carpeta === 'true';

    // Para CARPETAS: Estilo Google Drive (ícono + nombre + menú, sin preview)
    if (esCarpeta) {
        const colorPersonalizado = item.color_personalizado || item.color || '#5f6368';

        return `
            <div class="gd-folder-card"
                 data-ruta="${escHtml(item.ruta_completa || item.ruta)}"
                 data-acceso="${item.es_acceso_directo ? 'true' : ''}" data-destino="${item.destino || ''}"
                 data-folder-id="${item.folder_id || ''}"
                 data-carpeta="true"
                 data-nombre="${escHtml(item.nombre)}"
                 data-tipo="carpeta"
                 data-tamano="${item.tamano_humano || ''}"
                 data-modificado="${item.modificado_at || ''}"
                 data-favorito="${item.es_favorito || item.es_favorita || false}"
                 data-compartido="${item.es_compartido || item.es_compartida || false}"
                 data-color="${colorPersonalizado}"
                 draggable="true"
                 ondragstart="iniciarArrastre(event, this)"
                 ondragend="finalizarArrastre(event)"
                 ondragover="permitirSoltar(event, this)"
                 ondragleave="salirSoltar(event, this)"
                 ondrop="soltarEnCarpeta(event, this)"
                 ondblclick="abrirItem(this)"
                 onclick="seleccionarItem(event, this)"
                 oncontextmenu="mostrarContextMenu(event, this)">
                <div class="folder-icon">
                    <span class="material-icons" style="color: ${colorPersonalizado}">folder</span>
                </div>
                <span class="folder-name" title="${escHtml(item.nombre)}">${escHtml(item.nombre)}</span>
                <button class="folder-menu" onclick="event.stopPropagation(); mostrarContextMenu(event, this.closest('.gd-folder-card'))" title="Más opciones">
                    <span class="material-icons">more_vert</span>
                </button>
            </div>
        `;
    }

    // Para ARCHIVOS: Nueva estructura de tarjeta
    // 1. Encabezado: Ícono tipo + Nombre
    // 2. Menú ⋮: Esquina superior derecha
    // 3. Cuerpo: Preview
    // 4. Pie: Contexto de actividad

    // Determinar contexto de actividad
    const fechaCorta = formatearFechaCorta(item.modificado_at || item.ultimo_acceso);
    const accion = item.accion || 'subido';
    const contextoTexto = fechaCorta ? `Tú lo has ${accion} · ${fechaCorta}` : '';

    // Generar URL de preview
    let previewUrl = item.preview_url || '';
    if (!previewUrl) {
        const extLower = (item.extension || '').toLowerCase();
        const tiposConPreview = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'odt', 'ods', 'odp'];
        if (tiposConPreview.includes(extLower)) {
            previewUrl = `${API_BASE}/preview?file=${encodeURIComponent(item.ruta_completa || item.ruta)}&x=256&y=256`;
        }
    }

    // Determinar ícono y clase de tipo para el encabezado
    const extLower = (item.extension || '').toLowerCase();
    let typeClass = 'default';
    let typeIcon = icono;

    if (['doc', 'docx', 'odt', 'rtf'].includes(extLower)) {
        typeClass = 'word';
        typeIcon = 'description';
    } else if (['xls', 'xlsx', 'ods', 'csv'].includes(extLower)) {
        typeClass = 'excel';
        typeIcon = 'grid_on';
    } else if (['ppt', 'pptx', 'odp'].includes(extLower)) {
        typeClass = 'powerpoint';
        typeIcon = 'slideshow';
    } else if (extLower === 'pdf') {
        typeClass = 'pdf';
        typeIcon = 'picture_as_pdf';
    } else if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(extLower)) {
        typeClass = 'image';
        typeIcon = 'image';
    } else if (['mp4', 'avi', 'mkv', 'mov', 'webm'].includes(extLower)) {
        typeClass = 'video';
        typeIcon = 'videocam';
    } else if (['mp3', 'wav', 'ogg', 'flac', 'm4a'].includes(extLower)) {
        typeClass = 'audio';
        typeIcon = 'audiotrack';
    } else if (['zip', 'rar', '7z', 'tar', 'gz'].includes(extLower)) {
        typeClass = 'archive';
        typeIcon = 'folder_zip';
    } else if (['txt', 'md', 'json', 'xml', 'html', 'css', 'js'].includes(extLower)) {
        typeClass = 'text';
        typeIcon = 'article';
    }

    // HTML del preview
    let previewHtml;
    if (previewUrl) {
        previewHtml = `
            <div class="gd-card-preview lazy-preview" data-preview-url="${previewUrl}" data-icon="${typeIcon}">
                <span class="material-icons preview-placeholder">${typeIcon}</span>
            </div>`;
    } else {
        previewHtml = `
            <div class="gd-card-preview">
                <span class="material-icons">${typeIcon}</span>
            </div>`;
    }

    return `
        <div class="gd-card"
             data-ruta="${escHtml(item.ruta_completa || item.ruta)}"
                 data-acceso="${item.es_acceso_directo ? 'true' : ''}" data-destino="${item.destino || ''}"
             data-carpeta="false"
             data-nombre="${escHtml(item.nombre)}"
             data-tipo="${item.tipo || 'archivo'}"
             data-extension="${item.extension || ''}"
             data-tamano="${item.tamano_humano || ''}"
             data-modificado="${item.modificado_at || ''}"
             data-favorito="${item.es_favorito || false}"
             data-compartido="${item.es_compartido || false}"
             data-editable="${item.es_editable || false}"
             data-mime-type="${item.mime_type || ''}"
             data-preview-url="${previewUrl}"
             data-file-id="${item.id || item.file_id || ''}"
             draggable="true"
             ondragstart="iniciarArrastre(event, this)"
             ondragend="finalizarArrastre(event)"
             ondblclick="abrirItem(this)"
             onclick="seleccionarItem(event, this)"
             oncontextmenu="mostrarContextMenu(event, this)">
            <!-- MENÚ: Esquina superior derecha, separado -->
            <button class="gd-card-menu" onclick="event.stopPropagation(); mostrarContextMenu(event, this.closest('.gd-card'))" title="Más opciones">
                <span class="material-icons">more_vert</span>
            </button>
            <!-- ENCABEZADO: Ícono tipo + Nombre -->
            <div class="gd-card-header">
                <div class="type-icon ${typeClass}">
                    <span class="material-icons">${typeIcon}</span>
                </div>
                <span class="file-name" title="${escHtml(item.nombre)}">${escHtml(item.nombre)}</span>
            </div>
            <!-- CUERPO: Preview -->
            ${previewHtml}
            <!-- PIE: Contexto de actividad -->
            <div class="gd-card-footer">
                <div class="gd-card-meta">${contextoTexto}</div>
            </div>
        </div>
    `;
}


function crearCardSugerido(item) {
    const motivo = item.motivo || '';
    const colorPersonalizado = item.color || '#5f6368';

    if (item.es_carpeta) {
        return `
            <div class="gd-folder-card"
                 data-ruta="${escHtml(item.ruta_completa || item.ruta)}"
                 data-acceso="${item.es_acceso_directo ? 'true' : ''}" data-destino="${item.destino || ''}"
                 data-folder-id="${item.file_id || item.folder_id || ''}"
                 data-file-id="${item.file_id || ''}"
                 data-carpeta="true"
                 data-nombre="${escHtml(item.nombre)}"
                 ondblclick="abrirItem(this)"
                 onclick="seleccionarItem(event, this); registrarActividad(this, 'apertura')"
                 oncontextmenu="mostrarContextMenu(event, this)">
                <div class="folder-icon">
                    <span class="material-icons" style="color: ${colorPersonalizado}">folder</span>
                </div>
                <div class="folder-name" title="${escHtml(item.nombre)}">${escHtml(item.nombre)}</div>
                <div class="folder-motivo" title="${motivo}">${motivo}</div>
            </div>
        `;
    } else {
        const icono = ICONOS[item.tipo] || 'insert_drive_file';
        return `
            <div class="gd-card"
                 data-ruta="${escHtml(item.ruta_completa || item.ruta)}"
                 data-acceso="${item.es_acceso_directo ? 'true' : ''}" data-destino="${item.destino || ''}"
                 data-file-id="${item.file_id || ''}"
                 data-carpeta="false"
                 data-nombre="${escHtml(item.nombre)}"
                 ondblclick="abrirItem(this)"
                 onclick="seleccionarItem(event, this); registrarActividad(this, 'apertura')"
                 oncontextmenu="mostrarContextMenu(event, this)">
                <div class="gd-card-preview">
                    <span class="material-icons">${icono}</span>
                </div>
                <div class="gd-card-info">
                    <div class="gd-card-name" title="${escHtml(item.nombre)}">${escHtml(item.nombre)}</div>
                    <div class="gd-card-motivo">${motivo}</div>
                </div>
            </div>
        `;
    }
}


function crearFilaSugerido(item) {
    const motivo = item.motivo || '';
    const icono = item.es_carpeta ? 'folder' : (ICONOS[item.tipo] || 'insert_drive_file');
    const colorIcono = item.es_carpeta ? (item.color || '#5f6368') : '#5f6368';

    return `
        <tr class="gd-list-item"
            data-ruta="${escHtml(item.ruta_completa || item.ruta)}"
                 data-acceso="${item.es_acceso_directo ? 'true' : ''}" data-destino="${item.destino || ''}"
            data-file-id="${item.file_id || ''}"
            data-carpeta="${item.es_carpeta}"
            data-nombre="${escHtml(item.nombre)}"
            ondblclick="abrirItem(this)"
            onclick="seleccionarItem(event, this); registrarActividad(this, 'apertura')"
            oncontextmenu="mostrarContextMenu(event, this)">
            <td>
                <div class="gd-list-name">
                    <span class="material-icons" style="color: ${colorIcono}">${icono}</span>
                    <span>${escHtml(item.nombre)}</span>
                </div>
            </td>
            <td class="gd-list-motivo">${motivo}</td>
            <td>Yo</td>
            <td>${formatearFechaCorta(item.modificado_at || item.ultimo_acceso)}</td>
            <td>
                <button class="gd-icon-btn" onclick="event.stopPropagation(); mostrarContextMenu(event, this.closest('tr'))">
                    <span class="material-icons">more_vert</span>
                </button>
            </td>
        </tr>
    `;
}


function crearFila(item) {
    const tipo = item.es_carpeta ? 'carpeta' : item.tipo;
    const icono = ICONOS[tipo] || 'insert_drive_file';
    const clase = CLASES_TIPO[tipo] || 'default';

    // Formatear fecha de modificación
    const fechaFormateada = formatearFecha(item.modificado_at);

    // Propietario / "Compartido por": avatar (foto real de Nomina) + nombre
    const _esCompartido = !!item.propietario_nc;
    const _ownerNc = item.propietario_nc || (typeof USUARIO_NC !== 'undefined' ? USUARIO_NC : '');
    const _ownerNombre = item.propietario_nombre || (_esCompartido ? '' : 'yo');
    const _ownerEmail = item.propietario_email || '';
    const _ownerTitle = (_ownerEmail ? (_ownerNombre + ' (' + _ownerEmail + ')') : _ownerNombre).replace(/"/g,'&quot;');
    const _ownerInicial = (_ownerNombre && _ownerNombre !== 'yo') ? _ownerNombre.trim().charAt(0).toUpperCase() : 'Y';
    let _ownerAvatar;
    if (_ownerNc) {
        _ownerAvatar = '<img class="owner-avatar-img" src="/api/nextcloud/avatar/' + encodeURIComponent(_ownerNc) + '" onerror="_avatarOnError(this, \'' + _ownerInicial + '\')" alt="">';
    } else {
        _ownerAvatar = '<div class="owner-avatar">' + _ownerInicial + '</div>';
    }

    return `
        <tr data-ruta="${escHtml(item.ruta_completa || item.ruta)}"
                 data-acceso="${item.es_acceso_directo ? 'true' : ''}" data-destino="${item.destino || ''}"
            data-file-id="${item.file_id || ''}"
            data-folder-id="${item.es_carpeta ? (item.file_id || item.folder_id || '') : ''}"
            data-carpeta="${item.es_carpeta}"
            data-nombre="${escHtml(item.nombre)}"
            data-tipo="${item.tipo || (item.es_carpeta ? 'carpeta' : 'archivo')}"
            data-extension="${item.extension || ''}"
            data-tamano="${item.tamano_humano || ''}"
            data-modificado="${item.modificado_at || ''}"
            data-favorito="${item.es_favorito || item.es_favorita || false}"
            data-compartido="${item.es_compartido || item.es_compartida || false}"
            data-editable="${item.es_editable || false}"
            data-mime-type="${item.mime_type || ''}"
            data-preview-url="${item.preview_url || ''}"
            ondblclick="abrirItem(this)"
            onclick="seleccionarItem(event, this)"
            oncontextmenu="mostrarContextMenu(event, this)">
            <td>
                <div class="gd-list-name">
                    <div class="file-icon">
                        <span class="material-icons" style="color: ${item.color || '#5f6368'}">${icono}</span>
                    </div>
                    <span class="file-name">${escHtml(item.nombre)}</span>
                </div>
            </td>
            <td>
                <div class="gd-list-owner" title="${_ownerTitle}">
                    ${_ownerAvatar}
                    <span>${_ownerNombre || 'yo'}</span>
                </div>
            </td>
            <td>${fechaFormateada}</td>
            <td>${item.tamano_humano || '-'}</td>
            <td class="gd-list-actions">
                <div class="gd-list-actions-btns">
                    <button class="gd-icon-btn" onclick="event.stopPropagation(); compartirItem(this.closest('tr'))" title="Compartir">
                        <span class="material-icons">person_add</span>
                    </button>
                    <button class="gd-icon-btn" onclick="event.stopPropagation(); descargarItem(this.closest('tr'))" title="Descargar">
                        <span class="material-icons">download</span>
                    </button>
                    <button class="gd-icon-btn" onclick="event.stopPropagation(); mostrarContextMenu(event, this.closest('tr'))" title="Más opciones">
                        <span class="material-icons">more_vert</span>
                    </button>
                </div>
            </td>
        </tr>
    `;
}
