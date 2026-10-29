"""Servicio local de E4. n8n conserva la credencial de Claude y consulta Nhost; aquí solo hay cálculo determinista."""
from __future__ import annotations

import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from jsonschema import ValidationError

from . import contrato, entrada
from .construir import HomologacionInvalida, build

app = FastAPI(title="CostFlow E4", docs_url=None, redoc_url=None)
MODELO = os.getenv("E4_MODELO", "claude-sonnet-5-5")


def internal(x_costflow_internal_key: str | None = Header(default=None)):
    expected = os.getenv("E3_INTERNAL_KEY", "")
    if not expected or not hmac.compare_digest(x_costflow_internal_key or "", expected):
        raise HTTPException(401, "Acceso interno no válido.")


@app.get("/health")
def health():
    return {"ok": True, "modelo": MODELO}


@app.post("/e4/preparar", dependencies=[Depends(internal)])
def preparar(payload: dict):
    """Recibe el paquete de Nhost (entrada_e4) y devuelve la petición lista para Claude y la huella de la entrada."""
    preparado = entrada.prepare(payload["paquete"])
    return {"huella": preparado["huella"], "version_ids": preparado["version_ids"], "base": preparado["base"]["tipo"],
            "postores": len(preparado["postores"]), "sin_final": preparado["sin_final"], "modelo": MODELO,
            "cuerpo_claude": contrato.request(preparado, MODELO)}


@app.post("/e4/construir", dependencies=[Depends(internal)])
def construir(payload: dict):
    """Valida la respuesta de Claude contra la entrada y arma homologacion.json. Un error de formato es reintentable."""
    preparado = entrada.prepare(payload["paquete"])
    try:
        homologacion = build(preparado, contrato.parse_text(payload["texto"]), payload.get("modelo", MODELO))
    except HomologacionInvalida as error:
        return JSONResponse(status_code=422, content={"resultado": "respuesta_invalida", "errores": error.errores})
    except (ValueError, ValidationError) as error:
        return JSONResponse(status_code=422, content={"resultado": "respuesta_invalida", "errores": [str(error)[:300]]})
    return {"resultado": "construida", "homologacion": homologacion, "estado_revision": homologacion["estado_revision"],
            "huella": preparado["huella"], "version_ids": preparado["version_ids"]}
