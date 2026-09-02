# Exportador ODK -> xlsx en Drive Maquita: Datos ODK/<Proyecto>/<Formulario>.xlsx
import sys, io, re, os
sys.path.insert(0,'/home/sistemas/Maquita')
sys.path.insert(0,'/home/sistemas/almacen-maquita/servicio')
import xml.etree.ElementTree as ET
import openpyxl
from modulos.odk_analytics.aplicacion.servicios.servicio_database import DatabaseService
import nucleo_archivos as nucleo

U = 14  # Drive de Wilson

def _seguro(nombre):
    n = re.sub(r'[\\/:*?"<>|]', '_', str(nombre)).strip()
    return (n[:120] or 'sin_nombre')

def flatten(xml_str):
    row = {}
    try:
        root = ET.fromstring(xml_str)
    except Exception:
        return row
    def walk(el):
        tag = el.tag.split('}')[-1]
        hijos = list(el)
        if hijos:
            for c in hijos: walk(c)
        else:
            txt = (el.text or '').strip()
            if tag not in row or txt:
                row[tag] = txt
    for c in list(root): walk(c)
    return row

def export_form(db, proyecto, form):
    fid = int(form['id']); fname = _seguro(form.get('name') or form.get('xmlFormId') or fid)
    n = int(form.get('submission_count') or 0)
    if n <= 0:
        return f'  - {fname}: 0 submissions (omitido)'
    df = db.get_form_submissions_odk_style(fid, start=0, length=n)
    filas = []
    for _, s in df.iterrows():
        base = {'_instanceId': s.get('instanceId'), '_fecha': str(s.get('createdAt')),
                '_estado': s.get('reviewState')}
        base.update(flatten(s.get('response_data') or ''))
        filas.append(base)
    # columnas: union preservando orden de aparición
    cols = []
    for f in filas:
        for k in f:
            if k not in cols: cols.append(k)
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = 'Datos'
    ws.append(cols)
    for f in filas:
        ws.append([f.get(c,'') for c in cols])
    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    carpeta = f"/Datos ODK/{_seguro(proyecto['name'])}"
    nucleo.crear_carpeta(U, '/Datos ODK', 'x') if False else None
    nucleo.subir(U, carpeta, f'{fname}.xlsx', buf)
    return f'  - {fname}.xlsx: {len(filas)} filas, {len(cols)} columnas OK'

def main(solo_con_datos=True, proyecto_id=None):
    db = DatabaseService()
    proyectos = db.get_projects_list_odk_style()
    for _, p in proyectos.iterrows():
        if proyecto_id is not None and int(p['id']) != int(proyecto_id): continue
        if solo_con_datos and int(p.get('total_submissions') or 0) <= 0: continue
        print(f"PROYECTO {p['id']} - {p['name']} ({p.get('total_submissions')} subs)")
        forms = db.get_forms_by_project_odk_style(int(p['id']))
        for _, fm in forms.iterrows():
            try:
                print(export_form(db, p, fm))
            except Exception as e:
                print(f'  ! {fm.get("name")}: ERROR {e}')

if __name__ == '__main__':
    pid = int(sys.argv[1]) if len(sys.argv) > 1 else None
    main(proyecto_id=pid)
