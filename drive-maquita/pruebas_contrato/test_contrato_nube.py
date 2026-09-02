# -*- coding: utf-8 -*-
"""
PRUEBAS DE CONTRATO — API de la Nube (/api/nextcloud)
======================================================
Verifican que la API responde EXACTAMENTE lo que el explorador web espera.

Hoy corren contra el sistema actual (FARO + Nextcloud): verde = el contrato
queda congelado como especificación. Cuando exista el Almacén Maquita, la
MISMA suite debe pasar verde contra él — esa es la definición de "listo".

Uso:      bash correr.sh   (o: venv/bin/python3 -m unittest desde /home/sistemas/Maquita)
Usuario:  master_pruebas (id 54, cuenta Nube "pruebas") — JAMÁS usar cuentas reales.
Autoría:  Equipo de Tecnología Maquita — 2026-07-03
"""
import io
import os
import sys
import unittest

# ¿Contra qué motor corre la suite? (la MISMA suite valida ambos)
#   faro    → sistema actual (FARO + Nextcloud)  [por defecto]
#   almacen → Almacén Maquita (Fase 1)
OBJETIVO = os.getenv('OBJETIVO_CONTRATO', 'faro')

# La app de FARO vive aquí; las pruebas se ejecutan con su venv y su código
sys.path.insert(0, '/home/sistemas/Maquita')

USUARIO_PRUEBAS_ID = 54                      # master_pruebas (Nube activa)
CARPETA = '/__contrato_fase0__'              # carpeta de trabajo, se limpia al inicio y al final
CONTENIDO = b'contrato de la nube maquita - archivo de prueba fase 0\n' * 10

# Campos que el frontend usa de cada item (ArchivoResponseDTO.to_dict).
# Si el Almacén no devuelve alguno, el explorador se rompe: son EL contrato.
CAMPOS_ITEM = {
    'id', 'nombre', 'ruta', 'es_carpeta', 'tipo', 'extension',
    'tamano_bytes', 'tamano_humano', 'mime_type', 'icono',
    'es_favorito', 'es_compartido', 'es_editable',
}


class PruebasContratoNube(unittest.TestCase):
    """Flujo completo de un usuario sobre la API: crear, subir, listar, descargar,
    renombrar, copiar, mover, compartir, buscar, cuota y papelera."""

    @classmethod
    def setUpClass(cls):
        """Levanta el motor elegido en modo prueba y abre sesión del usuario de pruebas."""
        if OBJETIVO == 'almacen':
            sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
            from app_almacen import crear_app_almacen
            cls.app = crear_app_almacen()
        else:
            from app import crear_aplicacion
            cls.app = crear_aplicacion()
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False   # solo en pruebas: sin token CSRF
        cls.cliente = cls.app.test_client()

        # Sesión autenticada (flask-login) del usuario de pruebas
        with cls.cliente.session_transaction() as sesion:
            sesion['_user_id'] = str(USUARIO_PRUEBAS_ID)
            sesion['_fresh'] = True
            sesion['usuario_id'] = USUARIO_PRUEBAS_ID

        cls._limpiar()   # por si una corrida anterior quedó a medias

    @classmethod
    def tearDownClass(cls):
        """Deja la cuenta de pruebas como estaba."""
        cls._limpiar()

    @classmethod
    def _limpiar(cls):
        """Borra la carpeta de trabajo (ignora errores: puede no existir)."""
        cls.cliente.delete(f'/api/nextcloud/archivos?ruta={CARPETA}')
        cls.cliente.delete(f'/api/nextcloud/archivos?ruta={CARPETA}_movida')

    # ── utilitario ──
    def _json_ok(self, resp, contexto, codigos=(200, 201)):
        """Exige HTTP de éxito (200 o 201, según el contrato real) + success=True.
        CONTRATO: crear carpeta, subir archivo y compartir devuelven 201 (creado)."""
        self.assertIn(resp.status_code, codigos,
                      f'{contexto}: HTTP {resp.status_code} — {resp.get_data(as_text=True)[:200]}')
        datos = resp.get_json()
        self.assertIsNotNone(datos, f'{contexto}: la respuesta no es JSON')
        self.assertTrue(datos.get('success'), f'{contexto}: success != true — {str(datos)[:200]}')
        return datos

    # ═══════════════ 1. Salud y sesión ═══════════════
    def test_01_status(self):
        """El motor reporta estado y la sesión de pruebas es válida."""
        self._json_ok(self.cliente.get('/api/nextcloud/status'), 'status')

    # ═══════════════ 2. Carpetas ═══════════════
    def test_02_crear_carpeta(self):
        """POST /carpetas crea una carpeta en la raíz."""
        datos = self._json_ok(self.cliente.post(
            '/api/nextcloud/carpetas',
            json={'nombre': CARPETA.strip('/'), 'ruta': '/'}
        ), 'crear carpeta')
        self.assertIn('carpeta', datos)

    def test_03_listar_raiz_estructura(self):
        """GET /archivos devuelve la estructura completa que el explorador consume."""
        datos = self._json_ok(self.cliente.get('/api/nextcloud/archivos?ruta=/'), 'listar raíz')
        for clave in ('ruta_actual', 'breadcrumb', 'carpetas', 'archivos',
                      'total_carpetas', 'total_archivos'):
            self.assertIn(clave, datos, f'listar: falta la clave "{clave}"')
        nombres = [c['nombre'] for c in datos['carpetas']]
        self.assertIn(CARPETA.strip('/'), nombres, 'la carpeta creada no aparece al listar')

    # ═══════════════ 3. Subir y listar item ═══════════════
    def test_04_subir_archivo(self):
        """POST /archivos sube un archivo multipart a la carpeta de trabajo."""
        self._json_ok(self.cliente.post(
            '/api/nextcloud/archivos',
            data={'archivo': (io.BytesIO(CONTENIDO), 'contrato.txt'), 'carpeta': CARPETA},
            content_type='multipart/form-data'
        ), 'subir archivo')

    def test_05_item_tiene_campos_del_contrato(self):
        """Cada item listado trae TODOS los campos que el explorador necesita."""
        datos = self._json_ok(self.cliente.get(f'/api/nextcloud/archivos?ruta={CARPETA}'),
                              'listar carpeta')
        self.assertEqual(len(datos['archivos']), 1, 'debe haber exactamente 1 archivo')
        item = datos['archivos'][0]
        faltantes = CAMPOS_ITEM - set(item.keys())
        self.assertFalse(faltantes, f'faltan campos del contrato en el item: {faltantes}')
        self.assertEqual(item['nombre'], 'contrato.txt')
        self.assertFalse(item['es_carpeta'])
        self.assertEqual(item['tamano_bytes'], len(CONTENIDO))

    def test_06_descargar_bytes_identicos(self):
        """GET /archivos/descargar devuelve exactamente los bytes subidos."""
        resp = self.cliente.get(f'/api/nextcloud/archivos/descargar?ruta={CARPETA}/contrato.txt')
        self.assertEqual(resp.status_code, 200, 'descarga: HTTP != 200')
        self.assertEqual(resp.data, CONTENIDO, 'descarga: los bytes NO coinciden con lo subido')

    # ═══════════════ 4. Renombrar / copiar / mover ═══════════════
    def test_07_renombrar(self):
        """POST /archivos/renombrar cambia el nombre sin perder el archivo."""
        self._json_ok(self.cliente.post('/api/nextcloud/archivos/renombrar', json={
            'ruta': f'{CARPETA}/contrato.txt', 'nuevo_nombre': 'contrato_v2.txt'
        }), 'renombrar')
        datos = self._json_ok(self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}&nocache=1'), 'listar tras renombrar')
        self.assertEqual(datos['archivos'][0]['nombre'], 'contrato_v2.txt')

    def test_08_copiar(self):
        """POST /archivos/copiar duplica el archivo dentro de la misma carpeta."""
        self._json_ok(self.cliente.post('/api/nextcloud/archivos/copiar', json={
            'origen': f'{CARPETA}/contrato_v2.txt',
            'destino': f'{CARPETA}/copia.txt'
        }), 'copiar')
        datos = self._json_ok(self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}&nocache=1'), 'listar tras copiar')
        self.assertEqual(len(datos['archivos']), 2, 'la copia no aparece')

    def test_09_mover_carpeta(self):
        """POST /archivos/mover renombra/mueve la carpeta completa con su contenido."""
        self._json_ok(self.cliente.post('/api/nextcloud/archivos/mover', json={
            'origen': CARPETA, 'destino': f'{CARPETA}_movida'
        }), 'mover carpeta')
        datos = self._json_ok(self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}_movida&nocache=1'), 'listar carpeta movida')
        self.assertEqual(len(datos['archivos']), 2, 'el contenido no sobrevivió la movida')
        # regresarla para el resto de pruebas
        self._json_ok(self.cliente.post('/api/nextcloud/archivos/mover', json={
            'origen': f'{CARPETA}_movida', 'destino': CARPETA
        }), 'regresar carpeta')

    # ═══════════════ 5. Compartir ═══════════════
    def test_10_compartir_enlace_publico(self):
        """POST /compartir tipo 3 genera un enlace público con token/url."""
        datos = self._json_ok(self.cliente.post('/api/nextcloud/compartir', json={
            'ruta': f'{CARPETA}/contrato_v2.txt', 'tipo': 3, 'permisos': 1
        }), 'compartir enlace')
        self.assertIn('compartido', datos)
        comp = datos['compartido'] or {}
        self.assertTrue(comp.get('url') or comp.get('token'),
                        'el enlace público no trae url ni token')
        self._share_id = comp.get('id')
        # limpiar el share creado (si el endpoint lo permite)
        if comp.get('id'):
            self.cliente.delete(f"/api/nextcloud/compartidos/{comp['id']}")

    # ═══════════════ 6. Búsqueda y cuota ═══════════════
    def test_11_buscar(self):
        """GET /buscar encuentra el archivo por nombre."""
        datos = self._json_ok(self.cliente.get('/api/nextcloud/buscar?q=contrato_v2'),
                              'buscar')
        # CONTRATO REAL: la búsqueda devuelve 'resultados' (lista), 'termino' y 'total'
        self.assertIn('resultados', datos)
        self.assertIn('total', datos)
        nombres = [r['nombre'] for r in datos['resultados']]
        self.assertIn('contrato_v2.txt', nombres, 'la búsqueda no encontró el archivo')

    def test_12_cuota(self):
        """GET /cuota devuelve uso y límite de almacenamiento."""
        datos = self._json_ok(self.cliente.get('/api/nextcloud/cuota'), 'cuota')
        self.assertTrue(any(k in datos for k in ('cuota', 'usado', 'total', 'quota')),
                        f'cuota sin campos reconocibles: {list(datos.keys())}')

    def test_13_buscar_usuarios(self):
        """GET /usuarios/buscar autocompleta usuarios para compartir."""
        datos = self._json_ok(self.cliente.get('/api/nextcloud/usuarios/buscar?q=ma'),
                              'buscar usuarios')
        self.assertIn('usuarios', datos)

    # ═══════════════ 7. Papelera (eliminación) ═══════════════
    def test_14_eliminar_archivo(self):
        """DELETE /archivos manda el archivo a la papelera."""
        self._json_ok(self.cliente.delete(
            f'/api/nextcloud/archivos?ruta={CARPETA}/copia.txt'), 'eliminar archivo')
        datos = self._json_ok(self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}&nocache=1'), 'listar tras eliminar')
        self.assertEqual(len(datos['archivos']), 1, 'el archivo eliminado sigue apareciendo')

    def test_15_eliminar_carpeta(self):
        """DELETE de la carpeta completa deja la cuenta limpia."""
        self._json_ok(self.cliente.delete(
            f'/api/nextcloud/archivos?ruta={CARPETA}'), 'eliminar carpeta')


if __name__ == '__main__':
    unittest.main(verbosity=2)
