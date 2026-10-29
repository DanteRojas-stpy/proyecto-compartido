"""Arma lo que ve el modelo en E4 a partir de las versiones finales de E3 y del itemizado.

No lee PDF ni Excel: parte de los resultados JSON que el especialista aceptó como final.
"""
from __future__ import annotations

import hashlib
import json

MAX_TEXTO = 400
ESTADOS_PENDIENTES_E3 = {"pendiente", "aclaracion_solicitada"}


def canonico(valor) -> str:
    return json.dumps(valor, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def moneda_del_postor(resultado: dict) -> str | None:
    """La moneda de la oferta: la consolidada o, si falta, la única que usan sus documentos."""
    if resultado["datos_comerciales"].get("moneda"):
        return resultado["datos_comerciales"]["moneda"]
    monedas = {c["valores"].get("moneda") for c in resultado.get("datos_comerciales_documentos", []) if c["valores"].get("moneda")}
    return next(iter(monedas)) if len(monedas) == 1 else None


def prepare(paquete: dict) -> dict:
    """Devuelve lo que ve el modelo, la huella de la entrada y las versiones usadas."""
    solicitud = paquete["solicitud"]
    nombres = {p["id"]: p["nombre"] for p in paquete["proveedores"]}
    postores, evidencias = [], {}
    for final in sorted(paquete["finales"], key=lambda f: f["proveedor_id"]):
        r = final["resultado"]
        por_id = {e["id"]: e for e in r.get("evidencias", [])}
        usadas: set[str] = set()
        items = []
        for i in r.get("items", []):
            usadas.update(i["evidencia_ids"])
            items.append({"item_id": i["id"], "documento_id": i["documento_id"], "referencia_item": i.get("referencia_item"),
                          "descripcion": i["descripcion"], "cantidad": i["cantidad"], "unidad": i["unidad"],
                          "precio_unitario": i["precio_unitario"], "parcial": i["parcial"], "originales": i["originales"],
                          "evidencia_ids": i["evidencia_ids"]})
        especificaciones = []
        for s in r.get("especificaciones_tecnicas", []):
            usadas.update(s["evidencia_ids"])
            especificaciones.append({"documento_id": s["documento_id"], "referencia_item": s.get("referencia_item"), "campo": s["campo"],
                                     "valor_original": s["valor_original"], "valor_numerico": s["valor_numerico"],
                                     "unidad_original": s["unidad_original"], "evidencia_ids": s["evidencia_ids"]})
        por_documento = []
        for c in r.get("datos_comerciales_documentos", []):
            usadas.update(c["evidencia_ids"])
            por_documento.append({"documento_id": c["documento_id"], "valores": c["valores"], "originales": c["originales"],
                                  "evidencia_ids": c["evidencia_ids"]})
        for evidencia_id in sorted(usadas):
            e = por_id.get(evidencia_id)
            if e:
                evidencias[evidencia_id] = {"id": e["id"], "proveedor_id": final["proveedor_id"], "documento_id": e["documento_id"],
                                            "campo": e["campo"], "pagina": e.get("ubicacion", {}).get("pagina"),
                                            "texto_fuente": e["texto_fuente"][:MAX_TEXTO]}
        observaciones = [{"tipo": o["tipo"], "severidad": o["severidad"], "requiere_aclaracion": o["requiere_aclaracion"],
                          "estado": o["estado"], "descripcion": o["descripcion"]} for o in r.get("observaciones", [])]
        postores.append({
            "proveedor_id": final["proveedor_id"], "nombre": nombres.get(final["proveedor_id"], final["proveedor_id"]),
            "version_id": final["version_id"], "numero_version": final["numero_version"], "moneda": moneda_del_postor(r),
            "documentos": [{"documento_id": d["documento_id"], "nombre": d["nombre_original"]} for d in r.get("documentos", [])],
            "comercial": r["datos_comerciales"], "comercial_por_documento": por_documento, "items": items,
            "especificaciones": especificaciones, "observaciones": observaciones, "decisiones": r.get("decisiones", []),
        })
    con_final = {p["proveedor_id"] for p in postores}
    sin_final = [{"proveedor_id": p["id"], "nombre": p["nombre"]} for p in paquete["proveedores"]
                 if p["id"] not in con_final and p.get("estado") != "descartado"]
    partidas = paquete["partidas"]
    base = {"tipo": "itemizado" if partidas else "provisional",
            "partidas": [{"codigo": p["codigo"], "descripcion": p["descripcion"], "unidad": p["unidad"], "metrado": p["metrado"]} for p in partidas]}
    # Moneda de comparación: la que comparten las ofertas que identifican su moneda; si hay varias, la de la solicitud.
    monedas = {p["moneda"] for p in postores if p["moneda"]}
    moneda_comun = len(monedas) == 1
    moneda_comparacion = next(iter(monedas)) if moneda_comun else solicitud["moneda"]
    version_ids = sorted(p["version_id"] for p in postores)
    huella = hashlib.sha256(canonico({"versiones": version_ids, "base": base["partidas"], "moneda": solicitud["moneda"]}).encode()).hexdigest()
    return {
        "huella": huella, "version_ids": version_ids,
        "solicitud": {"id": solicitud["id"], "codigo": solicitud["codigo"], "nombre": solicitud["nombre"], "moneda": solicitud["moneda"],
                      "moneda_comparacion": moneda_comparacion, "fecha_evaluacion": paquete["fecha_evaluacion"], "proyecto": solicitud["proyecto"]},
        "moneda_comparacion_origen": "moneda común de las ofertas" if moneda_comun else "moneda de la solicitud",
        "base": base, "postores": postores, "evidencias": list(evidencias.values()), "sin_final": sin_final,
    }
