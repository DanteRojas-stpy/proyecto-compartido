#!/usr/bin/env python3
"""Configura relaciones y permisos de CostFlow en Nhost/Hasura.

El secreto administrativo se solicita de forma oculta y solo se usa en memoria.
"""

from __future__ import annotations

import getpass
import json
import sys
import urllib.error
import urllib.request


ROLE = "user"
SESSION_USER = "X-Hasura-User-Id"
SOURCE = "default"


def request_metadata(base_url: str, secret: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{base_url}/v1/metadata",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-hasura-admin-secret": secret,
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body else {}


def normalize_url(value: str) -> str:
    url = value.strip().rstrip("/")
    for suffix in ("/v1/graphql", "/v1/auth", "/v1/storage", "/v1/metadata"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    if not url.startswith("https://"):
        raise ValueError("La URL debe comenzar con https://")
    return url


def table_metadata(metadata: dict, schema: str, name: str) -> dict:
    for source in metadata.get("sources", []):
        if source.get("name") != SOURCE:
            continue
        for table in source.get("tables", []):
            identifier = table.get("table", {})
            if identifier.get("schema") == schema and identifier.get("name") == name:
                return table
    return {}


def relationship_exists(table: dict, name: str) -> bool:
    relationships = table.get("object_relationships", [])
    return any(item.get("name") == name for item in relationships)


def permission_exists(table: dict, action: str) -> bool:
    return any(
        item.get("role") == ROLE
        for item in table.get(f"{action}_permissions", [])
    )


def relationship_operation(table: str, name: str, foreign_key: str) -> dict:
    return {
        "type": "pg_create_object_relationship",
        "args": {
            "source": SOURCE,
            "table": {"schema": "public", "name": table},
            "name": name,
            "using": {"foreign_key_constraint_on": foreign_key},
        },
    }


def permission_operations(
    metadata: dict, table: str, action: str, permission: dict
) -> list[dict]:
    operations: list[dict] = []
    current = table_metadata(metadata, "public", table)
    common = {
        "source": SOURCE,
        "table": {"schema": "public", "name": table},
        "role": ROLE,
    }
    if permission_exists(current, action):
        operations.append(
            {"type": f"pg_drop_{action}_permission", "args": common.copy()}
        )
    create_args = common.copy()
    create_args["permission"] = permission
    operations.append(
        {"type": f"pg_create_{action}_permission", "args": create_args}
    )
    return operations


def owner_filter(column: str) -> dict:
    return {column: {"_eq": SESSION_USER}}


def main() -> int:
    print("Configuracion automatica de Nhost para CostFlow")
    print("El secreto no se mostrara ni se guardara.\n")
    try:
        base_url = normalize_url(input("Backend URL de Nhost: "))
    except ValueError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    secret = getpass.getpass("HASURA_GRAPHQL_ADMIN_SECRET: ")
    if not secret:
        print("Error: el secreto es obligatorio.", file=sys.stderr)
        return 1

    try:
        metadata = request_metadata(base_url, secret, {"type": "export_metadata", "args": {}})
        operations: list[dict] = []

        relationships = [
            ("solicitudes_cotizacion", "proyecto_asociado", "proyecto_id"),
            ("solicitud_proveedores", "solicitud_cotizacion", "solicitud_id"),
            ("solicitud_proveedores", "proveedor_asociado", "proveedor_id"),
            ("documentos", "solicitud_cotizacion", "solicitud_id"),
            ("partidas", "solicitud_cotizacion", "solicitud_id"),
        ]
        for table, name, foreign_key in relationships:
            current = table_metadata(metadata, "public", table)
            if not relationship_exists(current, name):
                operations.append(relationship_operation(table, name, foreign_key))

        proyecto_filter = owner_filter("responsable_id")
        solicitud_filter = owner_filter("creado_por")
        proveedor_filter = owner_filter("creado_por")
        solicitud_insert_filter = {
            "_and": [
                solicitud_filter,
                {"proyecto_asociado": {"responsable_id": {"_eq": SESSION_USER}}},
            ]
        }
        vinculo_filter = {
            "_and": [
                {"solicitud_cotizacion": solicitud_filter},
                {"proveedor_asociado": proveedor_filter},
            ]
        }
        documento_filter = {
            "_and": [
                owner_filter("subido_por"),
                {"solicitud_cotizacion": solicitud_filter},
            ]
        }
        partida_filter = {"solicitud_cotizacion": solicitud_filter}

        definitions = {
            "proyectos": {
                "select": {
                    "columns": ["id", "responsable_id", "codigo", "nombre", "created_at", "updated_at"],
                    "filter": proyecto_filter,
                    "allow_aggregations": False,
                },
                "insert": {
                    "columns": ["codigo", "nombre"],
                    "check": proyecto_filter,
                    "set": {"responsable_id": SESSION_USER},
                },
                "update": {"columns": ["codigo", "nombre"], "filter": proyecto_filter, "check": None},
                "delete": {"filter": proyecto_filter},
            },
            "solicitudes_cotizacion": {
                "select": {
                    "columns": ["id", "proyecto_id", "creado_por", "codigo", "nombre", "moneda", "vigencia_dias", "fecha_limite", "estado", "created_at", "updated_at"],
                    "filter": solicitud_filter,
                    "allow_aggregations": False,
                },
                "insert": {
                    "columns": ["proyecto_id", "codigo", "nombre", "moneda", "vigencia_dias", "fecha_limite"],
                    "check": solicitud_insert_filter,
                    "set": {"creado_por": SESSION_USER},
                },
                "update": {
                    "columns": ["codigo", "nombre", "moneda", "vigencia_dias", "fecha_limite", "estado"],
                    "filter": solicitud_filter,
                    "check": None,
                },
                "delete": {"filter": solicitud_filter},
            },
            "proveedores": {
                "select": {
                    "columns": ["id", "creado_por", "nombre", "ruc", "correo", "contacto", "telefono", "created_at", "updated_at"],
                    "filter": proveedor_filter,
                    "allow_aggregations": False,
                },
                "insert": {
                    "columns": ["nombre", "ruc", "correo", "contacto", "telefono"],
                    "check": proveedor_filter,
                    "set": {"creado_por": SESSION_USER},
                },
                "update": {
                    "columns": ["nombre", "ruc", "correo", "contacto", "telefono"],
                    "filter": proveedor_filter,
                    "check": None,
                },
                "delete": {"filter": proveedor_filter},
            },
            "solicitud_proveedores": {
                "select": {
                    "columns": ["solicitud_id", "proveedor_id", "estado", "created_at"],
                    "filter": vinculo_filter,
                    "allow_aggregations": False,
                },
                "insert": {"columns": ["solicitud_id", "proveedor_id"], "check": vinculo_filter},
                "update": {"columns": ["estado"], "filter": vinculo_filter, "check": None},
                "delete": {"filter": vinculo_filter},
            },
            "documentos": {
                "select": {
                    "columns": ["id", "solicitud_id", "tipo", "nombre_original", "storage_file_id", "mime_type", "tamano_bytes", "subido_por", "created_at"],
                    "filter": documento_filter,
                    "allow_aggregations": False,
                },
                "insert": {
                    "columns": ["solicitud_id", "tipo", "nombre_original", "storage_file_id", "mime_type", "tamano_bytes"],
                    "check": documento_filter,
                    "set": {"subido_por": SESSION_USER},
                },
                "delete": {"filter": documento_filter},
            },
            "partidas": {
                "select": {
                    "columns": ["id", "solicitud_id", "codigo", "descripcion", "unidad", "metrado", "orden", "created_at"],
                    "filter": partida_filter,
                    "allow_aggregations": False,
                },
                "insert": {
                    "columns": ["solicitud_id", "codigo", "descripcion", "unidad", "metrado", "orden"],
                    "check": partida_filter,
                },
                "update": {
                    "columns": ["codigo", "descripcion", "unidad", "metrado", "orden"],
                    "filter": partida_filter,
                    "check": None,
                },
                "delete": {"filter": partida_filter},
            },
        }

        for table, actions in definitions.items():
            for action, permission in actions.items():
                operations.extend(permission_operations(metadata, table, action, permission))

        request_metadata(base_url, secret, {"type": "bulk", "args": operations})
        print("\nConfiguracion aplicada correctamente.")
        print(f"Relaciones revisadas: {len(relationships)}")
        print(f"Operaciones aplicadas: {len(operations)}")
        return 0
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        print(f"Error HTTP {error.code}: {detail}", file=sys.stderr)
        return 1
    except urllib.error.URLError as error:
        print(f"No se pudo conectar con Nhost: {error.reason}", file=sys.stderr)
        return 1
    finally:
        secret = ""


if __name__ == "__main__":
    raise SystemExit(main())
