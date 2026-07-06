# Servicio de Chat Maquita (independiente, dockerizado)

> Chat institucional como **servicio propio**: mensajería en tiempo real (texto, voz,
> GIF, adjuntos), llamadas y videollamadas 1-a-1 y grupales (LiveKit), presencia y
> notificaciones. Pensado para que **varios clientes** lo consuman con una sola
> identidad: el correo/webmail, la app de escritorio (Windows) y la de Android, además
> del panel web propio.

> **Estado: ANDAMIAJE (Fase A en curso).** El código del chat está empaquetado aquí
> desde el sistema de origen; la puesta en marcha (migraciones, arranque, pruebas) es la
> siguiente iteración. NO desplegar en producción todavía — hoy el chat sigue sirviéndose
> desde su instancia actual y el correo lo embebe vía `/chat/?embed=1`.

## Qué hace
- API REST `/api/chat/*` + WebSocket (Socket.IO) para tiempo real.
- Video: se apoya en un **servidor LiveKit** (SFU) externo para reuniones grupales
  (hasta ~25 cámaras) y en Jitsi para reuniones extensas. Se configuran por variables.
- Mensajería/notificaciones vía **Redis** (message queue).
- Datos en **PostgreSQL** (conversaciones, mensajes, participantes, presencia…).

## Arquitectura del servicio
```
[cliente: correo / app Windows / Android / FARO]
        │  (login -> JWT)
        ▼
  chat-service (este)  ── PostgreSQL (chat)
   Flask + Socket.IO   ── Redis (tiempo real)
   auth JWT            ── LiveKit (video grupal)
```

## Estructura
```
chat-service/
├── app/
│   ├── modulos/chat/         ← núcleo (dominio/infra/interfaces, DDD)
│   └── interfaces/           ← controlador HTTP + websocket + estáticos + template
├── app_chat.py               ← arranque del servicio (Flask + Socket.IO + auth)  [andamiaje]
├── shims/                    ← reemplazo de las dependencias del sistema de origen
│   ├── base_datos.py         ← SQLAlchemy Base + sesión (era compartido.infraestructura)
│   └── (ai opcional)         ← el chat-IA queda desactivado por defecto
├── Dockerfile
├── docker-compose.yml        ← chat + postgres + redis
├── requirements.txt
├── .env.example
└── README.md
```

## Instalación (cuando esté lista la Fase A)
```bash
cd chat-service
cp .env.example .env && nano .env      # BD, Redis, JWT, LiveKit
docker compose up -d --build
# healthcheck y migraciones (script en la siguiente iteración)
```

## Autenticación (piloto → producción)
- **Piloto:** JWT firmado con un secreto compartido con el correo (el mismo patrón del
  puente actual). El cliente inicia sesión en el correo, obtiene el JWT y lo presenta.
- **Producción:** un emisor único de identidad (Keycloak) para las 4 interfaces, cuando
  se libere el correo nuevo y se retire Zimbra.

## Dependencias del sistema de origen a desacoplar (pendiente Fase A)
1. `compartido.infraestructura.base_datos.Base` → `shims/base_datos.py`.
2. `interfaces.websocket` (emitir_*) → el propio Socket.IO del servicio.
3. `compartido.servicios.ai_worker_service` (chat-IA) → opcional, desactivado.

## Nota para quien lo adopte
Este servicio es genérico: cualquier organización puede levantarlo con su propio correo
como identidad. No contiene datos ni dominios de una instalación concreta (van en `.env`).
