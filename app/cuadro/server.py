"""Servicio local de E5. Llena la plantilla con la homologación; n8n conserva Storage y las colas."""
from __future__ import annotations

import base64
import binascii
import hmac
import os

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from .llenar import CuadroNoGenerable, generar

app = FastAPI(title="CostFlow E5", docs_url=None, redoc_url=None)


def internal(x_costflow_internal_key: str | None = Header(default=None)):
    expected = os.getenv("E3_INTERNAL_KEY", "")
    if not expected or not hmac.compare_digest(x_costflow_internal_key or "", expected):
        raise HTTPException(401, "Acceso interno no válido.")


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/e5/generar", dependencies=[Depends(internal)])
def generar_cuadro(payload: dict):
    """Recibe homologacion, tipo_cambio (o null) y la plantilla en base64. Devuelve el xlsx en base64 y la validación.
    Un cuadro que no se puede armar responde 422 con recuperable=false: reintentar no lo arregla."""
    try:
        plantilla = base64.b64decode(payload["plantilla_b64"], validate=True)
    except (KeyError, binascii.Error, ValueError):
        return JSONResponse({"ok": False, "recuperable": False, "error": "La plantilla no llegó o no es válida."}, status_code=422)
    try:
        archivo, validacion = generar(plantilla, payload["homologacion"], payload.get("tipo_cambio"))
    except CuadroNoGenerable as error:
        return JSONResponse({"ok": False, "recuperable": False, "error": str(error)}, status_code=422)
    return {"ok": True, "estado": "validado" if validacion["validado"] else "borrador", "validacion": validacion,
            "archivo_b64": base64.b64encode(archivo).decode()}
