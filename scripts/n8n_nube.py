"""Prepara y sube los flujos de E3, E4 y E5 a una instancia de n8n (por ejemplo, n8n Cloud).

Los JSON del repositorio apuntan a los servicios de E3 y E4 por su nombre dentro de Docker (E5 corre dentro de n8n y no necesita servicio) y a marcadores SUBDOMINIO/REGION.
Este programa los adapta a la dirección pública de cada servicio, ajusta la frecuencia de los sondeos (en la nube cada
ejecución cuenta para la cuota) y, si se pide, los crea por la API de n8n enlazando los flujos que se invocan entre sí.

No lee ni escribe credenciales: la clave de la API de n8n se toma de la variable N8N_API_KEY y nunca de un argumento.
Después de subir hay que asignar las credenciales a mano en n8n (el programa muestra qué nodos las piden).

  python scripts/n8n_nube.py preparar --salida n8n-nube
  python scripts/n8n_nube.py subir   [--activar]
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Orden de creación: primero los flujos que otros invocan (E3.3 y E3.2), para conocer su identificador al enlazarlos.
ORDEN = ["costflowEtapa3_3", "costflowEtapa3_2", "costflowEtapa3_1", "costflowEtapa3_5", "costflowEtapa3_4", "costflowE4_1", "costflowE5_1"]
CARPETAS = ["n8n/etapa3", "n8n/etapa4", "n8n/etapa5"]
SERVICIOS_LOCALES = {
    "http://costflow-etapa3:8093": "servicio_e3",
    "http://costflow-homologacion:8094": "servicio_e4",
}
# Estos flujos revisan una cola por sondeo; E4 y E5 además despiertan por webhook cuando se pulsa el botón.
FLUJOS_DE_COLA_CON_AVISO = {"costflowE4_1", "costflowE5_1"}
CREDENCIALES = {
    "CREDENCIAL_E3:internal": "CostFlow E3 - Acceso interno",
    "CREDENCIAL_E3:claude": "CostFlow E3 - Claude",
    "CREDENCIAL_E3:gmail": "Gmail (OAuth de Google)",
    "CREDENCIAL_E3:storage": "CostFlow E3 - Nhost Storage",
    "CREDENCIAL_E4:internal": "CostFlow E3 - Acceso interno",
    "CREDENCIAL_E4:claude": "CostFlow E3 - Claude",
    "CREDENCIAL_E4:storage": "CostFlow E3 - Nhost Storage",
}


class ConfiguracionInvalida(ValueError):
    pass


def cargar_flujos(raiz: Path = ROOT) -> dict[str, dict]:
    flujos = {}
    for carpeta in CARPETAS:
        for ruta in sorted((raiz / carpeta).glob("e[345]-*.json")):
            flujo = json.loads(ruta.read_text(encoding="utf-8"))
            flujos[flujo["id"]] = flujo
    faltan = [i for i in ORDEN if i not in flujos]
    if faltan:
        raise ConfiguracionInvalida("Faltan flujos en el repositorio: " + ", ".join(faltan))
    return flujos


def _https(valor: str, nombre: str) -> str:
    valor = (valor or "").strip().rstrip("/")
    if not re.fullmatch(r"https://[A-Za-z0-9.-]+(:\d+)?(/[A-Za-z0-9._~/-]*)?", valor):
        raise ConfiguracionInvalida(f"{nombre} debe ser una dirección https:// válida (recibido: {valor or 'vacío'}).")
    return valor


def configuracion(args: argparse.Namespace, entorno: dict | None = None) -> dict:
    entorno = os.environ if entorno is None else entorno
    leer = lambda nombre, por_defecto="": getattr(args, nombre, None) or entorno.get(nombre.upper(), por_defecto)
    cfg = {
        "subdominio": leer("nhost_subdomain"), "region": leer("nhost_region", "sa-east-1"),
        "servicio_e3": _https(leer("servicio_e3_url"), "SERVICIO_E3_URL"),
        "servicio_e4": _https(leer("servicio_e4_url"), "SERVICIO_E4_URL"),
        "intervalo_e3": int(getattr(args, "intervalo_e3", 5)), "intervalo_cola": int(getattr(args, "intervalo_cola", 30)),
    }
    if not re.fullmatch(r"[a-z0-9]{10,30}", cfg["subdominio"]):
        raise ConfiguracionInvalida("NHOST_SUBDOMAIN no tiene la forma de un subdominio de Nhost.")
    if not re.fullmatch(r"[a-z]{2}-[a-z]+-\d", cfg["region"]):
        raise ConfiguracionInvalida("NHOST_REGION no tiene la forma de una región (por ejemplo, sa-east-1).")
    for clave in ("intervalo_e3", "intervalo_cola"):
        if not 1 <= cfg[clave] <= 1440:
            raise ConfiguracionInvalida(f"{clave} debe estar entre 1 y 1440 minutos.")
    return cfg


def _recorrer(valor, cambiar):
    if isinstance(valor, str):
        return cambiar(valor)
    if isinstance(valor, list):
        return [_recorrer(x, cambiar) for x in valor]
    if isinstance(valor, dict):
        return {k: _recorrer(v, cambiar) for k, v in valor.items()}
    return valor


def adaptar(flujo: dict, cfg: dict) -> dict:
    """Copia del flujo con las direcciones públicas, el sondeo ajustado y sin credenciales ni activación."""
    copia = copy.deepcopy(flujo)

    def texto(valor: str) -> str:
        for local, clave in SERVICIOS_LOCALES.items():
            valor = valor.replace(local, cfg[clave])
        valor = valor.replace("SUBDOMINIO", cfg["subdominio"])
        return re.sub(r"\bREGION\b", cfg["region"], valor)

    copia["active"] = False
    copia["nodes"] = _recorrer(copia["nodes"], texto)
    minutos = cfg["intervalo_cola"] if copia["id"] in FLUJOS_DE_COLA_CON_AVISO else cfg["intervalo_e3"]
    for nodo in copia["nodes"]:
        nodo.pop("credentials", None)
        if nodo["type"].endswith(".scheduleTrigger"):
            nodo["parameters"]["rule"] = {"interval": [{"field": "minutes", "minutesInterval": minutos}]}
    return copia


def credenciales_pendientes(flujos: list[dict]) -> list[tuple[str, str, str]]:
    """(flujo, nodo, credencial) por cada nodo que necesita una credencial asignada a mano."""
    filas = []
    for flujo in flujos:
        for nodo in flujo["nodes"]:
            marca = nodo.get("notes", "")
            if marca in CREDENCIALES:
                filas.append((flujo["name"], nodo["name"], CREDENCIALES[marca]))
    return filas


def enlazar(flujo: dict, ids: dict[str, str]) -> dict:
    """Reemplaza los identificadores de los flujos invocados por los que asignó n8n al crearlos."""
    for nodo in flujo["nodes"]:
        if nodo["type"].endswith(".executeWorkflow"):
            destino = nodo["parameters"]["workflowId"]["value"]
            if destino not in ids:
                raise ConfiguracionInvalida(f"«{nodo['name']}» invoca {destino}, que todavía no se creó.")
            nodo["parameters"]["workflowId"]["value"] = ids[destino]
    return flujo


def cuerpo_api(flujo: dict) -> dict:
    return {"name": flujo["name"], "nodes": flujo["nodes"], "connections": flujo["connections"], "settings": flujo.get("settings", {})}


class ClienteN8n:
    def __init__(self, url: str, clave: str, sesion=None):
        import requests
        self.base = _https(url, "N8N_URL") + "/api/v1"
        self.sesion = sesion or requests.Session()
        self.sesion.headers.update({"X-N8N-API-KEY": clave, "Accept": "application/json"})

    def _pedir(self, metodo: str, ruta: str, **kw):
        r = self.sesion.request(metodo, self.base + ruta, timeout=60, **kw)
        if r.status_code >= 400:
            raise RuntimeError(f"n8n respondió {r.status_code} en {metodo} {ruta}: {r.text[:300]}")
        return r.json() if r.content else {}

    def existentes(self) -> dict[str, str]:
        datos, cursor = {}, None
        while True:
            pagina = self._pedir("GET", "/workflows", params={"limit": 100, **({"cursor": cursor} if cursor else {})})
            datos.update({w["name"]: w["id"] for w in pagina.get("data", [])})
            cursor = pagina.get("nextCursor")
            if not cursor:
                return datos

    def crear_o_actualizar(self, flujo: dict, existente: str | None) -> str:
        if existente:
            return self._pedir("PUT", f"/workflows/{existente}", json=cuerpo_api(flujo))["id"]
        return self._pedir("POST", "/workflows", json=cuerpo_api(flujo))["id"]

    def activar(self, identificador: str) -> None:
        self._pedir("POST", f"/workflows/{identificador}/activate")


def subir(cliente: ClienteN8n, adaptados: dict[str, dict], activar: bool = False) -> dict[str, str]:
    existentes = cliente.existentes()
    ids: dict[str, str] = {}
    for clave in ORDEN:
        flujo = enlazar(copy.deepcopy(adaptados[clave]), ids)
        ids[clave] = cliente.crear_o_actualizar(flujo, existentes.get(flujo["name"]))
    if activar:
        for clave in ORDEN:
            cliente.activar(ids[clave])
    return ids


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("accion", choices=["preparar", "subir"])
    ap.add_argument("--nhost-subdomain"), ap.add_argument("--nhost-region")
    ap.add_argument("--servicio-e3-url"), ap.add_argument("--servicio-e4-url"), ap.add_argument("--servicio-e5-url", help="(ya no se usa: E5 corre dentro de n8n)")
    ap.add_argument("--intervalo-e3", type=int, default=5, help="minutos entre sondeos de E3.1 y E3.5 (por defecto 5)")
    ap.add_argument("--intervalo-cola", type=int, default=30, help="minutos entre sondeos de respaldo de E4 y E5 (por defecto 30)")
    ap.add_argument("--n8n-url", help="dirección de la instancia, por ejemplo https://miempresa.app.n8n.cloud")
    ap.add_argument("--salida", default="n8n-nube", help="carpeta donde `preparar` deja los JSON")
    ap.add_argument("--activar", action="store_true", help="activa los flujos al terminar (solo con las credenciales ya asignadas)")
    args = ap.parse_args(argv)
    try:
        cfg = configuracion(args)
        adaptados = {i: adaptar(f, cfg) for i, f in cargar_flujos().items()}
        lista = [adaptados[i] for i in ORDEN]
        if args.accion == "preparar":
            carpeta = Path(args.salida)
            carpeta.mkdir(parents=True, exist_ok=True)
            for i in ORDEN:
                (carpeta / f"{i}.json").write_text(json.dumps(adaptados[i], ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Listos {len(lista)} flujos en {carpeta}/ (sin credenciales, inactivos).")
        else:
            clave = os.environ.get("N8N_API_KEY", "")
            if not clave:
                raise ConfiguracionInvalida("Define la variable de entorno N8N_API_KEY (clave de la API de n8n).")
            url = args.n8n_url or os.environ.get("N8N_URL", "")
            ids = subir(ClienteN8n(url, clave), adaptados, args.activar)
            print("Flujos creados o actualizados:")
            for i in ORDEN:
                print(f"  {adaptados[i]['name']}  ->  {ids[i]}")
        print("\nAsigna estas credenciales en n8n antes de activar:")
        for flujo, nodo, credencial in credenciales_pendientes(lista):
            print(f"  [{flujo}] {nodo}: {credencial}")
        return 0
    except (ConfiguracionInvalida, RuntimeError) as error:
        print("Error:", error, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
