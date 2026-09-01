"""App de Tableros / BI — Aplicación del Drive Maquita.

Elige un archivo de datos del Drive (.xlsx/.csv) y genera tableros automáticos
(KPIs + gráficos) con el motor de BI. Autenticación por el token del Drive.

Arranque:
    gunicorn 'app_bi:app' --bind 0.0.0.0:8791     # producción
    python app_bi.py                               # dev
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PARENT = os.path.dirname(_HERE)
for _p in (_PARENT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from flask import Flask, request, jsonify, render_template_string, redirect

from config import Config
import auth_drive
import cliente_drive
from bi.conector_drive import ConectorDrive
from bi.tableros import generar_tableros

_SELECTOR = """<!doctype html><meta charset=utf-8><title>Tableros — Drive Maquita</title>
<style>body{font:15px system-ui;margin:2rem;color:#1b2330}a{color:#1666c4;text-decoration:none}
li{margin:.4rem 0}h1{font-size:1.4rem}</style>
<h1>Tableros del Drive</h1>
<p>Elige un archivo de datos (.xlsx / .csv) para ver su tablero:</p>
<ul>{% for a in archivos %}<li>📊 <a href="/tablero?ruta={{ a.ruta|urlencode }}">{{ a.nombre }}</a></li>
{% else %}<li><em>No se encontraron archivos de datos en la carpeta.</em></li>{% endfor %}</ul>"""

_TABLERO = """<!doctype html><meta charset=utf-8><title>Tablero — {{ nombre }}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>body{font:15px system-ui;margin:1.5rem;color:#1b2330;background:#f6f8fb}
.kpis{display:flex;gap:1rem;flex-wrap:wrap;margin:1rem 0}
.kpi{background:#fff;border:1px solid #dce2ea;border-radius:10px;padding:1rem 1.4rem;min-width:130px}
.kpi .v{font-size:1.6rem;font-weight:700}.kpi .t{color:#667;font-size:.8rem}
.chart{background:#fff;border:1px solid #dce2ea;border-radius:10px;padding:1rem;margin:1rem 0;max-width:720px}
a{color:#1666c4}</style>
<p><a href="/">← Tableros</a></p><h1 style="font-size:1.3rem">{{ nombre }}</h1>
<div id="kpis" class="kpis"></div><div id="charts"></div>
<script>
fetch('/api/tablero?ruta='+encodeURIComponent({{ ruta|tojson }})).then(r=>r.json()).then(d=>{
 if(d.error){document.body.insertAdjacentHTML('beforeend','<p style="color:#c0392b">'+d.error+'</p>');return;}
 d.tableros.forEach(t=>{
  if(t.tipo==='kpi'){t.kpis.forEach(k=>{document.getElementById('kpis').insertAdjacentHTML('beforeend',
    '<div class=kpi><div class=v>'+k.valor+'</div><div class=t>'+k.titulo+'</div></div>');});}
  else{const id='c'+Math.random().toString(36).slice(2);
    document.getElementById('charts').insertAdjacentHTML('beforeend',
     '<div class=chart><b>'+t.titulo+'</b><canvas id='+id+'></canvas></div>');
    new Chart(document.getElementById(id),t.chartjs);}
 });
});
</script>"""


def crear_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.secret_key = Config.SECRET_KEY or "cambia-esto-en-produccion"
    auth_drive.init_auth(app)

    from flask_login import login_required

    @app.route("/")
    @login_required
    def inicio():
        carpeta = request.args.get("carpeta", "/")
        try:
            archivos = cliente_drive.listar_datos(carpeta)
        except Exception:
            archivos = []
        return render_template_string(_SELECTOR, archivos=archivos)

    @app.route("/tablero")
    @login_required
    def tablero():
        ruta = request.args.get("ruta", "")
        if not ruta:
            return redirect("/")
        return render_template_string(_TABLERO, ruta=ruta, nombre=ruta.rsplit("/", 1)[-1])

    @app.route("/api/tablero")
    @login_required
    def api_tablero():
        ruta = request.args.get("ruta", "")
        if not ruta:
            return jsonify({"error": "Falta 'ruta'"}), 400
        try:
            df = ConectorDrive(cliente_drive.leer_bytes).obtener_datos({"ruta": ruta})
            return jsonify({"tableros": generar_tableros(df)})
        except Exception as exc:
            return jsonify({"error": "No se pudo generar el tablero: %s" % exc}), 500

    return app


app = crear_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8791")))
