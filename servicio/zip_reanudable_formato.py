"""
Formato del ZIP reanudable (Drive Maquita): bytes de cada pieza y su posición.

Por qué se escribe a mano y no con `zipfile`: para poder REANUDAR una descarga
hay que saber, antes de enviar nada, cuánto mide el ZIP y en qué byte cae cada
archivo. Eso solo es posible si nada se comprime (método «almacenado») y si el
tamaño de cada cabecera no depende del contenido. Aquí todo se calcula a partir
del nombre, el tamaño y la fecha de cada entrada.

La suma de verificación (CRC) de un archivo de disco no se conoce hasta leerlo:
va DESPUÉS de sus datos (descriptor de datos) y en el directorio central, que
está al final. Las entradas cuyo CRC ya se sabe (copias propias, textos en
memoria, carpetas) lo llevan en la cabecera y no usan descriptor.

ZIP64 solo donde hace falta (archivo o posición de 4 GB o más, o más de 65.535
entradas): así los ZIP normales siguen abriendo en cualquier programa.
"""
import struct
import time

LIMITE32 = 0xFFFFFFFF
LIMITE16 = 0xFFFF

_UTF8 = 0x800
_DESCRIPTOR = 0x08
_ATRIB_ARCHIVO = 0o100644 << 16
_ATRIB_CARPETA = (0o40755 << 16) | 0x10


class Entrada:
    """Una entrada del ZIP. tipo: 'a' archivo en disco, 'm' contenido en
    memoria, 'd' carpeta vacía. `crc` es None mientras no se conozca."""

    __slots__ = ('nombre', 'origen', 'tipo', 'tam', 'fecha', 'crc', 'memoria',
                 'propia', 'desplazamiento', 'nombre_b')

    def __init__(self, nombre, tipo, tam, fecha, origen=None, crc=None,
                 memoria=None, propia=False):
        self.nombre = nombre
        self.tipo = tipo
        self.tam = tam
        self.fecha = fecha
        self.origen = origen
        self.crc = crc
        self.memoria = memoria
        self.propia = propia
        self.desplazamiento = 0
        self.nombre_b = nombre.encode('utf-8')

    @property
    def grande(self):
        return self.tam >= LIMITE32

    @property
    def con_descriptor(self):
        return self.crc is None

    def _banderas(self):
        banderas = _DESCRIPTOR if self.con_descriptor else 0
        try:
            self.nombre.encode('ascii')
        except UnicodeEncodeError:
            banderas |= _UTF8
        return banderas

    def _fecha_dos(self):
        t = time.localtime(self.fecha)
        if t.tm_year < 1980:
            return 0, (1 << 5) | 1
        anio = min(t.tm_year, 2107)
        return ((t.tm_hour << 11) | (t.tm_min << 5) | (t.tm_sec // 2),
                ((anio - 1980) << 9) | (t.tm_mon << 5) | t.tm_mday)

    # ── piezas ───────────────────────────────────────────────────────────
    def cabecera(self):
        hora, fecha = self._fecha_dos()
        if self.con_descriptor:
            crc, tam, extra_tam = 0, 0, 0
        else:
            crc, tam, extra_tam = self.crc, self.tam, self.tam
        extra = b''
        if self.grande:
            extra = struct.pack('<HHQQ', 1, 16, extra_tam, extra_tam)
            tam = LIMITE32
        return struct.pack('<4sHHHHHLLLHH', b'PK\x03\x04', 45 if self.grande else 20,
                           self._banderas(), 0, hora, fecha, crc, tam, tam,
                           len(self.nombre_b), len(extra)) + self.nombre_b + extra

    def largo_cabecera(self):
        return 30 + len(self.nombre_b) + (20 if self.grande else 0)

    def descriptor(self, crc):
        if not self.con_descriptor:
            return b''
        return struct.pack('<4sLQQ' if self.grande else '<4sLLL',
                           b'PK\x07\x08', crc, self.tam, self.tam)

    def largo_descriptor(self):
        if not self.con_descriptor:
            return 0
        return 24 if self.grande else 16

    def largo_total(self):
        return self.largo_cabecera() + self.tam + self.largo_descriptor()

    def _extra_central(self):
        campos = []
        if self.grande:
            campos += [self.tam, self.tam]
        if self.desplazamiento >= LIMITE32:
            campos.append(self.desplazamiento)
        return campos

    def central(self, crc):
        hora, fecha = self._fecha_dos()
        campos = self._extra_central()
        extra = struct.pack('<HH' + 'Q' * len(campos), 1, 8 * len(campos), *campos) if campos else b''
        tam = LIMITE32 if self.grande else self.tam
        version = 45 if campos else 20
        return struct.pack(
            '<4sBBHHHHHLLLHHHHHLL', b'PK\x01\x02', version, 3, version,
            self._banderas(), 0, hora, fecha, crc, tam, tam,
            len(self.nombre_b), len(extra), 0, 0, 0,
            _ATRIB_CARPETA if self.tipo == 'd' else _ATRIB_ARCHIVO,
            min(self.desplazamiento, LIMITE32)) + self.nombre_b + extra

    def largo_central(self):
        campos = len(self._extra_central())
        return 46 + len(self.nombre_b) + (4 + 8 * campos if campos else 0)


def distribuir(entradas):
    """Asigna a cada entrada su posición. Devuelve (inicio del directorio
    central, su tamaño, tamaño total del ZIP)."""
    posicion = 0
    for entrada in entradas:
        entrada.desplazamiento = posicion
        posicion += entrada.largo_total()
    central = sum(entrada.largo_central() for entrada in entradas)
    return posicion, central, posicion + central + len(cierre(len(entradas), posicion, central))


def cierre(cantidad, inicio_central, tam_central):
    """Registros finales del ZIP (con los de ZIP64 si hacen falta)."""
    zip64 = b''
    if cantidad > LIMITE16 or inicio_central >= LIMITE32 or tam_central >= LIMITE32:
        zip64 = struct.pack('<4sQHHLLQQQQ', b'PK\x06\x06', 44, 45, 45, 0, 0,
                            cantidad, cantidad, tam_central, inicio_central)
        zip64 += struct.pack('<4sLQL', b'PK\x06\x07', 0, inicio_central + tam_central, 1)
    return zip64 + struct.pack('<4sHHHHLLH', b'PK\x05\x06', 0, 0,
                               min(cantidad, LIMITE16), min(cantidad, LIMITE16),
                               min(tam_central, LIMITE32), min(inicio_central, LIMITE32), 0)
