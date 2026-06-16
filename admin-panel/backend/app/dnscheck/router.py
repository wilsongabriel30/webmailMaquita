"""DNS Check — verificacion de configuracion DNS para dominios de correo.

Usa resolvers publicos (Google 8.8.8.8, Cloudflare 1.1.1.1) con timeout corto.
Consultas en paralelo para velocidad.
Actualizado: 2026-04-13
"""
import asyncio
from asyncio.subprocess import PIPE
from fastapi import APIRouter, Depends, Query, Request
from app.auth.dependencies import get_current_admin

router = APIRouter(prefix="/api/dnscheck", tags=["dnscheck"])

# Resolver publico para evitar timeouts con DNS interno
DNS_RESOLVER = "8.8.8.8"
DIG_TIMEOUT = "5"  # segundos


async def _run(*cmd, timeout: int = 10) -> str:
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return out.decode(errors="replace").strip()
    except asyncio.TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        return ""
    except Exception:
        return ""


async def _dig(record_type: str, domain: str) -> list[str]:
    """Consulta DNS via dig usando resolver publico con timeout."""
    out = await _run(
        "dig", f"@{DNS_RESOLVER}", "+short", "+time=3", "+tries=1",
        record_type, domain,
        timeout=8
    )
    # Filtrar lineas de error (communications error, connection timed out, etc.)
    lines = []
    for line in out.split("\n"):
        line = line.strip()
        if not line:
            continue
        if any(err in line.lower() for err in [
            "error", "timed out", "connection", "servfail",
            "nxdomain", ";;", "no servers"
        ]):
            continue
        lines.append(line)
    return lines


async def _dig_full(record_type: str, domain: str) -> str:
    """Consulta DNS con output completo (para diagnostico)."""
    out = await _run(
        "dig", f"@{DNS_RESOLVER}", "+time=3", "+tries=1",
        record_type, domain,
        timeout=8
    )
    return out


@router.get("")
async def list_managed_domains(request: Request, admin: dict = Depends(get_current_admin)):
    """Lista dominios administrados por el servidor para acceso rapido."""
    db = request.app.state.db
    rows = await db.fetch("SELECT domain FROM domain WHERE active = true ORDER BY domain")
    return {"domains": [r["domain"] for r in rows]}


def _extract_base_domain(domain: str) -> str | None:
    """Si el dominio es un subdominio (ej: mail.maquita.com.ec), extraer dominio base.
    Maneja TLDs de dos niveles como .com.ec, .org.ec, .gob.ec, .co.uk, etc."""
    parts = domain.split(".")
    two_level_tlds = {"com", "org", "gob", "gov", "edu", "net", "mil", "co"}
    if len(parts) >= 4 and parts[-2] in two_level_tlds:
        # mail.maquita.com.ec → maquita.com.ec
        return ".".join(parts[-3:])
    elif len(parts) >= 3 and parts[-2] not in two_level_tlds:
        # mail.maquita.org → maquita.org
        return ".".join(parts[-2:])
    return None


@router.get("/{domain}")
async def check_domain(domain: str, admin: dict = Depends(get_current_admin)):
    """Verificar configuracion DNS de un dominio de correo."""

    # Ejecutar todas las consultas DNS en paralelo
    mx_task = _dig("MX", domain)
    txt_task = _dig("TXT", domain)
    a_task = _dig("A", domain)
    dmarc_task = _dig("TXT", f"_dmarc.{domain}")

    # DKIM: verificar selectores comunes en paralelo
    dkim_selectors = ["default", "dkim", "mail", "selector1", "selector2", "maquita", "google", "k1"]
    dkim_tasks = {sel: _dig("TXT", f"{sel}._domainkey.{domain}") for sel in dkim_selectors}

    # Esperar todas las consultas al mismo tiempo
    mx_records, txt_records, a_records, dmarc_records = await asyncio.gather(
        mx_task, txt_task, a_task, dmarc_task
    )
    dkim_results = {}
    dkim_values = await asyncio.gather(*dkim_tasks.values())
    for sel, val in zip(dkim_tasks.keys(), dkim_values):
        dkim_results[sel] = val

    results = {}

    # --- MX ---
    results["mx"] = {
        "records": mx_records,
        "ok": len(mx_records) > 0,
        "message": f"{len(mx_records)} registros MX encontrados" if mx_records else "Sin registros MX — el correo no se puede entregar a este dominio",
    }

    # --- SPF ---
    spf = [r for r in txt_records if "v=spf1" in r.lower()]
    spf_msg = "SPF configurado correctamente"
    if not spf:
        spf_msg = "Sin registro SPF — riesgo de suplantacion de identidad. Agregue un registro TXT con v=spf1"
    elif len(spf) > 1:
        spf_msg = "Multiples registros SPF encontrados — solo deberia haber uno"
    results["spf"] = {
        "records": spf,
        "ok": len(spf) == 1,
        "message": spf_msg,
    }

    # --- DKIM ---
    dkim_found = []
    for sel, records in dkim_results.items():
        if records and any("v=dkim1" in r.lower() or "p=" in r for r in records):
            dkim_found.append({
                "selector": sel,
                "record": records[0][:120] + ("..." if len(records[0]) > 120 else ""),
            })
    results["dkim"] = {
        "records": dkim_found,
        "ok": len(dkim_found) > 0,
        "message": f"DKIM encontrado ({len(dkim_found)} selector{'es' if len(dkim_found) != 1 else ''}): {', '.join(d['selector'] for d in dkim_found)}" if dkim_found else "Sin DKIM configurado — los correos no se firman digitalmente",
        "selectors_checked": dkim_selectors,
    }

    # --- DMARC ---
    dmarc = [r for r in dmarc_records if "v=dmarc1" in r.lower()]
    results["dmarc"] = {
        "records": dmarc,
        "ok": len(dmarc) > 0,
        "message": "DMARC configurado" if dmarc else "Sin DMARC — no hay política de autenticación. Agregue _dmarc.{} TXT".format(domain),
    }

    # --- A record ---
    results["a"] = {
        "records": a_records,
        "ok": len(a_records) > 0,
        "message": f"Resuelve a: {', '.join(a_records)}" if a_records else "Sin registro A",
    }

    # --- PTR (DNS inverso) para IPs del MX ---
    ptr_results = []
    if mx_records:
        # Extraer hostname del MX (ej: "10 mail.maquita.org." → "mail.maquita.org")
        mx_hosts = []
        for mx in mx_records[:3]:
            parts = mx.split()
            host = parts[-1].rstrip(".") if parts else ""
            if host:
                mx_hosts.append(host)

        # Resolver IPs de los MX hosts
        mx_ip_tasks = [_dig("A", h) for h in mx_hosts]
        mx_ip_results = await asyncio.gather(*mx_ip_tasks)

        all_ips = []
        for host, ips in zip(mx_hosts, mx_ip_results):
            for ip in ips[:2]:
                all_ips.append((host, ip))

        # Consultar PTR para cada IP
        if all_ips:
            # Convertir IP a formato in-addr.arpa para PTR
            ptr_tasks = []
            for host, ip in all_ips:
                # dig -x hace reverse lookup
                ptr_tasks.append(_run(
                    "dig", f"@{DNS_RESOLVER}", "+short", "+time=3", "+tries=1",
                    "-x", ip,
                    timeout=8
                ))

            ptr_raw = await asyncio.gather(*ptr_tasks)
            for (host, ip), ptr_out in zip(all_ips, ptr_raw):
                ptr_name = ptr_out.strip().rstrip(".") if ptr_out.strip() and "error" not in ptr_out.lower() else ""
                ptr_results.append({
                    "mx_host": host,
                    "ip": ip,
                    "ptr": ptr_name,
                    "match": ptr_name.lower() == host.lower() if ptr_name else False,
                })

    has_ptr = any(p.get("ptr") for p in ptr_results)
    has_match = any(p.get("match") for p in ptr_results)
    if has_match:
        ptr_msg = "PTR configurado y coincide con MX"
    elif has_ptr:
        ptr_msg = "PTR encontrado pero NO coincide con el hostname MX — puede causar problemas de entrega"
    else:
        ptr_msg = "Sin PTR (DNS inverso) — servidores como Gmail pueden rechazar correos"

    results["ptr"] = {
        "records": ptr_results,
        "ok": has_ptr,
        "match": has_match,
        "message": ptr_msg,
    }

    # --- AUTOCONFIG / AUTODISCOVER ---
    autoconfig_records = await _dig("CNAME", f"autoconfig.{domain}")
    autodiscover_records = await _dig("CNAME", f"autodiscover.{domain}")
    results["autoconfig"] = {
        "autoconfig": autoconfig_records,
        "autodiscover": autodiscover_records,
        "ok": bool(autoconfig_records or autodiscover_records),
        "message": "Autoconfiguración disponible" if (autoconfig_records or autodiscover_records) else "Sin autoconfig/autodiscover — los clientes de correo no se configuraran automaticamente",
    }

    # --- Score ---
    checks = {
        "mx": (results["mx"]["ok"], 25),
        "spf": (results["spf"]["ok"], 20),
        "dkim": (results["dkim"]["ok"], 20),
        "dmarc": (results["dmarc"]["ok"], 20),
        "ptr": (results.get("ptr", {}).get("ok", False), 10),
        "autoconfig": (results.get("autoconfig", {}).get("ok", False), 5),
    }
    score = sum(pts for ok, pts in checks.values() if ok)
    results["score"] = score
    results["grade"] = (
        "A" if score >= 95 else
        "B" if score >= 75 else
        "C" if score >= 50 else
        "D" if score >= 25 else
        "F"
    )

    # --- Resumen para migracion ---
    results["summary"] = {
        "ready_for_mail": results["mx"]["ok"],
        "ready_for_delivery": results["mx"]["ok"] and results["spf"]["ok"] and has_ptr,
        "fully_authenticated": results["spf"]["ok"] and results["dkim"]["ok"] and results["dmarc"]["ok"],
        "recommendations": _get_recommendations(results),
    }

    response = {"domain": domain, "results": results}

    # Si no tiene MX y parece subdominio (mail.dominio.com), verificar dominio base
    base = _extract_base_domain(domain)
    if base and base != domain:
        base_mx = await _dig("MX", base)
        if base_mx or not results["mx"]["ok"]:
            # El dominio base tiene MX o el subdominio no — sugerir verificar el base
            response["base_domain"] = base
            response["hint"] = (
                f"Parece que ingresaste el hostname del servidor ({domain}). "
                f"Los registros de correo (MX, SPF, DKIM) se configuran en el dominio base: {base}. "
                f"Verifica '{base}' para ver la configuracion real de correo."
            )
            if base_mx:
                response["base_has_mx"] = True

    return response


def _get_recommendations(results: dict) -> list[str]:
    """Genera recomendaciones basadas en los resultados."""
    recs = []
    if not results["mx"]["ok"]:
        recs.append("CRITICO: Agregar registros MX apuntando al servidor de correo")
    if not results["spf"]["ok"]:
        recs.append("Agregar registro SPF (TXT) para autorizar servidores de envio")
    if not results["dkim"]["ok"]:
        recs.append("Configurar DKIM para firmar correos salientes")
    if not results["dmarc"]["ok"]:
        recs.append("Agregar registro DMARC para definir politica de autenticacion")
    if not results.get("ptr", {}).get("ok"):
        recs.append("Configurar PTR (DNS inverso) en el proveedor de IP/hosting")
    if results.get("ptr", {}).get("ok") and not results.get("ptr", {}).get("match"):
        recs.append("El PTR no coincide con el hostname MX — corregir para mejor entregabilidad")
    if not results.get("autoconfig", {}).get("ok"):
        recs.append("Agregar registros autoconfig/autodiscover para configuracion automatica de clientes")
    return recs
