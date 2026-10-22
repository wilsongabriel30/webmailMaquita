# -*- coding: utf-8 -*-
"""
Documentos de Office EN BLANCO para «Nuevo → Documento / Hoja / Presentación».
==============================================================================
El Almacén del webmail no tiene las plantillas vacías del sistema central
(`recursos/plantillas/vacio.*`), y la política de superficie mínima del servicio no
admite python-docx ni similares. Por eso se arman aquí, con `zipfile`, los paquetes
OOXML mínimos y válidos que abren Word, Excel, PowerPoint y OnlyOffice.

`documento_vacio('docx' | 'xlsx' | 'pptx')` → bytes del archivo.
"""
import io
import zipfile

_XML = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_NS_REL = 'http://schemas.openxmlformats.org/package/2006/relationships'
_NS_DOC_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
_NS_A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
_NS_P = 'http://schemas.openxmlformats.org/presentationml/2006/main'
_TIPO = 'application/vnd.openxmlformats-officedocument.'
_REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/'


def _tipos(por_defecto, partes):
    filas = ''.join('<Override PartName="%s" ContentType="%s"/>' % p for p in partes)
    return (_XML + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>' + por_defecto + filas + '</Types>')


def _relaciones(lista):
    filas = ''.join('<Relationship Id="%s" Type="%s%s" Target="%s"/>' % (i, _REL, t, d) for i, t, d in lista)
    return _XML + '<Relationships xmlns="%s">%s</Relationships>' % (_NS_REL, filas)


def _paquete(partes):
    salida = io.BytesIO()
    with zipfile.ZipFile(salida, 'w', zipfile.ZIP_DEFLATED) as zf:
        for nombre, contenido in partes:   # [Content_Types].xml va primero
            zf.writestr(nombre, contenido)
    return salida.getvalue()


# ── Word ─────────────────────────────────────────────────────────────────
def _docx():
    documento = (_XML + '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                 '<w:body><w:p/><w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                 '<w:pgMar w:top="1417" w:right="1701" w:bottom="1417" w:left="1701" '
                 'w:header="708" w:footer="708" w:gutter="0"/></w:sectPr></w:body></w:document>')
    return _paquete([
        ('[Content_Types].xml', _tipos('', [
            ('/word/document.xml', _TIPO + 'wordprocessingml.document.main+xml')])),
        ('_rels/.rels', _relaciones([('rId1', 'officeDocument', 'word/document.xml')])),
        ('word/document.xml', documento),
    ])


# ── Excel ────────────────────────────────────────────────────────────────
def _xlsx():
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    libro = (_XML + '<workbook xmlns="%s" xmlns:r="%s"><sheets>'
             '<sheet name="Hoja1" sheetId="1" r:id="rId1"/></sheets></workbook>' % (ns, _NS_DOC_REL))
    hoja = _XML + '<worksheet xmlns="%s"><sheetData/></worksheet>' % ns
    return _paquete([
        ('[Content_Types].xml', _tipos('', [
            ('/xl/workbook.xml', _TIPO + 'spreadsheetml.sheet.main+xml'),
            ('/xl/worksheets/sheet1.xml', _TIPO + 'spreadsheetml.worksheet+xml')])),
        ('_rels/.rels', _relaciones([('rId1', 'officeDocument', 'xl/workbook.xml')])),
        ('xl/workbook.xml', libro),
        ('xl/_rels/workbook.xml.rels', _relaciones([('rId1', 'worksheet', 'worksheets/sheet1.xml')])),
        ('xl/worksheets/sheet1.xml', hoja),
    ])


# ── PowerPoint ───────────────────────────────────────────────────────────
def _arbol_vacio():
    return ('<p:cSld><p:spTree><p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/>'
            '</p:nvGrpSpPr><p:grpSpPr/></p:spTree></p:cSld>')


def _tema():
    colores = (('dk1', '<a:sysClr val="windowText" lastClr="000000"/>'),
               ('lt1', '<a:sysClr val="window" lastClr="FFFFFF"/>'),
               ('dk2', '<a:srgbClr val="44546A"/>'), ('lt2', '<a:srgbClr val="E7E6E6"/>'),
               ('accent1', '<a:srgbClr val="4472C4"/>'), ('accent2', '<a:srgbClr val="ED7D31"/>'),
               ('accent3', '<a:srgbClr val="A5A5A5"/>'), ('accent4', '<a:srgbClr val="FFC000"/>'),
               ('accent5', '<a:srgbClr val="5B9BD5"/>'), ('accent6', '<a:srgbClr val="70AD47"/>'),
               ('hlink', '<a:srgbClr val="0563C1"/>'), ('folHlink', '<a:srgbClr val="954F72"/>'))
    esquema = ''.join('<a:%s>%s</a:%s>' % (n, v, n) for n, v in colores)
    letra = '<a:latin typeface="%s"/><a:ea typeface=""/><a:cs typeface=""/>'
    relleno = '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    linea = '<a:ln w="9525"><a:solidFill><a:schemeClr val="phClr"/></a:solidFill></a:ln>'
    efecto = '<a:effectStyle><a:effectLst/></a:effectStyle>'
    return (_XML + '<a:theme xmlns:a="%s" name="Tema"><a:themeElements>'
            '<a:clrScheme name="Tema">%s</a:clrScheme>'
            '<a:fontScheme name="Tema"><a:majorFont>%s</a:majorFont><a:minorFont>%s</a:minorFont></a:fontScheme>'
            '<a:fmtScheme name="Tema"><a:fillStyleLst>%s</a:fillStyleLst><a:lnStyleLst>%s</a:lnStyleLst>'
            '<a:effectStyleLst>%s</a:effectStyleLst><a:bgFillStyleLst>%s</a:bgFillStyleLst></a:fmtScheme>'
            '</a:themeElements></a:theme>'
            % (_NS_A, esquema, letra % 'Calibri Light', letra % 'Calibri',
               relleno * 3, linea * 3, efecto * 3, relleno * 3))


def _pptx():
    ns = 'xmlns:a="%s" xmlns:r="%s" xmlns:p="%s"' % (_NS_A, _NS_DOC_REL, _NS_P)
    presentacion = (_XML + '<p:presentation %s>'
                    '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
                    '<p:sldIdLst><p:sldId id="256" r:id="rId2"/></p:sldIdLst>'
                    '<p:sldSz cx="12192000" cy="6858000"/><p:notesSz cx="6858000" cy="9144000"/>'
                    '</p:presentation>' % ns)
    maestra = (_XML + '<p:sldMaster %s>%s'
               '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" accent2="accent2" '
               'accent3="accent3" accent4="accent4" accent5="accent5" accent6="accent6" hlink="hlink" '
               'folHlink="folHlink"/>'
               '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
               '</p:sldMaster>' % (ns, _arbol_vacio()))
    diseno = (_XML + '<p:sldLayout %s type="blank" preserve="1">%s'
              '<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sldLayout>' % (ns, _arbol_vacio()))
    diapositiva = (_XML + '<p:sld %s>%s<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>'
                   % (ns, _arbol_vacio()))
    pml = _TIPO + 'presentationml.'
    return _paquete([
        ('[Content_Types].xml', _tipos('', [
            ('/ppt/presentation.xml', pml + 'presentation.main+xml'),
            ('/ppt/slideMasters/slideMaster1.xml', pml + 'slideMaster+xml'),
            ('/ppt/slideLayouts/slideLayout1.xml', pml + 'slideLayout+xml'),
            ('/ppt/slides/slide1.xml', pml + 'slide+xml'),
            ('/ppt/theme/theme1.xml', _TIPO + 'theme+xml')])),
        ('_rels/.rels', _relaciones([('rId1', 'officeDocument', 'ppt/presentation.xml')])),
        ('ppt/presentation.xml', presentacion),
        ('ppt/_rels/presentation.xml.rels', _relaciones([
            ('rId1', 'slideMaster', 'slideMasters/slideMaster1.xml'),
            ('rId2', 'slide', 'slides/slide1.xml'),
            ('rId3', 'theme', 'theme/theme1.xml')])),
        ('ppt/slideMasters/slideMaster1.xml', maestra),
        ('ppt/slideMasters/_rels/slideMaster1.xml.rels', _relaciones([
            ('rId1', 'slideLayout', '../slideLayouts/slideLayout1.xml'),
            ('rId2', 'theme', '../theme/theme1.xml')])),
        ('ppt/slideLayouts/slideLayout1.xml', diseno),
        ('ppt/slideLayouts/_rels/slideLayout1.xml.rels', _relaciones([
            ('rId1', 'slideMaster', '../slideMasters/slideMaster1.xml')])),
        ('ppt/slides/slide1.xml', diapositiva),
        ('ppt/slides/_rels/slide1.xml.rels', _relaciones([
            ('rId1', 'slideLayout', '../slideLayouts/slideLayout1.xml')])),
        ('ppt/theme/theme1.xml', _tema()),
    ])


_FABRICAS = {'docx': _docx, 'xlsx': _xlsx, 'pptx': _pptx}
EXTENSIONES = frozenset(_FABRICAS)


def documento_vacio(extension: str) -> bytes:
    """Bytes de un documento de Office en blanco (`docx`, `xlsx` o `pptx`)."""
    return _FABRICAS[extension.lower()]()
