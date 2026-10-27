"""Servicio local de apoyo. n8n conserva las credenciales de Gmail, Storage y Gemini."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import threading
import uuid
from pathlib import Path

import requests
from fastapi import Depends, FastAPI, Header, HTTPException

from . import contract, documents, rag

app = FastAPI(title="CostFlow E3", docs_url=None, redoc_url=None)
READ_LOCK = threading.Lock()


def internal(x_costflow_internal_key: str | None = Header(default=None)):
    expected = os.getenv("E3_INTERNAL_KEY", "")
    if not expected or not hmac.compare_digest(x_costflow_internal_key or "", expected):
        raise HTTPException(401, "Acceso interno no válido.")


def identifier(value) -> str:
    return str(uuid.UUID(str(value)))


class Bridge:
    def __init__(self):
        self.root = os.getenv("E3_N8N_URL", "http://n8n:5678").rstrip("/")
        self.headers = {"X-Costflow-Internal-Key": os.environ["E3_INTERNAL_KEY"]}

    def call(self, operation: str, data: dict | None = None, timeout=120) -> dict:
        response = requests.post(self.root + "/webhook/e3-interno-datos", headers=self.headers,
                                 json={"operacion": operation, "datos": data or {}}, timeout=timeout)
        response.raise_for_status()
        result = response.json()
        if result.get("error"):
            raise RuntimeError(str(result["error"])[:1500])
        return result.get("respuesta", result)

    def upload(self, meta: dict, content: bytes) -> dict:
        head = self.call("storage_head", {"storage_file_id": meta["storage_file_id"]})
        if head.get("statusCode") == 200:
            return meta
        if head.get("statusCode") != 404:
            raise RuntimeError("Storage no permitió comprobar el archivo.")
        response = requests.post(self.root + "/webhook/e3-interno-datos", headers=self.headers,
            data={"operacion": "storage_upload", "metadata": json.dumps({"id": meta["storage_file_id"],
                "name": meta["nombre_original"], "metadata": {"tipo": "documento_e3", "sha256": meta["sha256"]}})},
            files={"file": (meta["nombre_original"], content, meta["mime_type"] or "application/octet-stream")}, timeout=180)
        response.raise_for_status()
        result = response.json()
        if not any(x.get("id") == meta["storage_file_id"] for x in result.get("processedFiles", [])):
            # La carrera de dos correos con el mismo archivo puede haberlo guardado entre HEAD y POST.
            if self.call("storage_head", {"storage_file_id": meta["storage_file_id"]}).get("statusCode") != 200:
                raise RuntimeError("Storage no confirmó el archivo guardado.")
        return meta

    def download(self, file_id: str) -> bytes:
        result = self.call("storage_get", {"storage_file_id": identifier(file_id)})
        return base64.b64decode(result["contenido_base64"], validate=True)

    def gemini(self, model_name: str, body: dict) -> dict:
        response = requests.post(self.root + "/webhook/e3-interno-gemini", headers=self.headers,
                                 json={"modelo": model_name, "peticion": body}, timeout=180)
        response.raise_for_status()
        return response.json()


def cache_path(meta: dict) -> Path:
    folder = Path(os.getenv("E3_CACHE_DIR", "/datos/extracciones"))
    folder.mkdir(parents=True, exist_ok=True)
    return folder / f"{identifier(meta['documento_id'])}-{meta['sha256']}.json"


def read_document(data: bytes, meta: dict) -> dict:
    path = cache_path(meta)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    result = documents.extract(data, meta)
    rag.index_document(result)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)
    return result


@app.get("/health")
def health():
    return {"ok": True, "gemini": "credencial administrada por n8n", "salida": "json_nhost"}


@app.post("/receive", dependencies=[Depends(internal)])
def receive(payload: dict):
    bridge = Bridge()
    context = payload["contexto"]
    if context.get("resultado") != "version_creada":
        return context
    version_id = identifier(context["version_id"])
    try:
        if payload.get("error"):
            raise RuntimeError("Gmail no entregó el mensaje y sus adjuntos: " + str(payload["error"])[:1000])
        incoming = payload.get("archivos", [])
        if not incoming:
            raise RuntimeError("Gmail no devolvió adjuntos descargables.")
        unique = {}
        for attachment in incoming:
            data = base64.b64decode(attachment["contenido_base64"], validate=True)
            meta = documents.describe(data, attachment["nombre_original"], attachment["mime_type"], version_id)
            if meta["sha256"] in unique:
                unique[meta["sha256"]]["nombres_originales"].append(meta["nombre_original"])
                continue
            bridge.upload(meta, data)
            meta["nombres_originales"] = [meta["nombre_original"]]
            unique[meta["sha256"]] = meta
        return bridge.call("registrar_documentos", {"version_id": version_id, "token": context["token"], "documentos": list(unique.values())})
    except Exception as exc:
        return bridge.call("fallo", {"version_id": version_id, "token": context.get("token"), "fase": "recepcion",
                           "recuperable": not isinstance(exc, documents.DocumentError),
                           "error": {"tipo": type(exc).__name__, "mensaje": str(exc)[:2000]}})


@app.post("/read", dependencies=[Depends(internal)])
def read(payload: dict):
    bridge = Bridge()
    version_id = identifier(payload["version_id"])
    if not READ_LOCK.acquire(blocking=False):
        return {"resultado": "ocupado", "version_id": version_id}
    context = None
    try:
        context = bridge.call("iniciar_lectura", {"version_id": version_id})
        if context["resultado"] != "iniciada":
            return context
        snapshot = bridge.call("version", {"version_id": version_id})
        config = bridge.call("configuracion")
        version = snapshot["version"]
        sources = []
        for row in snapshot["documentos"]:
            bridge.call("renovar_lease", {"version_id": version_id, "token": context["token"]})
            content = bridge.download(row["storage_file_id"])
            meta = documents.describe(content, row["nombre_original"], row["mime_type"], version_id)
            # Mantiene el documento ya registrado, incluso al releer un legado autorizado.
            meta["documento_id"] = row["id"]
            meta["storage_file_id"] = row["storage_file_id"]
            meta["nombres_originales"] = row.get("e3_detalle", {}).get("nombres_originales", [row["nombre_original"]])
            if row.get("sha256") and row["sha256"] != meta["sha256"]:
                raise documents.DocumentError("La huella del archivo cambió desde su recepción.")
            sources.append(read_document(content, meta))
        if not sources:
            raise documents.DocumentError("La versión no tiene documentos registrados.")
        # Los vectores se envían en grupos para respetar el límite de cuerpo de n8n.
        for source in sources:
            for offset in range(0, len(source["fragmentos"]), 250):
                subset = {**source, "fragmentos": source["fragmentos"][offset:offset + 250]}
                bridge.call("guardar_fuentes", {"version_id": version_id, "token": context["token"], "documentos": [subset]})
        maximum = int(os.getenv("E3_CONTEXT_CHARS", "24000")) // (2 ** (context["intento"] - 1))
        batches = rag.context_batches(sources, maximum=maximum)
        responses = []
        for batch in batches:
            bridge.call("renovar_lease", {"version_id": version_id, "token": context["token"]})
            responses.append(contract.parse_response(bridge.gemini(config["modelo"], contract.request(batch, sources))))
        result = contract.combine(responses, sources, version, config["modelo"])
        return bridge.call("guardar_resultado", {"version_id": version_id, "token": context["token"], "resultado": result}, timeout=180)
    except Exception as exc:
        if not context or context.get("resultado") != "iniciada":
            raise HTTPException(503, "No se pudo iniciar la lectura; el evento permanece pendiente.") from exc
        return bridge.call("fallo", {"version_id": version_id, "token": context["token"], "fase": "lectura",
            "recuperable": not isinstance(exc, documents.DocumentError),
            "error": {"tipo": type(exc).__name__, "mensaje": str(exc)[:2000]}})
    finally:
        READ_LOCK.release()


@app.post("/notify", dependencies=[Depends(internal)])
def notify(payload: dict):
    return Bridge().call("notificar", {"version_id": identifier(payload["version_id"])})


@app.post("/recover", dependencies=[Depends(internal)])
def recover():
    maintenance()
    return Bridge().call("recuperar")


@app.post("/action", dependencies=[Depends(internal)])
def action(payload: dict, authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer ") or len(authorization) > 16384:
        return {"ok": False, "http_code": 401, "mensaje": "Inicia sesión en Nhost."}
    subdomain = os.environ["NHOST_SUBDOMAIN"]
    region = os.getenv("NHOST_REGION", "sa-east-1")
    try:
        response = requests.get(f"https://{subdomain}.auth.{region}.nhost.run/v1/user", headers={"Authorization": authorization}, timeout=30)
        if response.status_code != 200:
            return {"ok": False, "http_code": 401 if response.status_code in (400, 401, 403) else 503,
                    "mensaje": "La sesión venció o no pudo verificarse. Vuelve a ingresar."}
        user = response.json()
        if user.get("isAnonymous") or "user" not in user.get("roles", []) + [user.get("defaultRole")]:
            return {"ok": False, "http_code": 403, "mensaje": "La cuenta no tiene el rol requerido."}
        user_id = identifier(user["id"])
        # La identidad del cuerpo nunca se utiliza para autorizar ni auditar.
        data = {k: v for k, v in payload.items() if k not in {"usuario_id", "accessToken", "refreshToken"}}
        if data.get("accion") == "ver_documento":
            bridge = Bridge()
            document = bridge.call("documento_accesible", {"usuario_id_verificado": user_id, "documento_id": identifier(data.get("documento_id"))})
            if not document:
                return {"ok": False, "http_code": 404, "mensaje": "Documento no disponible para esta cuenta."}
            content = bridge.download(document["storage_file_id"])
            return {"ok": True, "http_code": 200, "nombre": document["nombre_original"], "mime_type": document["mime_type"],
                    "contenido_base64": base64.b64encode(content).decode("ascii")}
        return Bridge().call("decision", {"usuario_id_verificado": user_id, "accion": data})
    except (ValueError, KeyError):
        return {"ok": False, "http_code": 400, "mensaje": "La petición contiene un identificador o dato inválido."}
    except requests.RequestException as exc:
        raise HTTPException(503, "No se pudo verificar o registrar la decisión. Reintenta con el mismo accion_id.") from exc


@app.post("/maintenance", dependencies=[Depends(internal)])
def maintenance():
    """Solo limpia caché de extracción; no borra originales ni observaciones de Nhost."""
    import time
    removed = 0
    limit = time.time() - 30 * 86400
    folder = Path(os.getenv("E3_CACHE_DIR", "/datos/extracciones"))
    if folder.exists():
        for path in folder.glob("*.json"):
            if path.stat().st_mtime < limit:
                path.unlink()
                removed += 1
    return {"cache_eliminada": removed}
