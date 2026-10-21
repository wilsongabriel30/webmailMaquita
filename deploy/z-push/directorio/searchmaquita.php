<?php
/*
 * Libreta de la organización (GAL) para Z-Push: al escribir un destinatario en Outlook o en el
 * celular, el teléfono busca aquí los buzones de su propio dominio.
 *
 * Lee /var/lib/z-push/directorio/<dominio>.json, que genera en el anfitrión
 * maquita-zpush-directorio (buzones activos: solo nombre y correo, sin teléfonos). Cada usuario
 * ve únicamente el directorio de su dominio. Sustituye a la búsqueda por CardDAV, que pedía una
 * colección «GAL» que Radicale no tiene (respondía 403).
 */

class BackendSearchMaquita implements ISearchProvider {
    const CARPETA = '/var/lib/z-push/directorio/';
    const MAXIMO = 100;

    public function SupportsType($searchtype) {
        return ($searchtype == ISearchProvider::SEARCH_GAL);
    }

    private function directorio() {
        $usuario = strtolower((string) Request::GetAuthUser());
        $pos = strrpos($usuario, '@');
        if ($pos === false) {
            return array();
        }
        $dominio = substr($usuario, $pos + 1);
        if (!preg_match('/^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$/D', $dominio)) {
            return array();
        }
        $texto = @file_get_contents(self::CARPETA . $dominio . '.json');
        if ($texto === false) {
            ZLog::Write(LOGLEVEL_WARN, sprintf("BackendSearchMaquita: no hay directorio para '%s'", $dominio));
            return array();
        }
        $datos = json_decode($texto, true);
        return is_array($datos) ? $datos : array();
    }

    private static function normalizar($texto) {
        $texto = mb_strtolower((string) $texto, 'UTF-8');
        $sin = @iconv('UTF-8', 'ASCII//TRANSLIT//IGNORE', $texto);
        return $sin === false ? $texto : $sin;
    }

    public function GetGALSearchResults($searchquery, $searchrange, $searchpicture) {
        $consulta = self::normalizar(trim((string) $searchquery));
        $encontrados = array();
        if ($consulta !== '') {
            foreach ($this->directorio() as $persona) {
                if (!isset($persona['correo'])) {
                    continue;
                }
                $nombre = isset($persona['nombre']) ? (string) $persona['nombre'] : '';
                if (strpos(self::normalizar($nombre . ' ' . $persona['correo']), $consulta) !== false) {
                    $encontrados[] = $persona;
                }
                if (count($encontrados) >= self::MAXIMO) {
                    break;
                }
            }
        }

        $inicio = 0;
        $fin = 49;
        if ($searchrange != '0' && strpos((string) $searchrange, '-') !== false) {
            list($inicio, $fin) = array_map('intval', explode('-', (string) $searchrange, 2));
        }
        $items = array('searchtotal' => count($encontrados));
        $rc = 0;
        for ($i = $inicio; $i <= $fin && $i < count($encontrados); $i++) {
            $p = $encontrados[$i];
            $nombre = (isset($p['nombre']) && $p['nombre'] !== '') ? $p['nombre'] : $p['correo'];
            $items[$rc] = array(
                SYNC_GAL_DISPLAYNAME => $nombre,
                SYNC_GAL_EMAILADDRESS => $p['correo'],
                SYNC_GAL_ALIAS => strstr($p['correo'], '@', true),
            );
            if (!empty($p['nombres'])) {
                $items[$rc][SYNC_GAL_FIRSTNAME] = $p['nombres'];
            }
            $items[$rc][SYNC_GAL_LASTNAME] = !empty($p['apellidos']) ? $p['apellidos'] : $nombre;
            $rc++;
        }
        $items['range'] = $inicio . '-' . ($rc > 0 ? $inicio + $rc - 1 : $inicio);
        return $items;
    }

    public function GetMailboxSearchResults($cpo) {
        return array();
    }

    public function TerminateSearch($pid) {
        return true;
    }

    public function Disconnect() {
        return true;
    }
}
