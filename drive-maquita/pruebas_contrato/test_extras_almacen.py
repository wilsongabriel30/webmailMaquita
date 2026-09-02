# -*- coding: utf-8 -*-
"""
PRUEBAS DE LOS EXTRAS DEL ALMACÉN — favoritos, papelera, deduplicación
======================================================================
Verifican funcionalidades del motor propio que van más allá del núcleo básico.
Solo corren contra el Almacén (OBJETIVO_CONTRATO=almacen); contra Nextcloud
se saltan (su semántica interna es distinta y no la controlamos).

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import io
import os
import sys
import unittest

OBJETIVO = os.getenv('OBJETIVO_CONTRATO', 'faro')
USUARIO_PRUEBAS_ID = 54
CARPETA = '/__extras_fase2__'
CONTENIDO = b'contenido identico para probar deduplicacion maquita\n' * 100


@unittest.skipUnless(OBJETIVO == 'almacen', 'Solo aplica al Almacén Maquita')
class PruebasExtrasAlmacen(unittest.TestCase):
    """Favoritos, papelera con restauración y deduplicación por hash."""

    @classmethod
    def setUpClass(cls):
        """Levanta el Almacén en modo prueba con sesión del usuario de pruebas."""
        sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
        from app_almacen import crear_app_almacen
        cls.app = crear_app_almacen()
        cls.app.config['TESTING'] = True
        cls.cliente = cls.app.test_client()
        with cls.cliente.session_transaction() as sesion:
            sesion['usuario_id'] = USUARIO_PRUEBAS_ID
        cls.cliente.post('/api/nextcloud/carpetas',
                         json={'nombre': CARPETA.strip('/'), 'ruta': '/'})

    @classmethod
    def tearDownClass(cls):
        """Limpia carpeta y vacía la papelera."""
        cls.cliente.delete(f'/api/nextcloud/archivos?ruta={CARPETA}')
        cls.cliente.post('/api/nextcloud/papelera/vaciar')

    def _subir(self, nombre, contenido=CONTENIDO):
        return self.cliente.post(
            '/api/nextcloud/archivos',
            data={'archivo': (io.BytesIO(contenido), nombre), 'carpeta': CARPETA},
            content_type='multipart/form-data')

    # ── favoritos ──
    def test_01_favorito_toggle_y_listado(self):
        """Marcar favorito lo agrega al listado; desmarcarlo lo quita."""
        self._subir('fav.txt')
        ruta = f'{CARPETA}/fav.txt'

        r = self.cliente.post('/api/nextcloud/archivos/favorito', json={'ruta': ruta})
        self.assertTrue(r.get_json()['es_favorito'], 'debió quedar marcado')

        favs = self.cliente.get('/api/nextcloud/favoritos').get_json()
        nombres = [a['nombre'] for a in favs['archivos']]
        self.assertIn('fav.txt', nombres, 'el favorito no aparece en el listado')

        r = self.cliente.post('/api/nextcloud/archivos/favorito', json={'ruta': ruta})
        self.assertFalse(r.get_json()['es_favorito'], 'debió quedar desmarcado')

    # ── papelera con restauración ──
    def test_02_papelera_eliminar_y_restaurar(self):
        """Eliminar manda a papelera; restaurar lo devuelve a su sitio."""
        self._subir('borrame.txt')
        ruta = f'{CARPETA}/borrame.txt'

        self.cliente.delete(f'/api/nextcloud/archivos?ruta={ruta}')
        # ya no está en la carpeta
        listado = self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}&nocache=1').get_json()
        self.assertNotIn('borrame.txt', [a['nombre'] for a in listado['archivos']])

        # sí está en la papelera
        papelera = self.cliente.get('/api/nextcloud/papelera').get_json()
        item = next((a for a in papelera['archivos'] if a['nombre'] == 'borrame.txt'), None)
        self.assertIsNotNone(item, 'no llegó a la papelera')

        # restaurar por su identificador de papelera (campo 'ruta')
        r = self.cliente.post('/api/nextcloud/papelera/restaurar',
                              json={'ruta': item['ruta']})
        self.assertTrue(r.get_json()['success'], 'no se pudo restaurar')

        listado = self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}&nocache=1').get_json()
        self.assertIn('borrame.txt', [a['nombre'] for a in listado['archivos']],
                      'el archivo no volvió tras restaurar')

    # ── deduplicación real ──
    def test_03_deduplicacion_comparte_inodo(self):
        """Dos archivos con contenido IDÉNTICO comparten inodo (0 bytes extra)."""
        sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
        from seguridad_rutas import ruta_fisica

        self._subir('dedup_a.txt')
        self._subir('dedup_b.txt')   # mismo contenido exacto

        fisica_a = ruta_fisica(USUARIO_PRUEBAS_ID, f'{CARPETA}/dedup_a.txt')
        fisica_b = ruta_fisica(USUARIO_PRUEBAS_ID, f'{CARPETA}/dedup_b.txt')
        self.assertTrue(os.path.exists(fisica_a) and os.path.exists(fisica_b))
        # Mismo inodo = el filesystem guarda UNA sola copia física
        self.assertEqual(os.stat(fisica_a).st_ino, os.stat(fisica_b).st_ino,
                         'los archivos idénticos NO se dedupdaron (inodos distintos)')

    def test_04_dedup_borrar_uno_no_afecta_al_otro(self):
        """Seguridad de la dedup: borrar una copia deja intacta la otra."""
        from seguridad_rutas import ruta_fisica
        # (dedup_a y dedup_b existen del test anterior, comparten inodo)
        self.cliente.delete(f'/api/nextcloud/archivos?ruta={CARPETA}/dedup_a.txt')

        fisica_b = ruta_fisica(USUARIO_PRUEBAS_ID, f'{CARPETA}/dedup_b.txt')
        self.assertTrue(os.path.exists(fisica_b), 'borrar una copia borró la otra (BUG grave)')
        with open(fisica_b, 'rb') as f:
            self.assertEqual(f.read(), CONTENIDO, 'la copia superviviente se corrompió')


if __name__ == '__main__':
    unittest.main(verbosity=2)
