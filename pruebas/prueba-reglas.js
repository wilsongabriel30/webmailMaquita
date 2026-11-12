// Casos compartidos de reglas y cálculos: el motor de JavaScript (js/almacen/encuesta-reglas.js).
// Uso: node pruebas/prueba-reglas.js [ruta del motor]
const fs = require('fs'), path = require('path');
const motor = process.argv[2] || path.join(__dirname, '..', '..', 'Maquita', 'interfaces', 'web', 'estaticos', 'js', 'almacen', 'encuesta-reglas.js');
const R = require(motor);
const datos = JSON.parse(fs.readFileSync(path.join(__dirname, 'reglas-casos.json'), 'utf8'));
let fallas = 0;
for (const c of datos.casos) {
    R.validar(c.regla);
    const ob = R.evaluar(c.regla, c.valores, c.actual, datos.hoy);
    const esp = c.esperado;
    const ok = (ob === null && esp === null) || ob === esp;
    if (!ok) { fallas++; console.log('FALLA', c.nombre, '→', JSON.stringify(ob), 'esperado', JSON.stringify(esp)); }
}
for (const mala of [{op: 'xor', args: []}, {fn: 'eval', args: []}, {fn: 'si', args: [{num: 1}]},
                    {fn: 'patron', args: [{ref: 'a'}, {ref: 'b'}]}, {num: Infinity}, {otra: 1}]) {
    try { R.validar(mala); fallas++; console.log('FALLA: aceptó', JSON.stringify(mala)); } catch (e) { if (!(e instanceof R.ReglaInvalida)) throw e; }
}
console.log(datos.casos.length + ' casos, ' + fallas + ' fallas');
process.exit(fallas ? 1 : 0);
