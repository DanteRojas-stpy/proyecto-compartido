"""E3 dentro de n8n: el JavaScript del lector equivale a app/etapa3 (que queda como referencia) y cubre lo que n8n aporta (PDF, Claude)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="Estas pruebas ejecutan el código de los nodos y requieren Node.js.")


def test_el_javascript_del_lector_da_lo_mismo_que_python(tmp_path):
    from casos_lector import CASOS
    archivo = tmp_path / "casos_e3.json"
    archivo.write_text(json.dumps(CASOS, ensure_ascii=False, default=str), encoding="utf-8")
    r = subprocess.run([NODE, "--test", str(ROOT / "tests/etapa3/lector_paridad.test.js")], capture_output=True, text=True, encoding="utf-8",
                       env={**os.environ, "CASOS": str(archivo)}, timeout=240)
    assert r.returncode == 0, r.stdout[-3500:] + r.stderr[-1500:]
