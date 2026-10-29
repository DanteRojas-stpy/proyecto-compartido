"""E4: la entrada sale solo de los finales de E3 y los números los copia el código, nunca el modelo."""
import copy
import json

import pytest

from app.homologacion import contrato, entrada
from app.homologacion.construir import HomologacionInvalida, build
from datos_ficticios import ALFA, BETA, DELTA, GAMMA, SOLICITUD, comercial, paquete, respuesta_modelo


def armar(con_itemizado=False, cambiar=None):
    datos = paquete(con_itemizado)
    if cambiar:
        cambiar(datos)
    preparado = entrada.prepare(datos)
    return datos, preparado, respuesta_modelo(preparado, con_itemizado)


def tipos(h, bloquea=None):
    return [p["motivo"] for p in h["pendientes"] if bloquea is None or p["bloquea_comparacion"] is bloquea]


def test_la_entrada_sale_de_los_finales_y_es_compacta():
    datos, prep, _ = armar()
    assert [p["proveedor_id"] for p in prep["postores"]] == [ALFA, BETA, GAMMA]
    assert prep["sin_final"] == [{"proveedor_id": DELTA, "nombre": "Delta SRL"}]
    assert prep["base"]["tipo"] == "provisional" and prep["base"]["partidas"] == []
    gamma = next(p for p in prep["postores"] if p["proveedor_id"] == GAMMA)
    assert gamma["moneda"] == "USD", 'la moneda sale de sus documentos cuando la consolidada es null'
    assert all(len(e["texto_fuente"]) <= entrada.MAX_TEXTO for e in prep["evidencias"])
    assert "paginas" not in json.dumps(prep['postores']), 'no se envían páginas ni datos de lectura al modelo'


def test_huella_estable_y_sensible_a_lo_que_importa():
    _, a, _ = armar()
    _, b, _ = armar()
    assert a["huella"] == b["huella"]
    _, con_base, _ = armar(True)
    assert con_itemizado_distinta(a, con_base)
    _, otra_version, _ = armar(cambiar=lambda d: d["finales"][0].update(version_id="50000009-0000-0000-0000-000000000001"))
    assert a["huella"] != otra_version["huella"]


def con_itemizado_distinta(a, b):
    return a["huella"] != b["huella"] and b["base"]["tipo"] == "itemizado"


def test_sin_itemizado_la_base_es_provisional_y_exige_revision():
    _, prep, salida = armar()
    h = build(prep, salida, "claude-sonnet-5-5")
    assert h["base"]["tipo"] == "provisional"
    assert h["estado_revision"] == "requiere_revision"
    assert any("provisional" in m for m in tipos(h, True))
    assert any("Delta SRL no tiene" in m for m in tipos(h, False)), 'un proveedor sin final queda como pendiente, no bloquea'


def test_con_itemizado_y_equivalencias_con_evidencia_queda_lista_para_el_cuadro():
    _, prep, salida = armar(True)
    h = build(prep, salida, "claude-sonnet-5-5")
    assert h["estado_revision"] == "listo_para_cuadro", tipos(h, True)
    assert h["proveedores_sin_final"] == [{"proveedor_id": DELTA, "nombre": "Delta SRL"}]
    assert h["base"] == {"tipo": "itemizado", "identificador": SOLICITUD, "version": None, "origen_proveedor_id": None, "nota": None}
    assert h["moneda_comparacion"] == "USD" and h["tipo_cambio"] is None and h["escenarios"] == []


def test_los_numeros_salen_de_e3_y_no_del_modelo():
    _, prep, salida = armar(True)
    h = build(prep, salida, "claude-sonnet-5-5")
    alfa = next(o for o in h["partidas"][0]["ofertas"] if o["proveedor_id"] == ALFA)
    assert [(i["original"]["cantidad"], i["original"]["precio_unitario"], i["original"]["parcial"]) for i in alfa["items"]] == [(1, 36800, 36800)] * 2
    assert alfa["items"][0]["comparable"] == {"cantidad": 1, "precio_unitario": 36800, "parcial": 36800, "moneda": "USD",
                                              "operacion": "sin_cambio", "criterio": "Misma moneda; sin conversión ni ajuste de IGV."}
    beta = next(p for p in h["postores"] if p["proveedor_id"] == BETA)
    assert beta["totales_originales"] == {"subtotal": 73875.10, "impuestos": 13297.52, "total": 87172.62}
    gamma = next(p for p in h["postores"] if p["proveedor_id"] == GAMMA)
    assert [d["total"] for d in gamma["totales_por_documento"]] == [89184.40, 86963.81]
    assert gamma["totales_originales"]["total"] is None, 'dos equipos distintos no se suman ni se elige uno'


def test_el_modelo_no_puede_escribir_importes():
    _, prep, salida = armar(True)
    salida["partidas"][0]["ofertas"][0]["precio_unitario"] = 1
    with pytest.raises(HomologacionInvalida, match='formato'):
        build(prep, salida, "m")
    _, prep, salida = armar(True)
    salida["partidas"][0]["ofertas"][0]["item_ids"] = []
    salida["partidas"][0]["ofertas"][0]["estado"] = "cotizado"
    with pytest.raises(HomologacionInvalida, match='necesita ítems'):
        build(prep, salida, "m")


@pytest.mark.parametrize("cambio, mensaje", [
    (lambda s, p: s["partidas"][0]["ofertas"][0]["item_ids"].append("00000000-0000-0000-0000-000000000000"), "no pertenece"),
    (lambda s, p: s["partidas"][0]["ofertas"][0].update(proveedor_id="40000009-0000-0000-0000-000000000001"), "no tiene versión final"),
    (lambda s, p: s["partidas"][0]["ofertas"][0]["evidencia_ids"].append("00000000-0000-0000-0000-000000000000"), "no existe en la entrada"),
    (lambda s, p: s["partidas"][0]["ofertas"][0].update(evidencia_ids=[]), "no cita evidencia"),
    (lambda s, p: s["partidas"][0]["ofertas"].append(dict(s["partidas"][0]["ofertas"][0])), "aparece dos veces"),
    (lambda s, p: s["partidas"][1]["ofertas"][2]["item_ids"].append(s["partidas"][0]["ofertas"][1]["item_ids"][0]), "no pertenece"),
    (lambda s, p: s["partidas"][1]["ofertas"][0].update(item_ids=[s["partidas"][0]["ofertas"][1]["item_ids"][0]], estado="cotizado"), "no pertenece"),
    (lambda s, p: s["partidas"][0].update(metrado=3), "cambió la unidad o el metrado"),
    (lambda s, p: s["partidas"].pop(), "no coinciden con el itemizado"),
    (lambda s, p: s["diferencias"][0]["evidencia_ids"].append("00000000-0000-0000-0000-000000000000"), "Diferencia"),
    (lambda s, p: s["pendientes"].append({"proveedor_id": "40000009-0000-0000-0000-000000000001", "partida_codigo": None, "partida_descripcion": None,
                                          "motivo": "x", "bloquea_comparacion": False, "decision_requerida": "y", "evidencia_ids": []}), "no es de esta solicitud"),
])
def test_lo_que_el_modelo_cita_y_no_existe_se_rechaza(cambio, mensaje):
    _, prep, salida = armar(True)
    cambio(salida, prep)
    with pytest.raises(HomologacionInvalida, match=mensaje):
        build(prep, salida, "m")


def test_un_item_en_dos_partidas_solo_si_es_precio_global():
    _, prep, salida = armar(True)
    compartido = salida["partidas"][0]["ofertas"][1]["item_ids"][0]
    segunda = salida["partidas"][1]["ofertas"][1]
    segunda.update(item_ids=[compartido], estado="cotizado")
    with pytest.raises(HomologacionInvalida, match='varias partidas'):
        build(prep, salida, "m")
    salida["partidas"][0]["ofertas"][1]["estado"] = "global"
    salida["partidas"][1]["ofertas"][1]["estado"] = "global"
    segunda["equivalencia"], segunda["evidencia_ids"] = "pendiente", []
    assert build(prep, salida, "m")["estado_revision"] == "requiere_revision"


def test_un_item_que_el_modelo_no_relaciono_queda_como_adicional_y_bloquea():
    _, prep, salida = armar(True)
    salida["partidas"][0]["ofertas"][0]["item_ids"].pop()
    h = build(prep, salida, "m")
    assert len(h["adicionales"]) == 1 and h["adicionales"][0]["proveedor_id"] == ALFA
    assert h["estado_revision"] == "requiere_revision"
    assert any("no quedó relacionado" in m for m in tipos(h, True))


def test_equivalencia_dudosa_genera_pendiente_bloqueante_sin_duplicarlo():
    _, prep, salida = armar(True)
    oferta = salida["partidas"][0]["ofertas"][1]
    oferta.update(equivalencia="pendiente", evidencia_ids=[])
    h = build(prep, salida, "m")
    assert h["estado_revision"] == "requiere_revision"
    assert sum("equivalencia técnica no está resuelta" in m for m in tipos(h, True)) == 1
    _, prep, salida = armar(True)
    oferta = salida["partidas"][0]["ofertas"][1]
    oferta.update(equivalencia="no_equivalente", evidencia_ids=[])
    salida["pendientes"].append({"proveedor_id": BETA, "partida_codigo": "MA-01", "partida_descripcion": None, "motivo": "Potencia distinta",
                                 "bloquea_comparacion": True, "decision_requerida": "Aprobar", "evidencia_ids": []})
    h = build(prep, salida, "m")
    assert [m for m in tipos(h, True) if "técnicamente distinta" in m] == [], 'el pendiente del modelo ya cubre esa partida'


def test_otra_moneda_sin_cambio_no_se_compara_ni_se_inventa_un_cambio():
    _, prep, salida = armar(True, cambiar=lambda d: d["finales"][1]["resultado"]["datos_comerciales"].update(moneda="PEN"))
    h = build(prep, salida, "m")
    beta = next(p for p in h["postores"] if p["proveedor_id"] == BETA)
    assert beta["comparable_en_moneda_de_comparacion"] is False
    oferta = next(o for o in h["partidas"][0]["ofertas"] if o["proveedor_id"] == BETA)
    assert oferta["items"][0]["comparable"]["parcial"] is None and oferta["items"][0]["original"]["parcial"] == 73875.10
    assert h["tipo_cambio"] is None and h["estado_revision"] == "requiere_revision"
    assert any("Autorizar un tipo de cambio" in p["decision_requerida"] for p in h["pendientes"] if p["bloquea_comparacion"])


def test_moneda_no_identificada_bloquea():
    def sin_moneda(d):
        d["finales"][2]["resultado"]["datos_comerciales_documentos"][0]["valores"]["moneda"] = None
        d["finales"][2]["resultado"]["datos_comerciales_documentos"][1]["valores"]["moneda"] = None
    _, prep, salida = armar(True, cambiar=sin_moneda)
    h = build(prep, salida, "m")
    assert any("No se identificó la moneda" in m for m in tipos(h, True))


def test_la_suma_de_parciales_se_verifica_y_se_informa_sin_corregir():
    def descuadrado(d):
        d["finales"][0]["resultado"]["datos_comerciales_documentos"][0]["valores"]["subtotal"] = 70000
    _, prep, salida = armar(True, cambiar=descuadrado)
    h = build(prep, salida, "m")
    assert any("no coincide con el subtotal" in m for m in tipos(h, False))
    assert h["estado_revision"] == "listo_para_cuadro", 'una diferencia aritmética se informa, no bloquea'


def test_igv_vigencia_y_observaciones_de_e3_quedan_como_pendientes_informativos():
    _, prep, salida = armar(True)
    h = build(prep, salida, "m")
    informativos = tipos(h, False)
    assert any("Beta SA no indica su vigencia" in m for m in informativos)
    assert any("Gamma Lift" in m and "no indica su vigencia" in m for m in informativos)
    assert any("Alfa SAC: el especialista aceptó la versión con 1 observaciones" in m for m in informativos)
    assert not any("IGV de la oferta de Alfa" in m for m in informativos)


def test_decisiones_del_especialista_y_trazabilidad_se_conservan():
    _, prep, salida = armar(True)
    h = build(prep, salida, "claude-sonnet-5-5")
    assert len(h["decisiones"]) == 3 and h["decisiones"][0]["accion"] == "aceptar_version"
    assert h["trazabilidad"]["version_ids"] == prep["version_ids"] and h["trazabilidad"]["huella"] == prep["huella"]
    assert h["generado"]["modelo"] == "claude-sonnet-5-5"
    assert {e["proveedor_id"] for e in h["trazabilidad"]["evidencias"]} == {ALFA, BETA, GAMMA}


def test_instrucciones_y_peticion_a_claude():
    texto = contrato.system_prompt()
    assert "Homologar cotizaciones" in texto and "Método de homologación" in texto and "NO escribas importes" in texto
    assert not texto.startswith("---"), 'la cabecera de la skill no se envía al modelo'
    _, prep, _ = armar(True)
    cuerpo = contrato.request(prep, "claude-sonnet-5-5")
    assert cuerpo["model"] == "claude-sonnet-5-5" and cuerpo["max_tokens"] == 16000
    assert not {"temperature", "top_p", "top_k", "tool_choice", "thinking"} & set(cuerpo)
    enviado = json.loads(cuerpo["messages"][0]["content"])
    assert set(enviado) == {"solicitud", "base", "postores", "evidencias", "sin_final"}
    assert "huella" not in enviado and "version_ids" not in enviado
    assert enviado["solicitud"]["moneda_comparacion"] == "USD"
    assert "no los repitas" in texto and "solicitud.moneda_comparacion" in texto


@pytest.mark.parametrize("envoltura", ["{}", "```json\n{}\n```", "Resultado:\n{}\nListo.", "{}\n\nNota: revisé el caso {dudoso} y {otro}.", '{}\n{"extra": 1}'])
def test_la_respuesta_se_lee_aunque_venga_con_texto(envoltura):
    _, prep, salida = armar(True)
    assert contrato.parse_text(envoltura.replace("{}", json.dumps(salida))) == salida


def test_respuestas_que_no_son_el_formato_se_rechazan():
    with pytest.raises(ValueError, match="objeto JSON"):
        contrato.parse_text("No puedo ayudar con eso")
    with pytest.raises(Exception):
        contrato.parse_text('{"partidas": []}')


# --- Servicio -----------------------------------------------------------------------------------------------

@pytest.fixture
def cliente(monkeypatch):
    from fastapi.testclient import TestClient
    from app.homologacion.server import app
    monkeypatch.setenv("E3_INTERNAL_KEY", "clave-de-prueba")
    return TestClient(app), {"x-costflow-internal-key": "clave-de-prueba"}


def test_el_servicio_exige_la_clave_interna(cliente):
    http, _ = cliente
    assert http.get("/health").status_code == 200
    assert http.post("/e4/preparar", json={"paquete": paquete()}).status_code == 401
    assert http.post("/e4/preparar", json={"paquete": paquete()}, headers={"x-costflow-internal-key": "otra"}).status_code == 401


def test_preparar_devuelve_la_peticion_para_claude_con_sonnet(cliente):
    http, cabeceras = cliente
    r = http.post("/e4/preparar", json={"paquete": paquete(True)}, headers=cabeceras)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["modelo"] == "claude-sonnet-5-5" and cuerpo["cuerpo_claude"]["model"] == "claude-sonnet-5-5"
    assert cuerpo["postores"] == 3 and cuerpo["base"] == "itemizado" and len(cuerpo["huella"]) == 64
    assert cuerpo["sin_final"] == [{"proveedor_id": DELTA, "nombre": "Delta SRL"}]


def test_construir_valida_y_devuelve_el_resultado(cliente):
    http, cabeceras = cliente
    datos = paquete(True)
    salida = respuesta_modelo(entrada.prepare(datos), True)
    r = http.post("/e4/construir", json={"paquete": datos, "texto": "```json\n" + json.dumps(salida) + "\n```", "modelo": "claude-sonnet-5-5"}, headers=cabeceras)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["resultado"] == "construida" and cuerpo["estado_revision"] == "listo_para_cuadro"
    assert cuerpo["homologacion"]["generado"]["modelo"] == "claude-sonnet-5-5"
    assert cuerpo["huella"] == entrada.prepare(datos)["huella"] and len(cuerpo["version_ids"]) == 3


def test_construir_rechaza_con_422_lo_que_no_cuadra_con_la_entrada(cliente):
    http, cabeceras = cliente
    datos = paquete(True)
    salida = respuesta_modelo(entrada.prepare(datos), True)
    salida["partidas"][0]["ofertas"][0]["item_ids"].append("00000000-0000-0000-0000-000000000000")
    r = http.post("/e4/construir", json={"paquete": datos, "texto": json.dumps(salida)}, headers=cabeceras)
    assert r.status_code == 422 and r.json()["resultado"] == "respuesta_invalida" and "no pertenece" in r.json()["errores"][0]
    r = http.post("/e4/construir", json={"paquete": datos, "texto": "No puedo ayudar"}, headers=cabeceras)
    assert r.status_code == 422 and "objeto JSON" in r.json()["errores"][0]


def test_el_modelo_puede_senalar_al_proveedor_sin_final_sin_duplicar_el_pendiente():
    _, prep, salida = armar(True)
    salida["pendientes"].append({"proveedor_id": DELTA, "partida_codigo": None, "partida_descripcion": None, "motivo": "Delta no cotizó",
                                 "bloquea_comparacion": False, "decision_requerida": "Esperar su cotización", "evidencia_ids": []})
    h = build(prep, salida, "m")
    assert sum(p["proveedor_id"] == DELTA for p in h["pendientes"]) == 1
    assert h["estado_revision"] == "listo_para_cuadro"


def test_metrado_provisional_acepta_la_suma_de_cantidades_de_un_proveedor():
    _, prep, salida = armar(False)
    salida["partidas"][0]["metrado"] = 2  # Alfa cotizó dos ítems de 1 unidad cada uno
    salida["partidas"][0]["ofertas"] = [o for o in salida["partidas"][0]["ofertas"] if o["proveedor_id"] == ALFA]
    assert build(prep, salida, "m")["partidas"][0]["metrado"] == 2
    salida["partidas"][0]["metrado"] = 7
    with pytest.raises(HomologacionInvalida, match="metrado no coincide"):
        build(prep, salida, "m")


def test_una_oferta_sin_moneda_no_cambia_la_moneda_de_comparacion():
    """Pasó en vivo: TK sin moneda y la solicitud en PEN bloqueaban a las ofertas que sí declaran USD."""
    def sin_moneda_de_tk(d):
        d["solicitud"]["moneda"] = "PEN"
        for c in d["finales"][2]["resultado"]["datos_comerciales_documentos"]:
            c["valores"]["moneda"] = None
    _, prep, salida = armar(True, cambiar=sin_moneda_de_tk)
    h = build(prep, salida, "m")
    assert h["moneda_comparacion"] == "USD"
    assert h["trazabilidad"]["moneda_comparacion_origen"] == "moneda común de las ofertas"
    comparables = {p["nombre"]: p["comparable_en_moneda_de_comparacion"] for p in h["postores"]}
    assert comparables == {"Alfa SAC": True, "Beta SA": True, "Gamma Lift": False}
    motivos = tipos(h, True)
    assert sum("No se identificó la moneda" in m and "Gamma Lift" in m for m in motivos) == 1
    assert not any("la comparación en PEN" in m for m in motivos), 'no se exige un cambio a ofertas que ya están en la moneda común'
    assert h["estado_revision"] == "requiere_revision"


def test_con_monedas_distintas_se_usa_la_de_la_solicitud():
    _, prep, salida = armar(True, cambiar=lambda d: d["finales"][1]["resultado"]["datos_comerciales"].update(moneda="PEN"))
    h = build(prep, salida, "m")
    assert h["moneda_comparacion"] == "USD" and h["trazabilidad"]["moneda_comparacion_origen"] == "moneda de la solicitud"


def test_plazo_y_vigencia_salen_de_cada_documento_si_el_consolidado_esta_vacio():
    """Schindler tenía dos plazos distintos en el mismo documento y el resumen mostraba el plazo vacío."""
    def dos_plazos(d):
        r = d["finales"][0]["resultado"]
        r["datos_comerciales"].update(plazo_entrega=None, vigencia_oferta=None)
        doc = r["datos_comerciales_documentos"][0]["documento_id"]
        r["datos_comerciales_documentos"][0]["valores"].update(plazo_entrega="9 meses", vigencia_oferta="15 días")
        r["datos_comerciales_documentos"].append(comercial(doc, "USD", None, None, None, [], vigencia="15 días", plazo="6 meses de materiales"))
    _, prep, salida = armar(True, cambiar=dos_plazos)
    alfa = next(p for p in build(prep, salida, "m")["postores"] if p["proveedor_id"] == ALFA)
    assert alfa["condiciones"]["plazo_entrega"] == "9 meses / 6 meses de materiales"
    assert alfa["condiciones"]["vigencia_oferta"] == "15 días", 'un valor repetido en varios documentos no se duplica'


def test_el_consolidado_prevalece_sobre_los_documentos():
    _, prep, salida = armar(True)
    beta = next(p for p in build(prep, salida, "m")["postores"] if p["proveedor_id"] == BETA)
    assert beta["condiciones"]["plazo_entrega"] == "8.5 meses" and beta["condiciones"]["vigencia_oferta"] is None


def test_el_modelo_recibe_la_moneda_de_comparacion_ya_resuelta():
    """En vivo el modelo escribió un pendiente «comparación en PEN» porque solo veía la moneda de la solicitud."""
    def sin_moneda_de_tk(d):
        d["solicitud"]["moneda"] = "PEN"
        for c in d["finales"][2]["resultado"]["datos_comerciales_documentos"]:
            c["valores"]["moneda"] = None
    datos = paquete(True)
    sin_moneda_de_tk(datos)
    prep = entrada.prepare(datos)
    enviado = json.loads(contrato.request(prep, "m")["messages"][0]["content"])
    assert enviado["solicitud"]["moneda"] == "PEN" and enviado["solicitud"]["moneda_comparacion"] == "USD"
    assert prep["moneda_comparacion_origen"] == "moneda común de las ofertas"
