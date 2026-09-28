// Utilidades del recorrido: códigos de segundo factor y una imagen PNG de verdad, sin dependencias.
const crypto = require('crypto');
const zlib = require('zlib');

function base32(texto) {
  const alfabeto = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const c of texto.replace(/[\s=]/g, '').toUpperCase()) bits += alfabeto.indexOf(c).toString(2).padStart(5, '0');
  return Buffer.from((bits.match(/.{8}/g) || []).map((b) => parseInt(b, 2)));
}

/** Código TOTP (RFC 6238, SHA-1, 6 dígitos, 30 s) para un intervalo dado. */
function codigo(secreto, paso) {
  const contador = Buffer.alloc(8);
  contador.writeBigUInt64BE(BigInt(paso));
  const h = crypto.createHmac('sha1', base32(secreto)).update(contador).digest();
  const o = h[h.length - 1] & 0xf;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1e6).padStart(6, '0');
}

const pasoActual = () => Math.floor(Date.now() / 30000);

function png(lado, [r, g, b]) {
  const tabla = Array.from({ length: 256 }, (_, n) => { let c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; return c >>> 0; });
  const crc = (buf) => { let c = 0xffffffff; for (const x of buf) c = tabla[(c ^ x) & 0xff] ^ (c >>> 8); return (c ^ 0xffffffff) >>> 0; };
  const trozo = (tipo, datos) => {
    const cuerpo = Buffer.concat([Buffer.from(tipo), datos]);
    const largo = Buffer.alloc(4); largo.writeUInt32BE(datos.length);
    const suma = Buffer.alloc(4); suma.writeUInt32BE(crc(cuerpo));
    return Buffer.concat([largo, cuerpo, suma]);
  };
  const cabecera = Buffer.alloc(13);
  cabecera.writeUInt32BE(lado, 0); cabecera.writeUInt32BE(lado, 4); cabecera[8] = 8; cabecera[9] = 2;
  const fila = Buffer.concat([Buffer.from([0]), Buffer.alloc(lado * 3).map((_, i) => [r, g, b][i % 3])]);
  const pixeles = Buffer.concat(Array.from({ length: lado }, () => fila));
  return Buffer.concat([Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]), trozo('IHDR', cabecera), trozo('IDAT', zlib.deflateSync(pixeles)), trozo('IEND', Buffer.alloc(0))]);
}

module.exports = { codigo, pasoActual, png };
