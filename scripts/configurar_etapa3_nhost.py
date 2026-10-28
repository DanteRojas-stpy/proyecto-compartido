"""Publica consultas y permisos de E3 en Hasura sin poner secretos en el frontend."""
from __future__ import annotations

import argparse
import copy
import getpass
import json
import urllib.request
from pathlib import Path

TABLES = {
    "e3_bandeja_versiones": ["version_id", "correo_id", "solicitud_id", "proveedor_id", "numero_version", "es_final", "estado_procesamiento", "intentos", "legado", "recibido_at", "estado_correo", "error_visible", "documentos"],
    "e3_resultados": ["version_id", "correo_id", "solicitud_id", "proveedor_id", "resultado", "modelo", "uso_ocr", "uso_rag", "created_at"],
    "e3_versiones_estructuradas": ["version_id", "correo_id", "solicitud_id", "proveedor_id", "numero_version", "es_final", "estado_procesamiento", "resultado"],
    "e3_finales_e4": ["version_id", "correo_id", "solicitud_id", "proveedor_id", "numero_version", "es_final", "estado_procesamiento", "resultado"],
    "e3_observaciones": ["id", "version_id", "documento_id", "tipo", "descripcion", "severidad", "requiere_aclaracion", "estado", "evidencia_ids", "motivo_descarte", "decidido_por", "decidido_at", "created_at"],
    "e3_evidencias": ["id", "version_id", "documento_id", "fragmento_id", "campo", "texto_fuente", "ubicacion", "confianza", "datos"],
    "e3_items": ["id", "version_id", "documento_id", "datos"],
    "e3_especificaciones": ["id", "version_id", "documento_id", "datos"],
    "e3_decisiones": ["id", "version_id", "correo_id", "usuario_id", "accion", "motivo", "medio", "observacion_id", "resultado", "created_at"],
    "e3_aclaraciones": ["id", "version_id", "decision_id", "usuario_id", "motivo", "medio", "observacion_ids", "created_at"],
    "e3_ejecuciones": ["id", "version_id", "correo_id", "ciclo", "intento", "fase", "estado", "started_at", "finished_at"],
}


def operations(metadata: dict) -> list[dict]:
    source = next(x for x in metadata["sources"] if x["name"] == "default")
    existing = {x["table"]["name"]: x for x in source["tables"] if x["table"].get("schema") == "public"}
    actions = []
    # Solo relaciones nuevas; no se reemplazan permisos de E1/E2.
    relations = [("versiones_cotizacion", "solicitud_e3", "solicitudes_cotizacion", {"solicitud_id": "id"})]
    for table, columns in TABLES.items():
        if table not in existing:
            actions.append({"type": "pg_track_table", "args": {"source": "default", "table": {"schema": "public", "name": table}}})
        direct = "solicitud_id" in columns
        relations.append((table, "solicitud_e3" if direct else "version_e3", "solicitudes_cotizacion" if direct else "versiones_cotizacion",
                          {"solicitud_id": "id"} if direct else {"version_id": "id"}))
    for table, name, remote, mapping in relations:
        if not any(r["name"] == name for r in existing.get(table, {}).get("object_relationships", [])):
            actions.append({"type": "pg_create_object_relationship", "args": {"source": "default", "table": {"schema": "public", "name": table},
                "name": name, "using": {"manual_configuration": {"remote_table": {"schema": "public", "name": remote}, "column_mapping": mapping, "insertion_order": None}}}})
    # El propietario se comprueba sin permitir a un cliente declarar usuario_id.
    owner = {"_or": [{"creado_por": {"_eq": "X-Hasura-User-Id"}}, {"proyecto_asociado": {"responsable_id": {"_eq": "X-Hasura-User-Id"}}}]}
    for table, columns in TABLES.items():
        if any(p["role"] == "user" for p in existing.get(table, {}).get("select_permissions", [])):
            actions.append({"type": "pg_drop_select_permission", "args": {"source": "default", "table": {"schema": "public", "name": table}, "role": "user"}})
        rule = {"solicitud_e3": owner} if "solicitud_id" in columns else {"version_e3": {"solicitud_e3": owner}}
        actions.append({"type": "pg_create_select_permission", "args": {"source": "default", "table": {"schema": "public", "name": table}, "role": "user",
            "permission": {"columns": columns, "filter": rule, "allow_aggregations": True}}})
    return actions


def replacement(snapshot: dict) -> dict:
    """Prepara un cambio atómico y rechaza sobrescribir una revisión concurrente."""
    if not isinstance(snapshot.get("resource_version"), int) or "metadata" not in snapshot:
        raise ValueError("Hasura debe exportar la revisión de configuración (export_metadata versión 2).")
    metadata = copy.deepcopy(snapshot["metadata"])
    actions = operations(metadata)
    source = next(x for x in metadata["sources"] if x["name"] == "default")
    tables = {t["table"]["name"]: t for t in source["tables"] if t["table"].get("schema") == "public"}
    for action in actions:
        kind, args = action["type"], action["args"]
        name = args["table"]["name"]
        if kind == "pg_track_table":
            table = {"table": args["table"]}
            source["tables"].append(table)
            tables[name] = table
        elif kind == "pg_create_object_relationship":
            tables[name].setdefault("object_relationships", []).append({"name": args["name"], "using": args["using"]})
        elif kind == "pg_drop_select_permission":
            tables[name]["select_permissions"] = [p for p in tables[name].get("select_permissions", []) if p["role"] != args["role"]]
        elif kind == "pg_create_select_permission":
            tables[name].setdefault("select_permissions", []).append({"role": args["role"], "permission": args["permission"]})
        else:
            raise ValueError("La preparación de E3 contiene una operación no admitida.")
    return {"type": "replace_metadata", "version": 2, "resource_version": snapshot["resource_version"],
            "args": {"allow_inconsistent_metadata": False, "metadata": metadata}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Base Hasura administrativa, sin /v1/metadata")
    parser.add_argument("--respaldo", required=True, type=Path)
    args = parser.parse_args()
    url = args.url.rstrip("/").removesuffix("/v1/metadata") + "/v1/metadata"
    if not url.startswith("https://"):
        raise ValueError("La conexión administrativa remota debe ser HTTPS.")
    secret = getpass.getpass("Hasura admin secret (no se guarda): ")

    def send(body):
        request = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
            headers={"Content-Type": "application/json", "x-hasura-admin-secret": secret})
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.load(response)
    snapshot = send({"type": "export_metadata", "version": 2, "args": {}})
    args.respaldo.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    send(replacement(snapshot))
    send({"type": "reload_metadata", "args": {"reload_sources": True}})
    print("Consultas E3/E4 publicadas. Los usuarios solo pueden leer sus solicitudes; las decisiones siguen por n8n.")


if __name__ == "__main__":
    main()
