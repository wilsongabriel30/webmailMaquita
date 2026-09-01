"""Conector de datos del Drive Maquita para el motor de BI.

Lee un archivo tabular (`.xlsx`/`.xls`/`.csv`) guardado en el Drive y lo entrega como
`pandas.DataFrame`, para que el motor (`motor_consultas`, `motor_visualizacion`)
genere tableros a partir de él — igual que el conector de ODK, pero sobre archivos.

Diseño desacoplado: recibe una función `leer_bytes(ruta) -> bytes`. Así el motor no
depende de ningún cliente concreto del Drive; en producción se le pasa un lector que
llama a la API del Drive con el token del usuario, y en pruebas uno que devuelve bytes
en memoria.
"""
import io
from typing import Any, Dict, Optional

import pandas as pd

from .motor_datos import IConectorDatos, DatasetSchema, SchemaCampo


class ConectorDrive(IConectorDatos):
    """Fuente de datos: un archivo tabular del Drive. `config = {'ruta': '/.../datos.xlsx'}`."""

    def __init__(self, leer_bytes):
        # leer_bytes: Callable[[str], bytes] — devuelve el contenido del archivo del Drive.
        self._leer_bytes = leer_bytes

    def _cargar(self, config: Dict[str, Any]) -> pd.DataFrame:
        ruta = (config or {}).get("ruta", "")
        if not ruta:
            raise ValueError("Falta 'ruta' del archivo en el Drive")
        datos = self._leer_bytes(ruta)
        buffer = io.BytesIO(datos)
        low = ruta.lower()
        if low.endswith((".xlsx", ".xls")):
            return pd.read_excel(buffer)
        if low.endswith((".csv", ".txt")):
            return pd.read_csv(buffer)
        raise ValueError("Formato no soportado (usa .xlsx, .xls o .csv): %s" % ruta)

    def obtener_datos(self, config: Dict[str, Any], limit: Optional[int] = None) -> pd.DataFrame:
        df = self._cargar(config)
        return df.head(limit) if limit else df

    def obtener_esquema(self, config: Dict[str, Any]) -> DatasetSchema:
        df = self._cargar(config).head(500)
        campos = []
        for columna in df.columns:
            campos.append(SchemaCampo(
                nombre=str(columna),
                tipo=self._inferir_tipo(df[columna]),
                descripcion="Columna del archivo del Drive: %s" % columna,
            ))
        return DatasetSchema(campos)

    def test_conexion(self, config: Dict[str, Any]) -> bool:
        try:
            self._cargar(config)
            return True
        except Exception:
            return False

    @staticmethod
    def _inferir_tipo(serie: pd.Series) -> str:
        if pd.api.types.is_numeric_dtype(serie):
            return "numerico"
        if pd.api.types.is_datetime64_any_dtype(serie):
            return "fecha"
        return "texto"
