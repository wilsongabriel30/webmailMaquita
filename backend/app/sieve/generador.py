"""Genera el script Sieve «webmail» a partir de la respuesta automática y las reglas.

Decisiones (09/11/2026, revisión independiente de las reglas de correo):
- «De/Para es exactamente» y «coincide con patrón» usan el test `address`, que compara solo
  la dirección (el encabezado From casi siempre es «Nombre <dirección>», así que `header :is`
  no coincidía nunca). «Contiene» sigue con `header :contains`, de modo que «contiene
  example.org» sirve como filtro por dominio. El asunto siempre va con `header`.
- Toda cadena pasa por `escapado.escapar` (barra invertida y comilla).
- «Mover» usa `fileinto :create` (la carpeta se crea si no existe).
- «Marcar» usa `addflag` (añade la bandera) y no `setflag` (que borraba las demás).

Reglas avanzadas (10/11/2026):
- Varias condiciones: `if allof (t1, t2) {` o `if anyof (…) {`; una sola: `if t1 {`.
- Negación con `not`; cuerpo con `body :contains`; tamaño con `size :over 500K`; encabezado a
  elegir con `header :contains "X-Nombre"`; expresiones regulares con `:regex`; «Para o Cc»
  con la lista `["To", "Cc"]`.
- Varias acciones por regla; «copiar» es `fileinto :copy`, «reenviar copia» `redirect :copy`,
  «marcar como leído» `addflag "\\Seen"`. `stop;` solo si la regla lo pide (por defecto sí,
  salvo que solo marque).
- Regla desactivada: `if allof (false, …) {`: el servidor la salta y el analizador la relee.
"""

from typing import Optional

from app.sieve import analizador
from app.sieve.escapado import escapar, sanear
from app.sieve.modelos import (
    FilterAction,
    FilterCondition,
    FilterRule,
    VacationSettings,
    bandera_canonica,
    validar_correo_reenvio,
)

MARCA_VACACIONES = "# --- VACATION ---"
MARCA_REGLAS = "# --- FILTERS ---"
VACACIONES_APAGADAS = "# vacation disabled"

# Encabezados por campo; «recipients» es una lista (Para o Cc).
ENCABEZADOS = {
    "from": ["From"],
    "to": ["To"],
    "cc": ["Cc"],
    "recipients": ["To", "Cc"],
    "subject": ["Subject"],
    "list": ["List-Id"],
}
_COMPARADOR = {
    "contains": ":contains",
    "is": ":is",
    "matches": ":matches",
    "regex": ":regex",
}


def _lista_sieve(valores: list[str]) -> str:
    if len(valores) == 1:
        return f'"{escapar(valores[0])}"'
    return "[" + ", ".join(f'"{escapar(v)}"' for v in valores) + "]"


def _operador_base(operator: str) -> tuple[bool, str]:
    """(negado, operador sin el «not_»)."""
    if operator.startswith("not_"):
        return True, operator[4:]
    return False, operator


def _test_condicion(cond: FilterCondition) -> str:
    """El test Sieve de una condición."""
    negado, op = _operador_base(cond.operator)
    if cond.field == "size":
        test = f"size :{op} {int(cond.value)}K"
    elif cond.field == "body":
        test = f'body {_COMPARADOR[op]} "{escapar(cond.value)}"'
    else:
        encabezados = ENCABEZADOS.get(cond.field) or [cond.header or ""]
        lista = _lista_sieve(encabezados)
        if op == "exists":
            test = f"exists {lista}"
        elif cond.field in ("from", "to", "cc", "recipients") and op in (
            "is",
            "matches",
        ):
            # Compara solo la dirección, no «Nombre <dirección>».
            test = f'address {_COMPARADOR[op]} {lista} "{escapar(cond.value)}"'
        else:
            test = f'header {_COMPARADOR[op]} {lista} "{escapar(cond.value)}"'
    return f"not {test}" if negado else test


def _requires_condicion(cond: FilterCondition, reqs: set[str]) -> None:
    _, op = _operador_base(cond.operator)
    if cond.field == "body":
        reqs.add("body")
    if op == "regex":
        reqs.add("regex")
    # «address», «header», «size», «exists» y «not» son del núcleo de Sieve.


def _requires_accion(accion: FilterAction, reqs: set[str]) -> None:
    if accion.type in ("move", "copy"):
        reqs.update({"fileinto", "mailbox"})
    if accion.type in ("copy", "forward_copy"):
        reqs.add("copy")
    if accion.type in ("flag", "read"):
        reqs.add("imap4flags")
    # «redirect», «discard» y «stop» son del núcleo: Pigeonhole (sievec) rechaza declararlos.


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
        for c in f.conditions:
            _requires_condicion(c, reqs)
        for a in f.actions:
            _requires_accion(a, reqs)
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


def _accion(accion: FilterAction) -> str:
    tipo = accion.type
    if tipo == "move":
        return f'fileinto :create "{escapar(accion.value or "INBOX")}";'
    if tipo == "copy":
        return f'fileinto :copy :create "{escapar(accion.value or "INBOX")}";'
    if tipo == "flag":
        return f'addflag "{escapar(bandera_canonica(accion.value))}";'
    if tipo == "read":
        return 'addflag "\\\\Seen";'
    if tipo == "delete":
        return "discard;"
    if tipo == "forward":
        return f'redirect "{escapar(validar_correo_reenvio(accion.value or ""))}";'
    if tipo == "forward_copy":
        return (
            f'redirect :copy "{escapar(validar_correo_reenvio(accion.value or ""))}";'
        )
    raise ValueError(f"Acción desconocida: {tipo}")


def _acciones(regla: FilterRule) -> list[str]:
    """Las líneas de acción de una regla (ya con sangría)."""
    lineas = [f"    {_accion(a)}" for a in regla.actions]
    if regla.stop:
        lineas.append("    stop;")
    return lineas


def regla_a_sieve(indice: int, regla: FilterRule) -> list[str]:
    """Las líneas Sieve de una regla: comentario con el nombre, condiciones y acciones."""
    tests = [_test_condicion(c) for c in regla.conditions]
    cuerpo = tests[0] if len(tests) == 1 else f"{regla.match} ({', '.join(tests)})"
    if not regla.enabled:
        # `false` dentro de un allof: la regla nunca se cumple pero sigue en el script.
        cuerpo = f"allof (false, {cuerpo})"
    lineas = [f"# filter[{indice}]: {escapar(regla.name)}", f"if {cuerpo} {{"]
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


def _normalizar_accion(a: FilterAction) -> dict:
    tipo = a.type
    if tipo in ("move", "copy"):
        valor = sanear(a.value or "INBOX")
    elif tipo == "flag":
        valor = bandera_canonica(a.value)
    elif tipo in ("forward", "forward_copy"):
        valor = sanear(a.value or "")
    else:
        valor = None
    return {"type": tipo, "value": valor}


def _normalizar(regla: FilterRule) -> FilterRule:
    """Cómo queda una regla tras pasar por el script (saneada y con valores canónicos)."""
    condiciones = []
    for c in regla.conditions:
        datos = c.model_dump()
        datos["value"] = sanear(c.value)
        condiciones.append(datos)
    # Con una sola condición el script no lleva allof/anyof y se relee como «allof».
    match = regla.match if len(regla.conditions) > 1 else "allof"
    return FilterRule(
        name=sanear(regla.name),
        match=match,
        conditions=condiciones,
        actions=[_normalizar_accion(a) for a in regla.actions],
        stop=regla.stop,
        enabled=regla.enabled,
    )
