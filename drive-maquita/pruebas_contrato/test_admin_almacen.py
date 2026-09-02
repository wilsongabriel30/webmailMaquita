# -*- coding: utf-8 -*-
"""
PRUEBAS DEL ACCESO GLOBAL DE MASTER — recuperación en minutos
=============================================================
Un master puede ver la papelera de otra persona y restaurar lo que borró;
un usuario normal NO puede (403). Solo corren contra el Almacén.

Autoría: Equipo de Tecnología Maquita — 2026-07-03
"""
import io
import os
import sys
import unittest

OBJETIVO = os.getenv('OBJETIVO_CONTRATO', 'faro')
MASTER_ID = 54          # master_pruebas (rol master_admin)
USUARIO_NORMAL_ID = 99999   # id inventado que NO es master (para probar el 403)
VICTIMA_ID = 88888      # "otra persona" cuyo archivo se recupera
CARPETA = '/__admin_fase2__'
CONTENIDO = b'documento importante borrado por error\n' * 20


@unittest.skipUnless(OBJETIVO == 'almacen', 'Solo aplica al Almacén Maquita')
class PruebasAccesoMaster(unittest.TestCase):
    """Recuperación global por parte de un master."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, '/home/sistemas/almacen-maquita/servicio')
        from app_almacen import crear_app_almacen
        from almacen_bd import _cache_roles
        # Fijar roles en caché para no depender de que existan en nómina
        _cache_roles[MASTER_ID] = 'master_admin'
        _cache_roles[USUARIO_NORMAL_ID] = 'user'
        _cache_roles[VICTIMA_ID] = 'user'
        cls.app = crear_app_almacen()
        cls.app.config['TESTING'] = True
        cls.cliente = cls.app.test_client()

    def _sesion(self, usuario_id):
        with self.cliente.session_transaction() as s:
            s['usuario_id'] = usuario_id

    @classmethod
    def tearDownClass(cls):
        import shutil
        from config_almacen import RAIZ_DATOS
        from almacen_bd import ejecutar
        for uid in (VICTIMA_ID,):
            ruta = os.path.join(RAIZ_DATOS, str(uid))
            if os.path.isdir(ruta):
                shutil.rmtree(ruta, ignore_errors=True)
            ejecutar('DELETE FROM retencion WHERE usuario_id = %s', (uid,))
            ejecutar('DELETE FROM papelera WHERE usuario_id = %s', (uid,))

    def test_01_usuario_normal_no_puede_administrar(self):
        """Un usuario sin rol master recibe 403 en las rutas de administración."""
        self._sesion(USUARIO_NORMAL_ID)
        r = self.cliente.get(f'/api/nextcloud/admin/papelera?usuario_id={VICTIMA_ID}')
        self.assertEqual(r.status_code, 403, 'un usuario normal NO debe administrar')

    def test_02_master_recupera_archivo_de_otro(self):
        """Flujo completo: la víctima borra un archivo; el master lo recupera."""
        # La víctima sube y borra un archivo
        self._sesion(VICTIMA_ID)
        self.cliente.post('/api/nextcloud/carpetas',
                          json={'nombre': CARPETA.strip('/'), 'ruta': '/'})
        self.cliente.post('/api/nextcloud/archivos',
                          data={'archivo': (io.BytesIO(CONTENIDO), 'importante.txt'),
                                'carpeta': CARPETA},
                          content_type='multipart/form-data')
        self.cliente.delete(f'/api/nextcloud/archivos?ruta={CARPETA}/importante.txt')

        # El master entra, ve la papelera de la víctima y restaura
        self._sesion(MASTER_ID)
        papelera = self.cliente.get(
            f'/api/nextcloud/admin/papelera?usuario_id={VICTIMA_ID}').get_json()
        item = next((a for a in papelera['archivos'] if a['nombre'] == 'importante.txt'), None)
        self.assertIsNotNone(item, 'el master no ve el archivo borrado de la víctima')

        r = self.cliente.post('/api/nextcloud/admin/restaurar',
                              json={'usuario_id': VICTIMA_ID, 'ruta': item['ruta']})
        self.assertTrue(r.get_json()['success'], 'el master no pudo restaurar')

        # El archivo volvió a la unidad de la víctima
        self._sesion(VICTIMA_ID)
        listado = self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}&nocache=1').get_json()
        self.assertIn('importante.txt', [a['nombre'] for a in listado['archivos']],
                      'el archivo recuperado no volvió a la unidad de la víctima')

    def test_03_master_explora_unidad_de_otro(self):
        """El master puede listar la unidad de otra persona."""
        self._sesion(MASTER_ID)
        r = self.cliente.get(f'/api/nextcloud/admin/archivos?usuario_id={VICTIMA_ID}&ruta=/')
        self.assertTrue(r.get_json()['success'])

    def test_04_retencion_tras_vaciar_papelera(self):
        """Si el usuario VACÍA su papelera, el master aún lo recupera (retención 90 días)."""
        # La víctima sube, borra y LUEGO vacía su papelera
        self._sesion(VICTIMA_ID)
        self.cliente.post('/api/nextcloud/carpetas',
                          json={'nombre': CARPETA.strip('/'), 'ruta': '/'})
        self.cliente.post('/api/nextcloud/archivos',
                          data={'archivo': (io.BytesIO(CONTENIDO), 'urgente.txt'),
                                'carpeta': CARPETA},
                          content_type='multipart/form-data')
        self.cliente.delete(f'/api/nextcloud/archivos?ruta={CARPETA}/urgente.txt')
        vaciado = self.cliente.post('/api/nextcloud/papelera/vaciar').get_json()
        self.assertGreaterEqual(vaciado['retenidos'], 1, 'no pasó a retención al vaciar')

        # Ya no está en la papelera de la víctima
        pap = self.cliente.get('/api/nextcloud/papelera').get_json()
        self.assertNotIn('urgente.txt', [a['nombre'] for a in pap['archivos']])

        # El master lo ve en retención y lo recupera
        self._sesion(MASTER_ID)
        ret = self.cliente.get(
            f'/api/nextcloud/admin/retencion?usuario_id={VICTIMA_ID}').get_json()
        item = next((e for e in ret['elementos'] if e['nombre'] == 'urgente.txt'), None)
        self.assertIsNotNone(item, 'el master no ve lo retenido')
        self.assertGreater(item['dias_restantes'], 80, 'la ventana de retención no es ~90 días')

        r = self.cliente.post('/api/nextcloud/admin/retencion/restaurar',
                              json={'usuario_id': VICTIMA_ID, 'ruta': item['ruta']})
        self.assertTrue(r.get_json()['success'], 'el master no pudo recuperar de retención')

        # Volvió a la unidad de la víctima
        self._sesion(VICTIMA_ID)
        listado = self.cliente.get(
            f'/api/nextcloud/archivos?ruta={CARPETA}&nocache=1').get_json()
        self.assertIn('urgente.txt', [a['nombre'] for a in listado['archivos']])

    def test_05_status_expone_es_master(self):
        """El frontend sabe si mostrar u ocultar las opciones de admin."""
        self._sesion(MASTER_ID)
        self.assertTrue(self.cliente.get('/api/nextcloud/status').get_json()['es_master'])
        self._sesion(USUARIO_NORMAL_ID)
        self.assertFalse(self.cliente.get('/api/nextcloud/status').get_json()['es_master'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
