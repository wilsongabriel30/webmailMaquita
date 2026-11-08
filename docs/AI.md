# Inteligencia Artificial — Fundacion Maquita Webmail

> **Proyecto de la Fundacion Maquita** — Comercializadora asociativa sin fines de lucro, Ecuador.

Guía para configurar el asistente de IA integrado en el webmail. Usa modelos de lenguaje ejecutados localmente (Ollama), sin enviar datos a servicios externos.

---

## Qué puede hacer la IA

- **Respuestas inteligentes** — sugiere 3 opciones de respuesta contextualizadas
- **Autocompletado** — completa frases mientras escribes
- **Resumen de correos** — resume correos largos
- **Redacción asistida** — ayuda a redactar correos profesionales
- **Dictado por voz** — transcripción con Whisper

## Requisitos

- Un servidor o PC con GPU NVIDIA (mínimo 8 GB VRAM)
- NVIDIA drivers + CUDA instalados
- Puede ser el mismo servidor del correo u otro dedicado

## Paso 1: Instalar drivers NVIDIA

```bash
# Verificar que el sistema detecta la GPU
lspci | grep -i nvidia

# Instalar drivers (Debian)
apt install -y nvidia-driver firmware-misc-nonfree

# Ubuntu:
# apt install -y nvidia-driver-535

# Reiniciar
reboot

# Verificar
nvidia-smi
# Debe mostrar la GPU, la memoria VRAM y la versión del driver
```

## Paso 2: Instalar Ollama

Ollama es el motor que ejecuta los modelos de IA localmente. Gratuito y de código abierto.

```bash
curl -fsSL https://ollama.com/install.sh | sh

# Verificar
systemctl status ollama
# Debe indicar "active (running)"

# Si no está corriendo:
systemctl enable --now ollama
```

## Paso 3: Descargar un modelo

Recomendaciones según la VRAM disponible:

| VRAM | Modelo recomendado | Comando | Calidad |
|------|-------------------|---------|---------|
| 8 GB | Gemma 2 9B | `ollama pull gemma2:9b` | Buena |
| 8 GB | Llama 3.1 8B | `ollama pull llama3.1:8b` | Buena |
| 8 GB | Qwen 2.5 7B | `ollama pull qwen2.5:7b` | Buena |
| 16 GB | Qwen 2.5 14B | `ollama pull qwen2.5:14b` | Muy buena |
| 24 GB | Gemma 4 26B | `ollama pull gemma4:26b` | Excelente |
| 24 GB | Llama 3.1 70B (Q4) | `ollama pull llama3.1:70b` | Excelente |

```bash
# Ejemplo: descargar Gemma 2 9B
ollama pull gemma2:9b

# Verificar modelos instalados
ollama list

# Probar el modelo
ollama run gemma2:9b "Hola, responde en una frase"
```

**Modelos recomendados por idioma:**
- **Español**: Gemma 4, Qwen 2.5, Llama 3.1 (todos funcionan bien)
- **Solo inglés**: Phi-3, Mistral (menos recomendados para webmail en español)

## Paso 4: Configurar acceso remoto

Si el servidor de IA es diferente al servidor de correo:

```bash
mkdir -p /etc/systemd/system/ollama.service.d
cat > /etc/systemd/system/ollama.service.d/override.conf << 'EOF'
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
Environment="OLLAMA_ORIGINS=*"
EOF

systemctl daemon-reload
systemctl restart ollama

# Verificar que el puerto está escuchando
ss -tlnp | grep 11434
# Debe mostrar 0.0.0.0:11434
```

**IMPORTANTE:** Proteger con firewall:
```bash
# Solo permitir acceso desde el servidor de correo
ufw allow from IP_SERVIDOR_CORREO to any port 11434
ufw deny 11434
```

## Paso 5: Crear el gateway de IA

El webmail no se conecta directamente a Ollama. Necesita un gateway FastAPI que autentica, enruta y realiza failover automático.

Crear `/opt/maquita-ia-gateway/gateway.py`:
```python
"""
Gateway de IA para Maquita Webmail
Proxy autenticado entre el webmail y Ollama
"""
import logging
import httpx
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel

app = FastAPI(title="Maquita IA Gateway")
logging.basicConfig(level=logging.INFO)

# --- CONFIGURACION ---
API_KEY = "tu-clave-api-segura"  # Cambiar por una clave real
OLLAMA_URL = "http://localhost:11434"
MODELO_DEFAULT = "gemma2:9b"  # Cambiar por el modelo deseado

def verificar_token(x_api_key: str = Header(None)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Token requerido")
    return "webmail"

class GenerateRequest(BaseModel):
    prompt: str
    system: str = ""
    model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 500
    preferir_gpu: str = "auto"

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/api/v1/ia/generate")
async def generate(req: GenerateRequest, user: str = Header(None, alias="X-API-Key")):
    verificar_token(user)
    modelo = req.model or MODELO_DEFAULT
    payload = {
        "model": modelo,
        "prompt": req.prompt,
        "system": req.system,
        "stream": False,
        "options": {"temperature": req.temperature, "num_predict": req.max_tokens},
    }
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{OLLAMA_URL}/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
        return {
            "respuesta": data.get("response", ""),
            "tokens_usados": data.get("eval_count", 0),
            "modelo": modelo,
            "gpu": "local",
            "tiempo_ms": int(data.get("total_duration", 0) / 1_000_000),
        }
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error Ollama: {e}")

@app.get("/api/v1/ia/status")
async def status(user: str = Header(None, alias="X-API-Key")):
    verificar_token(user)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            modelos = [m["name"] for m in resp.json().get("models", [])]
        return {"gpus": {"local": {"url": OLLAMA_URL, "modelos": modelos, "status": "ok"}}}
    except Exception as e:
        return {"gpus": {"local": {"status": "offline", "error": str(e)}}}

@app.get("/api/v1/ia/models")
async def models(user: str = Header(None, alias="X-API-Key")):
    verificar_token(user)
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{OLLAMA_URL}/api/tags")
            return {"modelos": [m["name"] for m in resp.json().get("models", [])]}
    except:
        return {"modelos": []}
```

Instalar y ejecutar:
```bash
cd /opt/maquita-ia-gateway
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn httpx

# Probar
uvicorn gateway:app --host 0.0.0.0 --port 8000

# En otra terminal:
curl -s -H "X-API-Key: tu-clave-api-segura" \
  -H "Content-Type: application/json" \
  -X POST http://localhost:8000/api/v1/ia/generate \
  -d '{"prompt": "Hola, responde brevemente"}'
```

## Paso 6: Servicio systemd

```bash
cat > /etc/systemd/system/maquita-ia-gateway.service << 'EOF'
[Unit]
Description=Maquita IA Gateway
After=network.target ollama.service

[Service]
Type=simple
WorkingDirectory=/opt/maquita-ia-gateway
ExecStart=/opt/maquita-ia-gateway/venv/bin/uvicorn gateway:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now maquita-ia-gateway

# Verificar
curl -s http://localhost:8000/health
```

## Paso 7: Conectar al webmail

En el archivo `.env` del webmail:
```ini
OLLAMA_URL=http://IP_SERVIDOR_IA:8000
IA_API_KEY=tu-clave-api-segura
```

Reiniciar el servicio:
```bash
systemctl restart maquita-webmail
```

## Paso 8: Verificar en el navegador

1. Ir al webmail
2. Abrir un correo recibido
3. Buscar el botón de "Respuesta inteligente" o el ícono de IA
4. Debe generar opciones de respuesta contextualizadas
5. Al redactar, el autocompletado debe sugerir texto

## Configuración avanzada: múltiples GPUs

Si hay dos o más GPUs disponibles, el sistema puede distribuir la carga:

- **GPU principal**: tareas pesadas (resúmenes largos, razonamiento)
- **GPU secundaria**: tareas rápidas (autocompletado, chat)
- **Failover automático** si una GPU falla

```python
# En el gateway, agregar segunda GPU
GPU_LOCAL = "http://localhost:11434"        # GPU 1
GPU_REMOTA = "http://IP_SEGUNDA_GPU:11434"  # GPU 2
```

## Solucionar problemas

| Problema | Solución |
|----------|----------|
| "El servicio de IA no respondió a tiempo" | El modelo es muy grande para la GPU disponible. Probar con uno más pequeño |
| "Error al comunicarse con el servicio de IA" | Verificar: `systemctl status ollama maquita-ia-gateway` |
| Respuestas lentas (>30 seg) | Usar un modelo más pequeño o una GPU con más VRAM |
| Respuestas de baja calidad | Usar un modelo más grande (14B o 26B) |
| "Token de autenticación requerido" | Verificar que `IA_API_KEY` en `.env` coincide con `API_KEY` en el gateway |
| GPU no detectada | Verificar drivers: `nvidia-smi`. Reinstalar si es necesario |
| Ollama usa CPU en vez de GPU | Verificar CUDA: `nvcc --version`. Reinstalar Ollama |

## Recursos

- Ollama: https://ollama.com
- Lista de modelos: https://ollama.com/library
- NVIDIA CUDA: https://developer.nvidia.com/cuda-downloads

---

*Fundacion Maquita — Tecnología al servicio de todos, no solo de quienes pueden pagarla.*

## Pregúntale a tu correo (RAG) — qué se indexa y cuándo

El panel «Asistente» responde preguntas sobre el buzón de la persona con sus propios correos como contexto
(RAG). Los correos nunca salen del servidor: los embeddings (`IA_EMBED_MODEL`, por defecto `nomic-embed-text`)
se guardan en PostgreSQL con pgvector (`rag_chunks`) y la respuesta la redacta el modelo normal (`IA_MODEL`).

**Habilitar por dominio** (sin filas, el panel dice que no está habilitado):

```sql
INSERT INTO rag_domains (domain, enabled) VALUES ('example.org', true);
```

**Dos pasadas automáticas** (unidades en `deploy/systemd/`; las instala `deploy/ajustes/56-asistente-rag-temporizadores.sh`,
que el actualizador aplica solo):

| Unidad | Cuándo | Qué hace |
|---|---|---|
| `rag-indexacion.timer` | 21:00 (hasta 9 h 30 min) | Todas las carpetas de todos los buzones habilitados, incremental y reanudable; quita del índice lo borrado desde cualquier cliente. |
| `rag-recientes.timer` | cada 15 min, 06:45–20:45 | Solo lo nuevo de Bandeja de entrada y Enviados, para que lo recibido en el día se pueda preguntar enseguida. |

Registros: `/var/log/rag-indexacion.log` y `/var/log/rag-recientes.log`. Pasada a mano: `systemctl start rag-recientes.service`.

**Qué NO se indexa:** Papelera, No deseado y Borradores; y, por cabeceras, el spam marcado por el servidor
(`X-Spam-Flag: YES`), rebotes y avisos automáticos (MAILER-DAEMON, `Auto-Submitted`) y publicidad masiva
(`List-Unsubscribe` + `Precedence: bulk`). Los remitentes de los dominios habilitados nunca se omiten. Lo omitido se
anota en `rag_omitidos`. Eliminar, mover, archivar o informar como no deseado desde el webmail quita el correo del
índice al instante.

**Variables** (`backend/.env`):

| Variable | Por defecto | Para qué |
|---|---|---|
| `RAG_CALIDAD` | `0` | `1` = responder con `IA_MODEL_CALIDAD` (más lento: 20–35 s con un 14B en una GPU modesta). |
| `RAG_INGEST_PAGE` / `RAG_CUERPO_CHARS` | `100` / `1500` | Correos por tanda y caracteres del cuerpo que se indexan. |
| `RAG_LIMITE_RONDA` / `RAG_MAX_MINUTOS` | `5000` / `570` | Pasada nocturna: correos por buzón y ronda, y hora tope. |
| `RAG_RECIENTES_MAX_BUZON` / `RAG_RECIENTES_MINUTOS` | `300` / `12` | Pasada de recientes: tope por buzón y por pasada. |
| `RAG_BUSQUEDA_EXACTA` | `5000` | Hasta tantos correos por buzón la búsqueda es exacta; por encima usa el índice HNSW. |
