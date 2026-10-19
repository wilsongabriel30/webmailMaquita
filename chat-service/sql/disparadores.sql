-- Disparadores del chat: fecha de modificación y, al llegar un mensaje, vista previa y orden de la
-- conversación y contador de NO LEÍDOS de los demás participantes. Sin ellos el chat funciona pero nunca
-- avisa de mensajes sin leer. Estaban solo en la base de la instalación original (creados a mano); aquí
-- quedan para toda instalación. Idempotente: lo aplica migrar_chat.py en cada actualización.

CREATE OR REPLACE FUNCTION public.update_chat_conversation_timestamp()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.update_chat_message_timestamp()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.update_conversation_last_message()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
DECLARE
    preview_text TEXT;
BEGIN
    IF NEW.message_type = 'text' THEN
        preview_text := LEFT(NEW.content, 100);
    ELSIF NEW.message_type = 'image' THEN
        preview_text := '📷 Imagen';
    ELSIF NEW.message_type = 'video' THEN
        preview_text := '🎥 Video';
    ELSIF NEW.message_type = 'audio' THEN
        preview_text := '🎵 Audio';
    ELSIF NEW.message_type = 'document' THEN
        preview_text := '📄 Documento';
    ELSIF NEW.message_type = 'sticker' THEN
        preview_text := '😊 Sticker';
    ELSIF NEW.message_type = 'system' THEN
        preview_text := NEW.content;
    ELSE
        preview_text := 'Nuevo mensaje';
    END IF;
    UPDATE chat_conversations
    SET
        last_message_at = NEW.created_at,
        last_message_preview = preview_text,
        updated_at = NOW()
    WHERE id = NEW.conversation_id;
    UPDATE chat_participants
    SET unread_count = COALESCE(unread_count, 0) + 1
    WHERE conversation_id = NEW.conversation_id
      AND user_id != NEW.sender_id
      AND is_active = TRUE;

    RETURN NEW;
END;
$function$;

CREATE OR REPLACE FUNCTION public.update_chat_user_presence_updated_at()
 RETURNS trigger
 LANGUAGE plpgsql
AS $function$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$function$;

DROP TRIGGER IF EXISTS trg_chat_conversations_updated ON public.chat_conversations;
CREATE TRIGGER trg_chat_conversations_updated BEFORE UPDATE ON public.chat_conversations FOR EACH ROW EXECUTE FUNCTION update_chat_conversation_timestamp();

DROP TRIGGER IF EXISTS trg_chat_messages_updated ON public.chat_messages;
CREATE TRIGGER trg_chat_messages_updated BEFORE UPDATE ON public.chat_messages FOR EACH ROW EXECUTE FUNCTION update_chat_message_timestamp();

DROP TRIGGER IF EXISTS trg_update_conversation_last_message ON public.chat_messages;
CREATE TRIGGER trg_update_conversation_last_message AFTER INSERT ON public.chat_messages FOR EACH ROW WHEN ((new.is_deleted = false)) EXECUTE FUNCTION update_conversation_last_message();

DROP TRIGGER IF EXISTS trigger_update_chat_user_presence_updated_at ON public.chat_user_presence;
CREATE TRIGGER trigger_update_chat_user_presence_updated_at BEFORE UPDATE ON public.chat_user_presence FOR EACH ROW EXECUTE FUNCTION update_chat_user_presence_updated_at();
