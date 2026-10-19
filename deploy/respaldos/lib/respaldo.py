"""Hacer un respaldo: volcado de las bases, instantánea restic, limpieza según la retención y copia al
destino externo. Cada base de datos va en su propio archivo (así se puede devolver una sola, p. ej. la de
un sitio web, sin tocar las demás)."""

import glob
import os
import shutil
import subprocess
import time

from ajustes import (CERROJO, ESTADO, REGISTROS, REPO_LOCAL, RUTAS, EXCLUIR, VOLCADOS, ErrorRespaldo, config,
                     guardar_json, iniciar_repo, leer_json, repo_externo, restic)


def _bases_postgresql():
    r = subprocess.run(["runuser", "-u", "postgres", "--", "psql", "-tAc",
                        "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname <> 'postgres'"],
                       capture_output=True, text=True, timeout=60, cwd="/tmp")
    return [b for b in r.stdout.split() if b] if r.returncode == 0 else []


def _bases_mariadb():
    if not shutil.which("mariadb"):
        return []
    r = subprocess.run(["mariadb", "--protocol=socket", "-u", "root", "-N", "-e", "SHOW DATABASES"],
                       capture_output=True, text=True, timeout=60)
    sistema = {"information_schema", "performance_schema", "mysql", "sys"}
    return [b for b in r.stdout.split() if b and b not in sistema] if r.returncode == 0 else []


def volcar_bases(registro):
    """Un archivo por base, coherente (pg_dump es una instantánea; mariadb-dump con --single-transaction)."""
    for motor in ("postgresql", "mariadb"):
        destino = os.path.join(VOLCADOS, motor)
        shutil.rmtree(destino, ignore_errors=True)
        os.makedirs(destino, mode=0o700)
    hechas = []
    for base in _bases_postgresql():
        with open(os.path.join(VOLCADOS, "postgresql", f"{base}.dump"), "wb") as f:
            r = subprocess.run(["runuser", "-u", "postgres", "--", "pg_dump", "-Fc", base], stdout=f,
                               stderr=subprocess.PIPE, timeout=7200, cwd="/tmp")
        if r.returncode != 0:
            raise ErrorRespaldo(f"no se pudo volcar la base {base}: " + r.stderr.decode(errors="replace")[-200:])
        hechas.append(f"postgresql/{base}")
    for base in _bases_mariadb():
        with open(os.path.join(VOLCADOS, "mariadb", f"{base}.sql"), "wb") as f:
            r = subprocess.run(["mariadb-dump", "--protocol=socket", "-u", "root", "--single-transaction", "--hex-blob",
                                "--routines", "--triggers", "--databases", base], stdout=f, stderr=subprocess.PIPE,
                               timeout=7200)
        if r.returncode != 0:
            raise ErrorRespaldo(f"no se pudo volcar la base {base}: " + r.stderr.decode(errors="replace")[-200:])
        hechas.append(f"mariadb/{base}")
    with open(registro, "a") as f:
        f.write("Bases volcadas: " + ", ".join(hechas) + "\n")
    return hechas


def respaldar(motivo="automático", rutas=None, etiqueta=None):
    """Respaldo completo (o de las rutas indicadas). Devuelve el resumen y lo anota en el estado."""
    try:
        cerrojo = os.open(CERROJO, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ErrorRespaldo("ya hay un respaldo o una restauración en curso")
    os.makedirs(REGISTROS, mode=0o750, exist_ok=True)
    inicio = time.time()
    registro = os.path.join(REGISTROS, time.strftime("%Y%m%d-%H%M%S") + ".log")
    estado = leer_json(ESTADO, {})
    resultado = {"inicio": time.strftime("%Y-%m-%d %H:%M:%S"), "motivo": motivo, "registro": registro}
    try:
        conf = config()
        iniciar_repo(REPO_LOCAL)
        bases = volcar_bases(registro)
        presentes = [r for r in (rutas or RUTAS) if os.path.exists(r)]
        args = ["backup", *presentes, "--tag", etiqueta or ("auto" if motivo == "automático" else "manual"),
                "--host", "servidor"]
        for patron in EXCLUIR:
            args += ["--exclude", patron]
        resumen = restic(REPO_LOCAL, *args, registro=registro, json_salida=True) or {}
        resultado.update(instantanea=(resumen.get("snapshot_id") or "")[:8], bases=len(bases),
                         archivos=resumen.get("total_files_processed"),
                         nuevo_mb=round((resumen.get("data_added") or 0) / 1048576, 1),
                         total_mb=round((resumen.get("total_bytes_processed") or 0) / 1048576, 1))
        c = conf["conservar"]
        restic(REPO_LOCAL, "forget", "--host", "servidor", "--keep-daily", str(c["diarios"]), "--keep-weekly",
               str(c["semanales"]), "--keep-monthly", str(c["mensuales"]), "--keep-tag", "antes-de-restaurar",
               "--prune", registro=registro)
        externo = repo_externo(conf)
        if externo:
            try:
                iniciar_repo(externo, desde_local=True)
                restic(externo, "copy", "--from-repo", REPO_LOCAL, "--from-password-file", "/etc/maquita-respaldos/clave",
                       registro=registro)
                restic(externo, "forget", "--host", "servidor", "--keep-daily", str(c["diarios"]), "--keep-weekly",
                       str(c["semanales"]), "--keep-monthly", str(c["mensuales"]), "--prune", registro=registro)
                resultado["externo"] = "copiado"
            except ErrorRespaldo as e:
                resultado["externo"] = f"falló: {e}"
        resultado["estado"] = "correcto" if not str(resultado.get("externo", "")).startswith("falló") else "sin copia externa"
    except Exception as e:
        resultado.update(estado="falló", error=str(e)[:400])
    finally:
        resultado["duracion_s"] = round(time.time() - inicio)
        for viejo in sorted(glob.glob(os.path.join(REGISTROS, "*.log")))[:-30]:
            os.remove(viejo)
        estado["ultimo"] = resultado
        if resultado.get("estado") == "correcto":
            estado["ultimo_correcto"] = resultado
        guardar_json(ESTADO, estado, 0o644)
        os.close(cerrojo)
        os.remove(CERROJO)
    if resultado["estado"] == "falló":
        raise ErrorRespaldo(resultado["error"])
    return resultado


def instantaneas(repo=REPO_LOCAL):
    lista = restic(repo, "snapshots", "--host", "servidor", json_salida=True, tiempo=300) or []
    return [{"id": s["short_id"], "fecha": s["time"][:16].replace("T", " "), "etiquetas": s.get("tags", [])}
            for s in sorted(lista, key=lambda s: s["time"], reverse=True)]
