-- Teléfonos institucionales (22/09/2026): el código de enrolamiento lo asigna Tecnología a una persona
-- y esa persona puede volver a verlo en su Configuración (y la app lo recibe para activar con un toque).
-- Para eso el código en claro se guarda CIFRADO (Fernet, clave DISP_CODIGO_CLAVE del .env, nunca en la
-- base) solo mientras el código está vigente: se borra al agotarse, al caducar y al anularse.
-- Compromiso documentado: se pierde el «solo se muestra una vez» a cambio de que la persona no dependa
-- de Tecnología para volver a verlo. Sigue con usos limitados, caducidad y anulable.
ALTER TABLE disp_codigos
    ADD COLUMN IF NOT EXISTS codigo_cifrado TEXT;
CREATE INDEX IF NOT EXISTS disp_codigos_custodio ON disp_codigos (custodio_email) WHERE custodio_email IS NOT NULL;
