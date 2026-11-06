"""Simulador de Nhost para probar los flujos de E3 de n8n SIN tocar un proyecto real.

Levanta un PostgreSQL aislado con TODAS las migraciones del repositorio (la lógica real de `e3_operar`) y un servidor HTTP que imita:
  - la Function `e3-operar` de Nhost   (POST /v1/e3-operar  {operacion, datos})
  - Storage                            (HEAD/GET /v1/files/{id}, POST /v1/files)
  - Nhost Auth                         (GET /v1/user)
  - la API de mensajes de Claude       (POST /v1/messages), con una respuesta determinista para los documentos de prueba
  - los adjuntos de un correo de prueba (GET /_adjuntos) y consultas de comprobación (GET /_sql?q=...)

Uso:  python scripts/simulador_e3.py [--puerto 8787]      (requiere Docker; se detiene con Ctrl+C y borra su base)
Los flujos se apuntan al simulador con `scripts/probar_e3_n8n.py`. Nada de esto se usa en producción.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import re
import subprocess
import sys
import threading
import time
import uuid
from email.parser import BytesParser
from email.policy import default
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
CONTENEDOR = "costflow-e3-simulador"
USUARIO = "10000000-0000-0000-0000-000000000001"
PROYECTO = "20000000-0000-0000-0000-000000000001"
SOLICITUD = "30000000-0000-0000-0000-000000000001"
PROVEEDOR = "40000000-0000-0000-0000-000000000001"
CORREO = "60000000-0000-0000-0000-000000000001"
TOKEN_USUARIO = "usuario-de-prueba"

ALMACEN: dict[str, tuple[bytes, str]] = {}  # Storage en memoria: id -> (contenido, nombre)
BLOQUEO = threading.Lock()


# ---- Base de datos ----------------------------------------------------------------------------------------------------
def migraciones() -> list[Path]:
    archivos = [*ROOT.glob("db/migraciones/*.sql"), *ROOT.glob("db/etapa3/*.sql"), *ROOT.glob("db/etapa4/*.sql")]
    return sorted(archivos, key=lambda p: int(p.name.split("_", 1)[0]))


def sql(texto: str, solo_una_fila: bool = True) -> str:
    r = subprocess.run(["docker", "exec", "-i", CONTENEDOR, "psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1", "-U", "postgres", "-d", "postgres"],
                       input=texto, capture_output=True, text=True, encoding="utf-8", timeout=120)
    if r.returncode:
        raise RuntimeError(r.stderr.strip()[-600:])
    return r.stdout.strip()


def preparar_base(imagen: str) -> None:
    subprocess.run(["docker", "rm", "-f", CONTENEDOR], capture_output=True)
    subprocess.run(["docker", "run", "--rm", "-d", "--name", CONTENEDOR, "--tmpfs", "/var/lib/postgresql:rw", "-e", "POSTGRES_HOST_AUTH_METHOD=trust", imagen],
                   check=True, capture_output=True, timeout=180)
    for _ in range(120):
        if subprocess.run(["docker", "exec", CONTENEDOR, "pg_isready", "-q", "-U", "postgres"], capture_output=True).returncode == 0:
            break
        time.sleep(0.5)
    else:
        raise RuntimeError("PostgreSQL no inició a tiempo.")
    sql("CREATE SCHEMA auth; CREATE TABLE auth.users (id uuid PRIMARY KEY);")
    for ruta in migraciones():
        sql(ruta.read_text(encoding="utf-8"))
    sql(f"""
    INSERT INTO auth.users VALUES ('{USUARIO}');
    INSERT INTO public.proyectos(id,responsable_id,codigo,nombre) VALUES('{PROYECTO}','{USUARIO}','SIM-1','Obra de simulación');
    INSERT INTO public.solicitudes_cotizacion(id,proyecto_id,creado_por,nombre,moneda,vigencia_dias,fecha_limite,tipo)
      VALUES('{SOLICITUD}','{PROYECTO}','{USUARIO}','Elevadores','USD',30,current_date+30,'MA');
    INSERT INTO public.proveedores(id,creado_por,nombre) VALUES('{PROVEEDOR}','{USUARIO}','Proveedor de simulación');
    INSERT INTO public.solicitud_proveedores(solicitud_id,proveedor_id,estado) VALUES('{SOLICITUD}','{PROVEEDOR}','respondio');
    SELECT set_config('costflow.e3_actor','{USUARIO}',false);
    INSERT INTO public.correos_proveedor(id,solicitud_id,proveedor_id,gmail_message_id,remitente,recibido_at,estado_correo,origen_estado,estado_asignado_por,adjuntos)
      VALUES('{CORREO}','{SOLICITUD}','{PROVEEDOR}','sim-1','proveedor@example.invalid',now(),'cotizacion_o_ficha_tecnica_recibida','usuario','{USUARIO}',
             '[{{"nombre":"Cotización.pdf"}},{{"nombre":"Detalle.xlsx"}}]'::jsonb);
    UPDATE public.e3_configuracion SET recepcion_habilitada=true, lector_habilitado=true, modelo='claude-opus-5-5' WHERE id;
    """)


def operar(operacion: str, datos: dict) -> dict:
    salida = sql(f"SELECT public.e3_operar({literal(operacion)},{literal(json.dumps(datos, ensure_ascii=False))}::jsonb)::text;")
    return json.loads(salida)


def literal(texto: str) -> str:
    etiqueta = "j" + uuid.uuid4().hex[:6]
    return f"${etiqueta}${texto}${etiqueta}$"


# ---- Adjuntos de prueba ----------------------------------------------------------------------------------------------
def adjuntos() -> list[dict]:
    import openpyxl
    import pymupdf
    pdf = pymupdf.open()
    pagina = pdf.new_page()
    lineas = ["COTIZACION 001 Ascensores del Peru", "Ascensor 630 kg Cant 2 PU 36,800.00 Parcial 73,600.00 USD",
              "Subtotal 73,600.00 USD", "IGV 13,248.00 USD", "Total 86,848.00 USD", "Plazo de entrega: 9 meses",
              "Condiciones de pago: 30% adelanto", "Vigencia: 15 dias"]
    for numero, linea in enumerate(lineas):  # una línea por dato: ningún valor se parte entre líneas
        pagina.insert_text((40, 60 + 20 * numero), linea, fontsize=10)
    libro = openpyxl.Workbook()
    hoja = libro.active
    hoja.title = "Detalle"
    hoja.append(["Descripción", "Cant", "P.U.", "Parcial"])
    hoja.append(["Ascensor 630 kg", "2", "36,800.00", "73,600.00"])
    buffer = io.BytesIO()
    libro.save(buffer)
    return [
        {"nombre": "Cotización.pdf", "mime": "application/pdf", "b64": base64.b64encode(pdf.tobytes()).decode()},
        {"nombre": "Detalle.xlsx", "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "b64": base64.b64encode(buffer.getvalue()).decode()},
    ]


# ---- Claude simulado ---------------------------------------------------------------------------------------------------
def responder_claude(cuerpo: dict) -> dict:
    """Devuelve una lectura válida con los datos del documento de prueba, citando fragmentos reales."""
    entrada = json.loads(cuerpo["messages"][0]["content"])
    fragmentos = entrada["fragmentos"]
    documentos = entrada["documentos"]
    nombre_de = {d["documento_id"]: d["nombre"] for d in documentos}
    comerciales, items, evidencias, clasificacion = [], [], [], []
    for i, f in enumerate(fragmentos):
        documento = f["documento_id"]
        if "Ascensor 630 kg" not in f["texto"]:
            continue
        ev = f"e{i}"
        evidencias.append({"id": ev, "fragmento_id": f["id"], "documento_id": documento, "campo": "oferta", "texto_fuente": f["texto"], "confianza": 0.98})
        if nombre_de[documento].endswith(".pdf"):
            comerciales.append({"documento_id": documento, "valores": {"moneda": "USD", "subtotal": 73600, "impuestos": 13248, "total": 86848, "plazo_entrega": "9 meses",
                                "condiciones_pago": "30% adelanto", "vigencia_oferta": "15 dias"},
                                "originales": {"moneda": "USD", "subtotal": "73,600.00", "impuestos": "13,248.00", "total": "86,848.00", "plazo_entrega": "9 meses",
                                               "condiciones_pago": "30% adelanto", "vigencia_oferta": "15 dias"}, "evidencia_ids": [ev]})
        items.append({"documento_id": documento, "referencia_item": None, "descripcion": "Ascensor 630 kg", "cantidad": 2, "unidad": None, "unidad_normalizada": None,
                      "precio_unitario": 36800, "parcial": 73600,
                      "originales": {"descripcion": "Ascensor 630 kg", "cantidad": "2", "unidad": None, "precio_unitario": "36,800.00", "parcial": "73,600.00"},
                      "evidencia_ids": [ev]})
    for d in documentos:
        clasificacion.append({"documento_id": d["documento_id"], "tipo_documental": "cotizacion_proveedor" if d["nombre"].endswith(".pdf") else "anexo_proveedor"})
    datos = {"comerciales": comerciales, "items": items, "especificaciones_tecnicas": [], "evidencias": evidencias, "observaciones": [],
             "documentos": clasificacion, "inferencias": []}
    return {"id": "msg_simulado", "type": "message", "role": "assistant", "model": cuerpo.get("model"), "stop_reason": "end_turn",
            "content": [{"type": "text", "text": json.dumps(datos, ensure_ascii=False)}], "usage": {"input_tokens": 1000, "output_tokens": 500}}


# ---- Servidor HTTP -----------------------------------------------------------------------------------------------------
class Manejador(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, formato, *args):
        sys.stderr.write("[sim] " + (formato % args) + "\n")

    def _responder(self, codigo: int, cuerpo=None, tipo="application/json", cabeceras=None, sin_cuerpo=False):
        datos = b"" if cuerpo is None else (cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo, ensure_ascii=False).encode("utf-8"))
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        for k, v in (cabeceras or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if not sin_cuerpo:
            self.wfile.write(datos)

    def _cuerpo(self) -> bytes:
        return self.rfile.read(int(self.headers.get("Content-Length") or 0))

    def do_HEAD(self):
        ruta = urlparse(self.path).path
        if ruta.startswith("/v1/files/"):
            existe = ruta.rsplit("/", 1)[1] in ALMACEN
            return self._responder(200 if existe else 404, b"", "application/octet-stream", sin_cuerpo=True)
        self._responder(404, {}, sin_cuerpo=True)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path.startswith("/v1/files/"):
            archivo = ALMACEN.get(url.path.rsplit("/", 1)[1])
            if not archivo:
                return self._responder(404, {"error": "no existe"})
            return self._responder(200, archivo[0], "application/octet-stream", {"Content-Disposition": f'attachment; filename="{archivo[1]}"'})
        if url.path == "/v1/user":
            if self.headers.get("Authorization") != f"Bearer {TOKEN_USUARIO}":
                return self._responder(401, {"error": "sesión inválida"})
            return self._responder(200, {"id": USUARIO, "roles": ["user"], "defaultRole": "user", "isAnonymous": False})
        if url.path == "/_adjuntos":
            return self._responder(200, adjuntos())
        if url.path == "/_sql":
            with BLOQUEO:
                return self._responder(200, {"filas": sql(parse_qs(url.query)["q"][0]).splitlines()})
        if url.path == "/_salud":
            return self._responder(200, {"ok": True, "archivos": len(ALMACEN)})
        self._responder(404, {"error": "ruta desconocida"})

    def do_POST(self):
        url = urlparse(self.path)
        cuerpo = self._cuerpo()
        try:
            if url.path == "/v1/e3-operar":
                pedido = json.loads(cuerpo)
                with BLOQUEO:
                    return self._responder(200, {"respuesta": operar(pedido["operacion"], pedido.get("datos") or {})})
            if url.path == "/v1/messages":
                return self._responder(200, responder_claude(json.loads(cuerpo)))
            if url.path == "/v1/files":
                mensaje = BytesParser(policy=default).parsebytes(b"Content-Type: " + self.headers["Content-Type"].encode() + b"\r\n\r\n" + cuerpo)
                metadata, contenido, nombre = None, None, "archivo"
                for parte in mensaje.iter_parts():
                    campo = parte.get_param("name", header="content-disposition")
                    if campo == "metadata[]":
                        metadata = json.loads(parte.get_content() if isinstance(parte.get_content(), str) else parte.get_payload(decode=True))
                    elif campo == "file[]":
                        contenido, nombre = parte.get_payload(decode=True), parte.get_filename() or "archivo"
                identificador = (metadata or {}).get("id") or str(uuid.uuid4())
                ALMACEN[identificador] = (contenido or b"", nombre)
                return self._responder(201, {"processedFiles": [{"id": identificador, "name": nombre, "size": len(contenido or b"")}]})
        except Exception as error:  # noqa: BLE001
            return self._responder(502, {"error": str(error)[:500]})
        self._responder(404, {"error": "ruta desconocida"})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--puerto", type=int, default=8787)
    ap.add_argument("--imagen", default="postgres:16-alpine")
    args = ap.parse_args()
    print("Preparando PostgreSQL con las migraciones…", flush=True)
    preparar_base(args.imagen)
    servidor = ThreadingHTTPServer(("0.0.0.0", args.puerto), Manejador)
    print(f"Simulador listo en http://localhost:{args.puerto} (desde n8n en Docker: http://host.docker.internal:{args.puerto})", flush=True)
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        subprocess.run(["docker", "rm", "-f", CONTENEDOR], capture_output=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
