import json
import uuid
from decimal import Decimal

import pytest
from jsonschema import ValidationError

from app.etapa3 import contract
from app.etapa3.rag import context_batches, index_document


def sample():
    doc, fragment, version, correo, solicitud, proveedor = [str(uuid.uuid4()) for _ in range(6)]
    text = "Equipo A cantidad 2 UND precio USD 100 parcial 200 subtotal 200 impuestos 36 total 236 plazo 7 dias pago contado vigencia 30 dias"
    source = {"documento_id": doc, "storage_file_id": str(uuid.uuid4()), "sha256": "a" * 64,
              "nombre_original": "ejemplo.pdf", "mime_type": "application/pdf", "tamano_bytes": 100,
              "fragmentos": [{"id": fragment, "documento_id": doc, "texto": text, "ubicacion": {"pagina": 1}}],
              "paginas": [{"pagina": 1, "procesada": True}], "hojas": [], "uso_ocr": False, "uso_rag": True, "observaciones": []}
    data = {"comerciales": [{"documento_id": doc, "valores": {"moneda": "USD", "subtotal": 200, "impuestos": 36, "total": 236,
             "plazo_entrega": "7 dias", "condiciones_pago": "contado", "vigencia_oferta": "30 dias"},
             "originales": {"moneda": "USD", "subtotal": "200", "impuestos": "36", "total": "236",
             "plazo_entrega": "7 dias", "condiciones_pago": "contado", "vigencia_oferta": "30 dias"}, "evidencia_ids": ["e1"]}],
        "items": [{"documento_id": doc, "referencia_item": "A", "descripcion": "Equipo A", "cantidad": 2, "unidad": "UND", "unidad_normalizada": "unidad",
                   "precio_unitario": 100, "parcial": 200, "originales": {"descripcion": "Equipo A", "cantidad": "2", "unidad": "UND", "precio_unitario": "100", "parcial": "200"}, "evidencia_ids": ["e1"]}],
        "especificaciones_tecnicas": [], "evidencias": [{"id": "e1", "fragmento_id": fragment, "documento_id": doc, "campo": "oferta", "texto_fuente": text, "confianza": .99}],
        "observaciones": [], "documentos": [{"documento_id": doc, "tipo_documental": "cotizacion_proveedor"}], "inferencias": []}
    context = {"id": version, "correo_id": correo, "solicitud_id": solicitud, "proveedor_id": proveedor, "version": 1, "es_final": False}
    return data, source, context


def test_modelo_estructura_y_trazabilidad_sin_excel():
    data, source, context = sample()
    result = contract.combine([data], [source], context, "gemini-prueba")
    assert result["estado_procesamiento"] == "completado"
    assert result["items"][0]["precio_unitario"] == 100
    assert result["evidencias"][0]["ubicacion"]["pagina"] == 1
    assert result["correo_id"] == context["correo_id"]
    assert result["es_final"] is False


def test_respuesta_truncada_y_esquema_en_lugar_de_datos_se_rechazan():
    with pytest.raises(ValueError):
        contract.parse_response({"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{}"}]}}]})
    with pytest.raises(ValidationError):
        contract.parse_response({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(contract.SCHEMA)}]}}]})


def test_cita_inventada_y_documento_de_otra_version_se_rechazan():
    data, source, context = sample()
    data["evidencias"][0]["texto_fuente"] = "dato que no existe"
    with pytest.raises(ValueError):
        contract.combine([data], [source], context, "gemini-prueba")
    data, source, context = sample()
    data["items"][0]["documento_id"] = str(uuid.uuid4())
    with pytest.raises(ValueError):
        contract.combine([data], [source], context, "gemini-prueba")


def test_incoherencia_aritmetica_independiente_de_gemini():
    data, source, context = sample()
    data["items"][0]["cantidad"] = 3
    data["items"][0]["originales"]["cantidad"] = "3"
    source["fragmentos"][0]["texto"] += " cantidad 3"
    data["evidencias"][0]["texto_fuente"] = source["fragmentos"][0]["texto"]
    result = contract.combine([data], [source], context, "gemini-prueba")
    assert any(o["tipo"] == "incoherencia_parcial" and o["requiere_aclaracion"] for o in result["observaciones"])
    assert result["items"][0]["parcial"] == 200  # No corrige el precio del proveedor.


def test_ausente_es_null_y_no_valor_inventado():
    data, source, context = sample()
    data["comerciales"][0]["valores"]["vigencia_oferta"] = None
    data["comerciales"][0]["originales"]["vigencia_oferta"] = None
    result = contract.combine([data], [source], context, "gemini-prueba")
    assert result["datos_comerciales"]["vigencia_oferta"] is None
    assert any(o["tipo"] == "dato_no_encontrado" for o in result["observaciones"])


def test_rag_recupera_por_criterio_y_no_pierde_fragmentos():
    class Embed:
        def embed(self, texts):
            return [[1., len(x) / 100.] for x in texts]
    _, source, _ = sample()
    source["fragmentos"] *= 1
    source["fragmentos"].append({**source["fragmentos"][0], "id": str(uuid.uuid4()), "texto": "Otra sección completa"})
    index_document(source, Embed())
    assert len(source["consultas_rag"]) == 7
    batches = context_batches([source], 200)
    assert {f["id"] for b in batches for f in b} == {f["id"] for f in source["fragmentos"]}
    assert all("embedding" not in f for b in batches for f in b)


@pytest.mark.parametrize("original,expected", [("US$ 1,250.50", Decimal("1250.50")), ("S/ 1.250,50", Decimal("1250.50")), ("1,234", None), ("1.234", None)])
def test_numeros_ambiguos_no_se_adivinan(original, expected):
    assert contract.number(original) == expected
