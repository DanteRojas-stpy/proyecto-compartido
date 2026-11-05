#!/usr/bin/env bash
# Instala los servicios de CostFlow (lector E3, homologación E4 y cuadro E5) con HTTPS en un servidor Ubuntu nuevo.
# Uso (como root, por SSH):   curl -fsSL https://raw.githubusercontent.com/DanteRojas-stpy/proyecto-compartido/main/deploy/instalar-servidor.sh -o instalar.sh && sudo bash instalar.sh
# No necesita dominio propio: usa nombres sslip.io que apuntan a la IP del servidor y obtienen certificado solos.
# La clave interna se pide escondida y se guarda solo en deploy/nube.env (permisos 600); no se imprime ni se sube a Git.
set -euo pipefail

[ "$(id -u)" -eq 0 ] || { echo "Ejecuta como root: sudo bash instalar.sh" >&2; exit 1; }
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
DOMINIO_E3="e3.${SUF}.sslip.io"; DOMINIO_E4="e4.${SUF}.sslip.io"; DOMINIO_E5="e5.${SUF}.sslip.io"

echo "== 2/6 Docker y firewall =="
if ! command -v docker >/dev/null 2>&1; then curl -fsSL https://get.docker.com | sh; fi
if command -v ufw >/dev/null 2>&1; then ufw allow 22/tcp >/dev/null; ufw allow 80/tcp >/dev/null; ufw allow 443/tcp >/dev/null; ufw --force enable >/dev/null; fi

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
DOMINIO_E4=${DOMINIO_E4}
DOMINIO_E5=${DOMINIO_E5}
EOF
chmod 600 deploy/nube.env

echo "== 5/6 Construyendo y levantando (la primera vez tarda unos minutos) =="
docker compose -f compose.nube.yml --env-file deploy/nube.env up -d --build

echo "== 6/6 Comprobando =="
for dominio in "$DOMINIO_E3" "$DOMINIO_E4" "$DOMINIO_E5"; do
  ok=""
  for _ in $(seq 1 40); do
    if curl -fsS "https://${dominio}/health" >/dev/null 2>&1; then ok="sí"; break; fi
    sleep 5
  done
  echo "  https://${dominio}/health -> ${ok:-NO responde todavía (revisa: docker compose -f compose.nube.yml logs)}"
done

cat <<EOF

Listo. Direcciones públicas de los servicios:
  E3 (lector):        https://${DOMINIO_E3}
  E4 (homologación):  https://${DOMINIO_E4}
  E5 (cuadro):        https://${DOMINIO_E5}

Siguiente paso (en tu equipo, con el repositorio): generar los flujos para n8n Cloud:
  python scripts/n8n_nube.py preparar --nhost-subdomain ${NHOST_SUBDOMAIN} --nhost-region ${NHOST_REGION} \\
    --servicio-e3-url https://${DOMINIO_E3} --servicio-e4-url https://${DOMINIO_E4} --servicio-e5-url https://${DOMINIO_E5}
EOF
