"""Prepara la web estática; nunca copia servicios, archivos locales ni secretos."""

import json
import os
import re
import shutil
from pathlib import Path


def preparar(destino: Path, fuente: Path) -> None:
    subdominio = os.environ.get("NHOST_SUBDOMAIN", "zgorsmkvfyytsouacrpa")
    region = os.environ.get("NHOST_REGION", "sa-east-1")
    for nombre, valor in (("NHOST_SUBDOMAIN", subdominio), ("NHOST_REGION", region)):
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", valor):
            raise ValueError(f"{nombre} debe contener solo letras minúsculas, números y guiones.")

    # Fallar si ya existe evita sobrescribir otra carpeta por accidente.
    destino.mkdir(parents=True, exist_ok=False)
    shutil.copy2(fuente / "index.html", destino / "index.html")
    for carpeta in ("css", "js", "assets"):
        origen = fuente / carpeta
        if origen.is_dir():
            shutil.copytree(
                origen,
                destino / carpeta,
                ignore=shutil.ignore_patterns(".*", "config.local.js", "config.example.js", "*.md"),
            )

    # Estos dos identificadores son públicos. No se utilizan credenciales de n8n o Nhost.
    (destino / "js" / "config.local.js").write_text(
        f"export const NHOST_SUBDOMAIN = {json.dumps(subdominio)};\n"
        f"export const NHOST_REGION = {json.dumps(region)};\n",
        encoding="utf-8",
    )
    (destino / ".nojekyll").touch()


if __name__ == "__main__":
    raiz = Path(__file__).resolve().parents[1]
    preparar(raiz / "_site", raiz / "frontend")
    print("Frontend preparado en _site/.")
