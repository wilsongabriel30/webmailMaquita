# Reglas de correo (Sieve): condiciones y acciones avanzadas

Las reglas se guardan como script Sieve en el servidor (Dovecot Pigeonhole, ManageSieve) y se aplican
a los correos que llegan desde que se crean. El webmail genera el script (`backend/app/sieve/generador.py`),
lo relee (`analizador.py`) y se niega a guardar si lo generado no se relee igual (`comprobar_relectura`).

## Dónde se crean

- **Clic derecho en un correo → «Crear regla con este correo…»**: abre la ventana con el remitente y el asunto
  del correo ya cargados como condiciones y, si está en una carpeta propia, esa carpeta como destino.
- **Barra superior → Reglas → «Crear regla…»**: igual, con el correo seleccionado (o vacía si no hay ninguno).
- **Ajustes → Reglas de correo**: lista, «Nueva regla» y «Editar» abren la misma ventana.

## Modelo (`POST`/`PUT /api/sieve/filters`)

```json
{
  "name": "Facturas de proveedores",
  "match": "allof",
  "conditions": [
    {"field": "from", "operator": "contains", "value": "@proveedor.example.org"},
    {"field": "subject", "operator": "regex", "value": "^(factura|invoice)"},
    {"field": "header", "operator": "exists", "header": "X-Priority"},
    {"field": "size", "operator": "over", "value": "5000"}
  ],
  "actions": [
    {"type": "copy", "value": "Proveedores.Facturas"},
    {"type": "read"},
    {"type": "forward_copy", "value": "contabilidad@example.org"}
  ],
  "stop": true,
  "enabled": true
}
```

| Campo (`field`) | Operadores | Sieve |
|---|---|---|
| `from`, `to`, `cc`, `recipients` (Para o Cc), `subject`, `list` (List-Id) | `contains`, `is`, `matches`, `regex` y sus negados `not_*`; `exists`, `not_exists` | `header` / `address` (De y Para «es exactamente» o «patrón» comparan solo la dirección) |
| `header` (+ `header`: nombre) | los mismos | `header :contains "X-Nombre" "…"` |
| `body` | `contains`, `not_contains`, `regex`, `not_regex` | `body :contains` |
| `size` (KB) | `over`, `under` | `size :over 500K` |

| Acción (`type`) | Sieve |
|---|---|
| `move` | `fileinto :create "Carpeta"` |
| `copy` | `fileinto :copy :create "Carpeta"` (el correo también queda en la Bandeja) |
| `flag` | `addflag "\\Flagged"` |
| `read` | `addflag "\\Seen"` |
| `delete` | `discard` (no pasa por la Papelera) |
| `forward` / `forward_copy` | `redirect` / `redirect :copy` (sujetos a la política de reenvío externo) |

- `match`: `allof` (todas) o `anyof` (alguna). Con una sola condición el script no lleva allof/anyof.
- `stop`: añade `stop;` (no aplicar más reglas). Si no se envía: `true`, salvo que la regla solo marque.
- `enabled: false`: la regla se escribe como `if allof (false, …)` y el servidor la salta sin perderla.
- Límites: 10 condiciones y 5 acciones por regla, 50 reglas por buzón.
- **Compatibilidad**: la forma antigua (`condition` y `action` en singular) se sigue aceptando y la respuesta
  siempre incluye `condition`/`action` (primera condición y primera acción) además de las listas.

Extensiones Sieve usadas: `fileinto`, `mailbox`, `imap4flags`, `copy`, `body`, `regex` (todas de serie en Pigeonhole).
Pruebas: `backend/tests/test_sieve_reglas.py` y `test_sieve_reglas_avanzadas.py` (incluye compilación con `sievec`
si está instalado).
