// =============================================================================
// SISTEMA DE COMPARTIR (Modal estilo Google Drive)
// =============================================================================

let shareArchivoActual = null;
let shareEnlaceActual = null;
let shareUsuariosActuales = [];
let searchTimeout = null;

// =============================================================================
// BLINDAJE DE PERMISOS - normalizarPermisosDropdown
// =============================================================================
// PROBLEMA ORIGINAL (2026-04-08):
// Nextcloud agrega el flag Share(16) automáticamente al guardar permisos.
// Ejemplo: se envía 15 (Read+Update+Create+Delete) pero Nextcloud devuelve 31
// (15 + Share(16)). El dropdown solo tenía opciones 1, 15, 17 → 31 no coincidía
// con ninguna → se mostraba "Lector" aunque el share era "Editor".
//
// SOLUCIÓN:
// Usar operaciones bitwise para detectar si tiene permiso de Update (bit 2).
// Si tiene Update → es Editor (valor 15 para el dropdown).
// Si no tiene Update → es Lector (valor 1 para el dropdown).
//
// NUNCA comparar permisos con === porque Nextcloud puede devolver valores
// diferentes a los que se enviaron (agrega/quita flags automáticamente).
// Siempre usar operaciones bitwise: (permisos & 2) para verificar Update.
// =============================================================================
function normalizarPermisosDropdown(permisos) {
    if (permisos & 2) return "15";   // Tiene Update = Editor
    if (permisos == 4) return "4";   // Solo Create = File drop (buzón)
    if (permisos & 16) return "17";  // Share sin Update = Comentador (1+16)
    return "1";  // Default: Lector
}

// Devuelve el nivel ('editor'|'comentador'|'lector') a partir de la máscara de permisos.
function nivelDesdePermisos(permisos) {
    if (permisos & 2) return 'editor';      // Update
    if (permisos & 16) return 'comentador'; // Share sin Update
    return 'lector';
}



// Abrir modal de compartir
async function abrirModalCompartir(archivo = null) {
    const item = archivo || itemSeleccionado;
    if (!item) return;

    shareArchivoActual = item;

    // Actualizar título del modal
    document.getElementById('shareModalTitle').textContent = `Compartir "${item.nombre}"`;

    // Resetear estado de búsqueda
    document.getElementById('shareSearchInput').value = '';
    document.getElementById('shareSearchResults').classList.remove('show');

    // Resetear acceso general a "Restringido"
    actualizarTextoAccesoGeneral('restricted');

    // Ocultar configuración de enlace
    document.getElementById('shareLinkConfig').style.display = 'none';
    document.getElementById('shareCopyLinkBtn').style.display = 'flex';
    document.getElementById('shareLinkUrlContainer').style.display = 'none';

    // Resetear campos de enlace
    document.getElementById('shareLinkPassword').value = '';
    document.getElementById('shareLinkExpiration').value = '';
    document.getElementById('shareLinkPermission').value = '1';

    // Mostrar estado vacío inicial
    document.getElementById('shareEmptyState').style.display = 'block';
    document.getElementById('shareUsersContainer').innerHTML = '';
    document.getElementById('shareCountBadge').textContent = '1'; // Solo propietario
    document.getElementById('sharePriorityRule').style.display = 'none';

    // Mostrar modal
    document.getElementById('shareModalOverlay').classList.add('show');
    document.body.style.overflow = 'hidden';

    // Cargar shares existentes
    await cargarSharesExistentes();
}

// Cerrar modal
function cerrarModalCompartir(event) {
    if (event && event.target !== event.currentTarget) return;
    document.getElementById('shareModalOverlay').classList.remove('show');
    document.body.style.overflow = '';
    shareArchivoActual = null;
    shareEnlaceActual = null;
}

// Cargar shares existentes del archivo
async function cargarSharesExistentes() {
    if (!shareArchivoActual) return;

    const ruta = shareArchivoActual.ruta_completa || shareArchivoActual.ruta;
    if (!ruta) {
        console.warn('[Compartir] Sin ruta para cargar shares');
        return;
    }

    console.log('[Compartir] Cargando shares de:', ruta);

    try {
        const response = await fetch(`${API_BASE}/shares?ruta=${encodeURIComponent(ruta)}`);
        const data = await response.json();

        if (data.success) {
            console.log('[Compartir] Shares encontrados:', data.total);
            renderizarUsuariosConAcceso(data.shares || []);

            // Verificar si hay enlace público
            const linkShare = (data.shares || []).find(s => s.tipo === 3 || s.share_type === 3);
            if (linkShare) {
                shareEnlaceActual = linkShare;
                activarVistaEnlacePublico(linkShare);
            }
        } else {
            console.warn('[Compartir] Error API:', data.error);
        }
    } catch (error) {
        console.error('[Compartir] Error cargando shares:', error);
    }
}

// Renderizar lista de usuarios con acceso (sin el propietario que ya está en el HTML)
function renderizarUsuariosConAcceso(shares) {
    const container = document.getElementById('shareUsersContainer');
    const emptyState = document.getElementById('shareEmptyState');
    const countBadge = document.getElementById('shareCountBadge');
    const priorityRule = document.getElementById('sharePriorityRule');

    // Usuarios compartidos (excluir enlaces públicos - tipo 3)
    // Tipos: 0=usuario, 1=grupo, 4=email
    const userShares = shares.filter(s => {
        const tipo = s.tipo ?? s.share_type;
        return tipo === 0 || tipo === 1 || tipo === 4;
    });
    shareUsuariosActuales = userShares;

    // Verificar si hay enlace público para mostrar regla de prioridad
    const hasPublicLink = shares.some(s => s.tipo === 3 || s.share_type === 3);

    if (userShares.length === 0) {
        emptyState.style.display = 'block';
        priorityRule.style.display = 'none';
        container.innerHTML = '';
        countBadge.textContent = '1'; // Solo propietario
        return;
    }

    emptyState.style.display = 'none';
    countBadge.textContent = (userShares.length + 1).toString(); // +1 por propietario

    // Mostrar regla de prioridad si hay usuarios y enlace público
    priorityRule.style.display = hasPublicLink && userShares.length > 0 ? 'flex' : 'none';

    let html = '';

    for (const share of userShares) {
        const nombre = share.compartido_con_nombre || share.share_with_displayname || share.compartido_con || share.share_with;
        const email = share.compartido_con || share.share_with;
        const permisos = share.permisos || share.permissions || 1;
        const shareId = share.id || share.share_id;
        const tipoShare = share.tipo ?? share.share_type;
        const esGrupo = tipoShare === 1;
        const esEmail = tipoShare === 4;
        const inicial = nombre ? nombre.charAt(0).toUpperCase() : '?';

        // Obtener nivel/descripción del permiso (3 niveles)
        const nivel = nivelDesdePermisos(permisos);
        const permDesc = nivel === 'editor' ? 'Editor' : (nivel === 'comentador' ? 'Comentador' : 'Lector');

        // Determinar icono y etiqueta según tipo
        let avatarContent = inicial;
        let etiquetaTipo = '';
        if (esGrupo) {
            avatarContent = '<span class="material-icons">group</span>';
            etiquetaTipo = ' (grupo)';
        } else if (esEmail) {
            avatarContent = '<span class="material-icons">mail_outline</span>';
            etiquetaTipo = ' <span class="badge bg-warning text-dark" style="font-size:10px;">Externo</span>';
        }

        html += `
            <div class="share-user-item" data-share-id="${shareId}">
                <div class="share-user-avatar" style="background: ${esEmail ? '#ffc107' : getColorForUser(nombre)};">
                    ${avatarContent}
                </div>
                <div class="share-user-info">
                    <span class="share-user-name">${escapeHtml(nombre)}${etiquetaTipo}</span>
                    <span class="share-user-email">${escapeHtml(email)}</span>
                </div>
                <div class="share-user-role-container">
                    <select class="share-permission-select" onchange="cambiarPermisoShare('${shareId}', this.value)" title="Cambiar permisos">
                        <option value="1" ${nivel === 'lector' ? 'selected' : ''}>Lector</option>
                        <option value="17" ${nivel === 'comentador' ? 'selected' : ''}>Comentador</option>
                        <option value="15" ${nivel === 'editor' ? 'selected' : ''}>Editor</option>
                    </select>
                    <button class="share-user-remove" onclick="confirmarEliminarShare('${shareId}', '${escapeHtml(nombre)}')" title="Quitar acceso">
                        <span class="material-icons">close</span>
                    </button>
                </div>
            </div>
        `;
    }

    container.innerHTML = html;
}

// Confirmar eliminación de acceso
async function confirmarEliminarShare(shareId, nombre) {
    const result = await Swal.fire({
        title: 'Quitar acceso',
        html: `¿Estás seguro de quitar el acceso de <strong>${nombre}</strong> a este archivo?`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#d33',
        cancelButtonColor: '#3085d6',
        confirmButtonText: 'Sí, quitar acceso',
        cancelButtonText: 'Cancelar'
    });

    if (result.isConfirmed) {
        await eliminarShare(shareId);
    }
}

// Extraer token de URL de Nextcloud o del campo token
function extraerToken(share) {
    // Primero intentar obtener del campo token directo
    if (share.token) return share.token;

    // Si no, extraer de la URL
    const url = share.url_publica || share.url || '';
    const match = url.match(/\/s\/([a-zA-Z0-9]+)/);
    return match ? match[1] : null;
}

// Construir URL del sistema central desde token
function construirUrlEnlace(token) {
    if (!token) return null;
    // Siempre construir sobre el dominio actual (window.location.origin)
    return `${window.location.origin}/archivos/s/${token}`;
}

// Activar vista de enlace público
// Actualiza el ícono y descripción del bloque "Acceso general" según el nivel.
function actualizarTextoAccesoGeneral(nivel) {
    const icon = document.getElementById('shareGeneralIcon');
    const desc = document.getElementById('shareGeneralDesc');
    const sel = document.getElementById('shareGeneralAccess');
    if (sel) sel.value = nivel;
    if (nivel === 'public') {
        if (icon) icon.innerHTML = '<span class="material-icons">public</span>';
        if (icon) icon.className = 'share-general-icon public';
        if (desc) desc.textContent = 'Cualquiera con el vínculo puede acceder';
    } else {
        if (icon) icon.innerHTML = '<span class="material-icons">lock</span>';
        if (icon) icon.className = 'share-general-icon restricted';
        if (desc) desc.textContent = 'Solo las personas con acceso pueden abrir';
    }
}

function activarVistaEnlacePublico(linkShare) {
    // Seleccionar opción "Público" en el desplegable
    actualizarTextoAccesoGeneral('public');

    // Mostrar configuración del enlace
    document.getElementById('shareLinkConfig').style.display = 'block';
    document.getElementById('shareCopyLinkBtn').style.display = 'flex';

    // Construir URL del sistema central (NUNCA usar URL de Nextcloud directamente)
    const token = extraerToken(linkShare);
    const urlEnlace = construirUrlEnlace(token);

    // Mostrar URL
    document.getElementById('shareLinkUrlContainer').style.display = 'block';
    document.getElementById('shareLinkUrl').value = urlEnlace || 'Error: No se pudo generar enlace';

    // Establecer permisos actuales (normalizar para dropdown)
    const permisos = linkShare.permisos || linkShare.permissions || 1;
    document.getElementById('shareLinkPermission').value = normalizarPermisosDropdown(permisos);

    // Establecer contraseña (indicar si tiene)
    if (linkShare.password_protegido) {
        document.getElementById('shareLinkPassword').placeholder = '••••••• (protegido)';
    }

    // Establecer fecha de expiración si existe
    if (linkShare.fecha_expiracion) {
        const fecha = linkShare.fecha_expiracion.split('T')[0];
        document.getElementById('shareLinkExpiration').value = fecha;
    }
}

// Cambiar nivel de acceso (Restringido/Público)
async function cambiarNivelAcceso(nivel) {
    const linkConfig = document.getElementById('shareLinkConfig');
    const copyBtn = document.getElementById('shareCopyLinkBtn');
    actualizarTextoAccesoGeneral(nivel);

    if (nivel === 'restricted') {
        // Si hay enlace público existente, eliminarlo
        if (shareEnlaceActual) {
            const result = await Swal.fire({
                title: 'Desactivar enlace público',
                text: 'El enlace público actual dejará de funcionar. ¿Continuar?',
                icon: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#d33',
                confirmButtonText: 'Sí, desactivar',
                cancelButtonText: 'Cancelar'
            });

            if (!result.isConfirmed) {
                // Revertir selección
                actualizarTextoAccesoGeneral('public');
                return;
            }

            await eliminarShare(shareEnlaceActual.id || shareEnlaceActual.share_id);
            shareEnlaceActual = null;
        }

        linkConfig.style.display = 'none';
        copyBtn.style.display = 'flex';
        document.getElementById('shareLinkUrlContainer').style.display = 'none';

    } else if (nivel === 'public') {
        // Crear enlace público si no existe
        if (!shareEnlaceActual) {
            await crearEnlacePublico();
        } else {
            // Solo mostrar configuración
            linkConfig.style.display = 'block';
            copyBtn.style.display = 'flex';
        }
    }
}

// Crear enlace público
async function crearEnlacePublico() {
    if (!shareArchivoActual) return;

    const ruta = shareArchivoActual.ruta_completa || shareArchivoActual.ruta;
    const permisos = parseInt(document.getElementById('shareLinkPermission').value) || 1;
    const password = document.getElementById('shareLinkPassword').value || null;
    const expiracion = document.getElementById('shareLinkExpiration').value || null;

    try {
        Swal.fire({
            title: 'Generando enlace...',
            allowOutsideClick: false,
            didOpen: () => { Swal.showLoading(); }
        });

        const response = await fetch(`${API_BASE}/compartir`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ruta: ruta,
                tipo: 3,  // Enlace público
                permisos: permisos,
                password: password,
                fecha_expiracion: expiracion
            })
        });
        const data = await response.json();

        Swal.close();

        if (data.success && data.compartido) {
            shareEnlaceActual = data.compartido;

            // Construir URL del sistema central (NUNCA usar URL de Nextcloud)
            const token = extraerToken(data.compartido);
            const urlEnlace = construirUrlEnlace(token);

            // Mostrar configuración
            document.getElementById('shareLinkConfig').style.display = 'block';
            document.getElementById('shareCopyLinkBtn').style.display = 'flex';
            document.getElementById('shareLinkUrlContainer').style.display = 'block';
            document.getElementById('shareLinkUrl').value = urlEnlace || 'Error generando enlace';

            // Actualizar regla de prioridad si hay usuarios
            if (shareUsuariosActuales && shareUsuariosActuales.length > 0) {
                document.getElementById('sharePriorityRule').style.display = 'flex';
            }

        } else {
            Swal.fire('Error', data.error || 'No se pudo crear el enlace', 'error');
            // Revertir selección
            actualizarTextoAccesoGeneral('restricted');
        }
    } catch (error) {
        Swal.close();
        console.error('Error creando enlace:', error);
        Swal.fire('Error', 'No se pudo crear el enlace público', 'error');
        actualizarTextoAccesoGeneral('restricted');
    }
}

// Toggle visibilidad de contraseña
function togglePasswordVisibility() {
    const input = document.getElementById('shareLinkPassword');
    const btn = event.currentTarget.querySelector('.material-icons');

    if (input.type === 'password') {
        input.type = 'text';
        btn.textContent = 'visibility_off';
    } else {
        input.type = 'password';
        btn.textContent = 'visibility';
    }
}

// Buscar usuarios para compartir (integrado con el sistema central/Nómina)
async function buscarUsuarios(query) {
    const resultsContainer = document.getElementById('shareSearchResults');

    if (query.length < 2) {
        resultsContainer.classList.remove('show');
        return;
    }

    // Debounce
    if (searchTimeout) clearTimeout(searchTimeout);
    searchTimeout = setTimeout(async () => {
        try {
            // Usar endpoint integrado con el sistema central/Nómina
            const response = await fetch(`${API_BASE}/usuarios/buscar?q=${encodeURIComponent(query)}`);
            const data = await response.json();

            if (data.success && data.usuarios && data.usuarios.length > 0) {
                let html = '';
                for (const user of data.usuarios) {
                    // Excluir usuarios que ya tienen acceso
                    const yaCompartido = shareUsuariosActuales.some(s =>
                        (s.compartido_con || s.share_with) === user.username ||
                        (s.compartido_con || s.share_with) === user.email
                    );

                    if (!yaCompartido) {
                        // Determinar icono según tipo
                        let icono = 'person';
                        if (user.tipo === 'interno') icono = 'badge';
                        else if (user.tipo === 'interno_sin_nc') icono = 'mail_outline';
                        else if (user.tipo === 'externo') icono = 'person_outline';

                        // Generar info adicional (departamento/cargo)
                        const infoAdicional = user.departamento || user.cargo
                            ? `<span class="share-search-item-dept">${escapeHtml(user.departamento)}${user.cargo ? ' - ' + escapeHtml(user.cargo) : ''}</span>`
                            : '';

                        // Usar username_nc para usuarios internos (Nextcloud), email para externos.
                        // Si el usuario interno aún no tiene cuenta Nube (requiere_sync),
                        // se envía destinatario vacío y se crea en NC al compartir vía id_directorio.
                        const userIdCompartir = user.username_nc || (user.requiere_sync ? '' : user.email);
                        const shareType = user.share_type || 0;  // 0=usuario, 4=email
                        const idDirectorio = (user.usuario_id !== undefined && user.usuario_id !== null) ? user.usuario_id : 'null';

                        // Usuarios internos SIN cuenta Nube y que no se pueden crear
                        // automáticamente (operarios sin correo institucional): se muestran
                        // pero al hacer clic solo se informa; no se intenta compartir.
                        const noCreable = (user.tipo === 'interno' && user.creable === false);
                        if (noCreable) icono = 'person_off';
                        const onClickAttr = noCreable
                            ? `onclick="usuarioSinCuentaNube('${escapeHtml(user.nombre)}')"`
                            : `onclick="agregarUsuario('${escapeHtml(userIdCompartir)}', '${escapeHtml(user.nombre)}', '${escapeHtml(user.email)}', '${user.tipo}', ${shareType}, ${idDirectorio})"`;

                        html += `
                            <div class="share-search-item${noCreable ? ' share-search-item-disabled' : ''}" ${onClickAttr}>
                                <span class="material-icons">${icono}</span>
                                <div class="share-search-item-info">
                                    <div class="share-search-item-header">
                                        <span class="share-search-item-name">${escapeHtml(user.nombre)}</span>
                                        <span class="badge ${user.badge_class} share-type-badge">${user.badge}</span>
                                    </div>
                                    <span class="share-search-item-email">${escapeHtml(user.email)}</span>
                                    ${infoAdicional}
                                </div>
                            </div>
                        `;
                    }
                }

                if (html) {
                    resultsContainer.innerHTML = html;
                    resultsContainer.classList.add('show');
                } else {
                    resultsContainer.innerHTML = '<div class="share-search-item"><span class="material-icons">info</span><span>Todos los usuarios encontrados ya tienen acceso</span></div>';
                    resultsContainer.classList.add('show');
                }
            } else {
                // Si no hay resultados pero el query parece un email, sugerir agregarlo como externo
                const esEmail = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(query);
                if (esEmail) {
                    // Detectar si es dominio Maquita
                    const dominio = query.split('@')[1].toLowerCase();
                    // Interno = mismo dominio que el usuario actual, o en la lista configurada
                    // (window.DOMINIOS_INTERNOS). Ya NO se compara contra 'maquita' fijo.
                    const _internos = (window.DOMINIOS_INTERNOS || []).map(d => (d || '').toLowerCase());
                    const _miDom = (window.USUARIO_DOMINIO || '').toLowerCase();
                    const esInterno = (!!_miDom && dominio === _miDom) || _internos.includes(dominio);
                    const badge = esInterno ? 'Interno' : 'Externo';
                    const badgeClass = esInterno ? 'bg-secondary' : 'bg-warning text-dark';
                    const tipoUser = esInterno ? 'interno_sin_nc' : 'externo';
                    const descripcion = esInterno
                        ? 'Usuario interno sin cuenta en el Drive - se enviará invitación por email'
                        : 'Usuario externo - se enviará invitación por email';

                    resultsContainer.innerHTML = `
                        <div class="share-search-item" onclick="agregarUsuario('${escapeHtml(query)}', '${escapeHtml(query.split('@')[0].replace('.', ' '))}', '${escapeHtml(query)}', '${tipoUser}', 4)">
                            <span class="material-icons">mail_outline</span>
                            <div class="share-search-item-info">
                                <div class="share-search-item-header">
                                    <span class="share-search-item-name">Invitar: ${escapeHtml(query)}</span>
                                    <span class="badge ${badgeClass} share-type-badge">${badge}</span>
                                </div>
                                <span class="share-search-item-email">${descripcion}</span>
                            </div>
                        </div>`;
                    resultsContainer.classList.add('show');
                } else {
                    resultsContainer.innerHTML = '<div class="share-search-item"><span class="material-icons">search_off</span><span>No se encontraron usuarios. Ingresa un correo completo para compartir.</span></div>';
                    resultsContainer.classList.add('show');
                }
            }
        } catch (error) {
            console.error('Error buscando usuarios:', error);
        }
    }, 300);
}

// Agregar usuario al compartir (soporta internos, internos sin NC y externos)
// shareType: 0=usuario Nextcloud, 4=compartir por email
// Usuario interno sin cuenta Nube (operario sin correo institucional): solo informar.
function usuarioSinCuentaNube(nombre) {
    document.getElementById('shareSearchResults').classList.remove('show');
    if (window.Swal) {
        Swal.fire({
            icon: 'info',
            title: 'Sin cuenta en la Nube',
            text: `${nombre} no tiene una cuenta en la Nube. Si necesita acceso, solicita a Tecnología que le cree una cuenta.`,
            confirmButtonColor: '#1a73e8'
        });
    } else {
        alert(`${nombre} no tiene cuenta en la Nube.`);
    }
}

async function agregarUsuario(userId, nombre, email, tipoUsuario = 'interno', shareType = 0, idDirectorio = null) {
    if (!shareArchivoActual) return;

    const ruta = shareArchivoActual.ruta_completa || shareArchivoActual.ruta;
    const permisos = parseInt(document.getElementById('shareNewPermission').value);

    document.getElementById('shareSearchResults').classList.remove('show');
    document.getElementById('shareSearchInput').value = '';

    // Determinar destinatario según tipo
    const destinatario = userId;

    try {
        const response = await fetch(`${API_BASE}/compartir`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                ruta: ruta,
                tipo: shareType,  // 0=usuario NC, 4=email
                destinatario: destinatario,
                permisos: permisos,
                id_directorio_destino: idDirectorio  // Si el destinatario no tiene cuenta Nube, se crea con este ID el sistema central
            })
        });
        const data = await response.json();

        if (data.success) {
            // Mostrar notificación de éxito con SweetAlert2 Toast
            let tipoTexto = 'institucional';
            let mensajeExtra = '';
            if (tipoUsuario === 'externo') {
                tipoTexto = 'externo';
                mensajeExtra = ' - Se enviará invitación por email';
            } else if (tipoUsuario === 'interno_sin_nc') {
                tipoTexto = 'de Maquita';
                mensajeExtra = ' - Se enviará por email';
            }

            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'success',
                title: `Usuario ${tipoTexto} agregado`,
                text: nombre + mensajeExtra,
                showConfirmButton: false,
                timer: 4000,
                timerProgressBar: true
            });
            // Recargar lista de shares
            await cargarSharesExistentes();
        } else {
            // Manejar errores específicos
            if (data.error && data.error.includes('cuenta válida')) {
                // Sugerir usar enlace público como alternativa
                Swal.fire({
                    icon: 'info',
                    title: 'Usuario no disponible',
                    html: `No se puede compartir directamente con <strong>${email}</strong>.<br><br>
                           <strong>Alternativa:</strong> Usa "Acceso General" para crear un enlace público y enviarlo manualmente.`,
                    confirmButtonText: 'Entendido'
                });
            } else if (data.error && (data.error.includes('ya tenga acceso') || data.error.includes('Failed to create') || data.error.includes('403'))) {
                // Share posiblemente duplicado
                Swal.fire({
                    icon: 'info',
                    title: 'Ya tiene acceso',
                    html: `<strong>${email}</strong> ya tiene acceso a este archivo.<br><br>
                           Revisa la lista de "Personas con acceso" para modificar sus permisos.`,
                    confirmButtonText: 'Entendido'
                });
                // Recargar para mostrar el share existente
                await cargarSharesExistentes();
            } else {
                Swal.fire('Error', data.error || 'No se pudo compartir', 'error');
            }
        }
    } catch (error) {
        console.error('Error agregando usuario:', error);
        Swal.fire('Error', 'No se pudo agregar el usuario', 'error');
    }
}

// Cambiar permisos de un share
async function cambiarPermisoShare(shareId, permisos) {
    try {
        const response = await fetch(`${API_BASE}/compartidos/${shareId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ permisos: parseInt(permisos) })
        });
        const data = await response.json();

        if (!data.success) {
            Swal.fire('Error', data.error || 'No se pudo actualizar los permisos', 'error');
            await cargarSharesExistentes();
            return false;
        }
        return true;
    } catch (error) {
        console.error('Error actualizando permisos:', error);
        return false;
    }
}

// Eliminar share
async function eliminarShare(shareId) {
    try {
        const response = await fetch(`${API_BASE}/compartidos/${shareId}`, {
            method: 'DELETE'
        });
        const data = await response.json();

        if (data.success) {
            await cargarSharesExistentes();
        } else {
            Swal.fire('Error', data.error || 'No se pudo eliminar', 'error');
        }
    } catch (error) {
        console.error('Error eliminando share:', error);
    }
}

// Actualizar permisos del enlace público
async function actualizarPermisoEnlace() {
    if (!shareEnlaceActual) return;

    const shareId = shareEnlaceActual.id || shareEnlaceActual.share_id;
    const permisos = parseInt(document.getElementById('shareLinkPermission').value);

    try {
        const exito = await cambiarPermisoShare(shareId, permisos);
        if (exito) {
            await cargarSharesExistentes();
            Swal.fire({
                toast: true,
                position: 'top-end',
                icon: 'success',
                title: 'Permisos actualizados',
                timer: 1500,
                showConfirmButton: false
            });
        }
    } catch (error) {
        console.error('Error actualizando permisos enlace:', error);
        Swal.fire('Error', 'No se pudieron actualizar los permisos', 'error');
    }
}

// Actualizar password del enlace público
async function actualizarPasswordEnlace() {
    if (!shareEnlaceActual) return;

    const shareId = shareEnlaceActual.id || shareEnlaceActual.share_id;
    const password = document.getElementById('shareLinkPassword').value;

    try {
        const response = await fetch(`${API_BASE}/compartidos/${shareId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password: password || null })
        });

        if (password) {
            document.getElementById('shareLinkPassword').placeholder = '••••••• (protegido)';
            Swal.fire({
                icon: 'success',
                title: 'Contraseña establecida',
                timer: 1500,
                showConfirmButton: false
            });
        }
    } catch (error) {
        console.error('Error actualizando password:', error);
    }
}

// Actualizar expiración del enlace público
async function actualizarExpiracionEnlace() {
    if (!shareEnlaceActual) return;

    const shareId = shareEnlaceActual.id || shareEnlaceActual.share_id;
    const expiration = document.getElementById('shareLinkExpiration').value;

    try {
        const response = await fetch(`${API_BASE}/compartidos/${shareId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ fecha_expiracion: expiration || null })
        });

        if (expiration) {
            const fechaFormateada = new Date(expiration).toLocaleDateString('es-EC', { day: 'numeric', month: 'long', year: 'numeric' });
            Swal.fire({
                icon: 'success',
                title: `Expira el ${fechaFormateada}`,
                timer: 2000,
                showConfirmButton: false
            });
        }
    } catch (error) {
        console.error('Error actualizando expiración:', error);
    }
}

// Copiar enlace al portapapeles
async function copiarEnlaceCompartir() {
    // Obtener URL desde el campo de texto primero
    const urlInput = document.getElementById('shareLinkUrl');
    let url = urlInput ? urlInput.value : '';

    // Si no hay URL en el campo o es de Nextcloud, reconstruir desde token
    if (!url || url.includes('/index.php/s/')) {
        if (shareEnlaceActual) {
            const token = extraerToken(shareEnlaceActual);
            url = construirUrlEnlace(token);
        }
    }

    // Si no hay enlace público, copiar el vínculo INTERNO al archivo (solo personas
    // con acceso podrán abrirlo, igual que en Google Drive con acceso restringido).
    if (!url || url.includes('Error')) {
        if (shareArchivoActual) {
            const ruta = shareArchivoActual.ruta_completa || shareArchivoActual.ruta || '';
            const esCarpeta = shareArchivoActual.es_carpeta || shareArchivoActual.tipo === 'carpeta';
            if (ruta) {
                url = esCarpeta
                    ? `${window.location.origin}/archivos/explorador${ruta.startsWith('/') ? '' : '/'}${ruta}`
                    : `${window.location.origin}/archivos/editar?ruta=${encodeURIComponent(ruta)}`;
            }
        }
    }

    if (!url || url.includes('Error')) {
        Swal.fire('Error', 'No hay enlace válido para copiar', 'warning');
        return;
    }

    try {
        await navigator.clipboard.writeText(url);
        Swal.fire({
            icon: 'success',
            title: 'Enlace copiado',
            html: `<small style="color:#5f6368;word-break:break-all;">${url}</small>`,
            timer: 2500,
            showConfirmButton: false
        });
    } catch (error) {
        // Fallback para navegadores que no soportan clipboard API
        const input = document.createElement('input');
        input.value = url;
        document.body.appendChild(input);
        input.select();
        document.execCommand('copy');
        document.body.removeChild(input);

        Swal.fire({
            icon: 'success',
            title: 'Enlace copiado',
            timer: 2000,
            showConfirmButton: false
        });
    }
}

// Utilidades
function getColorForUser(name) {
    const colors = ['#1a73e8', '#ea4335', '#34a853', '#fbbc04', '#673ab7', '#e91e63', '#00bcd4', '#ff5722'];
    let hash = 0;
    for (let i = 0; i < (name || '').length; i++) {
        hash = name.charCodeAt(i) + ((hash << 5) - hash);
    }
    return colors[Math.abs(hash) % colors.length];
}

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cerrar modal con Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && document.getElementById('shareModalOverlay').classList.contains('show')) {
        cerrarModalCompartir();
    }
});


// ============================================================
// CAMBIAR DE DUEÑO (estilo Google Drive) — 2026-07-03
// occ files:transfer-ownership via /api/nextcloud/cambiar-dueno
// ============================================================
async function cambiarDuenoSeleccionado() {
    const item = itemSeleccionado;
    if (!item) return;
    document.getElementById('contextMenu')?.classList.remove('show');
    if (typeof cerrarSubmenus === 'function') cerrarSubmenus();

    const esc = t => String(t == null ? '' : t).replace(/</g, '&lt;');

    const { value: elegido } = await Swal.fire({
        title: 'Cambiar de dueño',
        html: `
            <div style="text-align:left">
                <p style="font-size:.9rem;color:#5f6368;margin:0 0 6px">
                    Transferir <strong>${esc(item.nombre)}</strong> a otra persona.
                    Dejarás de ser el dueño y se moverá a su Nube.
                </p>
                <input id="cdQuien" class="swal2-input" style="width:100%;margin:8px 0"
                       placeholder="Buscar persona..." autocomplete="off">
                <div id="cdResultados" style="max-height:180px;overflow:auto"></div>
                <input type="hidden" id="cdElegido">
            </div>`,
        showCancelButton: true,
        confirmButtonText: 'Continuar',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#1a73e8',
        didOpen: () => {
            const inp = document.getElementById('cdQuien');
            let t = null;
            inp.addEventListener('input', () => {
                clearTimeout(t);
                t = setTimeout(async () => {
                    const q = inp.value.trim();
                    const box = document.getElementById('cdResultados');
                    document.getElementById('cdElegido').value = '';
                    if (q.length < 2) { box.innerHTML = ''; return; }
                    try {
                        const r = await fetch(`${API_BASE}/usuarios/buscar?q=` + encodeURIComponent(q));
                        const d = await r.json();
                        const usuarios = d.usuarios || [];
                        box.innerHTML = usuarios.length
                            ? usuarios.map(u => `
                                <div class="cd-opcion" data-id="${esc(u.id)}"
                                     style="padding:8px 10px;border-radius:8px;cursor:pointer"
                                     onmouseover="this.style.background='#f0f4f8'"
                                     onmouseout="this.style.background=''">
                                    ${esc(u.nombre || u.id)}
                                    <span style="color:#80868b;font-size:.8rem">${esc(u.email || '')}</span>
                                </div>`).join('')
                            : '<div style="color:#80868b;padding:8px">Sin resultados</div>';
                        box.querySelectorAll('.cd-opcion').forEach(el => el.addEventListener('click', () => {
                            document.getElementById('cdElegido').value = el.dataset.id;
                            inp.value = el.textContent.trim();
                            box.innerHTML = '';
                        }));
                    } catch (e) { box.innerHTML = ''; }
                }, 250);
            });
            setTimeout(() => inp.focus(), 150);
        },
        preConfirm: () => {
            const v = document.getElementById('cdElegido').value;
            if (!v) { Swal.showValidationMessage('Busca y selecciona a la persona'); return false; }
            return v;
        }
    });
    if (!elegido) return;

    const conf = await Swal.fire({
        title: '¿Confirmar transferencia?',
        html: `"<strong>${esc(item.nombre)}</strong>" pasará a ser propiedad de
               <strong>${esc(elegido)}</strong>.<br>Desaparecerá de tu unidad.`,
        icon: 'warning',
        showCancelButton: true,
        confirmButtonText: 'Sí, transferir',
        cancelButtonText: 'Cancelar',
        confirmButtonColor: '#d33'
    });
    if (!conf.isConfirmed) return;

    Swal.fire({ title: 'Iniciando transferencia...', allowOutsideClick: false, didOpen: () => Swal.showLoading() });
    try {
        const resp = await fetch(`${API_BASE}/cambiar-dueno`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ruta: item.ruta, nuevo_dueno: elegido })
        });
        const data = await resp.json();
        if (data.success) {
            await Swal.fire({ icon: 'success', title: 'Transferencia iniciada',
                              text: data.message, confirmButtonColor: '#1a73e8' });
            setTimeout(() => {
                if (typeof invalidarCache === 'function') invalidarCache(rutaActual);
                cargarArchivos(rutaActual);
            }, 1500);
        } else {
            Swal.fire({ icon: 'error', title: 'No se pudo transferir',
                        text: data.error || data.message || 'Error', confirmButtonColor: '#1a73e8' });
        }
    } catch (e) {
        Swal.fire({ icon: 'error', title: 'Error de conexión', confirmButtonColor: '#1a73e8' });
    }
}
window.cambiarDuenoSeleccionado = cambiarDuenoSeleccionado;
