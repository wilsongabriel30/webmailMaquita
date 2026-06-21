"""Embeddings para RAG (IA_EMBED_URL/IA_EMBED_MODEL). Fail-open: [] si falla."""
import httpx

from app.config import get_settings


async def embed(text: str) -> list:
    s = get_settings()
    url = (s.ia_embed_url or s.ia_base_url or s.ollama_url or "").rstrip("/")
    model = s.ia_embed_model
    if not url or not model or not text:
        return []
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            if "/v1" in url:
                r = await c.post(f"{url}/embeddings", json={"model": model, "input": text[:4000]},
                                 headers={"Authorization": f"Bearer {s.ia_api_key}"})
                r.raise_for_status()
                return r.json()["data"][0]["embedding"]
            r = await c.post(f"{url}/api/embeddings", json={"model": model, "prompt": text[:4000]})
            r.raise_for_status()
            return r.json().get("embedding", [])
    except Exception:
        return []
