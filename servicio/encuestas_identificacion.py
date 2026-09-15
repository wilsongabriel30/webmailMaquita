# -*- coding: utf-8 -*-
"""
Formularios del Almacén — cédula y RUC de Ecuador
=================================================
La validación «Identificación» de las respuestas cortas: que lo escrito sea una
cédula o un RUC que puede existir. Se separa de `encuestas_validacion.py`
porque son algoritmos con sus propias reglas y su propia historia, y conviene
poder leerlos y probarlos solos.

`encuesta-validacion.js` repite estas mismas reglas en el navegador. Si se
cambia una, se cambia en los dos sitios.

LAS REGLAS SE AJUSTARON CON DATOS REALES (10/09/2026)
-----------------------------------------------------
Se pasaron por aquí 205 cédulas de nómina y unas 22.700 identificaciones de
proveedores, clientes y asientos contables. Dos reglas de manual rechazaban
documentos que existen:

- «El tercer dígito de la cédula es menor que 6». Ya no: el Registro Civil
  emite cédulas 096… y 176… (Guayas y Pichincha agotaron la numeración). Se
  encontraron 16 con tercer dígito 6 o más y 15 cumplen el dígito verificador.
  Se comprueban la provincia y el dígito verificador, no el tercer dígito.
- «El RUC de una sociedad privada cumple el módulo 11». Ya no siempre: el SRI
  emite RUC de sociedades que no lo cumplen. De unos 2.470 RUC de sociedades
  privadas reales, 214 (8,7 %) fallaban. En las sociedades privadas se
  comprueba la estructura (provincia, tercer dígito 9, establecimiento), no
  el dígito.

Por lo mismo, un RUC 096…001 o 176…001 NO es de una entidad pública: es el de
una persona con cédula nueva. Por eso un RUC vale si CUALQUIERA de sus
lecturas posibles es correcta, en vez de decidir el tipo por el tercer dígito.

Autoría: Equipo de Tecnología Maquita — 2026-09-10
"""
import re

# Espacios, guiones y puntos se quitan: «1712345678», «171234567-8» y
# «1712 345 678» son la misma cédula y la gente las escribe de las tres formas.
_SEPARADORES = re.compile(r'[\s.\-]')
_DIEZ = re.compile(r'[0-9]{10}')
_TRECE = re.compile(r'[0-9]{13}')

_COEF_PUBLICA = (3, 2, 7, 6, 5, 4, 3, 2)
_COEF_PRIVADA = (4, 3, 2, 7, 6, 5, 4, 3, 2)


def normalizar(texto):
    return _SEPARADORES.sub('', str(texto or ''))


def _provincia(digitos):
    """01 a 24 son las provincias; 30, ecuatorianos registrados en el exterior."""
    codigo = int(digitos[:2])
    return 1 <= codigo <= 24 or codigo == 30


def _modulo10(digitos):
    suma = 0
    for posicion, cifra in enumerate(digitos[:9]):
        valor = int(cifra) * (2 if posicion % 2 == 0 else 1)
        suma += valor - 9 if valor > 9 else valor
    return (10 - suma % 10) % 10 == int(digitos[9])


def _modulo11(digitos, coeficientes):
    suma = sum(int(c) * k for c, k in zip(digitos, coeficientes))
    resto = 11 - suma % 11
    if resto == 11:
        resto = 0
    return resto != 10 and resto == int(digitos[len(coeficientes)])


def es_cedula(texto):
    digitos = normalizar(texto)
    return bool(_DIEZ.fullmatch(digitos)) and _provincia(digitos) \
        and _modulo10(digitos)


def es_ruc(texto):
    digitos = normalizar(texto)
    if not _TRECE.fullmatch(digitos) or not _provincia(digitos):
        return False
    # Persona natural: su cédula y un establecimiento (001, 002…).
    if digitos[10:] != '000' and _modulo10(digitos[:10]):
        return True
    # Entidad pública: tercer dígito 6, verificador en la novena posición y
    # cuatro dígitos de establecimiento.
    if digitos[2] == '6' and digitos[9:] != '0000' \
            and _modulo11(digitos, _COEF_PUBLICA):
        return True
    # Sociedad privada: tercer dígito 9 y establecimiento. Sin módulo 11: ver
    # la cabecera.
    return digitos[2] == '9' and digitos[10:] != '000'


def es_cedula_o_ruc(texto):
    return es_cedula(texto) or es_ruc(texto)
