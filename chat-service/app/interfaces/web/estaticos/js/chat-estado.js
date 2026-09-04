// chat-estado.js — Estado global de la página (conversación actual, modales, usuario).
// Extraído de chat-page.js (líneas 687-705) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // VARIABLES GLOBALES
    // ============================================
    let currentConversationId = null;
    let currentConversationType = null;
    let conversations = [];
    let currentTab = 'all';
    let typingTimeout = null;
    let messagePollingInterval = null;
    let newChatModal = null;
    let editMessageModal = null;
    let deleteMessageModal = null;
    let selectedMessageId = null;
    let selectedMessageContent = null;
    let chatInfoModal = null;

    // Usuario actual para reacciones y mensajes
    const currentUserId = window.CHAT_USER_ID;

