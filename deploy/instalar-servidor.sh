#!/usr/bin/env bash
# Instala el servicio de lectura de E3 de CostFlow con HTTPS en un servidor Ubuntu nuevo (Oracle Cloud «Always Free» u otro).
# E4 y E5 corren dentro de n8n y no necesitan servidor: aquí solo va el lector (OCR y búsqueda de fragmentos).
# Uso (por SSH):  curl -fsSL https://raw.githubusercontent.com/DanteRojas-stpy/proyecto-compartido/main/deploy/instalar-servidor.sh -o instalar.sh && sudo bash instalar.sh
# No necesita dominio propio: usa un nombre sslip.io que apunta a la IP del servidor y obtiene el certificado solo.
# La clave interna se pide escondida y se guarda solo en deploy/nube.env (permisos 600); no se imprime ni se sube a Git.
# Funciona en x86 y en ARM (las máquinas Ampere de Oracle).
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta con sudo: sudo bash instalar.sh" >&2; exit 1; }
REPO_URL="https://github.com/DanteRojas-stpy/proyecto-compartido.git"
DESTINO="/opt/costflow"

echo "== 1/6 Datos que necesito =="
IP="$(curl -4 -fsS https://api.ipify.org)"
SUF="$(echo "$IP" | tr '.' '-')"
read -r -p "Dirección de tu n8n Cloud (sin barra final) [https://especialistacotizaciones.app.n8n.cloud]: " N8N_URL
N8N_URL="${N8N_URL:-https://especialistacotizaciones.app.n8n.cloud}"
read -r -p "Subdominio de Nhost [zgorsmkvfyytsouacrpa]: " NHOST_SUBDOMAIN
NHOST_SUBDOMAIN="${NHOST_SUBDOMAIN:-zgorsmkvfyytsouacrpa}"
read -r -p "Región de Nhost [sa-east-1]: " NHOST_REGION
NHOST_REGION="${NHOST_REGION:-sa-east-1}"
read -r -s -p "Clave interna E3_INTERNAL_KEY (la misma de Nhost y de n8n; no se muestra): " E3_INTERNAL_KEY; echo
[ -n "$E3_INTERNAL_KEY" ] || { echo "La clave interna no puede estar vacía." >&2; exit 1; }
DOMINIO_E3="e3.${SUF}.sslip.io"

echo "== 2/6 Docker y firewall del servidor ($(uname -m)) =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq && apt-get install -y -qq curl git ca-certificates >/dev/null
if ! command -v docker >/dev/null 2>&1; then curl -fsSL https://get.docker.com | sh; fi
# Las imágenes de Oracle traen reglas de iptables que rechazan casi todo: se abren 80 y 443 (los certificados se piden por el 80).
if command -v iptables >/dev/null 2>&1; then
  for puerto in 80 443; do
    iptables -C INPUT -p tcp --dport "$puerto" -j ACCEPT 2>/dev/null || iptables -I INPUT 1 -p tcp --dport "$puerto" -j ACCEPT
  done
  if command -v netfilter-persistent >/dev/null 2>&1; then netfilter-persistent save >/dev/null 2>&1 || true; fi
fi

echo "== 3/6 Código =="
if [ -d "$DESTINO/.git" ]; then git -C "$DESTINO" pull --ff-only; else git clone --depth 1 "$REPO_URL" "$DESTINO"; fi
cd "$DESTINO"

echo "== 4/6 Configuración =="
umask 077
cat > deploy/nube.env <<EOF
E3_INTERNAL_KEY=${E3_INTERNAL_KEY}
NHOST_SUBDOMAIN=${NHOST_SUBDOMAIN}
NHOST_REGION=${NHOST_REGION}
N8N_URL=${N8N_URL}
DOMINIO_E3=${DOMINIO_E3}
EOF
chmod 600 deploy/nube.env

echo "== 5/6 Construyendo y levantando (la primera vez tarda varios minutos) =="
docker compose -f compose.nube.yml --env-file deploy/nube.env up -d --build

echo "== 6/6 Comprobando =="
ok=""
for _ in $(seq 1 60); do
  if curl -fsS "https://${DOMINIO_E3}/health" >/dev/null 2>&1; then ok="sí"; break; fi
  sleep 5
done
echo "  https://${DOMINIO_E3}/health -> ${ok:-NO responde todavía (revisa: docker compose -f compose.nube.yml logs; y que los puertos 80 y 443 estén abiertos en la red de Oracle)}"

cat <<EOF

Listo. Dirección pública del lector de E3:
  https://${DOMINIO_E3}

Siguiente paso (en tu equipo, con el repositorio): generar los flujos para n8n Cloud:
  python scripts/n8n_nube.py preparar --nhost-subdomain ${NHOST_SUBDOMAIN} --nhost-region ${NHOST_REGION} \\
    --servicio-e3-url https://${DOMINIO_E3}
EOF
