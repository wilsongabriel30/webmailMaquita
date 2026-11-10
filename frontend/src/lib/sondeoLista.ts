// Regla del refresco automático de la lista de correos (10/11/2026).
//
// La lista se vuelve a pedir cada 45 s para que lo recién llegado aparezca solo. Con una búsqueda
// activa eso repetía la misma búsqueda una y otra vez (caso: «perez», 23 111 resultados, cada 45 s
// durante 10 minutos). Mientras se busca no se sondea: los resultados ya están y el correo nuevo
// se verá al limpiar la búsqueda.

export function debeSondearLista(busquedaActiva: string): boolean {
  return !busquedaActiva.trim();
}
