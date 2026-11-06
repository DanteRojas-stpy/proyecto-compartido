# Llevar E3, E4 y E5 a n8n en la nube

> **E5 ya no necesita servidor:** el cuadro comparativo se arma dentro de n8n (nodos «Compression» y de código; ver
> `n8n/etapa5/README.md`). Solo E3 (lector) y E4 (homologación) siguen necesitando un servicio con dirección pública.

Esta guía mueve los flujos de n8n (hoy en tu Docker) a una instancia de n8n Cloud y los servicios de apoyo a un
servidor con HTTPS. Nhost, el front y las migraciones **no cambian**.

## Cómo queda

```
Front ──► Function de Nhost ──► cola en Nhost
                 │ (aviso)            ▲
                 ▼                    │
        n8n Cloud (flujos E3, E4, E5) ──► Claude, Gmail, Storage
                 │            ▲
                 ▼            │ (webhooks internos de E3)
   Servidor con Docker (compose.nube.yml): lector E3, detrás de HTTPS (E4 y E5 corren dentro de n8n y no necesitan servidor)
```

n8n Cloud no puede llegar a `http://costflow-etapa3:8093` y similares (son nombres internos de tu Docker). Por eso los
tres servicios van a un servidor con dirección pública, y el programa `scripts/n8n_nube.py` cambia las direcciones de los
flujos.

## Qué necesitas
- Una instancia de n8n Cloud y una **clave de API** (Settings → n8n API). Revisa que tu plan incluya la API.
- Un servidor con Docker, 2 vCPU y **4 GB de RAM** (el lector de E3 usa OCR y modelos de embeddings), y tres nombres de
  dominio que apunten a su IP: por ejemplo `e3.tudominio.com`, `e4.…`, `e5.…`.
- La misma clave interna `E3_INTERNAL_KEY` que ya usas en Nhost.

## Pasos

### 1. Servicios en el servidor
```bash
git clone https://github.com/DanteRojas-stpy/proyecto-compartido.git && cd proyecto-compartido
cp deploy/nube.env.example deploy/nube.env      # completa las variables
docker compose -f compose.nube.yml --env-file deploy/nube.env up -d --build
curl https://e3.tudominio.com/health            # debe responder {"ok":true,...}
```
Abre solo los puertos 80 y 443. El servicio de E3 llama de vuelta a n8n usando `N8N_URL`.

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
  --servicio-e3-url https://e3.tudominio.com
```
Crea (o actualiza) los siete flujos en el orden correcto y **enlaza E3.1, E3.2, E3.3 y E3.5 entre sí** con los
identificadores nuevos. Quedan **inactivos**. Si prefieres importar a mano, `preparar --salida n8n-nube` deja los JSON
listos (sin credenciales) en esa carpeta, pero tendrás que volver a enlazar los nodos «Invocar/Reintentar/Notificar».

Al terminar, el programa imprime qué nodo necesita qué credencial: asígnalas en n8n.

### 4. Avisos del botón (recomendado)
En n8n, copia la **URL de producción** del nodo «Aviso del botón» de E4 y de E5 (terminan en `/webhook/e4-ejecutar` y
`/webhook/e5-ejecutar`). En Nhost, en las variables de entorno de las Functions, agrega:

- `N8N_AVISO_E4` = URL de producción del webhook de E4
- `N8N_AVISO_E5` = URL de producción del webhook de E5

y vuelve a desplegar. Así, al pulsar «Homologar» o «Generar cuadro» el flujo arranca de inmediato y el sondeo queda solo
como respaldo (cada 30 minutos). Sin estas variables todo sigue funcionando, pero esperando al sondeo.

### 5. Apagar los flujos locales y activar los de la nube
Desactiva E3, E4 y E5 en tu n8n local **antes** de activar los de la nube, para que no compitan por la misma cola. Luego
activa los siete flujos en n8n Cloud (o vuelve a correr `subir --activar` con las credenciales ya asignadas).

### 6. Prueba mínima
1. En el front, abre MA-001 y pulsa «Homologar»: debe terminar en 1–3 minutos.
2. Pulsa «Generar cuadro» y luego «Descargar Excel».
3. Revisa en n8n Cloud, en Executions, que no haya errores.

## Cuota de ejecuciones (lo que más sorprende)
En n8n Cloud cada ejecución cuenta para el plan. Con el sondeo de cada minuto de hoy, cada flujo haría unas 43 000
ejecuciones al mes. El programa lo baja por defecto a **5 minutos** para E3.1 y E3.5 (≈ 8 600 al mes cada uno) y a
**30 minutos** para E4 y E5, que además despiertan por el aviso del botón. Ajusta con `--intervalo-e3` y
`--intervalo-cola` según el límite de tu plan. Un intervalo mayor para E3.1 retrasa la lectura de los correos nuevos
(hasta ese tiempo).

## Lo que esta guía no cubre
- Los flujos de las primeras etapas (`n8n/flujos/`: envío de solicitudes, seguimiento diario, análisis de respuestas con
  Gemini y estados) no están en el programa: exporta e importa esos desde n8n si también deben ir a la nube.
- No se probó contra una instancia real de n8n Cloud; las pruebas automáticas usan una API simulada. La primera subida
  conviene hacerla con un solo flujo activo a la vez.
