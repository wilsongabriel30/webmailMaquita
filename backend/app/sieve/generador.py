"""Genera el script Sieve «webmail» a partir de la respuesta automática y las reglas.

Decisiones (09/11/2026, revisión independiente de las reglas de correo):
- «De/Para es exactamente» y «coincide con patrón» usan el test `address`, que compara solo
  la dirección (el encabezado From casi siempre es «Nombre <dirección>», así que `header :is`
  no coincidía nunca). «Contiene» sigue con `header :contains`, de modo que «contiene
  example.org» sirve como filtro por dominio. El asunto siempre va con `header`.
- Toda cadena pasa por `escapado.escapar` (barra invertida y comilla).
- «Mover» usa `fileinto :create` (la carpeta se crea si no existe) y, como «eliminar» y
  «reenviar», termina con `stop;`: la primera regla que mueve, elimina o reenvía detiene las
  siguientes y evita copias duplicadas del mismo correo. «Marcar» no detiene nada.
- «Marcar» usa `addflag` (añade la bandera) y no `setflag` (que borraba las demás).
"""

from typing import Optional

from app.sieve import analizador
from app.sieve.escapado import escapar, sanear
from app.sieve.modelos import (
    FilterRule,
    VacationSettings,
    bandera_canonica,
    validar_correo_reenvio,
)

MARCA_VACACIONES = "# --- VACATION ---"
MARCA_REGLAS = "# --- FILTERS ---"
VACACIONES_APAGADAS = "# vacation disabled"

_ENCABEZADO = {"from": "From", "to": "To", "subject": "Subject"}
_COMPARADOR = {"contains": ":contains", "is": ":is", "matches": ":matches"}


def _test_condicion(field: str, operator: str) -> str:
    """`address` para dirección exacta o patrón en De/Para; `header` en los demás casos."""
    if field in ("from", "to") and operator in ("is", "matches"):
        return "address"
    return "header"


def _build_requires(
    vacation: Optional[VacationSettings], filters: list[FilterRule]
) -> list[str]:
    """Las extensiones que declara el `require`, ordenadas."""
    reqs: set[str] = set()
    if vacation and vacation.enabled:
        reqs.add("vacation")
        if vacation.start_date or vacation.end_date:
            reqs.update({"date", "relational"})
    for f in filters:
        if f.action.type == "move":
            reqs.update({"fileinto", "mailbox"})
        elif f.action.type == "flag":
            reqs.add("imap4flags")
        # «address», «header», «redirect», «discard» y «stop» son del núcleo de Sieve:
        # Pigeonhole (sievec) rechaza declararlos en «require» (comprobado 09/11/2026).
    return sorted(reqs)


def _bloque_vacaciones(vacation: Optional[VacationSettings]) -> list[str]:
    if not (vacation and vacation.enabled):
        return [VACACIONES_APAGADAS]
    orden = (
        f'vacation :days 7 :subject "{escapar(vacation.subject)}" '
        f'"{escapar(vacation.body)}";'
    )
    fechas: list[str] = []
    if vacation.start_date:
        fechas.append(
            f'currentdate :value "ge" "date" "{escapar(vacation.start_date)}"'
        )
    if vacation.end_date:
        fechas.append(f'currentdate :value "le" "date" "{escapar(vacation.end_date)}"')
    if not fechas:
        return [orden]
    return [f"if allof ({', '.join(fechas)}) {{", f"    {orden}", "}"]


def _acciones(regla: FilterRule) -> list[str]:
    """Las líneas de acción de una regla (ya con sangría)."""
    tipo = regla.action.type
    if tipo == "move":
        carpeta = escapar(regla.action.value or "INBOX")
        return [f'    fileinto :create "{carpeta}";', "    stop;"]
    if tipo == "flag":
        return [f'    addflag "{escapar(bandera_canonica(regla.action.value))}";']
    if tipo == "delete":
        return ["    discard;", "    stop;"]
    if tipo == "forward":
        direccion = validar_correo_reenvio(regla.action.value or "")
        return [f'    redirect "{escapar(direccion)}";', "    stop;"]
    raise ValueError(f"Acción desconocida: {tipo}")


def regla_a_sieve(indice: int, regla: FilterRule) -> list[str]:
    """Las líneas Sieve de una regla: comentario con el nombre, condición y acciones."""
    campo = regla.condition.field
    operador = regla.condition.operator
    test = _test_condicion(campo, operador)
    encabezado = _ENCABEZADO.get(campo, campo)
    comparador = _COMPARADOR.get(operador, ":contains")
    lineas = [f"# filter[{indice}]: {escapar(regla.name)}"]
    lineas.append(
        f'if {test} {comparador} "{encabezado}" "{escapar(regla.condition.value)}" {{'
    )
    lineas.extend(_acciones(regla))
    lineas.append("}")
    return lineas


def generate_sieve_script(
    vacation: Optional[VacationSettings], filters: list[FilterRule]
) -> str:
    """El script completo: `require`, bloque de vacaciones y bloque de reglas."""
    partes: list[str] = []
    requires = _build_requires(vacation, filters)
    if requires:
        partes.append("require [" + ", ".join(f'"{r}"' for r in requires) + "];")
    partes.append("")
    partes.append(MARCA_VACACIONES)
    partes.extend(_bloque_vacaciones(vacation))
    partes.append("")
    partes.append(MARCA_REGLAS)
    for indice, regla in enumerate(filters):
        partes.extend(regla_a_sieve(indice, regla))
    partes.append("")
    return "\n".join(partes)


def comprobar_relectura(
    script: str, vacation: Optional[VacationSettings], filters: list[FilterRule]
) -> None:
    """Garantiza que lo generado se vuelve a leer igual antes de subirlo al servidor.

    Si una regla o la respuesta automática se perdieran al releer, el siguiente guardado las
    borraría en silencio: mejor negarse a guardar y avisar. Lanza ValueError con el motivo.
    """
    releidas = analizador.parse_filters_from_script(script)
    if len(releidas) != len(filters):
        raise ValueError(
            f"se generaron {len(filters)} reglas pero solo se releen {len(releidas)}"
        )
    for esperada, leida in zip(filters, releidas):
        if _normalizar(esperada) != leida:
            raise ValueError(f"la regla «{esperada.name}» no se relee igual")
    esperada_vac = vacation if vacation and vacation.enabled else None
    leida_vac = analizador.parse_vacation_from_script(script)
    if bool(esperada_vac) != leida_vac.enabled:
        raise ValueError("la respuesta automática no se relee igual")
    if esperada_vac and (
        leida_vac.subject != esperada_vac.subject.strip()
        or leida_vac.body != esperada_vac.body.strip()
    ):
        raise ValueError("el texto de la respuesta automática no se relee igual")


def _normalizar(regla: FilterRule) -> FilterRule:
    """Cómo queda una regla tras pasar por el script (saneada y con valores canónicos)."""
    datos = regla.model_dump()
    datos["name"] = sanear(regla.name)
    datos["condition"]["value"] = sanear(regla.condition.value)
    tipo = regla.action.type
    if tipo == "move":
        datos["action"]["value"] = sanear(regla.action.value or "INBOX")
    elif tipo == "flag":
        datos["action"]["value"] = bandera_canonica(regla.action.value)
    elif tipo == "delete":
        datos["action"]["value"] = None
    elif tipo == "forward":
        datos["action"]["value"] = sanear(regla.action.value or "")
    return FilterRule(**datos)
