"""Safe Attachments — motor de análisis estático/heurístico de adjuntos (Fase 1).

Analiza un adjunto SIN ejecutarlo y devuelve un veredicto:
  clean | suspicious | malicious  (+ razones + sha256)

Capas: ClamAV (daemon), ejecutables disfrazados, macros Office (oletools),
PDF peligroso (JS/OpenAction/Launch), recursión en ZIP, reputación por hash.
Filosofía Maquita: no ejecuta nada; el llamador decide (simulación/cuarentena ZAP).
"""
from __future__ import annotations
import io
import hashlib
import zipfile

CLAMD_SOCKET = "/run/clamav/clamd.ctl"

# Extensiones ejecutables/peligrosas (la doble extensión .pdf.exe se detecta por la última)
DANGEROUS_EXT = {
    "exe", "scr", "com", "pif", "bat", "cmd", "vbs", "vbe", "js", "jse", "wsf",
    "wsh", "hta", "ps1", "msi", "msp", "cpl", "jar", "lnk", "reg", "iso", "img",
}
# Firmas mágicas de ejecutables
EXEC_MAGIC = [b"MZ", b"\x7fELF", b"#!/bin/", b"\xca\xfe\xba\xbe"]
PDF_BAD = [b"/JavaScript", b"/JS", b"/OpenAction", b"/Launch", b"/EmbeddedFile", b"/AA"]
MAX_DEPTH = 3
MAX_UNZIP = 60 * 1024 * 1024  # 60MB por archivo extraído (anti-bomba)

SEV = {"clean": 0, "suspicious": 1, "malicious": 2}


def _ext(name: str) -> str:
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def _clamav(data: bytes) -> tuple[str, str | None]:
    try:
        import clamd
        cd = clamd.ClamdUnixSocket(CLAMD_SOCKET)
        res = cd.instream(io.BytesIO(data))
        status, sig = res.get("stream", ("OK", None))
        if status == "FOUND":
            return "malicious", f"ClamAV: {sig}"
    except Exception as e:
        return "clean", f"_clamav_error:{e}"  # fail-open
    return "clean", None


def _disguised(name: str, data: bytes) -> list[tuple[str, str]]:
    out = []
    ext = _ext(name)
    if ext in DANGEROUS_EXT:
        out.append(("malicious", f"Extensión ejecutable/peligrosa: .{ext}"))
    # doble extensión enmascarada (documento.pdf.exe)
    parts = name.lower().split(".")
    if len(parts) >= 3 and parts[-2] in {"pdf", "doc", "docx", "xls", "xlsx", "jpg", "txt"} and parts[-1] in DANGEROUS_EXT:
        out.append(("malicious", f"Doble extensión engañosa: .{parts[-2]}.{parts[-1]}"))
    # ejecutable con extensión inofensiva (magic MZ/ELF pero dice .pdf/.doc)
    if any(data.startswith(m) for m in EXEC_MAGIC) and ext not in DANGEROUS_EXT and ext not in {"", "dll", "sys"}:
        out.append(("malicious", f"Ejecutable disfrazado de .{ext} (firma MZ/ELF)"))
    return out


def _office(name: str, data: bytes) -> list[tuple[str, str]]:
    ext = _ext(name)
    if ext not in {"doc", "docm", "dot", "dotm", "xls", "xlsm", "xlsb", "xlt", "xltm",
                   "ppt", "pptm", "docx", "xlsx", "pptx", "rtf"}:
        return []
    out = []
    try:
        from oletools.olevba import VBA_Parser
        vp = VBA_Parser(name, data=data)
        if vp.detect_vba_macros():
            res = vp.analyze_macros() or []
            kinds = {r[0] for r in res}  # AutoExec, Suspicious, IOC, ...
            if "AutoExec" in kinds or "Suspicious" in kinds:
                out.append(("malicious", f"Macro Office con auto-ejecución/sospechosa ({', '.join(sorted(kinds))})"))
            else:
                out.append(("suspicious", "Documento Office contiene macros VBA"))
        vp.close()
    except Exception as e:
        out.append(("clean", f"_office_error:{e}"))  # fail-open
    return out


def _pdf(name: str, data: bytes) -> list[tuple[str, str]]:
    if _ext(name) != "pdf" and not data.startswith(b"%PDF"):
        return []
    found = [k.decode() for k in PDF_BAD if k in data[:5_000_000]]
    if found:
        sev = "malicious" if ("/Launch" in found or "/JavaScript" in found or "/JS" in found) else "suspicious"
        return [(sev, f"PDF con elementos activos: {', '.join(found)}")]
    return []


def _archive(name: str, data: bytes, depth: int, redis_client) -> list[tuple[str, str]]:
    if not zipfile.is_zipfile(io.BytesIO(data)):
        return []
    out = []
    if depth >= MAX_DEPTH:
        return [("suspicious", "Archivo comprimido anidado demasiado profundo")]
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
        for zi in zf.infolist():
            if getattr(zi, "flag_bits", 0) & 0x1:
                out.append(("suspicious", f"Archivo protegido por contraseña: {zi.filename} (no analizable)"))
                continue
            if zi.file_size > MAX_UNZIP:
                out.append(("suspicious", f"Entrada muy grande (posible bomba): {zi.filename}"))
                continue
            try:
                inner = zf.read(zi)
            except Exception:
                continue
            sub = analyze(zi.filename, inner, depth + 1, redis_client)
            for r in sub["reasons"]:
                out.append((sub["verdict"], f"[en {zi.filename}] {r}"))
    except Exception as e:
        out.append(("clean", f"_archive_error:{e}"))
    return out


def _hash_rep(sha256: str, redis_client) -> list[tuple[str, str]]:
    if not redis_client:
        return []
    try:
        if redis_client.sismember("tintel:malhash", sha256):
            return [("malicious", "Hash en feed de malware (MalwareBazaar)")]
    except Exception:
        pass
    return []


def analyze(filename: str, data: bytes, depth: int = 0, redis_client=None) -> dict:
    """Analiza un adjunto y devuelve {verdict, score, reasons, sha256, size}."""
    sha256 = hashlib.sha256(data).hexdigest()
    reasons: list[tuple[str, str]] = []
    # capas
    v, r = _clamav(data)
    if r and not r.startswith("_"):
        reasons.append((v, r))
    reasons += _disguised(filename, data)
    reasons += _office(filename, data)
    reasons += _pdf(filename, data)
    reasons += _archive(filename, data, depth, redis_client)
    # veredicto = mayor severidad
    real = [(sev, msg) for sev, msg in reasons if sev in SEV and not msg.startswith("_")]
    verdict = "clean"
    for sev, _msg in real:
        if SEV[sev] > SEV[verdict]:
            verdict = sev
    return {
        "filename": filename,
        "sha256": sha256,
        "size": len(data),
        "verdict": verdict,
        "reasons": [m for _s, m in real],
    }
