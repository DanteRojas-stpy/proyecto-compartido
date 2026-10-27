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
    relationships = (
        table.get("object_relationships", []) + table.get("array_relationships", [])
    )
    return any(item.get("name") == name for item in relationships)


def permission_exists(table: dict, action: str) -> bool:
    return any(
        item.get("role") == ROLE
        for item in table.get(f"{action}_permissions", [])
    )


def relationship_operation(
    table: str, name: str, foreign_key: str | None = None,
    remote_table: str | None = None, column_mapping: dict | None = None,
) -> dict:
    if foreign_key:
        using = {"foreign_key_constraint_on": foreign_key}
    else:
        using = {
            "manual_configuration": {
                "remote_table": {"schema": "public", "name": remote_table},
                "column_mapping": column_mapping,
                "insertion_order": None,
            }
        }
    return {
        "type": "pg_create_object_relationship",
        "args": {
            "source": SOURCE,
            "table": {"schema": "public", "name": table},
            "name": name,
            "using": using,
        },
    }


def array_relationship_operation(
    table: str, name: str, remote_table: str, column_mapping: dict
) -> dict:
    return {
        "type": "pg_create_array_relationship",
        "args": {
            "source": SOURCE,
            "table": {"schema": "public", "name": table},
            "name": name,
            "using": {
                "manual_configuration": {
                    "remote_table": {"schema": "public", "name": remote_table},
                    "column_mapping": column_mapping,
                    "insertion_order": None,
                }
            },
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

        tracked_tables = [
            "correos_proveedor",
            "historial_estados_correo",
            "aclaraciones_proveedor",
            "coordinaciones_proveedor",
            "historial_respuestas_proveedor",
            "notificaciones",
        ]
        for name in tracked_tables:
            if not table_metadata(metadata, "public", name):
                operations.append({
                    "type": "pg_track_table",
                    "args": {"source": SOURCE, "table": {"schema": "public", "name": name}},
                })

        relationships = [
            ("solicitudes_cotizacion", "proyecto_asociado", "proyecto_id", None, None),
            ("solicitud_proveedores", "solicitud_cotizacion", "solicitud_id", None, None),
            ("solicitud_proveedores", "proveedor_asociado", "proveedor_id", None, None),
            ("documentos", "solicitud_cotizacion", "solicitud_id", None, None),
            ("documentos", "proveedor_asociado", "proveedor_id", None, None),
            ("documentos", "correo_origen", "correo_id", None, None),
            ("partidas", "solicitud_cotizacion", "solicitud_id", None, None),
            ("envios_solicitud", "solicitud_cotizacion", None, "solicitudes_cotizacion", {"solicitud_id": "id"}),
            ("envios_solicitud", "proveedor_asociado", None, "proveedores", {"proveedor_id": "id"}),
            ("envios_solicitud", "participacion_seguimiento", None, "solicitud_proveedores", {"solicitud_id": "solicitud_id", "proveedor_id": "proveedor_id"}),
            ("correos_proveedor", "solicitud_cotizacion", None, "solicitudes_cotizacion", {"solicitud_id": "id"}),
            ("correos_proveedor", "proveedor_asociado", None, "proveedores", {"proveedor_id": "id"}),
            ("historial_estados_correo", "correo_asociado", "correo_id", None, None),
            ("historial_estados_correo", "solicitud_cotizacion", None, "solicitudes_cotizacion", {"solicitud_id": "id"}),
            ("historial_estados_correo", "proveedor_asociado", None, "proveedores", {"proveedor_id": "id"}),
            ("aclaraciones_proveedor", "solicitud_cotizacion", None, "solicitudes_cotizacion", {"solicitud_id": "id"}),
            ("aclaraciones_proveedor", "proveedor_asociado", None, "proveedores", {"proveedor_id": "id"}),
            ("aclaraciones_proveedor", "correo_asociado", "correo_id", None, None),
            ("coordinaciones_proveedor", "solicitud_cotizacion", None, "solicitudes_cotizacion", {"solicitud_id": "id"}),
            ("coordinaciones_proveedor", "proveedor_asociado", None, "proveedores", {"proveedor_id": "id"}),
            ("historial_respuestas_proveedor", "solicitud_cotizacion", None, "solicitudes_cotizacion", {"solicitud_id": "id"}),
            ("historial_respuestas_proveedor", "proveedor_asociado", None, "proveedores", {"proveedor_id": "id"}),
            ("historial_respuestas_proveedor", "correo_asociado", "correo_id", None, None),
            ("notificaciones", "solicitud_cotizacion", "solicitud_id", None, None),
            ("notificaciones", "proveedor_asociado", None, "proveedores", {"proveedor_id": "id"}),
        ]
        for table, name, foreign_key, remote_table, column_mapping in relationships:
            current = table_metadata(metadata, "public", table)
            if not relationship_exists(current, name):
                operations.append(relationship_operation(
                    table, name, foreign_key, remote_table, column_mapping
                ))

        solicitud_proveedores_metadata = table_metadata(
            metadata, "public", "solicitud_proveedores"
        )
        if not relationship_exists(
            solicitud_proveedores_metadata, "aclaraciones_pendientes"
        ):
            operations.append(array_relationship_operation(
                "solicitud_proveedores",
                "aclaraciones_pendientes",
                "aclaraciones_proveedor",
                {"solicitud_id": "solicitud_id", "proveedor_id": "proveedor_id"},
            ))

        correos_metadata = table_metadata(metadata, "public", "correos_proveedor")
        relaciones_correo = [
            ("documentos_recuperados", "documentos"),
            ("historial_estados", "historial_estados_correo"),
            ("aclaraciones_detectadas", "aclaraciones_proveedor"),
        ]
        for name, remote_table in relaciones_correo:
            if not relationship_exists(correos_metadata, name):
                operations.append(array_relationship_operation(
                    "correos_proveedor", name, remote_table, {"id": "correo_id"}
                ))

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
        seguimiento_filter = {"solicitud_cotizacion": solicitud_filter}
        notificacion_filter = owner_filter("usuario_id")

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
                    "columns": ["id", "proyecto_id", "creado_por", "codigo", "tipo", "numero", "nombre", "moneda", "vigencia_dias", "fecha_limite", "partida_critica", "frecuencia_aviso_dias", "estado", "preparada_para_envio", "cerrada_at", "created_at", "updated_at"],
                    "filter": solicitud_filter,
                    "allow_aggregations": False,
                },
                "insert": {
                    "columns": ["proyecto_id", "tipo", "nombre", "moneda", "fecha_limite", "partida_critica"],
                    "check": solicitud_insert_filter,
                    "set": {"creado_por": SESSION_USER},
                },
                "update": {
                    "columns": ["nombre", "moneda", "fecha_limite", "partida_critica", "estado", "preparada_para_envio"],
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
                    "columns": ["solicitud_id", "proveedor_id", "estado", "estado_respuesta", "detalle_respuesta", "considerado", "numero_coordinaciones", "ultimo_correo_at", "proximo_seguimiento_at", "origen_clasificacion", "confianza_clasificacion", "evidencia_clasificacion", "created_at", "updated_at"],
                    "filter": vinculo_filter,
                    "allow_aggregations": False,
                },
                "insert": {"columns": ["solicitud_id", "proveedor_id"], "check": vinculo_filter},
                "update": {
                    "columns": ["estado", "estado_respuesta", "detalle_respuesta"],
                    "filter": vinculo_filter,
                    "check": None,
                    "set": {"origen_clasificacion": "usuario"},
                },
                "delete": {"filter": vinculo_filter},
            },
            "documentos": {
                "select": {
                    "columns": ["id", "solicitud_id", "proveedor_id", "correo_id", "tipo", "nombre_original", "storage_file_id", "mime_type", "tamano_bytes", "version", "documento_estado", "subido_por", "created_at"],
                    "filter": documento_filter,
                    "allow_aggregations": False,
                },
                "insert": {
                    "columns": ["solicitud_id", "proveedor_id", "correo_id", "tipo", "nombre_original", "storage_file_id", "mime_type", "tamano_bytes", "version"],
                    "check": documento_filter,
                    "set": {"subido_por": SESSION_USER},
                },
                "update": {
                    "columns": ["documento_estado"],
                    "filter": documento_filter,
                    "check": None,
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
            "correos_proveedor": {
                "select": {
                    "columns": ["id", "solicitud_id", "proveedor_id", "gmail_message_id", "gmail_thread_id", "remitente", "destinatarios", "asunto", "cuerpo_texto", "adjuntos", "recibido_at", "fuera_plazo", "analisis_agente", "estado_correo", "origen_estado", "estado_asignado_por", "estado_asignado_at", "created_at"],
                    "filter": seguimiento_filter,
                    "allow_aggregations": False,
                },
                "update": {
                    "columns": ["estado_correo"],
                    "filter": seguimiento_filter,
                    "check": None,
                },
            },
            "historial_estados_correo": {
                "select": {
                    "columns": ["id", "correo_id", "solicitud_id", "proveedor_id", "estado_anterior", "estado_nuevo", "origen", "cambiado_por", "created_at"],
                    "filter": seguimiento_filter,
                    "allow_aggregations": False,
                },
            },
            "aclaraciones_proveedor": {
                "select": {
                    "columns": ["id", "solicitud_id", "proveedor_id", "correo_id", "dedupe_key", "descripcion", "estado", "resuelta_por", "resuelta_at", "created_at"],
                    "filter": seguimiento_filter,
                    "allow_aggregations": False,
                },
                "update": {"columns": ["estado"], "filter": seguimiento_filter, "check": None},
            },
            "coordinaciones_proveedor": {
                "select": {
                    "columns": ["id", "solicitud_id", "proveedor_id", "medio", "comentario", "registrado_por", "created_at"],
                    "filter": seguimiento_filter,
                    "allow_aggregations": False,
                },
                "insert": {
                    "columns": ["solicitud_id", "proveedor_id", "medio", "comentario"],
                    "check": seguimiento_filter,
                    "set": {"registrado_por": SESSION_USER},
                },
            },
            "historial_respuestas_proveedor": {
                "select": {
                    "columns": ["id", "solicitud_id", "proveedor_id", "correo_id", "estado_anterior", "estado_nuevo", "detalle_anterior", "detalle_nuevo", "considerado_anterior", "considerado_nuevo", "origen", "confianza", "evidencia", "cambiado_por", "created_at"],
                    "filter": seguimiento_filter,
                    "allow_aggregations": False,
                },
            },
            "notificaciones": {
                "select": {
                    "columns": ["id", "usuario_id", "solicitud_id", "proveedor_id", "tipo", "titulo", "mensaje", "estado", "datos", "created_at", "leida_at", "atendida_at"],
                    "filter": notificacion_filter,
                    "allow_aggregations": False,
                },
                "update": {"columns": ["estado"], "filter": notificacion_filter, "check": None},
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
