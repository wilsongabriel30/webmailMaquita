"""Arranque de las tareas de fondo que NO deben repetirse en cada worker.

Inventario (para quien añada una tarea nueva, ver docs/GRAN-ESCALA.md):

| Tarea                         | Cómo evita duplicarse                                   |
|-------------------------------|---------------------------------------------------------|
| Correos programados           | reclamo atómico en PostgreSQL (pending → sending)       |
| Recordatorios                 | reclamo atómico en PostgreSQL (UPDATE … RETURNING)      |
| Lector de mail.log            | un líder por máquina (`Lider`, bloqueo en Redis)        |
| Detector de fraude            | `una_vez_por_intervalo` (5 min en todo el clúster)      |
| Listas de amenazas (12 h)     | `una_vez_por_intervalo` (12 h en todo el clúster)       |
| Correos pospuestos            | `una_vez_por_intervalo` (1 min en todo el clúster)      |
| WebSocket / sondeo IMAP       | por conexión: es estado de la conexión, no se comparte  |
| Limpieza del pool IMAP        | por proceso: cada proceso limpia sus conexiones         |
"""

from app.escala.bloqueo import Lider, nodo_id


def iniciar_lector_registro(app) -> Lider:
    """El lector de /var/log/mail.log corre en un solo worker por máquina.

    Antes cada worker abría el archivo y metía cada línea en mail_trace una vez por
    worker (4 copias con la configuración de serie). El registro es local de cada
    máquina, así que el bloqueo lleva el nombre del nodo: en un clúster cada nodo de
    correo tiene su lector y los nodos sin mail.log no hacen nada.
    """
    from app.log_ingestor.mail_log_ingestor import start_log_ingestor

    async def arrancar():
        return await start_log_ingestor(app.state.db_pool)

    return Lider(
        app.state.redis,
        f"log_ingestor:{nodo_id()}",
        arrancar=arrancar,
        parar=lambda ingestor: ingestor.stop(),
    ).iniciar()
