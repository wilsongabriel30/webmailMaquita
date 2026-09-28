import { api, enRuta } from '../api.js';
import { el, campo, casilla, ventana } from '../ui.js';

export function formularioReenvio(cuenta, actual, alTerminar) {
  const destinos = campo('Reenviar también a', { type: 'text', maxlength: 4000, valor: (actual?.destinos || []).join(', ') },
    'Una o varias direcciones separadas por comas, de tu dominio o de fuera. Vacío = sin reenvío.');
  const copia = casilla('Conservar copia en el buzón de la cuenta', actual ? actual.conserva_copia : true);
  ventana('Reenvío de ' + cuenta.username, el('div', null, destinos.nodo, copia.nodo), 'Guardar', async () => {
    const lista = destinos.entrada.value.split(/[,;\s]+/).filter(Boolean);
    await api.put('/reenvios/' + enRuta(cuenta.username), { destinos: lista, conserva_copia: copia.entrada.checked });
    alTerminar(lista.length ? 'Reenvío guardado.' : 'Reenvío quitado.');
  });
}

export function formularioEliminar(cuenta, alTerminar) {
  const motivo = campo('Motivo (opcional)', { type: 'text', maxlength: 500 });
  ventana('Pedir la eliminación de ' + cuenta.username, el('div', null,
    el('p', null, 'La cuenta se desactiva ahora mismo: deja de recibir correo y nadie puede entrar. El administrador general confirma el borrado definitivo, que no tiene vuelta atrás.'),
    motivo.nodo), 'Pedir eliminación', async () => {
    await api.post('/solicitudes/eliminar-cuenta', { cuenta: cuenta.username, motivo: motivo.entrada.value });
    alTerminar('Solicitud enviada. La cuenta quedó desactivada.');
  }, true);
}
