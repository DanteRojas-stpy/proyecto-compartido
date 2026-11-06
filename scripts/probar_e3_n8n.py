"""Importa los flujos E3 en el n8n local apuntados al simulador (scripts/simulador_e3.py) y ejecuta E3.1 de punta a punta.

Uso:  python scripts/probar_e3_n8n.py [--contenedor n8n_local] [--simulador http://host.docker.internal:8787] [--solo-importar]
Crea copias «PRUEBA E3 sim …» (ids pruebaE3sim_N); no toca los flujos reales. No usa credenciales ni servicios reales.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GMAIL_FALSO = """const adjuntos = await this.helpers.httpRequest({ url: '__SIM__/_adjuntos', json: true });
const binary = {};
for (let i = 0; i < adjuntos.length; i++) binary['adjunto_' + i] = await this.helpers.prepareBinaryData(Buffer.from(adjuntos[i].b64, 'base64'), adjuntos[i].nombre, adjuntos[i].mime);
return [{ json: { id: 'sim-1' }, binary }];"""


def preparar(numero: int, simulador: str, entrada: dict | None = None, disparador: str | None = None) -> dict:
    flujo = json.loads((ROOT / "n8n" / "etapa3" / f"e3-{numero}.json").read_text(encoding="utf-8"))
    texto = json.dumps(flujo, ensure_ascii=False)
    for i in range(1, 6):
        texto = texto.replace(f"costflowEtapa3_{i}", f"pruebaE3sim_{i}")
    texto = (texto.replace("https://SUBDOMINIO.functions.REGION.nhost.run/v1/e3-operar", simulador + "/v1/e3-operar")
             .replace("https://SUBDOMINIO.storage.REGION.nhost.run/v1/files", simulador + "/v1/files")
             .replace("https://SUBDOMINIO.auth.REGION.nhost.run/v1/user", simulador + "/v1/user")
             .replace("https://api.anthropic.com/v1/messages", simulador + "/v1/messages"))
    flujo = json.loads(texto)
    flujo["name"] = "PRUEBA E3 sim " + flujo["name"].split(" - ", 1)[1]
    flujo["active"] = False
    nodos = flujo["nodes"]
    for nodo in nodos:
        nodo.pop("notes", None)
        p = nodo["parameters"]
        if nodo["type"].endswith("httpRequest"):
            p["authentication"] = "none"
            p.pop("genericAuthType", None)
            if "Authorization" in json.dumps(p) and "Preparar decisión" in json.dumps(p):
                pass
        if nodo["type"].endswith(".gmail"):
            nodo["type"], nodo["typeVersion"] = "n8n-nodes-base.code", 2
            nodo["parameters"] = {"jsCode": GMAIL_FALSO.replace("__SIM__", simulador)}
            nodo.pop("onError", None)
        if nodo["type"].endswith("scheduleTrigger"):
            nodo["type"], nodo["typeVersion"], nodo["parameters"] = "n8n-nodes-base.manualTrigger", 1, {}
        if nodo["type"].endswith("executeWorkflow"):
            nodo["parameters"]["options"] = {"waitForSubWorkflow": True}
        if nodo["type"].endswith("webhook") and nodo["name"] != disparador:
            nodo["parameters"]["authentication"] = "none"
            nodo["parameters"]["path"] = "prueba-" + nodo["parameters"]["path"]
            nodo.pop("webhookId", None)
    if entrada is not None:  # ejecución directa de un subflujo: el disparador se sustituye por una entrada fija
        for nodo in nodos:
            if (nodo["name"] == disparador) if disparador else nodo["type"].endswith("executeWorkflowTrigger"):
                nombre = nodo["name"]
                nodo["type"], nodo["typeVersion"], nodo["parameters"] = "n8n-nodes-base.manualTrigger", 1, {}
                nodo.pop("webhookId", None)
                nodos.append({"id": "entrada-prueba", "name": "Entrada de prueba", "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [0, 200],
                              "parameters": {"jsCode": "return [{ json: " + json.dumps(entrada) + " }];"}})
                con = flujo["connections"]
                con["Entrada de prueba"] = con.get(nombre, {"main": [[]]})
                con[nombre] = {"main": [[{"node": "Entrada de prueba", "type": "main", "index": 0}]]}
                break
    return flujo


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--contenedor", default="n8n_local")
    ap.add_argument("--simulador", default="http://host.docker.internal:8787")
    ap.add_argument("--solo-importar", action="store_true")
    ap.add_argument("--flujo", type=int, default=1)
    ap.add_argument("--disparador", default=None, help="nombre del disparador a sustituir (webhook)")
    ap.add_argument("--entrada", default=None, help="JSON de entrada para ejecutar un subflujo directamente")
    args = ap.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        for n in range(1, 6):
            ruta = Path(tmp) / f"pruebaE3sim_{n}.json"
            ruta.write_text(json.dumps(preparar(n, args.simulador, json.loads(args.entrada) if args.entrada and n == args.flujo else None, args.disparador), ensure_ascii=False), encoding="utf-8")
            subprocess.run(["docker", "cp", str(ruta), f"{args.contenedor}:/tmp/pruebaE3sim_{n}.json"], check=True, capture_output=True, env={**__import__('os').environ, "MSYS_NO_PATHCONV": "1"})
            r = subprocess.run(["docker", "exec", args.contenedor, "n8n", "import:workflow", f"--input=/tmp/pruebaE3sim_{n}.json"], capture_output=True, text=True, encoding="utf-8")
            print(f"E3.{n} importado:", (r.stdout + r.stderr).strip().splitlines()[-1] if (r.stdout + r.stderr).strip() else r.returncode)
    for n in (2, 3):  # los subflujos deben estar publicados para que otros los invoquen
        subprocess.run(["docker", "exec", args.contenedor, "n8n", "publish:workflow", f"--id=pruebaE3sim_{n}"], capture_output=True)
    if args.solo_importar:
        return 0
    r = subprocess.run(["docker", "exec", args.contenedor, "n8n", "execute", f"--id=pruebaE3sim_{args.flujo}"], capture_output=True, text=True, encoding="utf-8", timeout=600)
    print(r.stdout[-6000:], r.stderr[-2000:])
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
