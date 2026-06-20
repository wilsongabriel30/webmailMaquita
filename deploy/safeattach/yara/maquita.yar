/* Reglas YARA base de SafeAttach Maquita. Ampliar con feeds (p.ej. YARA-Rules,
   Florian Roth signature-base) montando el directorio SAFEATTACH_YARA_DIR. */

rule Maquita_Doble_Extension_Ejecutable
{
    meta:
        descripcion = "Nombre con doble extension que termina en ejecutable"
        severidad = "suspicious"
    strings:
        $a = ".pdf.exe" nocase
        $b = ".doc.exe" nocase
        $c = ".xls.scr" nocase
        $d = ".jpg.exe" nocase
    condition:
        any of them
}

rule Maquita_PE_Disfrazado
{
    meta:
        descripcion = "Cabecera PE (MZ) en archivo que no deberia ser ejecutable"
        severidad = "suspicious"
    condition:
        uint16(0) == 0x5A4D and filesize < 8MB
}

rule Maquita_Script_Ofuscado
{
    meta:
        descripcion = "Indicadores de script ofuscado / descarga"
        severidad = "suspicious"
    strings:
        $p1 = "powershell" nocase
        $p2 = "-enc" nocase
        $p3 = "FromBase64String" nocase
        $p4 = "Invoke-Expression" nocase
        $p5 = "wscript.shell" nocase
    condition:
        2 of them
}
