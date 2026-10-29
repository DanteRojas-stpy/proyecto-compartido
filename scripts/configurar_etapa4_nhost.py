"""Publica el estado y los resultados de E4/E5 en Hasura para el rol user, sin poner secretos en el frontend.

Requiere la migración 017. Solo lectura de las solicitudes propias; solicitar E4/E5 pasa por la Function e4-operar."""
from __future__ import annotations

import argparse
import copy
import getpass
import json
import urllib.request
from pathlib import Path

TABLES = {
    # Estado para los botones y el cuadro; sin token, intentos ni errores internos.
    "e4_estado_solicitud": ["solicitud_id", "finales_e3", "e4_estado", "e4_solicitada_at", "e4_error", "homologacion_id", "estado_revision",
                            "homologada_at", "e4_modelo", "cuadro_id", "e5_estado", "e5_revision", "nombre_archivo", "cuadro_storage_file_id",
                            "cuadro_at", "e5_error"],
    "e4_homologaciones": ["id", "solicitud_id", "estado_revision", "resultado", "version_ids", "huella", "modelo", "tokens_entrada", "tokens_salida", "created_at"],
    "e5_cuadros": ["id", "homologacion_id", "solicitud_id", "revision", "estado", "nombre_archivo", "storage_file_id", "validacion", "created_at", "finished_at"],
}


def operations(metadata: dict) -> list[dict]:
    source = next(x for x in metadata["sources"] if x["name"] == "default")
    existing = {x["table"]["name"]: x for x in source["tables"] if x["table"].get("schema") == "public"}
    actions = []
    # Solo relaciones y permisos de las tablas de E4/E5; no se tocan los de E1, E2 ni E3.
    relations = []
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
            raise ValueError("La preparación de E4/E5 contiene una operación no admitida.")
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
    print("Estado y resultados de E4/E5 publicados. Los usuarios solo leen sus solicitudes; solicitar E4/E5 pasa por la Function e4-operar.")


if __name__ == "__main__":
    main()
