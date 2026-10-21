# Pruebas de humo del correo

Pruebas rápidas de extremo a extremo («candados») que comprueban que las funciones visibles siguen
vivas después de un cambio o de una actualización: correo sin internet, caché cifrada, chat, llamadas,
avisos, secciones, calendario ⇄ reuniones y tareas. Cada una imprime `[OK    ]` / `[FALLA ]` por punto
y sale con 0 si todo está bien.

## Uso rápido (en el servidor del correo)

```bash
echo 'HUMO_URL=https://mail.example.org' > /etc/maquita-humo.env   # una sola vez
bash /opt/maquita-webmail/deploy/pruebas-humo/ejecutar.sh           # todas
bash /opt/maquita-webmail/deploy/pruebas-humo/ejecutar.sh offline   # una
bash /opt/maquita-webmail/deploy/pruebas-humo/ejecutar.sh --listar
```

El ejecutor abre la **sesión de pruebas** con `sesion_prueba.py` (vale de impersonación del panel,
igual que «abrir buzón»): por eso necesita el `.env` del backend y solo funciona en el servidor.
Desde otro equipo, pase el token: `ejecutar.sh --token <access_token>`.

## Configuración (variables o `/etc/maquita-humo.env`)

| Variable | Para qué | Por omisión |
|---|---|---|
| `HUMO_URL` | dirección del correo | — (obligatoria) |
| `HUMO_CUENTA` | cuenta de pruebas | `test@<dominio>` |
| `HUMO_DESTINO` | destinatario de los correos de prueba | la cuenta de pruebas |
| `HUMO_PERSONA` | segunda cuenta (tareas, reuniones) | el destino |
| `HUMO_CONVERSACION` | id de una conversación del chat de la cuenta | `1` |
| `HUMO_UID_CORREO` | UID de un correo de su bandeja de entrada | `1` |
| `HUMO_DSN_GRABACIONES` | (opcional) BD de grabaciones de reuniones, solo lectura | no se comprueba |
| `HUMO_PYTHON` / `HUMO_TIEMPO` | Python con Playwright / segundos por prueba | `python3` / `240` |

Use una **cuenta de pruebas dedicada** (sin correo real): las pruebas envían y borran correos,
eventos y tareas de prueba.

## Grupos

- `navegador/`: Chromium real con Playwright (`pip install playwright && playwright install chromium`).
  Si no está, el ejecutor las marca **OMITIDA** en vez de fallar.
- `servidor/`: llamadas a la API y a la base del propio servidor (calendario ⇄ reuniones, tareas).
- `prueba-reinicio-sesion.sh`: reinicia el backend y comprueba que la sesión sobrevive sin 502
  (corta unos segundos: no correr en horario de trabajo).
