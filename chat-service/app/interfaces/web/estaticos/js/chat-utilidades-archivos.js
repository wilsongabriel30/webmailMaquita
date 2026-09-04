// chat-utilidades-archivos.js — Utilidades (escape, validación, formato) y adjuntar/subir archivos.
// Extraído de chat-page.js (líneas 2795-3029) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // FUNCIONES DE SEGURIDAD
    // ============================================

    /**
     * Escapa caracteres HTML peligrosos para prevenir XSS.
     * Esta es una capa de seguridad del lado del cliente.
     */
    function escapeHtml(text) {
        if (!text) return '';
        if (typeof text !== 'string') text = String(text);

        const htmlEntities = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#x27;',
            '/': '&#x2F;',
            '`': '&#x60;',
            '=': '&#x3D;'
        };

        return text.replace(/[&<>"'`=\/]/g, char => htmlEntities[char]);
    }

    /**
     * Sanitiza texto para prevenir inyecciones en atributos HTML.
     */
    function sanitizeAttribute(text) {
        if (!text) return '';
        // Remover caracteres peligrosos para atributos
        return escapeHtml(text).replace(/[\n\r\t]/g, ' ');
    }

    /**
     * Valida que un valor sea un ID numerico valido.
     */
    function validateId(value) {
        if (!value) return null;
        const id = parseInt(value, 10);
        return (!isNaN(id) && id > 0) ? id : null;
    }

    /**
     * Sanitiza el contenido de un mensaje antes de enviarlo.
     * Remueve scripts y contenido peligroso.
     */
    function sanitizeMessage(content) {
        if (!content) return '';
        if (typeof content !== 'string') content = String(content);

        // Remover tags de script
        content = content.replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '');

        // Remover event handlers
        content = content.replace(/\s*on\w+\s*=\s*["'][^"']*["']/gi, '');

        // Remover javascript: URLs
        content = content.replace(/javascript:/gi, '');

        // Limitar longitud
        const MAX_LENGTH = 5000;
        if (content.length > MAX_LENGTH) {
            content = content.substring(0, MAX_LENGTH);
        }

        return content.trim();
    }

    /**
     * Valida extension de archivo permitida.
     */
    function isAllowedFileExtension(filename) {
        if (!filename) return false;
        const ext = filename.split('.').pop().toLowerCase();
        const allowed = [
            // Imagenes
            'jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp',
            // Documentos
            'pdf', 'doc', 'docx', 'xls', 'xlsx', 'ppt', 'pptx', 'txt', 'csv',
            // Video
            'mp4', 'webm', 'mov', 'avi',
            // Audio
            'mp3', 'wav', 'ogg', 'm4a'
        ];
        return allowed.includes(ext);
    }

    /**
     * Valida tamaño de archivo.
     */
    function isAllowedFileSize(file, maxMB = 25) {
        if (!file) return false;
        const maxBytes = maxMB * 1024 * 1024;
        return file.size <= maxBytes;
    }

    // Utilidades
    function getInitials(name) {
        if (!name) return '?';
        const safeName = escapeHtml(name);
        const parts = safeName.split(' ').filter(p => p);
        if (parts.length >= 2) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return safeName.substring(0, 2).toUpperCase();
    }

    // Nombre corto tipo WhatsApp: 1er nombre + 1er apellido, en Title Case
    function nombreCorto(nombre) {
        if (!nombre) return 'Usuario';
        var w = String(nombre).trim().split(/\s+/);
        var tc = function(x){ return x ? x.charAt(0).toUpperCase() + x.slice(1).toLowerCase() : x; };
        if (w.length >= 3) return tc(w[0]) + ' ' + tc(w[2]);   // 1er nombre + 1er apellido
        if (w.length === 2) return tc(w[0]) + ' ' + tc(w[1]);
        return tc(w[0]);
    }
    window.nombreCorto = nombreCorto;

    function formatTime(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;

        if (diff < 86400000) { // Menos de 24 horas
            return date.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
        } else if (diff < 604800000) { // Menos de 7 días
            return date.toLocaleDateString('es-ES', { weekday: 'short' });
        }
        return date.toLocaleDateString('es-ES', { day: '2-digit', month: '2-digit' });
    }

    function formatMessageTime(dateString) {
        if (!dateString) return '';
        return new Date(dateString).toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
    }

    // Archivos
    function attachFile() {
        document.getElementById('fileInput').click();
    }

    function attachImage() {
        document.getElementById('imageInput').click();
    }

    async function handleFileSelect(event) {
        const file = event.target.files[0];
        if (!file || !currentConversationId) return;

        // Validar extension
        if (!isAllowedFileExtension(file.name)) {
            toastr.error('Tipo de archivo no permitido');
            event.target.value = '';
            return;
        }

        // Validar tamaño (25MB max)
        if (!isAllowedFileSize(file, 25)) {
            toastr.error('El archivo es demasiado grande (max 25MB)');
            event.target.value = '';
            return;
        }

        await uploadAndSendFile(file, 'file');
        event.target.value = '';
    }

    async function handleImageSelect(event) {
        const file = event.target.files[0];
        if (!file || !currentConversationId) return;

        // Validar que sea imagen
        const imageExts = ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp'];
        const ext = file.name.split('.').pop().toLowerCase();
        if (!imageExts.includes(ext)) {
            toastr.error('Solo se permiten imagenes (JPG, PNG, GIF, WebP)');
            event.target.value = '';
            return;
        }

        // Validar tamaño (10MB max para imagenes)
        if (!isAllowedFileSize(file, 10)) {
            toastr.error('La imagen es demasiado grande (max 10MB)');
            event.target.value = '';
            return;
        }

        await uploadAndSendFile(file, 'image');
        event.target.value = '';
    }

    async function uploadAndSendFile(file, type) {
        // Validar ID de conversacion
        const conversationId = validateId(currentConversationId);
        if (!conversationId) {
            toastr.error('Error: conversacion invalida');
            return;
        }

        const formData = new FormData();
        formData.append('file', file);
        formData.append('message_type', type);

        try {
            toastr.info('Subiendo archivo...');

            const response = await fetch(`/api/chat/conversations/${conversationId}/messages/upload`, {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.success) {
                toastr.success('Archivo enviado');
                const container = document.getElementById('chatMessages');
                container.insertAdjacentHTML('beforeend', renderSingleMessage(data.message));
                scrollToBottom(container, true);
                loadConversations();
            } else {
                toastr.error(data.error || 'Error al subir archivo');
            }
        } catch (error) {
            console.error('Error:', error);
            toastr.error('Error de conexión');
        }
    }

    function viewImage(url) {
        window.open(url, '_blank');
    }

