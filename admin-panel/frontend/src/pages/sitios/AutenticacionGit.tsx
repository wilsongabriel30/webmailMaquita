import { useCallback, useEffect, useState } from "react";
import { api } from "../../api/client";
import { campo } from "./datosComun";

export type Metodo = "clave-generada" | "clave-propia" | "token-https" | "usuario-contrasena" | "ninguna";

interface Estado {
  metodo: Metodo; configurada: boolean; compatible?: boolean; fecha?: string | null; repo?: string | null;
  clave_publica?: string | null; huella?: string | null; tipo_clave?: string | null; usuario?: string | null; final?: string | null;
  prueba?: { ok: boolean; error?: string } | null;
}

/* La recomendada primero; cada una con su ayuda breve (dónde se crea). */
export const METODOS: { id: Metodo; nombre: string; ayuda: string }[] = [
  { id: "clave-generada", nombre: "Clave de despliegue (recomendada)", ayuda: "El servidor crea una clave solo para este sitio: la privada nunca sale de él. Sirve solo para este repositorio, en solo lectura, y se revoca en GitHub sin afectar nada más. Use la dirección SSH (git@github.com:organizacion/repo.git)." },
  { id: "clave-propia", nombre: "Clave SSH propia", ayuda: "Pegue una clave privada SSH (ed25519, ECDSA o RSA de 3072 bits o más) sin frase de paso, creada solo para este repositorio: nunca la de su cuenta personal. Use la dirección SSH." },
  { id: "token-https", nombre: "Token de acceso (HTTPS)", ayuda: "GitHub: Settings → Developer settings → Fine-grained tokens, solo este repositorio, «Contents: Read-only» y con caducidad. GitLab: Settings → Repository → Deploy tokens (read_repository). Gitea y Forgejo: Configuración → Aplicaciones (read:repository). Bitbucket: Repository settings → Access tokens (Read). Use la dirección https://." },
  { id: "usuario-contrasena", nombre: "Usuario y contraseña (HTTPS)", ayuda: "Solo para servidores de git propios que no admitan claves ni tokens, con una cuenta que únicamente pueda leer este repositorio. Use la dirección https://." },
  { id: "ninguna", nombre: "Ninguna (repositorio público)", ayuda: "Repositorio público por https://: no hace falta credencial." },
];

/* Autenticación de git del sitio: la misma para el despliegue del sitio PHP y para la aplicación propia. El secreto se
   envía una vez y no se vuelve a mostrar: solo el método, la huella o los últimos caracteres del token y la fecha. */
export function AutenticacionGit({ dominio, repo }: { dominio: string; repo?: string }) {
  const ruta = `/sitios/${dominio}/git/credencial`;
  const [e, setE] = useState<Estado | null>(null);
  const [metodo, setMetodo] = useState<Metodo>("clave-generada");
  const [f, setF] = useState({ clave_privada: "", token: "", usuario: "", contrasena: "" });
  const [error, setError] = useState("");
  const [aviso, setAviso] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [copiado, setCopiado] = useState(false);

  const recibir = (d: Estado) => { setE(d); setMetodo(d.metodo); setF({ clave_privada: "", token: "", usuario: "", contrasena: "" }); };
  const cargar = useCallback(() => api.get<Estado>(ruta).then(recibir).catch((x) => setError(x.message)), [ruta]);
  useEffect(() => { cargar(); }, [cargar]);

  const enviar = async (fn: () => Promise<Estado>, texto: string) => {
    setError(""); setAviso(""); setOcupado(true);
    try {
      const d = await fn();
      recibir(d);
      setAviso(d.prueba && !d.prueba.ok ? `Guardada, pero la prueba falló: ${d.prueba.error}` : texto);
    } catch (x) { setError((x as Error).message); } finally { setOcupado(false); }
  };
  const guardar = (regenerar = false) => enviar(() => api.put<Estado>(ruta, {
    metodo, repo: repo?.trim() || undefined, regenerar,
    ...(metodo === "clave-propia" ? { clave_privada: f.clave_privada } : {}),
    ...(metodo === "token-https" ? { token: f.token, usuario: f.usuario || undefined } : {}),
    ...(metodo === "usuario-contrasena" ? { usuario: f.usuario, contrasena: f.contrasena } : {}),
  }), metodo === "clave-generada" ? "Clave lista: añádala en el repositorio." : "Credencial comprobada y guardada.");
  const borrar = () => { if (window.confirm("¿Borrar la credencial guardada? El repositorio tendrá que ser público.")) enviar(() => api.del<Estado>(ruta), "Credencial borrada."); };
  const copiar = (texto: string) => navigator.clipboard?.writeText(texto).then(() => { setCopiado(true); setTimeout(() => setCopiado(false), 1500); });

  if (!e) return <p className="text-xs text-ms-gray-60">{error || "Cargando la autenticación…"}</p>;
  const actual = METODOS.find((m) => m.id === metodo);
  const boton = "px-3 py-1.5 text-sm rounded border border-ms-gray-40 hover:bg-ms-gray-10 disabled:opacity-50";
  const guardada = e.metodo === metodo && e.configurada;
  return (
    <div className="border border-ms-gray-30 rounded p-3 space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <b>Autenticación</b>
        <select className={campo} value={metodo} onChange={(x) => setMetodo(x.target.value as Metodo)}>
          {METODOS.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
        </select>
        {e.configurada && <span className="text-xs text-ms-green">Configurada · {METODOS.find((m) => m.id === e.metodo)?.nombre}
          {e.tipo_clave && ` · ${e.tipo_clave}`}{e.huella && <> · <code>{e.huella}</code></>}{e.usuario && ` · usuario ${e.usuario}`}{e.final && ` · …${e.final}`}{e.fecha && ` · ${e.fecha}`}</span>}
      </div>
      {actual && <p className="text-xs text-ms-gray-90">{actual.ayuda}</p>}
      {metodo === "clave-propia" && <textarea className={`${campo} w-full font-mono`} rows={4} value={f.clave_privada} autoComplete="off" spellCheck={false}
        onChange={(x) => setF({ ...f, clave_privada: x.target.value })} placeholder={guardada ? "•••••• (guardada: pegue otra para reemplazarla)" : "-----BEGIN OPENSSH PRIVATE KEY-----"} />}
      {(metodo === "token-https" || metodo === "usuario-contrasena") && (
        <div className="grid sm:grid-cols-2 gap-2">
          <input className={campo} value={f.usuario} autoComplete="off" onChange={(x) => setF({ ...f, usuario: x.target.value })}
            placeholder={metodo === "token-https" ? "Usuario (opcional en GitHub, GitLab y Bitbucket)" : "Usuario"} />
          {metodo === "token-https"
            ? <input className={campo} type="password" autoComplete="new-password" value={f.token} onChange={(x) => setF({ ...f, token: x.target.value })} placeholder={guardada ? "•••••• (guardado)" : "Token"} />
            : <input className={campo} type="password" autoComplete="new-password" value={f.contrasena} onChange={(x) => setF({ ...f, contrasena: x.target.value })} placeholder={guardada ? "•••••• (guardada)" : "Contraseña"} />}
        </div>
      )}
      {metodo === "clave-generada" && e.metodo === "clave-generada" && e.clave_publica && (
        <div className="text-xs space-y-1">
          <p><b>Clave de despliegue</b> (añádala como de solo lectura): En GitHub: Settings → Deploy keys → Add deploy key, pegue esta clave y deje SIN marcar «Allow write access». En GitLab: Settings → Repository → Deploy keys.</p>
          <code className="block break-all bg-ms-gray-10 p-1 rounded select-all">{e.clave_publica}</code>
          <button className="text-ms-blue hover:underline" onClick={() => copiar(e.clave_publica || "")}>{copiado ? "Copiada" : "Copiar la clave"}</button>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        {metodo === "clave-generada"
          ? <button className={boton} disabled={ocupado} onClick={() => guardar(guardada)}>{guardada ? "Clave nueva" : "Generar la clave"}</button>
          : <button className={boton} disabled={ocupado || (metodo !== "ninguna" && !repo?.trim() && !e.repo)} onClick={() => guardar()}
              title={!repo?.trim() && !e.repo ? "Escriba antes la dirección del repositorio: la credencial se prueba con él" : undefined}>
              {metodo === "ninguna" ? "Usar sin credencial" : "Probar y guardar"}</button>}
        {e.configurada && <button className="text-ms-red text-xs hover:underline" disabled={ocupado} onClick={borrar}>Borrar la credencial</button>}
      </div>
      {ocupado && <p className="text-xs text-ms-gray-90">Comprobando con el servidor de git…</p>}
      {error && <p className="text-xs text-ms-red">{error}</p>}
      {aviso && <p className="text-xs text-ms-green">{aviso}</p>}
    </div>
  );
}
