        // Parche de Maquita: Radicale (y la RFC 6350) exige FN, y Outlook para móviles no siempre
        // envía «fileas»: sin esto el contacto se rechaza con 400 y no llega al servidor.
        if (empty($message->fileas)) {
            $partes = array();
            foreach (array('firstname', 'middlename', 'lastname') as $campo) {
                if (!empty($message->$campo)) {
                    $partes[] = $message->$campo;
                }
            }
            $nombre = trim(implode(' ', $partes));
            if ($nombre === '' && !empty($message->companyname)) {
                $nombre = $message->companyname;
            }
            if ($nombre === '' && !empty($message->email1address)) {
                $nombre = preg_replace(array('/.*</', '/>.*/'), array('', ''), $message->email1address);
            }
            if ($nombre === '' && !empty($message->mobilephonenumber)) {
                $nombre = $message->mobilephonenumber;
            }
            $message->fileas = ($nombre !== '') ? $nombre : 'Sin nombre';
        }
