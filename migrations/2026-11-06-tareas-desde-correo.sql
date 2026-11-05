-- Tareas creadas al soltar correos en el ícono Tareas (06/11/2026): a qué mensaje apunta cada una.
-- Tabla aparte de task_correo: aquella es la de «Correo marcado», que completa la tarea cuando el correo
-- pierde la bandera y le quita la bandera al completarla. Un correo soltado no tiene bandera ni debe ganarla.
-- Solo quien soltó el correo ve el enlace (es su buzón).
CREATE TABLE IF NOT EXISTS task_correo_origen (
    card_id    UUID PRIMARY KEY REFERENCES task_cards(id) ON DELETE CASCADE,
    user_email TEXT NOT NULL,
    carpeta    TEXT NOT NULL,
    uid        BIGINT NOT NULL,
    message_id TEXT NOT NULL DEFAULT '',
    asunto     TEXT NOT NULL DEFAULT '',
    remitente  TEXT NOT NULL DEFAULT '',
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_task_correo_origen_mensaje ON task_correo_origen(user_email, carpeta, uid);
