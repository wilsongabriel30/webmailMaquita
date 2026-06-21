"""Pregúntale a tu correo (RAG grounded)."""
from app.rag import store, config as rag_config
from app.rag.embeddings import embed


async def ask(db, username, question):
    if not await rag_config.domain_enabled(db, username):
        return {"answer": "El RAG no está habilitado para tu dominio.", "sources": []}
    qemb = await embed(question)
    if not qemb:
        return {"answer": "No se pudo generar el embedding de la pregunta (IA de embeddings no disponible).", "sources": []}
    rows = await store.search(db, username, qemb, k=6)
    if not rows:
        return {"answer": "Aún no hay correos indexados. Sincroniza tu bandeja primero.", "sources": []}
    ctx = "\n".join(f"- {r['subject']} (de {r['sender']})" for r in rows)
    ans = ""
    try:
        from app.ai.router import _call_llm
        ans = await _call_llm(
            f"Correos del usuario (los más relevantes a la pregunta):\n{ctx}\n\n"
            f"Pregunta: {question}\nResponde con base SOLO en esos correos; si no alcanza, dilo.",
            system="Asistente que responde sobre el correo del usuario. Conciso, en español, sin inventar.",
            temperature=0.1, max_tokens=400)
    except Exception:
        ans = ""
    return {"answer": ans or "(sin respuesta de la IA)",
            "sources": [{"subject": r["subject"], "sender": r["sender"], "sim": round(float(r["sim"]), 2)} for r in rows]}
