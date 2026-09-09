-- Que el prefijo de una contraseña no pueda mentir sobre su contenido.
--
-- Nace del aviso del equipo replica (09/09/2026): una cuenta suya tenía guardado un hash con el
-- prefijo {SHA512-CRYPT} cuyo contenido no era formato crypt. Dovecot no puede verificar eso
-- jamás; la persona escribe bien su contraseña, el servidor dice que no, y no hay ningún mensaje
-- que lo explique. Estuvo un mes sin poder entrar.
--
-- Es lo que pasa al migrar: el servidor de origen guarda {SSHA512}, Dovecot espera SHA512-CRYPT,
-- y una fila mal etiquetada deja a alguien fuera para siempre. Lo cruel es que NO falla al
-- importar: falla semanas después, cuando ya nadie relaciona una cosa con la otra.
--
-- DELIBERADAMENTE ES UNA LISTA NEGRA, NO BLANCA. Solo prohíbe las combinaciones que sabemos
-- imposibles; un esquema que no conozca lo deja pasar. Una restricción que exigiera una lista
-- cerrada impediría dar de alta un buzón el día que se use un esquema nuevo, y eso sería peor que
-- el fallo que evita.
--
-- LO QUE NO PUEDE VER: un hash sin prefijo. Ahí el valor es indistinguible del de un esquema
-- desconocido, y Dovecot lo interpreta con default_password_scheme. Eso lo caza
-- deploy/tools/verificar-hashes.py, que sí sabe cuál es ese esquema por omisión.
--
-- Idempotente: se puede pasar dos veces.

DO $$
DECLARE
  malas integer;
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'mailbox_prefijo_coherente' AND conrelid = 'mailbox'::regclass
  ) THEN
    -- NOT VALID: se aplica a lo que venga a partir de ahora sin recorrer la tabla entera,
    -- así que no bloquea el correo mientras se añade.
    ALTER TABLE mailbox ADD CONSTRAINT mailbox_prefijo_coherente CHECK (
      password IS NULL OR (
        (password NOT LIKE '{SHA512-CRYPT}%' OR password LIKE '{SHA512-CRYPT}$6$%') AND
        (password NOT LIKE '{SHA256-CRYPT}%' OR password LIKE '{SHA256-CRYPT}$5$%') AND
        (password NOT LIKE '{MD5-CRYPT}%'    OR password LIKE '{MD5-CRYPT}$1$%')    AND
        (password NOT LIKE '{BLF-CRYPT}%'    OR password LIKE '{BLF-CRYPT}$2%')     AND
        (password NOT LIKE '{CRYPT}%'        OR password LIKE '{CRYPT}$%')          AND
        (password NOT LIKE '{SSHA512}%'      OR length(password) > 9)               AND
        (password NOT LIKE '{SSHA256}%'      OR length(password) > 9)               AND
        (password NOT LIKE '{SSHA}%'         OR length(password) > 6)
      )
    ) NOT VALID;

    -- Y ahora lo ya guardado. Si esta instalación arrastra filas incoherentes, NO se aborta el
    -- despliegue por eso: la restricción se queda sin validar, que sigue impidiendo guardar
    -- valores nuevos incoherentes, y se avisa con el número exacto. Quien reportó el fallo tenía
    -- justamente una de esas filas; sería absurdo que la migración que lo previene le fallara.
    SELECT count(*) INTO malas FROM mailbox WHERE NOT (
      password IS NULL OR (
        (password NOT LIKE '{SHA512-CRYPT}%' OR password LIKE '{SHA512-CRYPT}$6$%') AND
        (password NOT LIKE '{SHA256-CRYPT}%' OR password LIKE '{SHA256-CRYPT}$5$%') AND
        (password NOT LIKE '{MD5-CRYPT}%'    OR password LIKE '{MD5-CRYPT}$1$%')    AND
        (password NOT LIKE '{BLF-CRYPT}%'    OR password LIKE '{BLF-CRYPT}$2%')     AND
        (password NOT LIKE '{CRYPT}%'        OR password LIKE '{CRYPT}$%')          AND
        (password NOT LIKE '{SSHA512}%'      OR length(password) > 9)               AND
        (password NOT LIKE '{SSHA256}%'      OR length(password) > 9)               AND
        (password NOT LIKE '{SSHA}%'         OR length(password) > 6)
      )
    );

    IF malas = 0 THEN
      ALTER TABLE mailbox VALIDATE CONSTRAINT mailbox_prefijo_coherente;
      RAISE NOTICE 'restriccion mailbox_prefijo_coherente creada y validada';
    ELSE
      RAISE WARNING 'restriccion creada, pero SIN VALIDAR: hay % cuenta(s) con el prefijo incoherente.', malas;
      RAISE WARNING 'Esas personas NO PUEDEN ENTRAR, por bien que escriban su contrasena.';
      RAISE WARNING 'Para ver cuales:  python3 deploy/tools/verificar-hashes.py';
      RAISE WARNING 'Se arregla asignandoles una contrasena nueva por el camino normal.';
      RAISE WARNING 'Despues:  ALTER TABLE mailbox VALIDATE CONSTRAINT mailbox_prefijo_coherente;';
    END IF;
  ELSE
    RAISE NOTICE 'la restriccion mailbox_prefijo_coherente ya existia: no se toca';
  END IF;
END $$;
