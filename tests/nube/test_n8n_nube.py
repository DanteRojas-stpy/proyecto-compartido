"""Preparación y subida de los flujos a n8n en la nube, sin llamar a ninguna instancia real."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("n8n_nube", ROOT / "scripts/n8n_nube.py")
nube = importlib.util.module_from_spec(spec)
sys.modules["n8n_nube"] = nube
spec.loader.exec_module(nube)

ENTORNO = {"NHOST_SUBDOMAIN": "abcdefghij1234567890", "NHOST_REGION": "sa-east-1", "SERVICIO_E3_URL": "https://e3.ejemplo.com",
           "SERVICIO_E4_URL": "https://e4.ejemplo.com", "SERVICIO_E5_URL": "https://e5.ejemplo.com/"}


def cfg(**cambios):
    args = argparse.Namespace(intervalo_e3=5, intervalo_cola=30, **{k.lower(): None for k in ENTORNO})
    for k, v in cambios.items():
        setattr(args, k, v)
    return nube.configuracion(args, {**ENTORNO})


def adaptados():
    c = cfg()
    return c, {i: nube.adaptar(f, c) for i, f in nube.cargar_flujos().items()}


def test_los_siete_flujos_se_adaptan_sin_dejar_marcadores_ni_direcciones_locales():
    _, flujos = adaptados()
    assert set(flujos) == set(nube.ORDEN)
    texto = json.dumps(flujos)
    for local in ("costflow-etapa3", "costflow-homologacion", "costflow-cuadro", "SUBDOMINIO", "REGION"):
        assert local not in texto, local
    assert "https://e3.ejemplo.com/read" in texto
    # E4 y E5 corren dentro de n8n: no hay servicio que apuntar y sus direcciones ya no se usan.
    assert "e4.ejemplo.com" not in texto and "e5.ejemplo.com" not in texto and "/e4/" not in texto and "/e5/generar" not in texto
    assert "abcdefghij1234567890.functions.sa-east-1.nhost.run" in texto
    assert all(f["active"] is False for f in flujos.values())


def test_el_sondeo_baja_de_frecuencia_y_e4_e5_conservan_el_aviso_del_boton():
    _, flujos = adaptados()
    minutos = lambda i: [n["parameters"]["rule"]["interval"][0]["minutesInterval"] for n in flujos[i]["nodes"] if n["type"].endswith("scheduleTrigger")]
    assert minutos("costflowEtapa3_1") == [5] and minutos("costflowEtapa3_5") == [5]
    assert minutos("costflowE4_1") == [30] and minutos("costflowE5_1") == [30]
    for i, ruta in (("costflowE4_1", "e4-ejecutar"), ("costflowE5_1", "e5-ejecutar")):
        avisos = [n for n in flujos[i]["nodes"] if n["type"].endswith(".webhook")]
        assert [a["parameters"]["path"] for a in avisos] == [ruta]
        assert avisos[0]["parameters"]["authentication"] == "headerAuth"
        assert flujos[i]["connections"]["Aviso del botón"]["main"][0][0]["node"].startswith("Tomar ")


def test_no_se_llevan_credenciales_y_se_listan_las_que_hay_que_asignar():
    c, flujos = adaptados()
    assert not any("credentials" in n for f in flujos.values() for n in f["nodes"])
    filas = nube.credenciales_pendientes([flujos[i] for i in nube.ORDEN])
    assert {f[2] for f in filas} == {"CostFlow E3 - Acceso interno", "CostFlow E3 - Claude", "Gmail (OAuth de Google)", "CostFlow E3 - Nhost Storage"}
    assert any(f[1] == "Aviso del botón" for f in filas)


@pytest.mark.parametrize("cambio,mensaje", [
    ({"servicio_e3_url": "http://inseguro.com"}, "https"),
    ({"servicio_e3_url": "https://x y.com"}, "SERVICIO_E3_URL"),
    ({"intervalo_cola": 0}, "intervalo_cola"),
    ({"nhost_subdomain": "Mal Subdominio"}, "NHOST_SUBDOMAIN"),
    ({"nhost_region": "mundo"}, "NHOST_REGION"),
])
def test_configuracion_invalida_se_rechaza(cambio, mensaje):
    with pytest.raises(nube.ConfiguracionInvalida, match=mensaje):
        cfg(**cambio)


class SesionFalsa:
    """Imita la API de n8n: asigna identificadores nuevos y recuerda lo que recibió."""
    def __init__(self, existentes=None):
        self.headers, self.llamadas, self.existentes = {}, [], existentes or {}
        self.siguiente = 100

    def request(self, metodo, url, timeout=0, json=None, params=None):
        self.llamadas.append((metodo, url.split("/api/v1")[1], json))
        resp = type("R", (), {})()
        resp.status_code, resp.text = 200, ""
        if metodo == "GET":
            cuerpo = {"data": [{"name": n, "id": i} for n, i in self.existentes.items()]}
        elif metodo == "POST" and url.endswith("/workflows"):
            self.siguiente += 1
            cuerpo = {"id": f"n8n{self.siguiente}"}
        elif metodo == "PUT":
            cuerpo = {"id": url.rsplit("/", 1)[1]}
        else:
            cuerpo = {"active": True}
        resp.content = b"x"
        resp.json = lambda: cuerpo
        return resp


def test_subir_crea_en_orden_enlaza_los_flujos_entre_si_y_no_activa_sin_pedirlo():
    _, flujos = adaptados()
    sesion = SesionFalsa()
    cliente = nube.ClienteN8n("https://demo.app.n8n.cloud", "clave-de-prueba", sesion)
    assert sesion.headers["X-N8N-API-KEY"] == "clave-de-prueba"
    ids = nube.subir(cliente, flujos)
    creados = [(m, r) for m, r, _ in sesion.llamadas if m == "POST"]
    assert len(creados) == 7 and not any("activate" in r for _, r, _ in sesion.llamadas)
    # E3.1 invoca a E3.2 y E3.3: debe llevar los identificadores que n8n asignó, no los del repositorio.
    cuerpo_e31 = next(c for m, r, c in sesion.llamadas if m == "POST" and c["name"] == flujos["costflowEtapa3_1"]["name"])
    invocados = [n["parameters"]["workflowId"]["value"] for n in cuerpo_e31["nodes"] if n["type"].endswith("executeWorkflow")]
    assert sorted(invocados) == sorted([ids["costflowEtapa3_2"], ids["costflowEtapa3_3"]])
    assert set(cuerpo_e31) == {"name", "nodes", "connections", "settings"}


def test_subir_actualiza_lo_que_ya_existe_y_activa_si_se_pide():
    _, flujos = adaptados()
    sesion = SesionFalsa({flujos["costflowE4_1"]["name"]: "viejo-e4"})
    ids = nube.subir(nube.ClienteN8n("https://demo.app.n8n.cloud", "k", sesion), flujos, activar=True)
    assert ids["costflowE4_1"] == "viejo-e4"
    assert ("PUT", "/workflows/viejo-e4") in [(m, r) for m, r, _ in sesion.llamadas]
    assert sum(1 for m, r, _ in sesion.llamadas if r.endswith("/activate")) == 7


def test_un_flujo_que_invoca_a_otro_no_creado_se_rechaza():
    flujo = adaptados()[1]["costflowEtapa3_1"]
    with pytest.raises(nube.ConfiguracionInvalida, match="todavía no se creó"):
        nube.enlazar(flujo, {})


def test_la_clave_de_la_api_no_se_acepta_por_argumento(capsys, monkeypatch):
    monkeypatch.delenv("N8N_API_KEY", raising=False)
    for k, v in ENTORNO.items():
        monkeypatch.setenv(k, v)
    assert nube.main(["subir", "--n8n-url", "https://demo.app.n8n.cloud"]) == 1
    assert "N8N_API_KEY" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        nube.main(["subir", "--n8n-api-key", "x"])


def test_preparar_escribe_los_siete_json_sin_secretos(tmp_path, monkeypatch):
    for k, v in ENTORNO.items():
        monkeypatch.setenv(k, v)
    assert nube.main(["preparar", "--salida", str(tmp_path)]) == 0
    archivos = sorted(p.name for p in tmp_path.glob("*.json"))
    assert len(archivos) == 7 and "costflowE5_1.json" in archivos
    assert "x-api-key" not in "".join(p.read_text(encoding="utf-8") for p in tmp_path.glob("*.json"))


def test_las_direcciones_de_los_servicios_de_e4_y_e5_ya_no_son_necesarias():
    entorno = {k: v for k, v in ENTORNO.items() if k not in ("SERVICIO_E4_URL", "SERVICIO_E5_URL")}
    args = argparse.Namespace(intervalo_e3=5, intervalo_cola=30, **{k.lower(): None for k in ENTORNO})
    assert not {"servicio_e4", "servicio_e5"} & set(nube.configuracion(args, entorno))
