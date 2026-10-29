"""Datos ficticios con la forma de las versiones finales de E3. No contienen cotizaciones reales."""
import copy
import uuid

SOLICITUD = "30000000-0000-0000-0000-000000000001"
ALFA, BETA, GAMMA, DELTA = (f"4000000{n}-0000-0000-0000-000000000001" for n in range(1, 5))
V_ALFA, V_BETA, V_GAMMA = (f"5000000{n}-0000-0000-0000-000000000001" for n in range(1, 4))


def uid(texto: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "e4-prueba/" + texto))


def evidencia(clave, documento, campo, texto, pagina=3):
    return {"id": uid(clave), "documento_id": documento, "fragmento_id": uid("f" + clave), "campo": campo, "confianza": 0.95,
            "ubicacion": {"pagina": pagina, "origen": "pdf_texto"}, "texto_fuente": texto}


def item(clave, documento, ref, desc, cant, pu, parcial, textos, evidencias, unidad="UND"):
    return {"id": uid(clave), "documento_id": documento, "referencia_item": ref, "descripcion": desc, "cantidad": cant, "unidad": unidad,
            "unidad_normalizada": "unidad", "precio_unitario": pu, "parcial": parcial, "originales": textos, "evidencia_ids": evidencias}


def comercial(documento, moneda, subtotal, impuestos, total, evidencias, vigencia="15 días", plazo="9 meses", pago="30% a la firma"):
    valores = {"moneda": moneda, "subtotal": subtotal, "impuestos": impuestos, "total": total, "plazo_entrega": plazo,
               "condiciones_pago": pago, "vigencia_oferta": vigencia}
    return {"documento_id": documento, "valores": valores, "originales": {k: (None if v is None else str(v)) for k, v in valores.items()},
            "evidencia_ids": evidencias}


def final(proveedor, version, documentos, items, por_documento, consolidado, evidencias, observaciones=()):
    return {"version_id": version, "proveedor_id": proveedor, "numero_version": 1, "resultado": {
        "version_id": version, "proveedor_id": proveedor, "solicitud_id": SOLICITUD, "es_final": True, "estado_procesamiento": "completado_con_observaciones",
        "documentos": [{"documento_id": d, "nombre_original": f"Ficha {n}.pdf", "paginas": [{"pagina": 1}]} for d, n in documentos],
        "datos_comerciales": consolidado, "datos_comerciales_documentos": por_documento, "items": items, "especificaciones_tecnicas": [
            {"id": uid("e" + version), "campo": "Capacidad", "documento_id": documentos[0][0], "referencia_item": None, "valor_original": "630 kg",
             "valor_numerico": 630, "unidad_original": "kg", "evidencia_ids": [evidencias[0]["id"]]}],
        "evidencias": evidencias, "observaciones": list(observaciones),
        "decisiones": [{"accion": "aceptar_version", "motivo": "Aceptada como final por el especialista", "created_at": "2026-10-29T01:00:00+00:00", "usuario_id": "u"}]}}


def paquete(con_itemizado=False):
    da, db, dg1, dg2 = (uid(x) for x in ("da", "db", "dg1", "dg2"))
    ev_a = evidencia("ea", da, "precio", "Ítem 00100 +1 x 36,800 = 36,800.00 USD Ítem 00200 +1 x 36,800 = 36,800.00 USD TOTAL 86,848.00 USD")
    ev_b = evidencia("eb", db, "precio", "Ascensor Pasajeros | Cantidad 2 | Precio unit. US$ 36.937,55 | Costo total US$ 73.875,10")
    ev_g1 = evidencia("eg1", dg1, "oferta_economica", "Equipos: Gamma 8 personas | Precio Unitario $ 37,790.00 | UND 2 | Sub Total $ 75,580.00")
    ev_g2 = evidencia("eg2", dg2, "oferta_economica", "Equipos: Gamma | Precio Unitario $ 36,849.07 | UND 2 | Sub Total $ 73,698.14")
    alfa = final(ALFA, V_ALFA, [(da, "Alfa")], [
        item("a1", da, "00100", "Ascensor Alfa 630 kg", 1, 36800, 36800, {"cantidad": "+1 x"}, [ev_a["id"]]),
        item("a2", da, "00200", "Ascensor Alfa 630 kg", 1, 36800, 36800, {"cantidad": "+1 x"}, [ev_a["id"]])],
        [comercial(da, "USD", 73600, 13248, 86848, [ev_a["id"]])], {"moneda": "USD", "subtotal": 73600, "impuestos": 13248, "total": 86848,
        "plazo_entrega": "9 meses", "condiciones_pago": "30% a la firma", "vigencia_oferta": "15 días"}, [ev_a],
        observaciones=[{"tipo": "version_borrador", "severidad": "media", "requiere_aclaracion": True, "estado": "pendiente", "descripcion": "Marca DRAFT"}])
    beta = final(BETA, V_BETA, [(db, "Beta")], [item("b1", db, "Powertech", "Ascensor Beta 630 kg", 2, 36937.55, 73875.10, {}, [ev_b["id"]])],
        [comercial(db, "USD", 73875.10, 13297.52, 87172.62, [ev_b["id"]], vigencia=None, plazo="8.5 meses")],
        {"moneda": "USD", "subtotal": 73875.10, "impuestos": 13297.52, "total": 87172.62, "plazo_entrega": "8.5 meses",
         "condiciones_pago": "Cuotas", "vigencia_oferta": None}, [ev_b])
    gamma = final(GAMMA, V_GAMMA, [(dg1, "Gamma 8"), (dg2, "Gamma 10")], [
        item("g1", dg1, "Gamma 8 personas", "Gamma 8 personas", 2, 37790, 75580, {}, [ev_g1["id"]]),
        item("g2", dg2, "Gamma", "Gamma", 2, 36849.07, 73698.14, {}, [ev_g2["id"]])],
        [comercial(dg1, "USD", 75580, 13604.40, 89184.40, [ev_g1["id"]], vigencia=None, plazo="7.5 meses"),
         comercial(dg2, "USD", 73698.14, None, 86963.81, [ev_g2["id"]], vigencia=None, plazo="7.5 meses")],
        {"moneda": None, "subtotal": None, "impuestos": None, "total": None, "plazo_entrega": "7.5 meses", "condiciones_pago": "Cuotas", "vigencia_oferta": None},
        [ev_g1, ev_g2])
    partidas = [
        {"id": uid("p1"), "codigo": "MA-01", "descripcion": "Ascensor de pasajeros 630 kg, 8 personas", "unidad": "und", "metrado": 2},
        {"id": uid("p2"), "codigo": "MA-02", "descripcion": "Ascensor de pasajeros 750 kg, 10 personas", "unidad": "und", "metrado": 2}] if con_itemizado else []
    return {"ejecucion_id": uid("ejecucion"), "fecha_evaluacion": "2026-10-29T12:00:00+00:00",
            "solicitud": {"id": SOLICITUD, "codigo": "MA-001", "nombre": "Elevadores", "moneda": "USD", "fecha_limite": "2026-11-29",
                          "proyecto": {"codigo": "P-10", "nombre": "Obra ficticia"}},
            "partidas": partidas,
            "proveedores": [{"id": ALFA, "nombre": "Alfa SAC", "estado": "respondio"}, {"id": BETA, "nombre": "Beta SA", "estado": "respondio"},
                            {"id": GAMMA, "nombre": "Gamma Lift", "estado": "respondio"}, {"id": DELTA, "nombre": "Delta SRL", "estado": "invitado"}],
            "finales": [alfa, beta, gamma]}


def respuesta_modelo(preparado, con_itemizado=False):
    """Una respuesta válida del modelo para el paquete ficticio: relaciona por identificador, sin cifras."""
    a, b, g = (next(p for p in preparado["postores"] if p["proveedor_id"] == x) for x in (ALFA, BETA, GAMMA))
    ev = lambda p: [e["id"] for e in preparado["evidencias"] if e["proveedor_id"] == p["proveedor_id"]][:1]
    g8, g10 = g["items"][0]["item_id"], g["items"][1]["item_id"]
    oferta = lambda p, ids, estado="cotizado", eq="equivalente": {"proveedor_id": p["proveedor_id"], "item_ids": ids, "estado": estado,
                                                                  "equivalencia": eq, "evidencia_ids": ev(p) if eq == "equivalente" else [], "nota": None}
    partidas = [
        {"codigo": "MA-01" if con_itemizado else None, "descripcion": "Ascensor de pasajeros 630 kg, 8 personas", "unidad": "und" if con_itemizado else None,
         "metrado": 2 if con_itemizado else None, "ofertas": [oferta(a, [i["item_id"] for i in a["items"]]), oferta(b, [b["items"][0]["item_id"]]), oferta(g, [g8])]},
        {"codigo": "MA-02" if con_itemizado else None, "descripcion": "Ascensor de pasajeros 750 kg, 10 personas", "unidad": "und" if con_itemizado else None,
         "metrado": 2 if con_itemizado else None, "ofertas": [oferta(a, [], "no_cotizado"), oferta(b, [], "no_cotizado"), oferta(g, [g10])]}]
    return {"especialidad": {"codigo": None, "nombre": "Ascensores"},
            "base": {"tipo": "itemizado" if con_itemizado else "provisional", "origen_proveedor_id": None if con_itemizado else GAMMA, "nota": None},
            "partidas": copy.deepcopy(partidas), "adicionales": [], "pendientes": [],
            "diferencias": [{"tipo": "plazo", "detalle": "Alfa 9 meses, Beta 8,5 y Gamma 7,5.", "proveedor_ids": [ALFA, BETA, GAMMA], "evidencia_ids": []}]}
