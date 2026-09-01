"""Generación automática de tableros a partir de un DataFrame, usando el motor de BI.

Dado un conjunto de datos (por ejemplo un archivo del Drive), detecta columnas
categóricas y numéricas y arma un tablero: unos KPIs de resumen y unos rankings
(categoría × medida) listos para dibujar con Chart.js en el navegador.
"""
from typing import Any, Dict, List

import pandas as pd

from .motor_visualizacion import MotorVisualizacion, TipoChart


def _clasificar(df: pd.DataFrame):
    numericas = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    categoricas = [c for c in df.columns if c not in numericas]
    return categoricas, numericas


def generar_tableros(df: pd.DataFrame, max_graficos: int = 3) -> List[Dict[str, Any]]:
    """Devuelve una lista de tableros: uno de KPIs y varios gráficos (Chart.js)."""
    categoricas, numericas = _clasificar(df)
    mv = MotorVisualizacion()
    tableros: List[Dict[str, Any]] = []

    # 1) KPIs de resumen: número de registros + suma de las primeras numéricas
    kpis = [{"titulo": "Registros", "valor": int(len(df))}]
    for col in numericas[:3]:
        kpis.append({"titulo": "Suma de %s" % col, "valor": round(float(df[col].sum()), 2)})
    tableros.append({"tipo": "kpi", "titulo": "Resumen", "kpis": kpis})

    # 2) Rankings: cada categórica (hasta el tope) contra la primera medida numérica
    if numericas and categoricas:
        medida = numericas[0]
        for categoria in categoricas[:max_graficos]:
            try:
                # Agregación con pandas (ranking Top 10 por categoría).
                agrupado = (
                    df.groupby(categoria)[medida].sum()
                    .sort_values(ascending=False).head(10).reset_index()
                )
                resultado = {"exitosa": True, "datos": agrupado,
                             "consulta": "ranking_%s" % categoria}
                viz = mv.crear_desde_consulta(resultado, TipoChart.BARRA)
                tableros.append({
                    "tipo": "chart",
                    "titulo": "%s por %s" % (medida, categoria),
                    "chartjs": viz.to_chartjs(),
                })
            except Exception:
                continue

    return tableros
