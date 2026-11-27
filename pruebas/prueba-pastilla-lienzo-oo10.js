/* 27/11/2026. Pastillas en todas las celdas con lista en OnlyOffice 10: los
   nombres internos se deducen del código de las funciones (fuentes reales de
   la 10.0, réplica del editor), nunca se escriben a mano. */
const B = process.env.MODULOS || '/home/sistemas/Maquita/interfaces/web/estaticos/js/almacen/';
global.window = global;
global.MaquitaEditor = { alAparecer() { } };
require(B + 'editor-boton-nativo-lista.js');
require(B + 'editor-pastilla-lienzo-oo10.js');
const bien = (r, q) => console.log((r ? 'OK  ' : 'MAL ') + q);
const fn = (s) => (0, eval)('(' + s + ')');

function Vista() { this.model = {}; }
Vista.prototype.bKj = fn('function(J){var V=this.model.getSelection(),sa=V.Zg.Fa,N=V.Zg.La;J&&(J=this.model.AB(V.Zg.Fa,V.Zg.La))&&(sa=J.r1,N=J.sa);return this.dfb(N,sa)}');
Vista.prototype.dfb = fn('function(J,V){var sa=0,N=0,ba=this.Xi.ka,ha=this.Xi.r1;if(this.Dh){var C=this.Eha(),da=this.Dh.UA(),qa=this.Dh.WA();J>=da?sa=C.offsetX:ba=this.VH();V>=qa?N=C.offsetY:ha=this.KE()}C=this.ag(J);da=this.yg(V);C-=this.NW(ba,!0);da-=this.WS(ha,!0);C+=sa;da+=N;this.no()&&(C=this.vF()-C);J=this.Bv(J);this.no()&&(J=-J);V=this.Iw(V);P.qlc()&&(C=AscCommon.Vd.Ik(C),da=AscCommon.Vd.Ik(da),J=AscCommon.Vd.Ik(J),V=AscCommon.Vd.Ik(V));return new AscCommon.DEa(C,da,J,V)}');
Vista.prototype.QFj = fn('function(J,V,sa){if(this.Aa.di()){var N=this.model.getSelection().Zg;if(J.B5a(N)){J=(J=this.model.SZd(N.La,N.Fa))&&J.Tof();var ba;J&&(ba=this.model.AB(N.Fa,N.La));(J||this.model.Mdh(N.La,N.Fa))&&this.UNe(V,sa,{hnd:!0,Flc:null,Clc:!1,Fa:J&&ba?ba.r1:N.Fa,La:J&&ba?ba.sa:N.La});return!1}return!0}}');
Vista.prototype.zdc = fn('function(J,V,sa){var ha=this.model;if(ha.Aa.Zo)return!1;var K=new Asc.Range(J.ka,J.r1,J.sa,J.r1);this.UNe(V,sa,K);return!0}');
Vista.prototype.otra = fn('function(J,V,sa){return new Asc.Range(1,2,3,4)}');
const vista = new Vista();
function Range(c1, r1, c2, r2) { this.ka = c1; this.r1 = r1; this.sa = c2; this.r2 = r2; this.xX = 3; }
const ventana = { Asc: { Range: Range, editor: { za: { lc: () => vista },
    asc_getActiveCellCoord: fn('function(P){var Z=this.za.lc();if(Z)return Z.n8?Z.Xc.S0e():Z.bKj(P)}') } } };

const n = window.MaquitaPastillaLienzo10.resolver(ventana);
bien(!!n, 'se deducen todos los nombres internos');
if (n) {
    bien(n.libro === 'za' && n.hojaVisible === 'lc', 'la hoja visible: za.lc()');
    bien(n.coordCelda === 'dfb', 'la posición de una celda: dfb(col, fila)');
    bien(n.validacion === 'SZd' && n.esLista === 'Tof', 'si la celda tiene lista: model.SZd(col, fila).Tof()');
    bien(n.combinada === 'AB', 'si la celda está combinada: model.AB(fila, col)');
    bien(n.filtros === 'zdc', 'se engancha en los botones de filtro (zdc), no en otra función parecida');
    bien(JSON.stringify(n.campo) === '{"c1":"ka","r1":"r1","c2":"sa","r2":"r2"}', 'campos del intervalo: ' + JSON.stringify(n.campo));
    bien(n.colIzq === 'ag' && n.filaArr === 'yg', 'dónde empiezan columnas y filas: ag(col), yg(fila)');
    bien(n.panel === 'Dh' && n.desfase === 'Eha' && n.col0 === 'UA' && n.fila0 === 'WA',
         'lo inmovilizado: Dh.UA()/Dh.WA() y su desfase Eha()');
    bien(n.navegador === 'Vd' && n.escalaPropia === 'qlc' && n.aRetina === 'Ik', 'la escala propia del navegador: AscCommon.Vd');
}
const sin = { Asc: { Range: Range, editor: { za: { lc: () => vista }, asc_getActiveCellCoord: function () { return 1; } } } };
bien(window.MaquitaPastillaLienzo10.resolver(sin) === null, 'otra versión del editor: no se toca nada');
