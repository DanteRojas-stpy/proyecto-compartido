"""Instala el apoyo local y los cinco flujos usando las credenciales existentes de n8n.

No descifra ni exporta contraseñas. Solo copia referencias de credenciales.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OLD_IDS = {"1ZkKft0tTPY0oeC7", "uSw30Vtt0Os8tza1", "SW4rHcXjJgPMtdUI",
           "costflowEspecialistaNhostV2", "costflowExportTest20261026", "costflowFormatTest20261027",
           "costflowStorageReview20261027", "costflowStorageBackup20261027", "costflowStorageDelete20261027",
           "costflowSpecialistSchema20261027", "costflowSpecialistPgSetup20261027", "costflowSpecialistParamsTest"}


def docker(*args, capture=False):
    return subprocess.run(["docker", *args], check=True, text=True,
                          stdout=subprocess.PIPE if capture else subprocess.DEVNULL).stdout


def n8n(*args):
    return docker("exec", "-u", "node", "n8n", "n8n", *args)


def bindings() -> dict:
    code = """const{DatabaseSync}=require('node:sqlite');const db=new DatabaseSync('/home/node/.n8n/database.sqlite',{readOnly:true});
const creds=db.prepare('SELECT id,name,type FROM credentials_entity').all();
const rows=db.prepare('SELECT id,nodes FROM workflow_entity').all();const source=rows.find(x=>x.id==='1ZkKft0tTPY0oeC7');
const storage=source?JSON.parse(source.nodes).find(n=>n.type==='n8n-nodes-base.httpRequest'&&n.credentials?.httpHeaderAuth)?.credentials.httpHeaderAuth:null;
const headers=creds.filter(c=>c.type==='httpHeaderAuth'&&!/gemini|interno/i.test(c.name));
console.log(JSON.stringify({postgres:creds.find(c=>c.type==='postgres'),gmail:creds.find(c=>c.type==='gmailOAuth2'),storage:storage||headers.find(c=>/nhost|storage|hasura/i.test(c.name))||(headers.length===1?headers[0]:null),
gemini:creds.find(c=>c.type==='httpHeaderAuth'&&/gemini/i.test(c.name)),running:db.prepare("SELECT count(*) n FROM execution_entity WHERE status='running' AND deletedAt IS NULL").get().n}));"""
    return json.loads(docker("exec", "n8n", "node", "-e", code, capture=True))


def environment() -> dict:
    path = ROOT / ".env.e3"
    data = {}
    if path.exists():
        data = dict(line.split("=", 1) for line in path.read_text(encoding="utf-8-sig").splitlines()
                    if "=" in line and not line.startswith("#"))
    data.setdefault("E3_INTERNAL_KEY", secrets.token_hex(32))
    data.setdefault("NHOST_SUBDOMAIN", "zgorsmkvfyytsouacrpa")
    data.setdefault("NHOST_REGION", "sa-east-1")
    path.write_text("\n".join(f"{k}={v}" for k, v in data.items()) + "\n", encoding="utf-8")
    return data


def install(publicar=False, retirar=False):
    subprocess.run([os.sys.executable, str(ROOT / "n8n/etapa3/generar.py")], cwd=ROOT, check=True)
    refs = bindings()
    if not refs["postgres"] or not refs["gmail"] or not refs["storage"]:
        raise RuntimeError("Asigna primero las credenciales Postgres, Gmail y Storage en n8n.")
    env = environment()
    with tempfile.TemporaryDirectory(prefix="costflow-e3-") as temporary:
        folder = Path(temporary)
        credential = [{"id": "costflowE3Interna", "name": "CostFlow E3 - Acceso interno", "type": "httpHeaderAuth",
                       "data": {"name": "X-Costflow-Internal-Key", "value": env["E3_INTERNAL_KEY"]}}]
        credential_path = folder / "credencial-interna.json"
        credential_path.write_text(json.dumps(credential), encoding="utf-8")
        docker("cp", str(credential_path), "n8n:/tmp/e3-credencial-interna.json")
        n8n("import:credentials", "--input=/tmp/e3-credencial-interna.json")
        docker("exec", "-u", "0", "n8n", "node", "-e", "require('fs').unlinkSync('/tmp/e3-credencial-interna.json')")
        credential_path.unlink()
        refs["internal"] = {"id": "costflowE3Interna", "name": "CostFlow E3 - Acceso interno"}
        workflows = []
        for path in sorted((ROOT / "n8n/etapa3").glob("e3-*.json")):
            workflow = json.loads(path.read_text(encoding="utf-8"))
            for node in workflow["nodes"]:
                marker = node.get("notes", "")
                if marker.startswith("CREDENCIAL_E3:"):
                    kind = marker.split(":", 1)[1]
                    credential_type = {"gmail": "gmailOAuth2", "postgres": "postgres"}.get(kind, "httpHeaderAuth")
                    if refs.get(kind):
                        node["credentials"] = {credential_type: {"id": refs[kind]["id"], "name": refs[kind]["name"]}}
                if "url" in node["parameters"]:
                    node["parameters"]["url"] = node["parameters"]["url"].replace("SUBDOMINIO", env["NHOST_SUBDOMAIN"]).replace("REGION", env["NHOST_REGION"])
            workflows.append(workflow)
        path = folder / "flujos.json"
        path.write_text(json.dumps(workflows), encoding="utf-8")
        docker("cp", str(path), "n8n:/tmp/e3-nuevos.json")
        if retirar:
            n8n("export:workflow", "--all", "--output=/tmp/e3-anteriores-para-retirar.json")
            old_path = folder / "anteriores.json"
            docker("cp", "n8n:/tmp/e3-anteriores-para-retirar.json", str(old_path))
            old = [w for w in json.loads(old_path.read_text(encoding="utf-8")) if w["id"] in OLD_IDS]
            for workflow in old:
                workflow["active"] = False
                workflow["isArchived"] = True
                if not workflow["name"].startswith("[ANTERIOR]"):
                    workflow["name"] = "[ANTERIOR] " + workflow["name"]
                for node in workflow["nodes"]:
                    if node["type"] in {"n8n-nodes-base.webhook", "n8n-nodes-base.manualTrigger", "n8n-nodes-base.gmailTrigger", "n8n-nodes-base.scheduleTrigger", "n8n-nodes-base.executeWorkflowTrigger"}:
                        node["disabled"] = True
            old_path.write_text(json.dumps(old), encoding="utf-8")
            docker("cp", str(old_path), "n8n:/tmp/e3-retirados.json")
            n8n("import:workflow", "--input=/tmp/e3-retirados.json")
        n8n("import:workflow", "--input=/tmp/e3-nuevos.json")
        if publicar:
            for workflow in workflows:
                n8n("publish:workflow", "--id=" + workflow["id"])
    network = subprocess.run(["docker", "network", "inspect", "costflow_e3"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if network.returncode:
        docker("network", "create", "costflow_e3")
    connected = json.loads(docker("inspect", "n8n", "--format", "{{json .NetworkSettings.Networks}}", capture=True))
    if "costflow_e3" not in connected:
        docker("network", "connect", "costflow_e3", "n8n")
    subprocess.run(["docker", "compose", "-f", "compose.etapa3.yml", "up", "-d", "--build"], cwd=ROOT, check=True)
    print("Cinco flujos importados. Gemini permanece pendiente hasta asignar su credencial y habilitar la configuración.")
    if publicar:
        print("Reinicia n8n cuando no haya ejecuciones en curso para registrar las entradas publicadas.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--publicar", action="store_true")
    parser.add_argument("--retirar-anteriores", action="store_true")
    args = parser.parse_args()
    install(args.publicar, args.retirar_anteriores)
