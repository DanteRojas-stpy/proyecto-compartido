"""Construye homologacion.json: valida las relaciones del modelo y copia los números desde E3.

Toda cifra sale de los resultados de E3; el modelo solo decide relaciones y equivalencias. Si la respuesta
cita algo que no existe en la entrada, se rechaza en lugar de corregirla.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from jsonschema import Draft202012Validator, ValidationError

from .contrato import SALIDA

TOLERANCIA = Decimal("0.02")


class HomologacionInvalida(ValueError):
    def __init__(self, errores: list[str]):
        super().__init__("; ".join(errores[:6]) + (f" (+{len(errores) - 6} más)" if len(errores) > 6 else ""))
        self.errores = errores


def numero(valor) -> Decimal | None:
    return None if valor is None else Decimal(str(valor))


def condicion(postor: dict, campo: str):
    """El valor consolidado o, si falta, los de cada documento sin repetirlos."""
    valor = postor["comercial"].get(campo)
    if valor is not None:
        return valor
    distintos = list(dict.fromkeys(c["valores"].get(campo) for c in postor["comercial_por_documento"] if c["valores"].get(campo)))
    return " / ".join(distintos) if distintos else None


def build(preparado: dict, salida: dict, modelo: str, ahora: datetime | None = None) -> dict:
    try:
        Draft202012Validator(SALIDA).validate(salida)
    except ValidationError as error:
        raise HomologacionInvalida([f"La respuesta no cumple el formato: {error.message[:160]}"]) from error
    errores: list[str] = []
    postores = {p["proveedor_id"]: p for p in preparado["postores"]}
    items = {i["item_id"]: (p["proveedor_id"], i) for p in postores.values() for i in p["items"]}
    evidencias = {e["id"] for e in preparado["evidencias"]}
    base = preparado["base"]
    pendientes = [dict(p, origen="modelo") for p in salida["pendientes"]]
    sin_final_ids = {p["proveedor_id"] for p in preparado["sin_final"]}

    def comprobar_evidencias(ids, donde):
        for evidencia_id in ids:
            if evidencia_id not in evidencias:
                errores.append(f"{donde}: la evidencia {evidencia_id[:8]} no existe en la entrada")

    # Base: con itemizado las partidas son exactamente las de la solicitud.
    if base["tipo"] == "itemizado":
        esperadas = {p["codigo"]: p for p in base["partidas"]}
        recibidas = {p["codigo"]: p for p in salida["partidas"]}
        if len(recibidas) != len(salida["partidas"]) or set(recibidas) != set(esperadas):
            errores.append("Las partidas devueltas no coinciden con el itemizado de la solicitud")
        else:
            for codigo, esperada in esperadas.items():
                if recibidas[codigo]["unidad"] != esperada["unidad"] or numero(recibidas[codigo]["metrado"]) != numero(esperada["metrado"]):
                    errores.append(f"La partida {codigo} cambió la unidad o el metrado del itemizado")
    elif salida["base"]["tipo"] != "provisional":
        errores.append("Sin itemizado cargado la base solo puede ser provisional")

    # Cada ítem va en una sola partida (salvo precio global) y pertenece al proveedor que la ofrece.
    ubicaciones: dict[str, list[str]] = {}
    for partida in salida["partidas"]:
        etiqueta = partida["codigo"] or partida["descripcion"][:40]
        vistos = set()
        for oferta in partida["ofertas"]:
            proveedor = oferta["proveedor_id"]
            if proveedor not in postores:
                errores.append(f"Partida {etiqueta}: el proveedor {proveedor[:8]} no tiene versión final")
                continue
            if proveedor in vistos:
                errores.append(f"Partida {etiqueta}: el proveedor {proveedor[:8]} aparece dos veces")
            vistos.add(proveedor)
            comprobar_evidencias(oferta["evidencia_ids"], f"Partida {etiqueta}")
            if oferta["estado"] == "no_cotizado" and oferta["item_ids"]:
                errores.append(f"Partida {etiqueta}: una oferta «no_cotizado» no puede traer ítems")
            if oferta["estado"] in ("cotizado", "global") and not oferta["item_ids"]:
                errores.append(f"Partida {etiqueta}: una oferta «{oferta['estado']}» necesita ítems")
            if oferta["equivalencia"] == "equivalente" and not oferta["evidencia_ids"]:
                errores.append(f"Partida {etiqueta}: la equivalencia de {proveedor[:8]} no cita evidencia")
            for item_id in oferta["item_ids"]:
                if item_id not in items or items[item_id][0] != proveedor:
                    errores.append(f"Partida {etiqueta}: el ítem {item_id[:8]} no pertenece a {proveedor[:8]}")
                else:
                    ubicaciones.setdefault(item_id, []).append(oferta["estado"])
        if base["tipo"] == "provisional" and partida["metrado"] is not None:
            cantidades = {numero(items[i][1]["cantidad"]) for o in partida["ofertas"] for i in o["item_ids"] if i in items}
            for o in partida["ofertas"]:
                suma = [numero(items[i][1]["cantidad"]) for i in o["item_ids"] if i in items]
                if suma and all(x is not None for x in suma):
                    cantidades.add(sum(suma))
            if numero(partida["metrado"]) not in cantidades:
                errores.append(f"Partida {etiqueta}: el metrado no coincide con ninguna cantidad cotizada")
    for item_id, estados in ubicaciones.items():
        if len(estados) > 1 and any(e != "global" for e in estados):
            errores.append(f"El ítem {item_id[:8]} está en varias partidas sin ser un precio global")
    adicionales = []
    for extra in salida["adicionales"]:
        if extra["item_id"] not in items or items[extra["item_id"]][0] != extra["proveedor_id"]:
            errores.append(f"Adicional: el ítem {extra['item_id'][:8]} no pertenece a {extra['proveedor_id'][:8]}")
        elif extra["item_id"] in ubicaciones:
            errores.append(f"El ítem {extra['item_id'][:8]} está a la vez en una partida y en adicionales")
        else:
            adicionales.append(extra)
    for diferencia in salida["diferencias"]:
        comprobar_evidencias(diferencia["evidencia_ids"], "Diferencia")
        for proveedor in diferencia["proveedor_ids"]:
            if proveedor not in postores:
                errores.append(f"Diferencia: el proveedor {proveedor[:8]} no tiene versión final")
    for pendiente in pendientes:
        comprobar_evidencias(pendiente["evidencia_ids"], "Pendiente")
        if pendiente["proveedor_id"] is not None and pendiente["proveedor_id"] not in postores and pendiente["proveedor_id"] not in sin_final_ids:
            errores.append(f"Pendiente: el proveedor {pendiente['proveedor_id'][:8]} no es de esta solicitud")
    if errores:
        raise HomologacionInvalida(errores)

    # Lo que el modelo no relacionó no se pierde: queda como adicional y pendiente.
    colocados = set(ubicaciones) | {a["item_id"] for a in adicionales}
    for item_id, (proveedor, item) in items.items():
        if item_id not in colocados:
            adicionales.append({"proveedor_id": proveedor, "item_id": item_id, "motivo": "El modelo no lo relacionó con ninguna partida."})
            pendientes.append({"proveedor_id": proveedor, "partida_codigo": None, "partida_descripcion": item["descripcion"], "origen": "sistema",
                               "motivo": "Un ítem cotizado no quedó relacionado con la base.", "bloquea_comparacion": True,
                               "decision_requerida": "Relacionar el ítem con una partida o aceptarlo como adicional.", "evidencia_ids": item["evidencia_ids"]})

    # La moneda de comparación se resolvió al preparar la entrada (entrada.prepare) y es la misma que vio el modelo.
    moneda_comparacion = preparado["solicitud"]["moneda_comparacion"]

    def sistema(proveedor, motivo, decision, bloquea):
        pendientes.append({"proveedor_id": proveedor, "partida_codigo": None, "partida_descripcion": None, "origen": "sistema", "motivo": motivo,
                           "bloquea_comparacion": bloquea, "decision_requerida": decision, "evidencia_ids": []})

    if base["tipo"] == "provisional":
        sistema(None, "El itemizado de la solicitud no está cargado: la base de comparación es provisional.",
                "Cargar el itemizado o aprobar la base provisional.", True)
    for sin in preparado["sin_final"]:
        if any(p["proveedor_id"] == sin["proveedor_id"] for p in pendientes):
            continue
        sistema(sin["proveedor_id"], f"{sin['nombre']} no tiene una cotización aceptada como final.", "Esperar o aceptar su cotización; no entra en la comparación.", False)

    salida_postores = []
    for p in postores.values():
        comparable = p["moneda"] == moneda_comparacion
        if not p["moneda"]:
            sistema(p["proveedor_id"], f"No se identificó la moneda de la oferta de {p['nombre']}.", "Confirmar la moneda con el proveedor.", True)
        elif not comparable:
            sistema(p["proveedor_id"], f"La oferta de {p['nombre']} está en {p['moneda']} y la comparación en {moneda_comparacion}.",
                    "Autorizar un tipo de cambio con fecha y fuente.", True)
        if p["comercial"].get("impuestos") is None and not any(c["valores"].get("impuestos") is not None for c in p["comercial_por_documento"]):
            sistema(p["proveedor_id"], f"No se conoce el IGV de la oferta de {p['nombre']}; los precios se comparan tal como se cotizaron.",
                    "Confirmar si los precios incluyen IGV.", False)
        if p["comercial"].get("vigencia_oferta") is None and not any(c["valores"].get("vigencia_oferta") for c in p["comercial_por_documento"]):
            sistema(p["proveedor_id"], f"La oferta de {p['nombre']} no indica su vigencia.", "Consultar la vigencia con el proveedor.", False)
        for c in p["comercial_por_documento"]:
            suma = [numero(i["parcial"]) for i in p["items"] if i["documento_id"] == c["documento_id"]]
            subtotal = numero(c["valores"].get("subtotal"))
            if subtotal is not None and suma and all(x is not None for x in suma) and abs(sum(suma) - subtotal) > TOLERANCIA:
                sistema(p["proveedor_id"], f"En {p['nombre']}, la suma de parciales ({sum(suma)}) no coincide con el subtotal ({subtotal}).",
                        "Revisar descuentos, cargos o ítems faltantes.", False)
        abiertas = [o for o in p["observaciones"] if o["requiere_aclaracion"] and o["estado"] in ("pendiente", "aclaracion_solicitada")]
        if abiertas:
            sistema(p["proveedor_id"], f"{p['nombre']}: el especialista aceptó la versión con {len(abiertas)} observaciones de lectura sin resolver.",
                    "Revisarlas si afectan la comparación.", False)
        salida_postores.append({
            "proveedor_id": p["proveedor_id"], "nombre": p["nombre"], "version_id": p["version_id"], "numero_version": p["numero_version"],
            "moneda": p["moneda"], "comparable_en_moneda_de_comparacion": comparable,
            "totales_originales": {c: p["comercial"].get(c) for c in ("subtotal", "impuestos", "total")},
            "totales_por_documento": [{"documento_id": c["documento_id"], **{k: c["valores"].get(k) for k in ("subtotal", "impuestos", "total")},
                                       "originales": {k: c["originales"].get(k) for k in ("subtotal", "impuestos", "total")}} for c in p["comercial_por_documento"]],
            "condiciones": {k: condicion(p, k) for k in ("plazo_entrega", "condiciones_pago", "vigencia_oferta")},
            "estado_vigencia": "no_determinada", "archivos": p["documentos"]})

    comparables = {p["proveedor_id"]: p["moneda"] == moneda_comparacion for p in postores.values()}

    def detalle_item(proveedor, item):
        cambio = {"cantidad": item["cantidad"], "precio_unitario": item["precio_unitario"], "parcial": item["parcial"]} if comparables[proveedor] else \
                 {"cantidad": None, "precio_unitario": None, "parcial": None}
        return {"item_id": item["item_id"], "documento_id": item["documento_id"],
                "original": {"descripcion": item["descripcion"], "unidad": item["unidad"], "cantidad": item["cantidad"],
                             "precio_unitario": item["precio_unitario"], "parcial": item["parcial"], "moneda": postores[proveedor]["moneda"],
                             "textos": item["originales"]},
                "comparable": {**cambio, "moneda": moneda_comparacion if comparables[proveedor] else None,
                               "operacion": "sin_cambio" if comparables[proveedor] else None,
                               "criterio": "Misma moneda; sin conversión ni ajuste de IGV." if comparables[proveedor] else "Sin tipo de cambio autorizado."},
                "evidencia_ids": item["evidencia_ids"]}

    salida_partidas = []
    for partida in salida["partidas"]:
        ofertas = []
        for oferta in partida["ofertas"]:
            proveedor = oferta["proveedor_id"]
            ofertas.append({"proveedor_id": proveedor, "estado": oferta["estado"], "equivalencia": oferta["equivalencia"], "nota": oferta["nota"],
                            "evidencia_ids": oferta["evidencia_ids"], "items": [detalle_item(proveedor, items[i][1]) for i in oferta["item_ids"]]})
            if oferta["equivalencia"] != "equivalente" and oferta["estado"] in ("cotizado", "global", "incluido_con_evidencia"):
                cubierto = any(p["proveedor_id"] == proveedor and (p["partida_codigo"] == partida["codigo"] and partida["codigo"] is not None
                               or p["partida_descripcion"] == partida["descripcion"]) for p in pendientes)
                if not cubierto:
                    pendientes.append({"proveedor_id": proveedor, "partida_codigo": partida["codigo"], "partida_descripcion": partida["descripcion"],
                                       "origen": "sistema", "motivo": "La equivalencia técnica no está resuelta." if oferta["equivalencia"] == "pendiente"
                                       else "La oferta es técnicamente distinta de la partida.", "bloquea_comparacion": True,
                                       "decision_requerida": "Decidir si la oferta se acepta como equivalente.", "evidencia_ids": oferta["evidencia_ids"]})
        salida_partidas.append({"codigo": partida["codigo"], "descripcion": partida["descripcion"], "unidad": partida["unidad"],
                                "metrado": partida["metrado"], "ofertas": ofertas})

    decisiones = [{"proveedor_id": p["proveedor_id"], "version_id": p["version_id"], "accion": d["accion"], "motivo": d.get("motivo"),
                   "fecha": d.get("created_at"), "usuario_id": d.get("usuario_id")} for p in postores.values() for d in p["decisiones"]]
    bloqueantes = sum(1 for p in pendientes if p["bloquea_comparacion"])
    solicitud = preparado["solicitud"]
    return {
        "solicitud_id": solicitud["id"],
        "proyecto": {"codigo": solicitud["proyecto"]["codigo"], "obra": solicitud["proyecto"]["nombre"], "solicitud": solicitud["codigo"],
                     "fecha_evaluacion": solicitud["fecha_evaluacion"], "revision": None},
        "especialidad": salida["especialidad"],
        "estado_revision": "requiere_revision" if bloqueantes else "listo_para_cuadro",
        "base": {"tipo": base["tipo"], "identificador": solicitud["id"] if base["tipo"] == "itemizado" else None, "version": None,
                 "origen_proveedor_id": salida["base"]["origen_proveedor_id"], "nota": salida["base"]["nota"]},
        "moneda_comparacion": moneda_comparacion, "tipo_cambio": None,
        "postores": salida_postores, "proveedores_sin_final": preparado["sin_final"], "partidas": salida_partidas, "adicionales": adicionales,
        "trazabilidad": {"entrada": "Resultados de E3 de las versiones aceptadas como final; no se leyeron PDF ni Excel.",
                         "version_ids": preparado["version_ids"], "huella": preparado["huella"],
                         "operaciones": ["Los importes se copian de E3 sin cambio; no hay conversión de moneda ni ajuste de IGV."],
                         "moneda_comparacion_origen": preparado["moneda_comparacion_origen"],
                         "evidencias": [e for e in preparado["evidencias"]]},
        "pendientes": pendientes, "diferencias": salida["diferencias"], "escenarios": [], "decisiones": decisiones,
        "generado": {"modelo": modelo, "fecha": (ahora or datetime.now(timezone.utc)).isoformat()},
    }
