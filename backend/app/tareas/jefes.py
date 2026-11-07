#!/opt/maquita-webmail/backend/venv/bin/python3
"""Jefes para el ESCALAMIENTO de tareas (T-34), tomados de NÓMINA (Raíces, BD nomina en VM 132). Cron diario + a mano.
La asignación de tareas es LIBRE (cualquiera a cualquiera); esto solo decide a quién avisar cuando una tarea vence.
Orden por persona (correo institucional): aprobador de vacaciones → quien ocupa el cargo superior (mismo departamento,
correo @maquita) → jefe del departamento. Escribe `task_jefes` y `task_escalamiento` (jefes por departamento, 2 días) y
completa `user_profiles.department` (GAL) cuando está vacío. Registro: /var/log/maquita-tareas.log
"""

import asyncio
import logging
import os
import sys

sys.path.insert(0, "/opt/maquita-webmail/backend")
os.chdir("/opt/maquita-webmail/backend")
import asyncpg  # noqa: E402

from app import organizacion  # noqa: E402
from app.branding.service import ORG_NAME_FALLBACK, get_org_name  # noqa: E402
from app.core.database import create_db_pool  # noqa: E402
from app.tareas import avisos  # noqa: E402

# Cache del directorio de la organizacion (correo -> nombre). Son datos
# personales: vive en el directorio de datos del servicio, NUNCA en el arbol
# de codigo, que se publica.
RUTA_NOMBRES = "/var/lib/maquita-webmail/nombres.json"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tareas.jefes")
DDL = """CREATE TABLE IF NOT EXISTS task_jefes (
    email TEXT PRIMARY KEY, jefe_email TEXT NOT NULL, jefe_nombre TEXT NOT NULL DEFAULT '', cargo TEXT NOT NULL DEFAULT '',
    departamento TEXT NOT NULL DEFAULT '', origen TEXT NOT NULL DEFAULT '', actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW());
CREATE TABLE IF NOT EXISTS task_personas (
    email TEXT PRIMARY KEY, nombre TEXT NOT NULL, cargo TEXT NOT NULL DEFAULT '', departamento TEXT NOT NULL DEFAULT '',
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW());"""
# user_profiles.fuente la crea el admin de la BD (ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS fuente TEXT; hecho 05/11/2026):
# el usuario de la aplicación no es dueño de esa tabla.


# Correos institucionales (cuentas que pueden ser jefes): ORG_DOMINIOS_INSTITUCIONALES de la
# configuración de la organización; si no está, todos sus dominios propios.
_PARTICULAS = {
    "de",
    "del",
    "la",
    "las",
    "los",
    "y",
    "e",
    "da",
    "do",
    "dos",
    "das",
    "van",
    "von",
}


def nombre_propio(s: str) -> str:
    """«MARJORIE DEL CARMEN BONILLA» → «Marjorie del Carmen Bonilla» (05/11/2026)."""
    out = []
    for i, w in enumerate((s or "").strip().lower().split()):
        out.append(w if (i and w in _PARTICULAS) else w[:1].upper() + w[1:])
    return " ".join(out)


def _es_institucional(email: str) -> bool:
    return (email or "").rsplit("@", 1)[-1].lower() in organizacion.dominios(
        "ORG_DOMINIOS_INSTITUCIONALES"
    )


def _palabras(nombre: str) -> set:
    import re
    import unicodedata

    t = unicodedata.normalize("NFD", (nombre or "").lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return {w for w in re.split(r"[^a-z]+", t) if len(w) > 2}


RUTA_DESAJUSTES = "/var/lib/maquita-webmail/desajustes-nomina-buzon.txt"


async def buzones_cruzados(db, trab) -> set:
    """Buzones cuyo nombre actual no se parece al de la persona que nómina tiene en ese correo (06/11/2026).

    Pasa cuando el buzón se reasignó (reemplazo) y nómina aún no se actualizó: p. ej. logisticaproductos@
    lo usa Thalia Vega y nómina lo tenía a nombre de Roberto Paul Rodriguez. En esos buzones NO se copian
    nombre, cargo ni foto de nómina (se mostraba a otra persona); se listan para Talento Humano. Cuando
    nómina se corrige, vuelven a sincronizarse solos.
    """
    nombres = {
        r["email"]: r["name"] or ""
        for r in await db.fetch("SELECT lower(username) AS email, name FROM mailbox")
    }
    cruzados, lineas = set(), []
    for t in trab:
        if (t["estado"] or "").lower() != "activo" or not _es_institucional(t["email"]):
            continue
        buzon = nombres.get(t["email"], "").strip()
        # Un buzón con nombre genérico («Maquita Turismo») no es de una persona: ahí manda nómina.
        if (
            buzon
            and "maquita" not in buzon.lower()
            and not (_palabras(buzon) & _palabras(t["nombre"]))
        ):
            cruzados.add(t["email"])
            lineas.append(
                f"{t['email']}\tbuzón: {buzon}\tnómina: {nombre_propio(t['nombre'])}"
            )
    try:
        with open(RUTA_DESAJUSTES, "w", encoding="utf-8") as f:
            f.write(
                "# Correo institucional con persona distinta en nómina y en el buzón (revisar con Talento Humano)\n"
            )
            f.write("\n".join(sorted(lineas)) + ("\n" if lineas else ""))
    except OSError:
        pass
    if lineas:
        log.warning(
            "Buzones con nombre distinto al de nómina (no se copia el perfil): %s",
            ", ".join(sorted(cruzados)),
        )
    return cruzados


async def nombres_por_coincidencia(db, trab) -> set:
    """Nombre COMPLETO de nómina para buzones que nómina no enlaza (06/11/2026).

    Muchos buzones los usa una persona activa cuyo correo en nómina es otro (p. ej. analista.pp@ lo usa
    Gissela Jaya y nómina la tiene con mejora.continua@): la lista mostraba «Gissela Jaya» y no su nombre
    completo como al resto. Si el nombre del buzón (≥2 palabras) está contenido en el de UNA sola persona
    ACTIVA, se usa el nombre completo. Nunca con desvinculados (lo histórico, p. ej. asiscontabilidad@ de
    Isabel Rodriguez, no cambia), ni si hay dos candidatos, ni en buzones genéricos («Maquita …»), ni
    encima de un nombre puesto a mano. Solo el nombre: sin cargo ni foto. fuente='nomina-nombre'.
    """
    activos: dict[str, set] = {}
    for t in trab:
        if (t["estado"] or "").lower() == "activo":
            n = nombre_propio(t["nombre"])
            activos.setdefault(n, _palabras(n))
    filas = await db.fetch(
        """SELECT lower(m.username) AS email, COALESCE(m.name, '') AS buzon,
                  COALESCE(p.display_name, '') AS perfil, COALESCE(p.fuente, '') AS fuente
           FROM mailbox m LEFT JOIN user_profiles p ON lower(p.user_email) = lower(m.username)
           WHERE m.active"""
    )
    asignar: dict[str, str] = {}
    for f in filas:
        if f["perfil"].strip() and f["fuente"] != "nomina-nombre":
            continue
        if "maquita" in f["buzon"].lower():
            continue
        palabras = _palabras(f["buzon"])
        if len(palabras) < 2:
            continue
        cand = [n for n, w in activos.items() if palabras <= w]
        if len(cand) == 1:
            asignar[f["email"]] = cand[0]
    cambiados: set = set()
    for f in filas:
        e = f["email"]
        if e in asignar:
            if f["perfil"] != asignar[e]:
                await db.execute(
                    """INSERT INTO user_profiles (user_email, display_name, fuente, updated_at)
                       VALUES ($1, $2, 'nomina-nombre', NOW())
                       ON CONFLICT (user_email) DO UPDATE SET display_name = EXCLUDED.display_name,
                           fuente = 'nomina-nombre', updated_at = NOW()
                       WHERE COALESCE(user_profiles.display_name, '') = '' OR user_profiles.fuente = 'nomina-nombre'""",
                    e,
                    asignar[e],
                )
                cambiados.add(e)
        elif f["fuente"] == "nomina-nombre":
            await db.execute(
                "UPDATE user_profiles SET display_name = NULL, fuente = NULL, updated_at = NOW() "
                "WHERE lower(user_email) = $1 AND fuente = 'nomina-nombre'",
                e,
            )
            cambiados.add(e)
    if cambiados:
        log.info(
            "Nombre completo por coincidencia con nómina: %d buzones actualizados",
            len(cambiados),
        )
    return cambiados


def _dsn():
    for l in open(".env", encoding="utf-8"):
        if l.startswith("NOMINA_DSN="):
            return l.split("=", 1)[1].strip()
    raise SystemExit("Falta NOMINA_DSN en .env")


async def devolver_tareas_de_salidos(db, activos):
    """Salidas de personal: quien estaba en el directorio y ya no está Activo en nómina. Sus tareas pendientes vuelven
    al asignador (queda como asignado si no había otro), con comentario, etiqueta «salida de personal» y aviso T-03 para
    que las realice, reasigne o elimine. Cada tarea se devuelve una sola vez."""
    salidos = await db.fetch(
        "SELECT email, nombre FROM task_personas WHERE email <> ALL($1::text[])",
        activos,
    )
    # El nombre de la organización sale de la marca; sin marca configurada, un texto neutro.
    org = await get_org_name(db) if salidos else ORG_NAME_FALLBACK
    lugar = "la organización" if org == ORG_NAME_FALLBACK else org
    for s in salidos:
        tareas = await db.fetch(
            """SELECT c.id, c.title, c.created_by, c.estado FROM task_cards c JOIN task_asignados a ON a.card_id = c.id
                                   WHERE a.email = $1 AND c.asignada AND NOT c.completed""",
            s["email"],
        )
        if not tareas:
            continue
        por_asignador = {}
        for t in tareas:
            await db.execute(
                "DELETE FROM task_asignados WHERE card_id = $1 AND email = $2",
                t["id"],
                s["email"],
            )
            quedan = await db.fetchval(
                "SELECT count(*) FROM task_asignados WHERE card_id = $1", t["id"]
            )
            if not quedan:
                await db.execute(
                    "INSERT INTO task_asignados (card_id, email) VALUES ($1,$2) ON CONFLICT DO NOTHING",
                    t["id"],
                    t["created_by"],
                )
            await db.execute(
                """UPDATE task_cards SET assigned_to = (SELECT email FROM task_asignados WHERE card_id = $1 ORDER BY asignado_en LIMIT 1),
                                estado = CASE WHEN estado = 'en_curso' THEN 'pendiente' ELSE estado END, aceptacion = 'sin_responder',
                                etiquetas = CASE WHEN etiquetas::text ILIKE '%salida de personal%' THEN etiquetas ELSE etiquetas || '["salida de personal"]'::jsonb END,
                                updated_at = NOW() WHERE id = $1""",
                t["id"],
            )
            await db.execute(
                "INSERT INTO task_comentarios (card_id, autor, texto) VALUES ($1, 'sistema', $2)",
                t["id"],
                f"{s['nombre']} ya no labora en {lugar} (salida registrada en nómina). Esta tarea quedó pendiente y vuelve a quien la asignó: realízala, reasígnala o elimínala.",
            )
            por_asignador.setdefault(t["created_by"], []).append(t["title"])
        for asignador, titulos in por_asignador.items():
            await avisos.emitir(
                [asignador],
                f"{s['nombre']} ya no labora: {len(titulos)} tarea(s) pendiente(s)",
                "Quedaron sin hacer: "
                + "; ".join(titulos)[:220]
                + ". Realízalas, reasígnalas o elimínalas.",
                avisos.URL_TAREAS + "&pestana=por-mi",
                asignador,
                {"accion": "asignado_salio"},
                db,
                None,
                "asignado_salio",
                incluir_originador=True,
            )
        log.info(
            "salida de %s: %s tareas devueltas a %s",
            s["email"],
            len(tareas),
            ", ".join(por_asignador),
        )


async def main():
    nom = await asyncpg.connect(_dsn())
    trab = await nom.fetch(
        """
        SELECT t.id, t.estado, lower(trim(t.email_institucional)) AS email, t.nombres||' '||t.apellidos AS nombre, t.cargo_id, t.departamento_id,
               t.aprobador_vacaciones_id, c.nombre AS cargo, c.cargo_superior_id, d.nombre AS departamento, d.jefe_departamento_id,
               t.telefono_movil_institucional AS movil, t.extension_telefono AS extension, a.nombre AS area
        FROM trabajadores t LEFT JOIN cargos c ON c.id = t.cargo_id LEFT JOIN departamentos_empresa d ON d.id = t.departamento_id
             LEFT JOIN areas a ON a.id = t.area_id
        WHERE t.es_version_actual AND lower(coalesce(t.estado,'')) IN ('activo','consultor externo') AND t.email_institucional ILIKE '%@%'"""
    )
    usuarios_raices = await nom.fetch(
        """SELECT lower(u.email) AS email, u.full_name, u.profile_picture, t.foto_perfil, lower(trim(t.email_institucional)) AS email_inst
        FROM usuarios u LEFT JOIN trabajadores t ON t.id = u.trabajador_id AND t.es_version_actual WHERE u.email ILIKE '%@%' AND COALESCE(u.full_name,'') <> ''"""
    )
    deptos = await nom.fetch(
        "SELECT id, nombre, jefe_departamento_id FROM departamentos_empresa WHERE activo IS DISTINCT FROM FALSE"
    )
    await nom.close()
    por_id = {t["id"]: t for t in trab}
    por_cargo = {}
    for t in trab:
        por_cargo.setdefault(t["cargo_id"], []).append(t)

    def inst(t):
        return t and _es_institucional(t["email"])

    def jefe_de(t):
        a = por_id.get(t["aprobador_vacaciones_id"])
        if inst(a) and a["id"] != t["id"]:
            return a, "aprobador_vacaciones"
        cand = [
            x
            for x in por_cargo.get(t["cargo_superior_id"], [])
            if inst(x) and x["id"] != t["id"]
        ]
        mismo = [x for x in cand if x["departamento_id"] == t["departamento_id"]]
        if mismo or cand:
            return (mismo or cand)[0], "cargo_superior"
        j = por_id.get(t["jefe_departamento_id"])
        if inst(j) and j["id"] != t["id"]:
            return j, "jefe_departamento"
        return None, ""

    pool = await create_db_pool()
    n = sin = 0
    async with pool.acquire() as db:
        await db.execute(DDL)
        cruzados = await buzones_cruzados(db, trab)  # 06/11/2026
        activos = [t["email"] for t in trab if (t["estado"] or "").lower() == "activo"]
        await devolver_tareas_de_salidos(db, activos)
        await db.execute(
            "DELETE FROM task_personas WHERE email <> ALL($1::text[])",
            [t["email"] for t in trab if (t["estado"] or "").lower() == "activo"],
        )
        for t in trab:
            if (t["estado"] or "").lower() != "activo":
                continue  # consultores: pueden ser jefes, pero no salen en el directorio
            await db.execute(
                """INSERT INTO task_personas (email, nombre, cargo, departamento, actualizado_en) VALUES ($1,$2,$3,$4,NOW())
                                ON CONFLICT (email) DO UPDATE SET nombre=EXCLUDED.nombre, cargo=EXCLUDED.cargo, departamento=EXCLUDED.departamento, actualizado_en=NOW()""",
                t["email"],
                (t["nombre"] or "").strip().title(),
                t["cargo"] or "",
                t["departamento"] or "",
            )
            # 05/11/2026: la nómina MANDA en el directorio: nombre, cargo, departamento, área, celular y extensión
            # se actualizan siempre (si el buzón pasa a otra persona, cambia para todos). fuente='nomina' permite
            # limpiar al salir. Solo buzones institucionales. La foto va aparte (más abajo).
            if not _es_institucional(t["email"]):
                continue
            if (
                t["email"] not in cruzados
            ):  # 06/11/2026: buzón reasignado y nómina sin actualizar
                await db.execute(
                    """INSERT INTO user_profiles (user_email, display_name, department, title, office_location, mobile, phone, fuente, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,'nomina',NOW())
                   ON CONFLICT (user_email) DO UPDATE SET display_name=EXCLUDED.display_name, department=EXCLUDED.department,
                       title=EXCLUDED.title, office_location=EXCLUDED.office_location, mobile=EXCLUDED.mobile, phone=EXCLUDED.phone,
                       fuente='nomina', updated_at=NOW()
                   WHERE (user_profiles.display_name, user_profiles.department, user_profiles.title, user_profiles.office_location,
                          user_profiles.mobile, user_profiles.phone, user_profiles.fuente) IS DISTINCT FROM
                         (EXCLUDED.display_name, EXCLUDED.department, EXCLUDED.title, EXCLUDED.office_location, EXCLUDED.mobile, EXCLUDED.phone, 'nomina')""",
                    t["email"],
                    nombre_propio(t["nombre"]),
                    t["departamento"] or "",
                    t["cargo"] or "",
                    t["area"] or "",
                    (t["movil"] or "").strip(),
                    (t["extension"] or "").strip(),
                )
            j, origen = jefe_de(t)
            if not j:
                sin += 1
                await db.execute("DELETE FROM task_jefes WHERE email = $1", t["email"])
                continue
            await db.execute(
                """INSERT INTO task_jefes (email, jefe_email, jefe_nombre, cargo, departamento, origen, actualizado_en)
                                VALUES ($1,$2,$3,$4,$5,$6,NOW()) ON CONFLICT (email) DO UPDATE SET jefe_email=EXCLUDED.jefe_email,
                                jefe_nombre=EXCLUDED.jefe_nombre, cargo=EXCLUDED.cargo, departamento=EXCLUDED.departamento,
                                origen=EXCLUDED.origen, actualizado_en=NOW()""",
                t["email"],
                j["email"],
                j["nombre"],
                t["cargo"] or "",
                t["departamento"] or "",
                origen,
            )
            n += 1
            if t["departamento"] and t["email"] not in cruzados:
                await db.execute(
                    """INSERT INTO user_profiles (user_email, department, title) VALUES ($1,$2,$3)
                                    ON CONFLICT (user_email) DO UPDATE SET department = CASE WHEN COALESCE(user_profiles.department,'')='' THEN EXCLUDED.department ELSE user_profiles.department END,
                                    title = CASE WHEN COALESCE(user_profiles.title,'')='' THEN EXCLUDED.title ELSE user_profiles.title END""",
                    t["email"],
                    t["departamento"],
                    t["cargo"] or "",
                )
        # Foto de perfil: la de Raíces (usuarios.profile_picture) o la de nómina (trabajadores.foto_perfil) → GAL del correo
        nf = 0
        activos_inst = {
            e for e in activos if _es_institucional(e)
        } - cruzados  # sin foto ni datos ajenos
        con_foto = set()
        for u in usuarios_raices:
            pp = (u["profile_picture"] or "").strip()
            fp = (u["foto_perfil"] or "").strip()
            if pp.startswith("http"):
                url = pp
            elif pp:
                url = (
                    organizacion.url_intranet()
                    + "/static/"
                    + (pp if pp.startswith("uploads/") else "uploads/profiles/" + pp)
                )
            elif fp:
                url = organizacion.url_intranet() + "/static/" + fp
            else:
                continue
            # 05/11/2026: solo buzones institucionales de personal ACTIVO (antes también correos personales y salidos)
            for correo in {u["email"], u["email_inst"]}:
                if correo and correo in activos_inst:
                    await db.execute(
                        """INSERT INTO user_profiles (user_email, photo_url, fuente) VALUES ($1,$2,'nomina')
                           ON CONFLICT (user_email) DO UPDATE SET photo_url = EXCLUDED.photo_url, fuente = 'nomina', updated_at = NOW()
                           WHERE user_profiles.photo_url IS DISTINCT FROM EXCLUDED.photo_url""",
                        correo,
                        url,
                    )
                    nf += 1
                    con_foto.add(correo)
        # 05/11/2026: salidas y buzones que cambiaron de persona: lo que puso la nómina se limpia (el nombre vuelve
        # al del buzón, sin cargo ni foto). Las fotos propias (fuente <> 'nomina') no se tocan. Y si la persona sigue
        # activa pero ya no tiene foto en Raíces, se retira la foto de la intranet.
        limpiados = await db.fetch(
            """UPDATE user_profiles SET display_name = NULL, title = '', department = '', office_location = '', mobile = '',
                      phone = '', photo_url = '', fuente = NULL, updated_at = NOW()
               WHERE fuente = 'nomina' AND lower(user_email) <> ALL($1::text[]) RETURNING user_email""",
            sorted(activos_inst),
        )
        await db.execute(
            """UPDATE user_profiles SET photo_url = '', updated_at = NOW()
               WHERE fuente = 'nomina' AND lower(user_email) = ANY($1::text[]) AND lower(user_email) <> ALL($2::text[])
                 AND photo_url LIKE $3 || '%'""",
            sorted(activos_inst),
            sorted(con_foto),
            organizacion.url_intranet() + "/static/",
        )
        por_nombre = await nombres_por_coincidencia(db, trab)  # 06/11/2026
        # caché de nombres y fotos del webmail (avatar:<correo>): se renueva en el próximo uso
        try:
            import redis as _redis

            url_redis = next(
                (
                    l.split("=", 1)[1].strip()
                    for l in open(".env", encoding="utf-8")
                    if l.startswith("REDIS_URL=")
                ),
                "",
            )
            if url_redis:
                claves = [
                    f"avatar:{e}"
                    for e in activos_inst
                    | {x["user_email"].lower() for x in limpiados}
                    | por_nombre
                ]
                r = _redis.from_url(url_redis)
                for i in range(0, len(claves), 200):
                    r.delete(*claves[i : i + 200])
        except Exception as e:  # noqa: BLE001
            log.warning("no se pudo limpiar la caché de avatares: %s", e)
        # 05/11/2026: salida registrada por Talento Humano → cierre del buzón (ver salidas_buzon.py; simula hasta activar)
        try:
            from app.tareas import salidas_buzon

            salidas = await salidas_buzon.procesar(
                db, activos_inst, _dsn(), _es_institucional
            )
        except Exception as e:  # noqa: BLE001
            salidas = {"modo": "error", "candidatos": [], "cerrados": 0}
            log.error("cierre de buzones por salida: %s", e)
        nd = 0
        for d in deptos:
            j = por_id.get(d["jefe_departamento_id"])
            if inst(j):
                await db.execute(
                    """INSERT INTO task_escalamiento (departamento, jefe_email, dias, actualizado_por) VALUES ($1,$2,2,'nomina')
                                    ON CONFLICT (departamento) DO UPDATE SET jefe_email = EXCLUDED.jefe_email, actualizado_en = NOW()
                                    WHERE task_escalamiento.actualizado_por = 'nomina'""",
                    d["nombre"],
                    j["email"],
                )
                nd += 1
    await pool.close()
    import json

    json.dump(
        {
            **{u["email"]: u["full_name"].strip().title() for u in usuarios_raices},
            **{t["email"]: (t["nombre"] or "").strip().title() for t in trab},
        },
        open(RUTA_NOMBRES, "w", encoding="utf-8"),
        ensure_ascii=False,
    )
    log.info(
        "nómina: %s personas en el directorio, %s con jefe, %s sin resolver, %s departamentos, %s fotos replicadas, %s perfiles limpiados (salidas); buzones por salida: modo %s, %s candidatos %s, %s cerrados",
        len(trab),
        n,
        sin,
        nd,
        nf,
        len(limpiados),
        salidas["modo"],
        len(salidas["candidatos"]),
        salidas["candidatos"],
        salidas["cerrados"],
    )


if __name__ == "__main__":
    asyncio.run(main())
