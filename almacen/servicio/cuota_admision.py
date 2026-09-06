"""Admisión de subidas por cuota y espacio libre (F-06, tercera revisión).

La cuota se calculaba y se mostraba, pero no se aplicaba al admitir archivos: cada subida
podía superar el límite y presionar el disco compartido. Aquí, ANTES de escribir:

1. `reservar()` —en UNA transacción— bloquea la fila de uso del usuario (SELECT … FOR UPDATE),
   suma uso + reservas vivas + tamaño esperado y, si cabe, anota una reserva. Es atómico: dos
   subidas simultáneas no pueden colarse juntas por debajo del límite.
2. Umbral global de espacio libre (`ALMACEN_MINIMO_LIBRE_BYTES`, 5 GB por defecto) con statvfs:
   por debajo, ninguna subida nueva.
3. Si no hay Content-Length fiable, la reserva es 0 y se contabiliza DURANTE el streaming:
   `comprobar_durante()` aborta en cuanto uso + escrito supera la cuota.
4. Al terminar, `liberar()` retira la reserva y ajusta el uso cacheado (sube o baja).

Las reservas caducan solas (RESERVA_TTL_SEG) por si un proceso muere a mitad de subida.
`conexion` es el gestor de contexto de almacen_bd (una transacción por bloque `with`).
"""

import os
import uuid

from psycopg2.extras import RealDictCursor

RESERVA_TTL_SEG = 900
MINIMO_LIBRE_BYTES = int(os.getenv("ALMACEN_MINIMO_LIBRE_BYTES", 5 * 1024**3))


class CuotaExcedida(Exception):
    codigo = 413

    def __init__(self, mensaje="Cuota de almacenamiento excedida"):
        super().__init__(mensaje)


class SinEspacio(Exception):
    codigo = 507

    def __init__(self, mensaje="El servidor no tiene espacio libre suficiente"):
        super().__init__(mensaje)


def asegurar_tabla(conexion):
    with conexion() as con, con.cursor() as cur:
        cur.execute(
            """CREATE TABLE IF NOT EXISTS cuotas_reservas (
                   id uuid PRIMARY KEY, usuario_id integer NOT NULL, bytes bigint NOT NULL,
                   creada_en timestamptz NOT NULL DEFAULT now())"""
        )
        cur.execute("CREATE INDEX IF NOT EXISTS cuotas_reservas_usuario ON cuotas_reservas (usuario_id)")


def espacio_libre(raiz: str) -> int:
    st = os.statvfs(raiz)
    return st.f_bavail * st.f_frsize


def comprobar_espacio_global(raiz: str, minimo: int = MINIMO_LIBRE_BYTES) -> None:
    if espacio_libre(raiz) < minimo:
        raise SinEspacio()


def reservar(conexion, usuario_id: int, esperado: int, limite: int, usado: int) -> str:
    """Reserva `esperado` bytes si cabe. Devuelve el id de la reserva ('' si esperado == 0).
    Todo dentro de una transacción con la fila de uso bloqueada."""
    with conexion() as con, con.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "DELETE FROM cuotas_reservas WHERE creada_en < now() - make_interval(secs => %s)",
            (RESERVA_TTL_SEG,),
        )
        cur.execute(
            """INSERT INTO cuotas_uso (usuario_id, usado_bytes, calculado_en) VALUES (%s, %s, now())
               ON CONFLICT (usuario_id) DO NOTHING""",
            (usuario_id, usado),
        )
        cur.execute("SELECT usado_bytes FROM cuotas_uso WHERE usuario_id = %s FOR UPDATE", (usuario_id,))
        fila = cur.fetchone()
        usado_bd = int(fila["usado_bytes"]) if fila else usado
        cur.execute(
            "SELECT COALESCE(SUM(bytes), 0) AS reservado FROM cuotas_reservas WHERE usuario_id = %s",
            (usuario_id,),
        )
        reservado = int(cur.fetchone()["reservado"])
        if limite and max(usado, usado_bd) + reservado + max(0, esperado) > limite:
            raise CuotaExcedida()
        if esperado <= 0:
            return ""
        rid = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO cuotas_reservas (id, usuario_id, bytes) VALUES (%s, %s, %s)",
            (rid, usuario_id, esperado),
        )
        return rid


def comprobar_durante(usado: int, escrito: int, limite: int, reservado: int) -> None:
    """Durante el streaming: lo escrito no puede superar la cuota (ni lo reservado si lo hay)."""
    if limite and usado + escrito > limite:
        raise CuotaExcedida("La subida supera tu cuota de almacenamiento")
    if reservado and escrito > reservado + 1024 * 1024:
        raise CuotaExcedida("El archivo es mayor de lo declarado")


def liberar(conexion, reserva_id: str, usuario_id: int, delta_bytes: int) -> None:
    """Retira la reserva y ajusta el uso cacheado (delta puede ser negativo si se descartó)."""
    with conexion() as con, con.cursor() as cur:
        if reserva_id:
            cur.execute("DELETE FROM cuotas_reservas WHERE id = %s", (reserva_id,))
        if delta_bytes:
            cur.execute(
                """INSERT INTO cuotas_uso (usuario_id, usado_bytes, calculado_en) VALUES (%s, GREATEST(%s, 0), now())
                   ON CONFLICT (usuario_id) DO UPDATE
                     SET usado_bytes = GREATEST(cuotas_uso.usado_bytes + %s, 0)""",
                (usuario_id, delta_bytes, delta_bytes),
            )
