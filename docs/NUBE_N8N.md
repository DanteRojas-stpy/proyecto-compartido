# Llevar E3, E4 y E5 a n8n en la nube

E4 (homologación) y E5 (cuadro comparativo) **corren dentro de n8n** con nodos de código (y «Compression» para el Excel): no
necesitan servidor. Solo E3 (lectura de cotizaciones) sigue necesitando un servicio aparte, por el OCR y la búsqueda de
fragmentos. Esta guía lleva los flujos a una instancia de n8n Cloud y ese servicio a un servidor con HTTPS. Nhost, el front y
las migraciones **no cambian**.

## Cómo queda

```
Front ──► Function de Nhost ──► cola en Nhost
                 │ (aviso)            ▲
                 ▼                    │
        n8n Cloud (flujos E3, E4, E5) ──► Claude, Gmail, Storage
                 │            ▲
                 ▼            │ (webhooks internos de E3)
   Servidor (compose.nube.yml): lector de E3 detrás de HTTPS
```

n8n Cloud no puede llegar a `http://costflow-etapa3:8093` (es un nombre interno de tu Docker). Por eso el lector de E3 va a un
servidor con dirección pública, y `scripts/n8n_nube.py` cambia esa dirección en los flujos.

## Qué necesitas
- Una instancia de n8n Cloud. Para subir los flujos con el programa hace falta una **clave de API** (Settings → n8n API); si
  tu plan no la trae, se importan a mano (ver «Sin API»).
- Un servidor con Docker, 2 vCPU y **4 GB de RAM** o más. Opción gratuita: Oracle Cloud «Always Free» (abajo).
- La misma clave interna `E3_INTERNAL_KEY` que ya usas en Nhost.

## Paso a paso

### 1. El servidor del lector de E3 (Oracle Cloud «Always Free»)
Oracle ofrece una máquina virtual ARM sin costo (hasta 4 núcleos y 24 GB). Los servicios de CostFlow se construyen también para ARM.

1. **Cuenta.** Crea una cuenta en <https://www.oracle.com/cloud/free/>. Pide una tarjeta para verificar la identidad; dentro de los
   límites gratuitos no se cobra. Elige la región de origen con cuidado: no se puede cambiar después.
2. **Pasa la cuenta a «Pay As You Go».** Sigue siendo gratis mientras no superes los límites de Always Free, y evita que Oracle
   recupere por inactividad las máquinas gratuitas (el lector pasa la mayor parte del tiempo sin trabajo). Confirma las
   condiciones vigentes en Oracle.
3. **Crea la máquina.** Menú → Compute → Instances → *Create instance*:
   - Imagen: **Canonical Ubuntu 24.04** (la versión para ARM, `aarch64`).
   - Forma: **VM.Standard.A1.Flex** (Ampere). Con **2 OCPU y 12 GB** sobra; hasta 4 y 24 GB son gratis.
   - Red: asigna una **IP pública**.
   - Llave SSH: en PowerShell ejecuta `ssh-keygen -t ed25519` y sube el contenido del archivo `.pub` (la llave privada no se comparte).
   - Si Oracle responde «Out of capacity», prueba más tarde u otro dominio de disponibilidad.
4. **Abre los puertos.** En la red de la máquina (Networking → VCN → Security List) agrega reglas de entrada **TCP 80 y 443** desde
   `0.0.0.0/0`. Sin esto no se obtiene el certificado ni se llega al servicio.
5. **Instala.** Conéctate y ejecuta el instalador:
   ```bash
   ssh -i RUTA_DE_TU_LLAVE ubuntu@LA_IP_PUBLICA
   curl -fsSL https://raw.githubusercontent.com/DanteRojas-stpy/proyecto-compartido/main/deploy/instalar-servidor.sh -o instalar.sh
   sudo bash instalar.sh
   ```
   Pide la dirección de tu n8n Cloud, los datos de Nhost y la clave interna (se escribe escondida y se guarda solo en
   `deploy/nube.env`, con permisos 600). Instala Docker, construye y levanta el lector con HTTPS y comprueba que responda.
6. **Direcciones.** No necesitas dominio: usa un nombre `sslip.io` que apunta a la IP (por ejemplo `https://e3.203-0-113-10.sslip.io`)
   y obtiene el certificado solo. Al terminar, el instalador imprime la dirección y el comando del paso 3. Si Let's Encrypt limitara
   los certificados de `sslip.io` (es un dominio compartido), usa un dominio propio y edita `deploy/nube.env`.
7. **Actualizar más adelante:** `cd /opt/costflow && git pull && docker compose -f compose.nube.yml --env-file deploy/nube.env up -d --build`.

Con otro proveedor (Hetzner, DigitalOcean…) los pasos 3 a 5 son equivalentes; usa Ubuntu 22.04 o 24.04 con 4 GB.

### 2. Credenciales en n8n Cloud (se crean a mano; no se pueden copiar)
| Nombre | Tipo | Valor |
|---|---|---|
| `CostFlow E3 - Acceso interno` | Header Auth | cabecera `X-Costflow-Internal-Key`, valor `E3_INTERNAL_KEY` |
| `CostFlow E3 - Claude` | Header Auth | cabecera `x-api-key`, valor tu clave de Anthropic |
| `CostFlow E3 - Nhost Storage` | Header Auth | cabecera `x-hasura-admin-secret`, valor el secreto de Nhost |
| Gmail | Gmail OAuth2 | vuelve a autorizar la cuenta de Google desde n8n Cloud |

Escribe cada valor directamente en n8n. No los pegues en chats, archivos del repositorio ni argumentos de comandos.

### 3. Subir los flujos
```bash
export N8N_API_KEY=...                     # solo en tu terminal
python scripts/n8n_nube.py subir \
  --n8n-url https://tuinstancia.app.n8n.cloud \
  --nhost-subdomain <subdominio-de-nhost> --nhost-region sa-east-1 \
  --servicio-e3-url https://e3.203-0-113-10.sslip.io
```
Crea (o actualiza) los siete flujos en el orden correcto y **enlaza E3.1, E3.2, E3.3 y E3.5 entre sí** con los identificadores
nuevos. Quedan **inactivos**. Al terminar, el programa imprime qué nodo necesita qué credencial: asígnalas en n8n.

**Sin API.** `python scripts/n8n_nube.py preparar --salida n8n-nube ...` deja los JSON listos (sin credenciales) para importarlos
desde el menú de n8n. Al importar, n8n cambia los identificadores: hay que volver a enlazar a mano los nodos «Invocar E3.2»,
«Notificar error definitivo» (E3.1), «Invocar E3.3» (E3.2) y «Reintentar E3.1», «Reintentar E3.2», «Notificar agotamiento» (E3.5).

### 4. Avisos del botón (recomendado)
En n8n, copia la **URL de producción** del nodo «Aviso del botón» de E4 y de E5 (terminan en `/webhook/e4-ejecutar` y
`/webhook/e5-ejecutar`). En Nhost, en las variables de entorno de las Functions, agrega:

- `N8N_AVISO_E4` = URL de producción del webhook de E4
- `N8N_AVISO_E5` = URL de producción del webhook de E5

y vuelve a desplegar. Así, al pulsar «Homologar» o «Generar cuadro» el flujo arranca de inmediato y el sondeo queda solo como
respaldo (cada 30 minutos). Sin estas variables todo sigue funcionando, pero esperando al sondeo.

### 5. Apagar los flujos locales y activar los de la nube
Desactiva E3, E4 y E5 en tu n8n local **antes** de activar los de la nube, para que no compitan por la misma cola. Luego activa
los siete flujos en n8n Cloud.

### 6. Prueba mínima
1. En el front, abre MA-001 y pulsa «Homologar»: debe terminar en 1–3 minutos.
2. Pulsa «Generar cuadro» y luego «Descargar Excel».
3. Revisa en n8n Cloud, en Executions, que no haya errores.

## Cuota de ejecuciones (lo que más sorprende)
En n8n Cloud cada ejecución cuenta para el plan. Con el sondeo de cada minuto, cada flujo haría unas 43 000 ejecuciones al mes.
El programa lo baja por defecto a **5 minutos** para E3.1 y E3.5 (≈ 8 600 al mes cada uno) y a **30 minutos** para E4 y E5, que
además despiertan por el aviso del botón. Ajusta con `--intervalo-e3` y `--intervalo-cola` según el límite de tu plan. Un
intervalo mayor para E3.1 retrasa la lectura de los correos nuevos (hasta ese tiempo).

## Lo que esta guía no cubre
- Los flujos de las primeras etapas (`n8n/flujos/`: envío de solicitudes, seguimiento diario, análisis de respuestas con Gemini y
  estados) no están en el programa: exporta e importa esos desde n8n si también deben ir a la nube.
- No se probó contra una instancia real de n8n Cloud ni de Oracle; las pruebas automáticas usan una API simulada y el servicio
  se construyó para ARM en un emulador.
