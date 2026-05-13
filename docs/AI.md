# Inteligencia Artificial — Fundacion Maquita Webmail

> **Proyecto de la Fundacion Maquita** — Comercializadora asociativa sin fines de lucro, Ecuador.

Guia para configurar el asistente de IA integrado en el webmail. Usa modelos de lenguaje ejecutados localmente (Ollama), sin enviar datos a servicios externos.

---

## Que puede hacer la IA

- **Respuestas inteligentes** — sugiere 3 opciones de respuesta contextualizadas
- **Autocompletado** — completa frases mientras escribes
- **Resumen de correos** — resume correos largos
- **Redaccion asistida** — ayuda a redactar correos profesionales
- **Dictado por voz** — transcripcion con Whisper

## Requisitos

- Un servidor o PC con GPU NVIDIA (minimo 8 GB VRAM)
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
# Debe mostrar tu GPU, memoria VRAM y version del driver
```

## Paso 2: Instalar Ollama

Ollama es el motor que ejecuta los modelos de IA localmente. Gratuito y open source.

```bash
curl -fsSL https://ollama.com/install.sh | sh

# Verificar
systemctl status ollama
# Debe decir "active (running)"

# Si no esta corriendo:
systemctl enable --now ollama
```

## Paso 3: Descargar un modelo

Recomendaciones segun tu VRAM:

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

# Verificar
ollama list

# Probar
ollama run gemma2:9b "Hola, responde en una frase"
```

**Modelos recomendados por idioma:**
- **Espanol**: Gemma 4, Qwen 2.5, Llama 3.1 (todos funcionan bien)
- **Solo ingles**: Phi-3, Mistral (menos recomendados para webmail en espanol)

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

# Verificar
ss -tlnp | grep 11434
# Debe mostrar 0.0.0.0:11434
```

**IMPORTANTE:** Proteger con firewall:
```bash
# Solo permitir acceso desde el servidor de correo
ufw allow from IP_SERVIDOR_CORREO to any port 11434
ufw deny 11434
```

## Paso 5: Crear el gateway IA

El webmail no se conecta directamente a Ollama. Necesita un gateway FastAPI que autentica, enruta y hace failover.

Crear `/opt/maquita-ia-gateway/gateway.py`:
```python
"""
Gateway IA para Maquita Webmail
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
MODELO_DEFAULT = "gemma2:9b"  # Cambiar por tu modelo

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

Reiniciar:
```bash
systemctl restart maquita-webmail
```

## Paso 8: Verificar en el navegador

1. Ir al webmail
2. Abrir un correo recibido
3. Buscar el boton de "Respuesta inteligente" o icono de IA
4. Debe generar opciones de respuesta contextualizadas
5. Al redactar, el autocompletado debe sugerir texto

## Configuracion avanzada: multiples GPUs

Si tienes dos o mas GPUs, el sistema puede distribuir la carga:

- **GPU principal**: tareas pesadas (resumenes largos, razonamiento)
- **GPU secundaria**: tareas rapidas (autocompletado, chat)
- **Failover automatico** si una GPU falla

```python
# En el gateway, agregar segunda GPU
GPU_LOCAL = "http://localhost:11434"        # GPU 1
GPU_REMOTA = "http://IP_SEGUNDA_GPU:11434"  # GPU 2
```

## Solucionar problemas

| Problema | Solucion |
|----------|----------|
| "El servicio de IA no respondio a tiempo" | El modelo es muy grande para tu GPU. Prueba uno mas pequeno |
| "Error al comunicarse con el servicio de IA" | Verificar: `systemctl status ollama maquita-ia-gateway` |
| Respuestas lentas (>30 seg) | Usa un modelo mas pequeno o GPU con mas VRAM |
| Respuestas de baja calidad | Usa un modelo mas grande (14B o 26B) |
| "Token de autenticacion requerido" | Verificar que `IA_API_KEY` en `.env` coincide con `API_KEY` en el gateway |
| GPU no detectada | Verificar drivers: `nvidia-smi`. Reinstalar si es necesario |
| Ollama usa CPU en vez de GPU | Verificar CUDA: `nvcc --version`. Reinstalar Ollama |

## Recursos

- Ollama: https://ollama.com
- Lista de modelos: https://ollama.com/library
- NVIDIA CUDA: https://developer.nvidia.com/cuda-downloads

---

*Fundacion Maquita — Tecnologia al servicio de todos, no solo de quienes pueden pagarla.*
