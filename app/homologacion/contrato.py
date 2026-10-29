"""Contrato con el modelo de E4: instrucciones, formato de respuesta y petición a Claude.

El modelo decide relaciones y equivalencias; nunca escribe importes. Los números los copia después el código
desde los resultados de E3 (construir.py), de modo que ninguna cifra depende del criterio del modelo.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

SKILL = Path(__file__).parent / "skill"
ESTADOS_OFERTA = ["cotizado", "incluido_con_evidencia", "global", "no_cotizado", "pendiente"]
EQUIVALENCIAS = ["equivalente", "no_equivalente", "pendiente"]
TIPOS_DIFERENCIA = ["precio", "alcance", "plazo", "moneda", "forma_de_pago", "vigencia", "especificacion", "metrado"]

TEXTO = {"type": "string"}
TEXTO_O_NULO = {"type": ["string", "null"]}
IDS = {"type": "array", "items": TEXTO}


def objeto(propiedades: dict) -> dict:
    return {"type": "object", "properties": propiedades, "required": list(propiedades), "additionalProperties": False}


SALIDA = objeto({
    "especialidad": objeto({"codigo": TEXTO_O_NULO, "nombre": TEXTO}),
    "base": objeto({"tipo": {"type": "string", "enum": ["itemizado", "provisional"]}, "origen_proveedor_id": TEXTO_O_NULO, "nota": TEXTO_O_NULO}),
    "partidas": {"type": "array", "items": objeto({
        "codigo": TEXTO_O_NULO, "descripcion": TEXTO, "unidad": TEXTO_O_NULO, "metrado": {"type": ["number", "null"]},
        "ofertas": {"type": "array", "items": objeto({
            "proveedor_id": TEXTO, "item_ids": IDS, "estado": {"type": "string", "enum": ESTADOS_OFERTA},
            "equivalencia": {"type": "string", "enum": EQUIVALENCIAS}, "evidencia_ids": IDS, "nota": TEXTO_O_NULO})}})},
    "adicionales": {"type": "array", "items": objeto({"proveedor_id": TEXTO, "item_id": TEXTO, "motivo": TEXTO})},
    "pendientes": {"type": "array", "items": objeto({
        "proveedor_id": TEXTO_O_NULO, "partida_codigo": TEXTO_O_NULO, "partida_descripcion": TEXTO_O_NULO, "motivo": TEXTO,
        "bloquea_comparacion": {"type": "boolean"}, "decision_requerida": TEXTO, "evidencia_ids": IDS})},
    "diferencias": {"type": "array", "items": objeto({
        "tipo": {"type": "string", "enum": TIPOS_DIFERENCIA}, "detalle": TEXTO, "proveedor_ids": IDS, "evidencia_ids": IDS})},
})

INSTRUCCIONES = """Eres el homologador de CostFlow (E4). Aplica el método de las instrucciones anteriores a las cotizaciones finales que recibes.

Entrada (JSON): la solicitud, la base (itemizado o provisional), los postores con sus ítems, importes originales,
especificaciones, observaciones de E3 y decisiones del especialista, las evidencias citables y los proveedores sin final.
Salida: SOLO un objeto JSON con el esquema indicado, sin texto adicional ni bloques de código.

Reglas de esta entrega:
- NO escribas importes, cantidades ni precios: relaciona por identificador. El sistema copia los números desde E3.
- Cada oferta lista los item_ids del proveedor que cubren esa partida. Usa solo identificadores que aparezcan en la entrada.
- Un ítem va en UNA partida, salvo un precio global que cubra varias: entonces estado «global» en cada una.
- Un ítem que no corresponde a ninguna partida va en «adicionales». Un proveedor que no cotiza una partida va con estado
  «no_cotizado» y sin item_ids. Una inclusión sin evidencia no es «incluido_con_evidencia».
- Equivalencia: «equivalente» exige evidencia_ids. Si dudas, «pendiente» y un pendiente con la pregunta concreta. Una partida
  técnicamente distinta es «no_equivalente», aunque sea más barata.
- Base «itemizado»: usa exactamente las partidas de la entrada (mismo código, unidad y metrado). Base «provisional»: propón las
  partidas desde el desglose más completo, con codigo null, y deja el metrado en null salvo que venga de la cantidad de un ítem.
- No elijas proveedor, no adjudiques, no inventes tipo de cambio, IGV, plazos ni inclusiones. Dato ausente: null.
- Señala diferencias de alcance, especificación, plazo, forma de pago, vigencia y precio con sus evidencias.
- Los pendientes que impiden comparar (equivalencia sin resolver, partida distinta) llevan bloquea_comparacion true.
"""


def _sin_cabecera(texto: str) -> str:
    return re.sub(r"\A---\n.*?\n---\n", "", texto, flags=re.S).strip()


def system_prompt() -> str:
    partes = [_sin_cabecera((SKILL / "SKILL.md").read_text(encoding="utf-8"))]
    for nombre in ("metodo-homologacion.md", "criterios-por-especialidad.md", "salida-homologacion.md"):
        partes.append(_sin_cabecera((SKILL / "references" / nombre).read_text(encoding="utf-8")))
    partes.append(INSTRUCCIONES)
    partes.append("Esquema JSON de la respuesta:\n" + json.dumps(SALIDA, ensure_ascii=False))
    return "\n\n".join(partes)


def request(preparado: dict, model: str) -> dict:
    """Cuerpo para la API de mensajes de Claude. Sin temperature ni tool_choice, que los modelos 5.x rechazan."""
    entrada = {k: preparado[k] for k in ("solicitud", "base", "postores", "evidencias", "sin_final")}
    return {"model": model, "max_tokens": 16000, "system": system_prompt(),
            "messages": [{"role": "user", "content": json.dumps(entrada, ensure_ascii=False)}],
            "output_config": {"effort": "medium"}}


def parse_text(texto: str) -> dict:
    """Lee el primer objeto JSON de la respuesta (tolera bloques de código y texto antes o después) y valida su forma."""
    limpio = re.sub(r"^```(?:json)?\s*", "", texto.strip(), flags=re.I)
    inicio = limpio.find("{")
    if inicio < 0:
        raise ValueError("El modelo no devolvió un objeto JSON.")
    try:
        datos, _ = json.JSONDecoder().raw_decode(limpio[inicio:])
    except json.JSONDecodeError as error:
        raise ValueError(f"El modelo no devolvió un objeto JSON válido: {error.msg}.") from error
    Draft202012Validator(SALIDA).validate(datos)
    return datos
