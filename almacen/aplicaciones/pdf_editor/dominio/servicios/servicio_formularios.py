# -*- coding: utf-8 -*-
"""
Servicio de Dominio: Lógica de formularios PDF.
"""

from typing import Dict, Any, List, Optional
from ..entidades.formulario import Formulario, CampoFormulario, RespuestaFormulario
from ..value_objects.tipos_pdf import TipoCampoFormulario


class ServicioFormularios:
    """
    Servicio de dominio para lógica de formularios.
    """

    @staticmethod
    def evaluar_logica_condicional(
        formulario: Formulario,
        valores_actuales: Dict[str, Any]
    ) -> Dict[str, bool]:
        """
        Evalúa la lógica condicional para determinar visibilidad de campos.

        Args:
            formulario: Formulario con reglas de lógica condicional
            valores_actuales: Valores actuales del formulario

        Returns:
            Diccionario {nombre_campo: es_visible}
        """
        visibilidad = {campo.nombre: True for campo in formulario.campos}

        for nombre_campo, reglas in formulario.logica_condicional.items():
            if nombre_campo not in visibilidad:
                continue

            for regla in reglas if isinstance(reglas, list) else [reglas]:
                campo_condicion = regla.get('campo')
                operador = regla.get('operador', '==')
                valor_condicion = regla.get('valor')
                accion = regla.get('accion', 'mostrar')

                valor_actual = valores_actuales.get(campo_condicion)

                # Evaluar condición
                condicion_cumplida = False
                if operador == '==':
                    condicion_cumplida = valor_actual == valor_condicion
                elif operador == '!=':
                    condicion_cumplida = valor_actual != valor_condicion
                elif operador == 'contiene':
                    condicion_cumplida = valor_condicion in str(valor_actual or '')
                elif operador == 'vacio':
                    condicion_cumplida = not valor_actual
                elif operador == 'no_vacio':
                    condicion_cumplida = bool(valor_actual)

                # Aplicar acción
                if accion == 'mostrar':
                    visibilidad[nombre_campo] = condicion_cumplida
                elif accion == 'ocultar':
                    visibilidad[nombre_campo] = not condicion_cumplida

        return visibilidad

    @staticmethod
    def calcular_campos(
        formulario: Formulario,
        valores: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calcula los valores de campos calculados.

        Args:
            formulario: Formulario con campos calculados
            valores: Valores actuales del formulario

        Returns:
            Valores calculados
        """
        calculados = {}

        for campo in formulario.campos:
            if campo.tipo != TipoCampoFormulario.CALCULADO:
                continue

            formula = campo.propiedades.get('formula', '')
            if not formula:
                continue

            try:
                # Reemplazar nombres de campos por valores
                expresion = formula
                for nombre, valor in valores.items():
                    if isinstance(valor, (int, float)):
                        expresion = expresion.replace(f'{{{nombre}}}', str(valor))
                    elif isinstance(valor, str) and valor.isdigit():
                        expresion = expresion.replace(f'{{{nombre}}}', valor)
                    else:
                        expresion = expresion.replace(f'{{{nombre}}}', '0')

                # Evaluar expresión segura (solo operaciones matemáticas básicas)
                resultado = ServicioFormularios._evaluar_expresion_segura(expresion)
                calculados[campo.nombre] = resultado

            except Exception:
                calculados[campo.nombre] = None

        return calculados

    @staticmethod
    def _evaluar_expresion_segura(expresion: str) -> Optional[float]:
        """
        Evalúa una expresión matemática de forma segura.

        Solo permite números y operadores básicos (+, -, *, /).
        Usa ast.parse para validar y compilar sin eval() directo.
        """
        import re
        import ast
        import operator

        # Solo permitir caracteres válidos (números, operadores, paréntesis, espacios)
        if not re.match(r'^[\d\s\+\-\*\/\.\(\)]+$', expresion):
            return None

        try:
            # Parser seguro usando AST: recorre el árbol y solo permite operaciones matemáticas
            ops = {
                ast.Add: operator.add,
                ast.Sub: operator.sub,
                ast.Mult: operator.mul,
                ast.Div: operator.truediv,
                ast.USub: operator.neg,
                ast.UAdd: operator.pos,
            }

            def _eval_nodo(nodo):
                if isinstance(nodo, ast.Expression):
                    return _eval_nodo(nodo.body)
                elif isinstance(nodo, ast.Constant) and isinstance(nodo.value, (int, float)):
                    return nodo.value
                elif isinstance(nodo, ast.BinOp) and type(nodo.op) in ops:
                    return ops[type(nodo.op)](_eval_nodo(nodo.left), _eval_nodo(nodo.right))
                elif isinstance(nodo, ast.UnaryOp) and type(nodo.op) in ops:
                    return ops[type(nodo.op)](_eval_nodo(nodo.operand))
                else:
                    raise ValueError(f"Operación no permitida: {type(nodo).__name__}")

            tree = ast.parse(expresion, mode='eval')
            resultado = _eval_nodo(tree)
            return float(resultado)
        except Exception:
            return None

    @staticmethod
    def exportar_datos_csv(
        formulario: Formulario,
        respuestas: List[RespuestaFormulario]
    ) -> str:
        """
        Exporta las respuestas de un formulario a formato CSV.

        Args:
            formulario: Definición del formulario
            respuestas: Lista de respuestas

        Returns:
            Contenido CSV como string
        """
        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        # Encabezados
        encabezados = ['ID', 'Usuario', 'Fecha', 'Completado']
        encabezados.extend([campo.nombre for campo in formulario.campos])
        writer.writerow(encabezados)

        # Datos
        for respuesta in respuestas:
            fila = [
                respuesta.id,
                respuesta.usuario_id,
                respuesta.created_at.isoformat() if respuesta.created_at else '',
                'Sí' if respuesta.completado else 'No'
            ]
            for campo in formulario.campos:
                valor = respuesta.datos.get(campo.nombre, '')
                fila.append(str(valor) if valor is not None else '')
            writer.writerow(fila)

        return output.getvalue()

    @staticmethod
    def importar_datos_csv(
        formulario: Formulario,
        contenido_csv: str,
        usuario_id: int
    ) -> List[RespuestaFormulario]:
        """
        Importa datos desde CSV a respuestas de formulario.

        Args:
            formulario: Definición del formulario
            contenido_csv: Contenido CSV
            usuario_id: ID del usuario que importa

        Returns:
            Lista de respuestas creadas
        """
        import csv
        from io import StringIO

        respuestas = []
        reader = csv.DictReader(StringIO(contenido_csv))

        nombres_campos = {campo.nombre for campo in formulario.campos}

        for fila in reader:
            datos = {}
            for nombre, valor in fila.items():
                if nombre in nombres_campos:
                    datos[nombre] = valor

            respuesta = RespuestaFormulario(
                formulario_id=formulario.id,
                usuario_id=usuario_id,
                datos=datos,
                completado=True
            )
            respuestas.append(respuesta)

        return respuestas

    @staticmethod
    def validar_estructura_formulario(
        formulario: Formulario
    ) -> tuple[bool, List[str]]:
        """
        Valida la estructura completa de un formulario.

        Args:
            formulario: Formulario a validar

        Returns:
            Tupla (es_valido, lista_errores)
        """
        errores = []

        # Validar nombres únicos
        nombres = [campo.nombre for campo in formulario.campos]
        duplicados = set([n for n in nombres if nombres.count(n) > 1])
        if duplicados:
            errores.append(f"Nombres de campo duplicados: {', '.join(duplicados)}")

        # Validar referencias en lógica condicional
        for nombre_campo, reglas in formulario.logica_condicional.items():
            if nombre_campo not in nombres:
                errores.append(
                    f"Lógica condicional referencia campo inexistente: {nombre_campo}"
                )

            for regla in reglas if isinstance(reglas, list) else [reglas]:
                campo_condicion = regla.get('campo')
                if campo_condicion and campo_condicion not in nombres:
                    errores.append(
                        f"Condición referencia campo inexistente: {campo_condicion}"
                    )

        # Validar campos calculados
        for campo in formulario.campos:
            if campo.tipo == TipoCampoFormulario.CALCULADO:
                formula = campo.propiedades.get('formula', '')
                if not formula:
                    errores.append(f"Campo calculado sin fórmula: {campo.nombre}")

        return len(errores) == 0, errores
