"""MediaWiki — el programa de Wikipedia, para wikis y manuales colaborativos (GPLv2+). https://www.mediawiki.org

Paquete oficial de releases.wikimedia.org. El proyecto no publica sumas: firma cada paquete con GPG, y
la firma se comprueba con las claves de sus responsables de versiones que publica mediawiki.org
(keys.txt). Instalación por su línea de órdenes (maintenance/run.php install) con las claves en archivos
de la carpeta privada. Sin edición anónima ni registro libre (el administrador da las cuentas), y las
tareas pendientes se ejecutan por cron en vez de en cada visita.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile

from comun import ErrorSitio, ejecutar

from . import descargas, receta

NOMBRE = "MediaWiki"
DESCRIPCION = "Wiki como Wikipedia: manuales, procedimientos y conocimiento escrito entre muchas personas."
LICENCIA = "GPLv2+"
CATEGORIA = "Wikis y documentación"
VERIFICACION = "firma oficial"  # firma GPG oficial del paquete (más fuerte que una suma)
RAIZ_WEB = ""
BASE = "https://releases.wikimedia.org/mediawiki"
CLAVES = "https://www.mediawiki.org/keys/keys.txt"
# Extensiones incluidas en el paquete que no necesitan programas externos (exec está desactivado).
EXTENSIONES = ("AbuseFilter,CategoryTree,Cite,CiteThisPage,ConfirmEdit,Echo,Gadgets,ImageMap,InputBox,Linter,"
               "MultimediaViewer,Nuke,OATHAuth,PageImages,ParserFunctions,Poem,ReplaceText,SecureLinkFixer,"
               "SpamBlacklist,TemplateData,TemplateStyles,TextExtracts,Thanks,TitleBlacklist,VisualEditor,WikiEditor")

# Según la guía de nginx de MediaWiki: solo los PHP de entrada; código, mantenimiento e instalador no se
# sirven; direcciones cortas /wiki/Página.
REGLAS_NGINX = r"""
    location ~ ^/(?!(?:index|load|api|thumb|thumb_handler|opensearch_desc|rest|img_auth)\.php(?:/|$$)).*\.php(?:/|$$) { deny all; }
    location ~ ^/(?:cache|includes|maintenance|languages|serialized|tests|docs|vendor|mw-config|sql|bin|images/(?:deleted|temp|lockdir))/ { deny all; }
    location ~ ^/(?:composer\.(?:json|lock|local\.json-sample)|[A-Z][A-Z_-]+(?:\.md|-[0-9.]+)?)$$ { deny all; }
    location ^~ /wiki/ { rewrite ^ /index.php last; }
    location ^~ /rest.php/ { try_files $$uri /rest.php?$$args; }
"""

# Cambio de clave con la API de cuentas de MediaWiki (script de mantenimiento propio, datos por entorno).
_CLAVE = r"""<?php
use MediaWiki\Maintenance\Maintenance;
require_once getenv('MW_INSTALL_PATH') . '/maintenance/Maintenance.php';
class RecetaCambiarClave extends Maintenance {
  public function execute() {
    $d = json_decode(getenv('RECETA_DATOS'), TRUE);
    $usuario = $this->getServiceContainer()->getUserFactory()->newFromName($d['usuario']);
    if (!$usuario || !$usuario->isRegistered()) { $this->fatalError('no existe el usuario'); }
    $estado = $usuario->changeAuthenticationData(['username' => $usuario->getName(), 'password' => $d['clave'], 'retype' => $d['clave']]);
    if (!$estado->isGood()) { $this->fatalError('no se aceptó la clave'); }
    $this->output("LISTO\n");
  }
}
$maintClass = RecetaCambiarClave::class;
require_once RUN_MAINTENANCE_IF_MAIN;
"""


def _ultima():
    """(versión, rama) de la última versión estable publicada."""
    indice = descargas.texto(BASE + "/")
    ramas = sorted({tuple(map(int, m)) for m in re.findall(r'href="(\d+)\.(\d+)/"', indice)}, reverse=True)
    for rama in ramas[:3]:
        r = "%d.%d" % rama
        archivos = descargas.texto(f"{BASE}/{r}/")
        versiones = {tuple(map(int, v.split("."))) for v in re.findall(r'href="mediawiki-(%s\.\d+)\.tar\.gz"' % re.escape(r), archivos)}
        if versiones:
            return ".".join(map(str, max(versiones))), r
    raise ErrorSitio("no se encontró una versión estable de MediaWiki")


def _verificar_firma(paquete, firma):
    """Firma GPG válida de alguna de las claves de versiones que publica mediawiki.org."""
    with tempfile.TemporaryDirectory() as gnupg:
        claves = os.path.join(gnupg, "keys.txt")
        with open(claves, "w") as f:
            f.write(descargas.texto(CLAVES))
        base = ["gpg", "--homedir", gnupg, "--batch", "--no-tty", "--quiet"]
        subprocess.run(base + ["--import", claves], capture_output=True, timeout=60)
        r = subprocess.run(base + ["--status-fd", "1", "--verify", firma, paquete], capture_output=True, text=True,
                           timeout=120)
    if r.returncode != 0 or "[GNUPG:] VALIDSIG " not in r.stdout:
        raise ErrorSitio("el paquete de MediaWiki no coincide con su firma oficial: instalación cancelada")


def _texto_php(texto):
    return "'" + str(texto).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _archivo_privado(meta, contenido, sufijo=""):
    fd, ruta = tempfile.mkstemp(dir=meta["tmp"], prefix=".receta-", suffix=sufijo)
    with os.fdopen(fd, "w") as f:
        f.write(contenido)
    ejecutar(["chown", meta["usuario"], ruta])
    return ruta


def instalar(meta, bd, bd_usuario, bd_clave, titulo, correo, admin_usuario, admin_clave):
    version, rama = _ultima()
    with tempfile.TemporaryDirectory(dir=meta["tmp"]) as tmp:
        paquete, firma = os.path.join(tmp, "mediawiki.tar.gz"), os.path.join(tmp, "mediawiki.tar.gz.sig")
        descargas.descargar(f"{BASE}/{rama}/mediawiki-{version}.tar.gz", paquete)
        descargas.descargar(f"{BASE}/{rama}/mediawiki-{version}.tar.gz.sig", firma, tope=65536)
        _verificar_firma(paquete, firma)
        meta["app_suma"] = descargas.suma(paquete, "sha256")
        descargas.extraer(paquete, os.path.join(tmp, "extraido"))
        for n in os.listdir(os.path.join(tmp, "extraido")):
            shutil.move(os.path.join(tmp, "extraido", n), os.path.join(meta["publico"], n))
    if not os.path.isfile(os.path.join(meta["publico"], "maintenance/run.php")):
        raise ErrorSitio("el paquete de MediaWiki no tiene la estructura esperada")
    receta.permisos(meta)
    meta["app_version"], meta["app_verificacion"] = version, VERIFICACION
    cache = receta.privada(meta, "mediawiki-cache")
    claves = [_archivo_privado(meta, bd_clave), _archivo_privado(meta, admin_clave)]
    try:
        receta.php(meta, "maintenance/run.php", "install", "--dbtype=mysql", "--dbserver=localhost", f"--dbname={bd}",
                   f"--dbuser={bd_usuario}", f"--dbpassfile={claves[0]}", f"--passfile={claves[1]}", "--lang=es",
                   "--scriptpath=", f"--server={receta.url(meta)}", f"--extensions={EXTENSIONES}",
                   f"--confpath={meta['publico']}", titulo, admin_usuario)
    finally:
        for c in claves:
            os.remove(c)
    with open(os.path.join(meta["publico"], "LocalSettings.php"), "a") as f:
        f.write(f"""
# Ajustes del panel de hospedaje.
$wgServer = WebRequest::detectServer();  # funciona con HTTP, HTTPS y los alias del sitio
$wgArticlePath = "/wiki/$1";
$wgLocaltimezone = "America/Guayaquil";
$wgEmergencyContact = $wgPasswordSender = {_texto_php(correo)};
$wgCacheDirectory = {_texto_php(cache)};
$wgEnableUploads = true;
$wgJobRunRate = 0;  # las tareas pendientes las ejecuta el cron del panel
$wgGroupPermissions['*']['edit'] = false;
$wgGroupPermissions['*']['createaccount'] = false;
""")
    os.chmod(os.path.join(meta["publico"], "LocalSettings.php"), 0o640)
    receta.permisos(meta)
    receta.quitar(meta, "mw-config")
    return receta.url(meta) + "/wiki/Especial:Entrar"


def clave_admin(meta, usuario, nueva):
    ruta = _archivo_privado(meta, _CLAVE, ".php")
    try:
        salida = ejecutar(["php", ruta], como=meta["usuario"], cwd=meta["publico"],
                          env_extra={"RECETA_DATOS": json.dumps({"usuario": usuario, "clave": nueva}),
                                     "MW_INSTALL_PATH": meta["publico"]})
    finally:
        os.remove(ruta)
    if "LISTO" not in salida:
        raise ErrorSitio("no se pudo cambiar la clave en MediaWiki")


def cron(meta):
    receta.php(meta, "maintenance/run.php", "runJobs", "--maxtime=240", "--memory-limit=256M", tiempo=280)
