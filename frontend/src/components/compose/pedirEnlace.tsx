/** Abre el cuadro del enlace y devuelve la dirección ya normalizada, '' si se dejó vacía o null si se canceló. */
import { createRoot } from 'react-dom/client';
import { CuadroEnlace } from './CuadroEnlace';

export function pedirEnlace(inicial = '', permiteVacio = false): Promise<string | null> {
  return new Promise(resolver => {
    const contenedor = document.createElement('div');
    document.body.appendChild(contenedor);
    const raiz = createRoot(contenedor);
    const alTerminar = (valor: string | null) => {
      raiz.unmount();
      contenedor.remove();
      resolver(valor);
    };
    raiz.render(<CuadroEnlace inicial={inicial} permiteVacio={permiteVacio} alTerminar={alTerminar} />);
  });
}
