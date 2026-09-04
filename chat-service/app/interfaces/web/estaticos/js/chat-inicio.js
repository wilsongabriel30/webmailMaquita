// chat-inicio.js — Inicialización (DOMContentLoaded): modales, listeners, pegado.
// Extraído de chat-page.js (líneas 834-936) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // INICIALIZACIÓN
    // ============================================
    document.addEventListener('DOMContentLoaded', function() {
        newChatModal = new bootstrap.Modal(document.getElementById('newChatModal'));
        chatInfoModal = new bootstrap.Modal(document.getElementById('chatInfoModal'));
        editMessageModal = new bootstrap.Modal(document.getElementById('editMessageModal'));
        deleteMessageModal = new bootstrap.Modal(document.getElementById('deleteMessageModal'));

        // Inicializar sonido de notificación
        initNotificationSound();

        // ✅ INICIALIZAR SOCKET.IO PARA TIEMPO REAL
        initSocket();

        // ⚡⚡⚡ INICIALIZAR CHAT ULTRA-RÁPIDO v3.0 (WebSocket puro)
        initChatUltraFast();

        loadConversations();

        // ⚡⚡⚡ POLLING como fallback temporal
        // Esperar 10 segundos antes de activar polling (dar tiempo al WebSocket)
        setTimeout(() => {
            if (!chatUltraFast || !chatUltraFast.connected) {
                console.log('⚠️ v3.0 aún no conectó - activando polling temporal');
                startFallbackPolling();
                // Cuando WebSocket conecte, polling se detendrá automáticamente (ver onConnect handler)
            } else {
                console.log('⚡ v3.0 conectado - polling DESACTIVADO permanentemente');
            }
        }, 10000);

        // Actualizar presencia del usuario actual cada 2 minutos
        updateUserPresence();
        setInterval(updateUserPresence, 120000); // 2 minutos

        // Actualizar estado de presencia de otros usuarios cada 30 segundos
        setInterval(updateOtherUsersPresence, 30000); // 30 segundos

        // Habilitar/deshabilitar botón de enviar
        document.getElementById('messageInput').addEventListener('input', function() {
            document.getElementById('btnSendMessage').disabled = !this.value.trim();
        });

        // Inicializar emojis
        initializeEmojis();

        // Cerrar pickers al hacer click fuera
        document.addEventListener('click', function(e) {
            const emojiPicker = document.getElementById('emojiPicker');
            const gifPicker = document.getElementById('gifPicker');
            const emojiBtn = document.querySelector('.emoji-btn');
            const gifBtn = document.querySelector('.gif-btn');

            // Cerrar emoji picker si click fuera
            if (emojiPicker && !emojiPicker.contains(e.target) && !emojiBtn.contains(e.target)) {
                emojiPicker.style.display = 'none';
                emojiBtn.classList.remove('active');
            }

            // Cerrar gif picker si click fuera
            if (gifPicker && !gifPicker.contains(e.target) && !gifBtn.contains(e.target)) {
                gifPicker.style.display = 'none';
                gifBtn.classList.remove('active');
            }
        });

        // Event listener para pegar imágenes con Ctrl+V
        document.getElementById('messageInput').addEventListener('paste', async function(e) {
            const items = e.clipboardData?.items;
            if (!items) return;

            for (let item of items) {
                if (item.type.indexOf('image') !== -1) {
                    e.preventDefault();

                    const file = item.getAsFile();
                    if (file) {
                        console.log('Imagen pegada en chat principal:', file.name, file.type, file.size);

                        // Verificar que hay una conversación abierta
                        if (!currentConversationId) {
                            toastr.warning('Por favor selecciona una conversación primero');
                            return;
                        }

                        // Enviar la imagen
                        await uploadAndSendFile(file, 'image');
                    }
                    break;
                }
            }
        });

        // Cerrar menú contextual al hacer clic fuera
        document.addEventListener('click', function(e) {
            const menu = document.getElementById('messageOptionsMenu');
            if (menu && !e.target.closest('.message-actions') && !e.target.closest('.message-options-menu')) {
                menu.classList.remove('show');
            }
        });
    });

