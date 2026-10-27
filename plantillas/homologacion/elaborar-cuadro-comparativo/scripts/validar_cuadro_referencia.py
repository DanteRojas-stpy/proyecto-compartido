#!/usr/bin/env python3
"""Valida comprobaciones del formato histórico de referencia.

No es un validador universal de plantillas ni valida homologación técnica.
Consultar references/validacion.md para conocer sus límites.

Uso:
    python3 validar_cuadro_referencia.py cuadro.xlsx [entrada.json]

Revisa:
  1. 0 errores de fórmula (#REF!, #DIV/0!, #VALUE!, #NAME?, #N/A) en todas las hojas.
  2. Hoja 1: la Hoja 1 no tiene vínculos a otras hojas (solo fórmulas internas).
  3. Subtotal sin IGV de cada postor en Hoja 1 y Hoja 2 = total declarado de su cotización
     (si se pasa entrada.json con "total_declarado_sin_igv"), tolerancia S/ 0.50.
  4. Hoja 1 y Hoja 2 dan el mismo subtotal por postor.
Sale con código 1 si algo falla.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

from openpyxl import load_workbook

ERRS = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!")


def recalcular(path):
    tmp = tempfile.mkdtemp()
    src = os.path.join(tmp, "in_" + os.path.basename(path))
    shutil.copy(path, src)
    out = os.path.join(tmp, "out")
    os.makedirs(out)
    cmd = ["soffice", "--headless", "--calc", "--convert-to", "xlsx:Calc MS Excel 2007 XML", "--outdir", out, src]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    return os.path.join(out, os.path.basename(src))


def subtotales(ws_v, ws_f, etiqueta_col, etiqueta):
    """Lee el subtotal sin IGV de cada postor buscando la fila por su rótulo."""
    fila = None
    for r in range(8, ws_v.max_row + 1):
        for c in range(2, 7):  # el rótulo puede estar en B, D o E según la hoja
            v = ws_v.cell(r, c).value
            if isinstance(v, str) and v.strip().upper().startswith(etiqueta):
                fila = r
                break
        if fila:
            break
    if fila is None:
        return {}
    res = {}
    for rg in ws_f.merged_cells.ranges:
        if rg.min_row == 6 and rg.min_col >= 8 and rg.max_col - rg.min_col >= 2:
            nombre = ws_f.cell(6, rg.min_col).value
            if not nombre or "OBSERVACIONES" in str(nombre).upper():
                continue
            # columna de total = última columna "Parcial" del bloque
            tot = None
            for c in range(rg.min_col, rg.max_col + 1):
                h = str(ws_f.cell(7, c).value or "").upper()
                if "PARCIAL" in h:
                    tot = c
            if tot:
                res[str(nombre)] = ws_v.cell(fila, tot).value
    return res


def main():
    path = sys.argv[1]
    spec = json.load(open(sys.argv[2], encoding="utf-8")) if len(sys.argv) > 2 else None
    ok = True
    rec = recalcular(path)
    wv = load_workbook(rec, data_only=True)
    wf = load_workbook(path)
    n_err = 0
    for ws in wv.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if isinstance(c.value, str) and c.value.strip() in ERRS:
                    n_err += 1
                    if n_err <= 20:
                        print(f"  ERROR {ws.title}!{c.coordinate}: {c.value}")
    print(f"[{'OK' if n_err == 0 else 'FALLA'}] Errores de fórmula: {n_err}")
    ok &= n_err == 0

    h1f = wf.worksheets[0]
    links = [c.coordinate for row in h1f.iter_rows() for c in row
             if isinstance(c.value, str) and c.value.startswith("=") and "!" in c.value]
    print(f"[{'OK' if not links else 'FALLA'}] Hoja 1 sin vínculos a otras hojas"
          + ("" if not links else f": {', '.join(links[:10])}"))
    ok &= not links

    s1 = subtotales(wv.worksheets[0], h1f, 5, "SUBTOTAL")
    s2 = subtotales(wv.worksheets[1], wf.worksheets[1], 2, "SUBTOTAL")
    decl = {}
    if spec:
        decl = {p["nombre"]: p.get("total_declarado_sin_igv") for p in spec["postores"]}
    for nombre, v1 in s1.items():
        v2 = s2.get(nombre)
        linea = f"  {nombre}: Hoja 1 {v1:,.2f}" if isinstance(v1, (int, float)) else f"  {nombre}: Hoja 1 {v1}"
        if isinstance(v2, (int, float)):
            linea += f" | Hoja 2 {v2:,.2f}"
        good = isinstance(v1, (int, float)) and (v2 is None or abs(v1 - v2) < 0.5)
        d = decl.get(nombre)
        if d is not None:
            linea += f" | declarado {float(d):,.2f}"
            good &= isinstance(v1, (int, float)) and abs(v1 - float(d)) < 0.5
        print(("[OK] " if good else "[FALLA] ") + linea.strip())
        ok &= good
    if not s1:
        print("[FALLA] No se encontró la fila SUBTOTAL en la Hoja 1")
        ok = False
    print("RESULTADO:", "VALIDADO" if ok else "CON OBSERVACIONES")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
