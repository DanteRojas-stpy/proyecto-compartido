import { timingSafeEqual } from 'node:crypto'
import type { Request, Response } from 'express'

// Solicitar E4 o E5 las hace el especialista desde el front, con su propia sesión.
// El resto de operaciones las usan n8n y los servicios, con la clave interna.
const OPERACIONES_DEL_ESPECIALISTA = new Set(['solicitar_e4', 'solicitar_e5'])
// El especialista descarga el Excel del cuadro a través de la Function: Storage solo lo lee la credencial administrativa.
const DESCARGAR_CUADRO = 'descargar_e5'
const OPERACIONES_INTERNAS = new Set([
  'tomar_e4',
  'entrada_e4',
  'guardar_e4',
  'fallo_e4',
  'tomar_e5',
  'entrada_e5',
  'guardar_e5',
  'fallo_e5',
])

function secretoValido(recibido: string, esperado: string): boolean {
  const a = Buffer.from(recibido)
  const b = Buffer.from(esperado)
  return a.length === b.length && timingSafeEqual(a, b)
}

function literal(valor: string): string {
  return `'${valor.replaceAll("'", "''")}'`
}

function baseHasura(): string {
  const configurada = process.env.NHOST_HASURA_URL ?? process.env.NHOST_GRAPHQL_URL
  if (!configurada) throw new Error('La URL de GraphQL/Hasura no está disponible en la función.')
  const url = new URL(configurada)
  if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) {
    throw new Error('La dirección de Hasura no es válida.')
  }
  if (/\.graphql\.[a-z0-9-]+\.nhost\.run$/.test(url.hostname)) {
    url.hostname = url.hostname.replace('.graphql.', '.hasura.')
    url.pathname = '/'
  } else {
    url.pathname = url.pathname.replace(/\/(?:console|v1\/(?:graphql|metadata)|v2\/query)\/?$/, '')
    if (url.pathname !== '' && url.pathname !== '/') throw new Error('Configura NHOST_HASURA_URL con la dirección administrativa de Hasura.')
  }
  return url.origin
}

function respuestaRunSql(payload: unknown): unknown {
  if (!payload || typeof payload !== 'object') throw new Error('Hasura no devolvió JSON.')
  const result = (payload as { result?: unknown }).result
  if (!Array.isArray(result) || result.length < 2 || !Array.isArray(result[1])) {
    throw new Error('Hasura no devolvió la respuesta de e4_operar.')
  }
  const value = result[1][0]
  if (typeof value !== 'string') throw new Error('La respuesta de e4_operar no es JSON.')
  return JSON.parse(value)
}

// Devuelve el id del usuario de Nhost a partir de su token de acceso, o null si no es válido.
async function usuarioVerificado(req: Request): Promise<string | null> {
  const cabecera = String(req.header('authorization') ?? '')
  const token = cabecera.startsWith('Bearer ') ? cabecera.slice(7).trim() : ''
  if (!token) return null
  const authBase = process.env.NHOST_AUTH_URL ?? `${baseHasura().replace('.hasura.', '.auth.')}/v1`
  const respuesta = await fetch(`${authBase}/user`, { headers: { Authorization: `Bearer ${token}` } })
  if (!respuesta.ok) return null
  const usuario = (await respuesta.json()) as { id?: unknown }
  return typeof usuario.id === 'string' ? usuario.id : null
}

// Orígenes del front que pueden llamar a la función desde el navegador (CORS).
const ORIGENES_PERMITIDOS = (process.env.CORS_ORIGINS ?? 'http://localhost:8000,http://127.0.0.1:8000')
  .split(',')
  .map((origen) => origen.trim())
  .filter(Boolean)

function baseStorage(): string {
  return `${baseHasura().replace('.hasura.', '.storage.')}/v1/files`
}

async function descargarCuadro(req: Request, res: Response, datos: unknown) {
  const usuario = await usuarioVerificado(req)
  if (!usuario) return res.status(401).json({ error: 'Inicia sesión para continuar.' })
  const cuadroId = typeof (datos as { cuadro_id?: unknown })?.cuadro_id === 'string' ? (datos as { cuadro_id: string }).cuadro_id : ''
  if (!/^[0-9a-f-]{36}$/i.test(cuadroId)) return res.status(400).json({ error: 'Operación o datos inválidos.' })
  const admin = process.env.NHOST_ADMIN_SECRET ?? process.env.HASURA_GRAPHQL_ADMIN_SECRET ?? ''
  if (!admin) return res.status(503).json({ error: 'Nhost no proporcionó su credencial administrativa.' })
  try {
    const sql = `SELECT public.e5_cuadro_para_descarga(${literal(usuario)}::uuid,${literal(cuadroId)}::uuid)::text AS respuesta;`
    const consulta = await fetch(`${baseHasura()}/v2/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-hasura-admin-secret': admin },
      body: JSON.stringify({ type: 'run_sql', args: { source: 'default', sql, cascade: false, read_only: true, check_metadata_consistency: false } }),
      signal: AbortSignal.timeout(30000),
    })
    const acceso = respuestaRunSql(await consulta.json().catch(() => null)) as {
      ok?: boolean
      http_code?: number
      mensaje?: string
      storage_file_id?: string
      nombre_archivo?: string
    }
    if (!consulta.ok || acceso.ok !== true) {
      return res.status(acceso.http_code ?? 502).json({ error: acceso.mensaje ?? 'No se pudo comprobar el acceso al cuadro.' })
    }
    const archivo = await fetch(`${baseStorage()}/${acceso.storage_file_id}`, {
      headers: { 'x-hasura-admin-secret': admin, 'Cache-Control': 'no-cache' },
      signal: AbortSignal.timeout(60000),
    })
    if (!archivo.ok) return res.status(502).json({ error: 'El archivo del cuadro no está disponible en Storage.' })
    const bytes = Buffer.from(await archivo.arrayBuffer())
    return res.status(200).json({ nombre_archivo: acceso.nombre_archivo, archivo_b64: bytes.toString('base64') })
  } catch {
    console.error('Fallo interno al descargar el cuadro; revisa Storage y Hasura.')
    return res.status(500).json({ error: 'No fue posible descargar el cuadro.' })
  }
}

export default async function handler(req: Request, res: Response) {
  res.setHeader('Cache-Control', 'no-store')
  const origen = String(req.header('origin') ?? '')
  if (origen && ORIGENES_PERMITIDOS.includes(origen)) {
    res.setHeader('Access-Control-Allow-Origin', origen)
    res.setHeader('Vary', 'Origin')
    res.setHeader('Access-Control-Allow-Headers', 'Authorization, Content-Type, x-costflow-internal-key')
    res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  }
  if (req.method === 'OPTIONS') return res.status(204).end()
  if (req.method !== 'POST') return res.status(405).json({ error: 'Utiliza POST.' })

  const operacion = typeof req.body?.operacion === 'string' ? req.body.operacion : ''
  let datos = req.body?.datos

  if (operacion === DESCARGAR_CUADRO) return descargarCuadro(req, res, datos)

  if (OPERACIONES_DEL_ESPECIALISTA.has(operacion)) {
    // La identidad sale de Nhost Auth, nunca de un campo que envía el cliente.
    const usuario = await usuarioVerificado(req)
    if (!usuario) return res.status(401).json({ error: 'Inicia sesión para continuar.' })
    if (datos && typeof datos === 'object' && !Array.isArray(datos)) {
      datos = { ...datos, usuario_id_verificado: usuario }
    }
  } else if (OPERACIONES_INTERNAS.has(operacion)) {
    const esperado = process.env.E3_INTERNAL_KEY ?? ''
    const recibido = String(req.header('x-costflow-internal-key') ?? '')
    if (!esperado || !secretoValido(recibido, esperado)) {
      return res.status(401).json({ error: 'Acceso interno no válido.' })
    }
  } else {
    return res.status(400).json({ error: 'Operación o datos inválidos.' })
  }

  if (!datos || typeof datos !== 'object' || Array.isArray(datos)) {
    return res.status(400).json({ error: 'Operación o datos inválidos.' })
  }

  const admin = process.env.NHOST_ADMIN_SECRET ?? process.env.HASURA_GRAPHQL_ADMIN_SECRET ?? ''
  if (!admin) return res.status(503).json({ error: 'Nhost no proporcionó su credencial administrativa.' })

  try {
    const json = JSON.stringify(datos)
    if (Buffer.byteLength(json, 'utf8') > 12 * 1024 * 1024) {
      return res.status(413).json({ error: 'La operación supera el tamaño permitido.' })
    }
    const sql = `SELECT public.e4_operar(${literal(operacion)},${literal(json)}::jsonb)::text AS respuesta;`
    const upstream = await fetch(`${baseHasura()}/v2/query`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'x-hasura-admin-secret': admin },
      body: JSON.stringify({
        type: 'run_sql',
        args: { source: 'default', sql, cascade: false, read_only: false, check_metadata_consistency: false },
      }),
      signal: AbortSignal.timeout(90000),
    })
    const payload = await upstream.json().catch(() => null)
    if (!upstream.ok) {
      console.error('e4_operar fue rechazado por Hasura', upstream.status)
      return res.status(502).json({ error: 'Nhost no pudo completar la operación de E4/E5.' })
    }
    return res.status(200).json({ respuesta: respuestaRunSql(payload) })
  } catch {
    console.error('Fallo interno en e4-operar; revisa la configuración y disponibilidad de Hasura.')
    return res.status(500).json({ error: 'No fue posible completar la operación de E4/E5.' })
  }
}

export { DESCARGAR_CUADRO, OPERACIONES_DEL_ESPECIALISTA, OPERACIONES_INTERNAS, literal, respuestaRunSql, secretoValido }
