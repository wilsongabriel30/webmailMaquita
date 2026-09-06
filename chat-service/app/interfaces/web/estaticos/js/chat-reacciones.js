// chat-reacciones.js — Reacciones a mensajes.
// Extraído de chat-page.js (líneas 1452-1672) el 28/08/2026 SIN cambios de código; ámbito global compartido.
// Orden de carga: ver plantillas/chat/index.html (mismo orden que el archivo original).

    // ============================================
    // REACCIONES A MENSAJES
    // ============================================

    function renderMessageReactions(msg) {
        // Manejar reactions como objeto, array o null/undefined
        let reactions = msg.reactions;

        // Si no hay reacciones, retornar vacío
        if (!reactions) {
            return '';
        }

        // Si es un objeto (no array), convertirlo a array
        if (!Array.isArray(reactions)) {
            // Si es un objeto vacío, retornar vacío
            if (typeof reactions === 'object' && Object.keys(reactions).length === 0) {
                return '';
            }
            // Convertir objeto a array de reacciones
            // El listado devuelve {emoji: [ids]}; el endpoint /reactions devuelve {emoji, count, user_ids}
            reactions = Object.entries(reactions).map(([emoji, data]) => {
                const ids = Array.isArray(data) ? data : (data && data.user_ids) || [];
                return { emoji: emoji, count: ids.length || (data && data.count) || 1, user_ids: ids };
            });
        }

        // Si el array está vacío, retornar vacío
        if (reactions.length === 0) {
            return '';
        }

        const esc = (t) => String(t == null ? '' : t).replace(/[&<>"']/g,
            c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

        const reactionsHtml = reactions.map(reaction => {
            const isMyReaction = reaction.user_ids && reaction.user_ids.map(Number).includes(Number(currentUserId));
            const activeClass = isMyReaction ? 'my-reaction' : '';
            // [A-1] `emoji` viene del mensaje y se metia crudo en el HTML y dentro
            // de una cadena de onclick. Ahora se escapa al pintar y el clic lo lee
            // del atributo, sin interpolarlo en codigo.
            const emojiSeguro = esc(reaction.emoji);
            return `
                <div class="message-reaction ${activeClass}"
                     data-emoji="${emojiSeguro}"
                     onclick="handleReactionClick(${Number(msg.id)}, this.dataset.emoji)"
                     title="${Number(reaction.count)} ${reaction.count === 1 ? 'persona' : 'personas'}">
                    <span class="reaction-emoji">${emojiSeguro}</span>
                    <span class="reaction-count">${Number(reaction.count)}</span>
                </div>
            `;
        }).join('');

        return `<div class="message-reactions">${reactionsHtml}</div>`;
    }

    async function toggleReactionPicker(messageId, event) {
        event.stopPropagation();

        // Crear picker si no existe
        let picker = document.getElementById(`reaction-picker-${messageId}`);
        if (!picker) {
            picker = document.createElement('div');
            picker.id = `reaction-picker-${messageId}`;
            picker.className = 'reaction-picker';
            picker.innerHTML = `
                <div class="reaction-emoji-list">
                    ${['❤️', '👍', '😂', '😮', '😢', '😡', '🙏', '🎉'].map(emoji =>
                        `<div class="reaction-emoji-item" onclick="addReaction(${messageId}, '${emoji}')">${emoji}</div>`
                    ).join('')}
                </div>
            `;

            const messageDiv = event.currentTarget.closest('.message');
            messageDiv.appendChild(picker);

            // Cerrar al hacer click fuera
            setTimeout(() => {
                document.addEventListener('click', function closePickerHandler(e) {
                    if (!picker.contains(e.target) && e.target !== event.currentTarget) {
                        picker.remove();
                        document.removeEventListener('click', closePickerHandler);
                    }
                });
            }, 100);
        } else {
            picker.remove();
        }
    }

    async function addReaction(messageId, emoji) {
        try {
            console.log('Agregando reacción:', messageId, emoji);

            const response = await fetch(`/api/chat/messages/${messageId}/reactions`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ emoji })
            });

            const result = await response.json();

            if (result.success) {
                console.log('Reacción agregada exitosamente');
                // Cerrar el picker
                const picker = document.getElementById(`reaction-picker-${messageId}`);
                if (picker) picker.remove();

                // Actualizar inmediatamente la UI (no esperar Socket.IO)
                actualizarReaccionEnMensaje(messageId, emoji, currentUserId, true);
            } else {
                console.error('Error agregando reacción:', result.error || result.mensaje);
                alert('Error al agregar reacción: ' + (result.error || result.mensaje || 'Error desconocido'));
            }
        } catch (error) {
            console.error('Error en addReaction:', error);
            alert('Error de conexión al agregar reacción');
        }
    }

    async function handleReactionClick(messageId, emoji) {
        try {
            // Verificar si ya tengo esta reacción
            const messageDiv = document.querySelector(`.message[data-message-id="${messageId}"]`);
            if (!messageDiv) return;

            const reactionDiv = Array.from(messageDiv.querySelectorAll('.message-reaction'))
                .find(r => r.textContent.includes(emoji));

            const isMyReaction = reactionDiv && reactionDiv.classList.contains('my-reaction');

            if (isMyReaction) {
                // Eliminar mi reacción
                const response = await fetch(`/api/chat/messages/${messageId}/reactions`, {
                    method: 'DELETE'
                });

                const result = await response.json();
                if (result.success) {
                    console.log('Reacción eliminada exitosamente');
                    // Actualizar inmediatamente la UI
                    actualizarReaccionEnMensaje(messageId, emoji, currentUserId, false);
                }
            } else {
                // Agregar reacción
                await addReaction(messageId, emoji);
            }
        } catch (error) {
            console.error('Error en handleReactionClick:', error);
        }
    }

    /**
     * Actualiza las reacciones de un mensaje en la UI.
     * Se usa tanto para actualizaciones locales como vía Socket.IO.
     * Ahora actualiza SOLO el mensaje afectado sin recargar todos.
     */
    async function actualizarReaccionEnMensaje(messageId, emoji, userId, agregar) {
        const messageDiv = document.querySelector(`.message[data-message-id="${messageId}"]`);
        if (!messageDiv) {
            console.log('💜 Mensaje no encontrado en DOM:', messageId);
            return;
        }

        console.log('💜 Actualizando reacciones del mensaje:', messageId);

        try {
            // Obtener las reacciones actualizadas del servidor
            const response = await fetch(`/api/chat/messages/${messageId}/reactions`);
            const data = await response.json();

            if (data.success && data.reactions) {
                // Buscar el contenedor de reacciones actual
                let reactionsContainer = messageDiv.querySelector('.message-reactions');

                // Si hay reacciones, crear/actualizar el contenedor
                if (data.reactions.length > 0) {
                    const reactionsHtml = data.reactions.map(reaction => {
                        const isMyReaction = reaction.user_ids && reaction.user_ids.map(Number).includes(Number(currentUserId));
                        const activeClass = isMyReaction ? 'my-reaction' : '';
                        return `
                            <div class="message-reaction ${activeClass}"
                                 onclick="handleReactionClick(${messageId}, '${reaction.emoji}')"
                                 title="${reaction.count} ${reaction.count === 1 ? 'persona' : 'personas'}">
                                ${reaction.emoji} ${reaction.count}
                            </div>
                        `;
                    }).join('');

                    if (reactionsContainer) {
                        // Actualizar contenedor existente
                        reactionsContainer.innerHTML = reactionsHtml;
                    } else {
                        // Crear nuevo contenedor - insertarlo después del contenido del mensaje
                        const messageContent = messageDiv.querySelector('.message-content');
                        if (messageContent) {
                            const newContainer = document.createElement('div');
                            newContainer.className = 'message-reactions';
                            newContainer.innerHTML = reactionsHtml;
                            messageContent.insertAdjacentElement('afterend', newContainer);
                        }
                    }
                } else if (reactionsContainer) {
                    // Si no hay reacciones, eliminar el contenedor
                    reactionsContainer.remove();
                }
            }
        } catch (error) {
            console.error('Error actualizando reacciones:', error);
        }
    }

    async function loadMessageReactions(messageId) {
        try {
            const response = await fetch(`/api/chat/messages/${messageId}/reactions`);
            const result = await response.json();

            if (result.success && result.reactions) {
                return result.reactions;
            }
            return [];
        } catch (error) {
            console.error('Error cargando reacciones:', error);
            return [];
        }
    }

