# -*- coding: utf-8 -*-
"""
PRUEBAS DE VERSIONES Y ESTILO DE CARPETA — Fase 3 del Almacén
=============================================================
Historial de versiones (como Google Drive) y color de carpeta. Solo Almacén.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import io
import os
import sys
import unittest

OBJETIVO = os.getenv('OBJETIVO_CONTRATO', 'faro')
USUARIO_PRUEBAS_ID = 54
CARPETA = '/__versiones_fase3__'


@unittest.skipUnless(OBJETIVO == 'almacen', 'Solo aplica al Almacén Maquita')
class PruebasVersiones(unittest.TestCase):
    """Versiones de archivo y estilo de carpeta."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
        from app_almacen import crear_app_almacen
        cls.app = crear_app_almacen()
        cls.app.config['TESTING'] = True
        cls.cliente = cls.app.test_client()
        with cls.cliente.session_transaction() as s:
            s['usuario_id'] = USUARIO_PRUEBAS_ID
        cls.cliente.post('/api/nextcloud/carpetas',
                         json={'nombre': CARPETA.strip('/'), 'ruta': '/'})

    @classmethod
    def tearDownClass(cls):
        cls.cliente.delete(f'/api/nextcloud/archivos?ruta={CARPETA}')
        cls.cliente.post('/api/nextcloud/papelera/vaciar')

    def _subir(self, nombre, contenido):
        return self.cliente.post(
            '/api/nextcloud/archivos',
            data={'archivo': (io.BytesIO(contenido), nombre), 'carpeta': CARPETA},
            content_type='multipart/form-data')

    def test_01_resubir_crea_version_y_se_restaura(self):
        """Re-subir a la misma ruta genera versión; se puede volver a la anterior."""
        self._subir('doc.txt', b'VERSION UNO\n')
        self._subir('doc.txt', b'VERSION DOS modificada\n')   # sobrescribe → versiona la 1

        # el archivo actual tiene el contenido nuevo
        actual = self.cliente.get(
            f'/api/nextcloud/archivos/descargar?ruta={CARPETA}/doc.txt').data
        self.assertEqual(actual, b'VERSION DOS modificada\n')

        # obtener file_id del item (el id estable)
        listado = self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}&nocache=1').get_json()
        item = next(a for a in listado['archivos'] if a['nombre'] == 'doc.txt')
        file_id = item['id']

        # hay 1 versión (la VERSION UNO)
        vers = self.cliente.get(f'/api/nextcloud/versiones/{file_id}').get_json()
        self.assertEqual(vers['total'], 1, 'debería haber 1 versión anterior')

        # restaurar esa versión
        version_id = vers['versiones'][0]['version_id']
        r = self.cliente.post(f'/api/nextcloud/versiones/{file_id}/restaurar',
                              json={'version_id': version_id})
        self.assertTrue(r.get_json()['success'])

        # ahora el archivo volvió a la VERSION UNO
        restaurado = self.cliente.get(
            f'/api/nextcloud/archivos/descargar?ruta={CARPETA}/doc.txt').data
        self.assertEqual(restaurado, b'VERSION UNO\n', 'no se restauró la versión anterior')

        # y NO se perdió la VERSION DOS: quedó como versión (ahora hay 2)
        vers2 = self.cliente.get(f'/api/nextcloud/versiones/{file_id}').get_json()
        self.assertEqual(vers2['total'], 2, 'restaurar debe preservar el contenido previo')

    def test_02_color_de_carpeta(self):
        """Poner color a una carpeta y verlo reflejado al listar."""
        self.cliente.post('/api/nextcloud/carpetas',
                          json={'nombre': 'Proyectos', 'ruta': CARPETA})
        listado = self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}&nocache=1').get_json()
        carpeta = next(c for c in listado['carpetas'] if c['nombre'] == 'Proyectos')
        folder_id = carpeta['id']

        r = self.cliente.post('/api/nextcloud/carpetas/estilo',
                              json={'folder_id': folder_id, 'color': '#ea4335', 'icono': 'star'})
        self.assertTrue(r.get_json()['success'])

        listado2 = self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}&nocache=1').get_json()
        carpeta2 = next(c for c in listado2['carpetas'] if c['nombre'] == 'Proyectos')
        self.assertEqual(carpeta2['color'], '#ea4335', 'el color no se aplicó al listar')
        self.assertEqual(carpeta2['icono'], 'star')


if __name__ == '__main__':
    unittest.main(verbosity=2)
